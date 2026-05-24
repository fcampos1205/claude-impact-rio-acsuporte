"""Testes de deduplicação — Fase 3. 5 testes."""
from dataclasses import dataclass
from datetime import date, timedelta
from uuid import UUID, uuid4

import pytest


async def test_obter_visitadas_no_ciclo_30_dias(db_session, seed_minimal):
    """Deve retornar UUIDs de crianças com status=VISITADA nos últimos 30 dias."""
    from app.models.lista_sugestoes import ListaSugestoes
    from app.motor.deduplicacao import obter_visitadas_no_ciclo

    acs = seed_minimal["acs_list"][0]
    criancas = [c for c in seed_minimal["criancas"] if c.profissional_id == acs.id]
    crianca = criancas[0]

    # Inserir sugestão com status VISITADA nos últimos 30 dias
    sugestao = ListaSugestoes(
        profissional_id=acs.id,
        crianca_ref=crianca.id,
        data_sugestao=date.today() - timedelta(days=10),
        status="VISITADA",
    )
    db_session.add(sugestao)
    await db_session.flush()

    visitadas = await obter_visitadas_no_ciclo(db_session, acs.id)
    assert crianca.id in visitadas


def test_filtrar_candidatos_remove_visitadas():
    from app.motor.deduplicacao import filtrar_candidatos

    @dataclass
    class Candidato:
        crianca_ref: UUID

    id_visitada = uuid4()
    id_nova = uuid4()

    candidatos = [Candidato(crianca_ref=id_visitada), Candidato(crianca_ref=id_nova)]
    visitadas = {id_visitada}

    resultado = filtrar_candidatos(candidatos, visitadas)
    assert len(resultado) == 1
    assert resultado[0].crianca_ref == id_nova


def test_filtrar_mantem_nao_visitadas():
    from app.motor.deduplicacao import filtrar_candidatos

    @dataclass
    class Candidato:
        crianca_ref: UUID

    ids = [uuid4() for _ in range(5)]
    candidatos = [Candidato(crianca_ref=i) for i in ids]
    visitadas: set[UUID] = set()  # nenhuma visitada

    resultado = filtrar_candidatos(candidatos, visitadas)
    assert len(resultado) == 5


async def test_filtrar_ciclo_reinicia_apos_30_dias(db_session, seed_minimal):
    """Visita feita há 31 dias não deve mais deduplicar."""
    from app.models.lista_sugestoes import ListaSugestoes
    from app.motor.deduplicacao import obter_visitadas_no_ciclo

    acs = seed_minimal["acs_list"][0]
    criancas = [c for c in seed_minimal["criancas"] if c.profissional_id == acs.id]
    crianca = criancas[0]

    # Inserir sugestão com status VISITADA há 31 dias (fora do ciclo)
    sugestao = ListaSugestoes(
        profissional_id=acs.id,
        crianca_ref=crianca.id,
        data_sugestao=date.today() - timedelta(days=31),
        status="VISITADA",
    )
    db_session.add(sugestao)
    await db_session.flush()

    visitadas = await obter_visitadas_no_ciclo(db_session, acs.id)
    assert crianca.id not in visitadas


async def test_ciclo_inicia_na_primeira_sugestao_do_mes(db_session, seed_minimal):
    """Definição de ciclo conforme PRD seção 4.3.

    Crianças com status SUGERIDA (não visitada) não entram no conjunto de deduplicação.
    """
    from app.models.lista_sugestoes import ListaSugestoes
    from app.motor.deduplicacao import obter_visitadas_no_ciclo

    acs = seed_minimal["acs_list"][0]
    criancas = [c for c in seed_minimal["criancas"] if c.profissional_id == acs.id]
    crianca = criancas[0]

    # Inserir sugestão com status SUGERIDA (não visitada)
    sugestao = ListaSugestoes(
        profissional_id=acs.id,
        crianca_ref=crianca.id,
        data_sugestao=date.today() - timedelta(days=5),
        status="SUGERIDA",
    )
    db_session.add(sugestao)
    await db_session.flush()

    # Apenas VISITADA entra no ciclo de deduplicação
    visitadas = await obter_visitadas_no_ciclo(db_session, acs.id)
    assert crianca.id not in visitadas
