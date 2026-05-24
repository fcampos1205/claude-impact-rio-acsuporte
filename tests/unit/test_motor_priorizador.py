"""Testes do priorizador (pipeline completo) — Fase 3. 8 testes.

Veja decisoes_design.md G8 (ordem), G9 (limite + mínimo 3 novos), G17 (ACS inativo).
"""
from datetime import date, timedelta
from uuid import uuid4

import pytest


async def test_gerar_lista_retorna_max_15_itens(db_session, seed_minimal):
    """Lista nunca passa de LIMITE_LISTA_DIARIA (15)."""
    from app.motor.priorizador import gerar_lista

    acs = seed_minimal["acs_list"][0]
    resultado = await gerar_lista(db_session, acs.id)
    assert len(resultado.itens) <= 15


async def test_overrides_primeiro_candidatos_novos_depois(db_session, seed_minimal):
    """Itens com eh_pendencia=True vêm antes dos novos."""
    from app.models.fila_reposicao import FilaReposicao
    from app.motor.priorizador import gerar_lista

    acs = seed_minimal["acs_list"][0]
    criancas = [c for c in seed_minimal["criancas"] if c.profissional_id == acs.id]

    # Adicionar um override para a primeira criança
    override = FilaReposicao(
        profissional_id=acs.id,
        crianca_ref=criancas[0].id,
        data_origem=date.today() - timedelta(days=1),
        dias_pendente=1,
        score_original=50,
        score_ajustado=100,
        grupo_risco=True,
        override_topo=True,
        resolvida_em=None,
    )
    db_session.add(override)
    await db_session.flush()

    resultado = await gerar_lista(db_session, acs.id)

    # O primeiro item deve ser o override (pendência)
    assert len(resultado.itens) > 0
    assert resultado.itens[0].eh_pendencia is True

    # Todos os overrides devem aparecer antes dos novos
    pendencias = [i for i in resultado.itens if i.eh_pendencia]
    novos = [i for i in resultado.itens if not i.eh_pendencia]

    if pendencias and novos:
        idx_ultimo_override = resultado.itens.index(pendencias[-1])
        idx_primeiro_novo = resultado.itens.index(novos[0])
        assert idx_ultimo_override < idx_primeiro_novo


async def test_limite_15_com_minimo_3_novos(db_session, seed_minimal):
    """G9 — 14 overrides + 10 novos → 12 overrides + 3 novos = 15."""
    from app.models.crianca import Crianca
    from app.models.fila_reposicao import FilaReposicao
    from app.motor.constants import LIMITE_LISTA_DIARIA, MINIMO_NOVOS_NA_LISTA
    from app.motor.priorizador import gerar_lista

    acs = seed_minimal["acs_list"][0]
    equipe = seed_minimal["equipe"]

    # Criar 14 crianças extras e adicionar como overrides
    overrides_criados = 0
    for _ in range(14):
        c = Crianca(
            profissional_id=acs.id,
            equipe_id=equipe.id,
            faixa_etaria="0-6",
            sexo="M",
            raca_cor="parda",
            situacao_vulnerabilidade=False,
            endereco_latitude=-22.9,
            endereco_longitude=-43.2,
            vacinacao_em_dia=True,
        )
        db_session.add(c)
        await db_session.flush()

        override = FilaReposicao(
            profissional_id=acs.id,
            crianca_ref=c.id,
            data_origem=date.today() - timedelta(days=1),
            dias_pendente=1,
            score_original=30,
            score_ajustado=30,
            grupo_risco=False,
            override_topo=False,
            resolvida_em=None,
        )
        db_session.add(override)
        overrides_criados += 1

    await db_session.flush()

    resultado = await gerar_lista(db_session, acs.id)

    # Total nunca excede LIMITE_LISTA_DIARIA
    assert len(resultado.itens) <= LIMITE_LISTA_DIARIA

    pendencias = [i for i in resultado.itens if i.eh_pendencia]
    novos = [i for i in resultado.itens if not i.eh_pendencia]

    # G9: no máximo LIMITE - MINIMO overrides e pelo menos MINIMO novos
    max_overrides = LIMITE_LISTA_DIARIA - MINIMO_NOVOS_NA_LISTA
    assert len(pendencias) <= max_overrides

    # Se há crianças novas disponíveis, deve ter pelo menos MINIMO_NOVOS_NA_LISTA
    if novos:
        assert len(novos) >= MINIMO_NOVOS_NA_LISTA


async def test_ordem_dentro_overrides_dias_pendente_desc(db_session, seed_minimal):
    """G8 — ORDER BY dias_pendente DESC, grupo_risco DESC, score DESC, created_at ASC."""
    from app.models.crianca import Crianca
    from app.models.fila_reposicao import FilaReposicao
    from app.motor.priorizador import gerar_lista

    acs = seed_minimal["acs_list"][0]
    equipe = seed_minimal["equipe"]

    # Criar duas crianças com diferentes dias_pendente
    c1 = Crianca(
        profissional_id=acs.id,
        equipe_id=equipe.id,
        faixa_etaria="0-6",
        sexo="M",
        raca_cor="parda",
        situacao_vulnerabilidade=False,
        endereco_latitude=-22.9,
        endereco_longitude=-43.2,
        vacinacao_em_dia=True,
    )
    c2 = Crianca(
        profissional_id=acs.id,
        equipe_id=equipe.id,
        faixa_etaria="0-6",
        sexo="F",
        raca_cor="parda",
        situacao_vulnerabilidade=False,
        endereco_latitude=-22.9,
        endereco_longitude=-43.2,
        vacinacao_em_dia=True,
    )
    db_session.add(c1)
    db_session.add(c2)
    await db_session.flush()

    # c2 tem mais dias pendente que c1 → deve aparecer primeiro
    override1 = FilaReposicao(
        profissional_id=acs.id,
        crianca_ref=c1.id,
        data_origem=date.today() - timedelta(days=2),
        dias_pendente=1,
        score_original=40,
        score_ajustado=40,
        grupo_risco=False,
        override_topo=False,
        resolvida_em=None,
    )
    override2 = FilaReposicao(
        profissional_id=acs.id,
        crianca_ref=c2.id,
        data_origem=date.today() - timedelta(days=5),
        dias_pendente=5,
        score_original=40,
        score_ajustado=40,
        grupo_risco=False,
        override_topo=False,
        resolvida_em=None,
    )
    db_session.add(override1)
    db_session.add(override2)
    await db_session.flush()

    resultado = await gerar_lista(db_session, acs.id)

    pendencias = [i for i in resultado.itens if i.eh_pendencia]
    assert len(pendencias) >= 2

    # c2 (5 dias pendente) deve vir antes de c1 (1 dia pendente)
    refs = [p.crianca_ref for p in pendencias]
    assert refs.index(c2.id) < refs.index(c1.id)


async def test_dedupe_aplicado_antes_do_ranking(db_session, seed_minimal):
    """Visitadas no ciclo NÃO aparecem entre candidatos novos."""
    from app.models.lista_sugestoes import ListaSugestoes
    from app.motor.priorizador import gerar_lista

    acs = seed_minimal["acs_list"][0]
    criancas = [c for c in seed_minimal["criancas"] if c.profissional_id == acs.id]
    crianca_visitada = criancas[0]

    # Marcar criança como visitada no ciclo
    sugestao = ListaSugestoes(
        profissional_id=acs.id,
        crianca_ref=crianca_visitada.id,
        data_sugestao=date.today() - timedelta(days=5),
        status="VISITADA",
    )
    db_session.add(sugestao)
    await db_session.flush()

    resultado = await gerar_lista(db_session, acs.id)

    refs_na_lista = {item.crianca_ref for item in resultado.itens}
    assert crianca_visitada.id not in refs_na_lista


async def test_lista_vazia_quando_acs_sem_criancas(db_session, seed_minimal):
    """ACS sem crianças sob responsabilidade retorna lista vazia."""
    from app.motor.priorizador import gerar_lista

    # UUID aleatório — não existe no banco
    resultado = await gerar_lista(db_session, uuid4())
    assert resultado.itens == []


async def test_acs_inativo_retorna_lista_vazia(db_session, seed_minimal):
    """G17 — ACS com ativo=False sempre retorna ListaPriorizada vazia."""
    from sqlalchemy import update

    from app.models.profissional import Profissional
    from app.motor.priorizador import gerar_lista

    acs = seed_minimal["acs_list"][0]
    await db_session.execute(
        update(Profissional).where(Profissional.id == acs.id).values(ativo=False)
    )
    await db_session.flush()

    resultado = await gerar_lista(db_session, acs.id)
    assert resultado.itens == []


async def test_truncamento_quando_muitos_overrides(db_session, seed_minimal):
    """G9 — 20 overrides + 5 novos → 12 overrides (truncados) + 3 novos."""
    from app.models.crianca import Crianca
    from app.models.fila_reposicao import FilaReposicao
    from app.motor.constants import LIMITE_LISTA_DIARIA, MINIMO_NOVOS_NA_LISTA
    from app.motor.priorizador import gerar_lista

    acs = seed_minimal["acs_list"][0]
    equipe = seed_minimal["equipe"]

    # Criar 20 crianças extras com overrides (além das 5 que já existem do seed)
    for idx in range(20):
        c = Crianca(
            profissional_id=acs.id,
            equipe_id=equipe.id,
            faixa_etaria="0-6",
            sexo="M",
            raca_cor="parda",
            situacao_vulnerabilidade=False,
            endereco_latitude=-22.9,
            endereco_longitude=-43.2,
            vacinacao_em_dia=True,
        )
        db_session.add(c)
        await db_session.flush()

        override = FilaReposicao(
            profissional_id=acs.id,
            crianca_ref=c.id,
            data_origem=date.today() - timedelta(days=idx + 1),
            dias_pendente=idx + 1,
            score_original=30,
            score_ajustado=30,
            grupo_risco=False,
            override_topo=False,
            resolvida_em=None,
        )
        db_session.add(override)

    await db_session.flush()

    resultado = await gerar_lista(db_session, acs.id)

    # Total nunca excede LIMITE_LISTA_DIARIA
    assert len(resultado.itens) <= LIMITE_LISTA_DIARIA

    pendencias = [i for i in resultado.itens if i.eh_pendencia]
    novos = [i for i in resultado.itens if not i.eh_pendencia]

    # Overrides truncados a LIMITE - MINIMO_NOVOS
    max_overrides = LIMITE_LISTA_DIARIA - MINIMO_NOVOS_NA_LISTA
    assert len(pendencias) <= max_overrides

    # Mínimo de candidatos novos garantido
    assert len(novos) >= MINIMO_NOVOS_NA_LISTA
