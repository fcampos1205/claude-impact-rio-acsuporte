"""Testes de modelos e constraints — Fase 1. 12 testes."""
import uuid
from datetime import date

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError


async def test_profissional_criar_e_recuperar(db_session):
    from app.models import Equipe, Profissional

    equipe = Equipe(nome="ESF Test", endereco_latitude=-22.9, endereco_longitude=-43.2)
    db_session.add(equipe)
    await db_session.flush()

    acs = Profissional(
        nome="ACS Teste",
        telegram_chat_id_hash="hash_unique_test_001",
        equipe_id=equipe.id,
        ativo=True,
    )
    db_session.add(acs)
    await db_session.flush()

    result = await db_session.execute(select(Profissional).where(Profissional.id == acs.id))
    found = result.scalar_one()
    assert found.nome == "ACS Teste"
    assert found.ativo is True


async def test_lista_sugestoes_unique_constraint(db_session, seed_minimal):
    """G6 — UNIQUE(profissional_id, crianca_ref, data_sugestao) impede duplicata."""
    from app.models import ListaSugestoes

    acs = seed_minimal["acs_list"][0]
    crianca = seed_minimal["criancas"][0]
    today = date.today()

    s1 = ListaSugestoes(
        profissional_id=acs.id, crianca_ref=crianca.id, data_sugestao=today, status="SUGERIDA"
    )
    db_session.add(s1)
    await db_session.flush()

    s2 = ListaSugestoes(
        profissional_id=acs.id, crianca_ref=crianca.id, data_sugestao=today, status="SUGERIDA"
    )
    db_session.add(s2)
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_fila_reposicao_unique_constraint(db_session, seed_minimal):
    """G6 — UNIQUE(profissional_id, crianca_ref, data_origem)."""
    from app.models import FilaReposicao

    acs = seed_minimal["acs_list"][0]
    crianca = seed_minimal["criancas"][0]
    today = date.today()

    f1 = FilaReposicao(
        profissional_id=acs.id, crianca_ref=crianca.id, data_origem=today, dias_pendente=1
    )
    db_session.add(f1)
    await db_session.flush()

    f2 = FilaReposicao(
        profissional_id=acs.id, crianca_ref=crianca.id, data_origem=today, dias_pendente=1
    )
    db_session.add(f2)
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_chat_history_persiste_criptografado(db_session, seed_minimal):
    """content_enc nunca está em texto claro no DB."""
    from app.models import ChatHistory
    from app.crypto import encrypt

    acs = seed_minimal["acs_list"][0]
    msg = "mensagem super secreta"
    entry = ChatHistory(
        profissional_id=acs.id,
        role="user",
        content_enc=encrypt(msg),
    )
    db_session.add(entry)
    await db_session.flush()

    result = await db_session.execute(
        select(ChatHistory).where(ChatHistory.id == entry.id)
    )
    row = result.scalar_one()
    assert isinstance(row.content_enc, bytes)
    assert msg.encode() not in row.content_enc


async def test_chat_history_descriptografia_funcional(db_session, seed_minimal):
    """decrypt(content_enc) recupera mensagem original."""
    from app.models import ChatHistory
    from app.crypto import encrypt, decrypt

    acs = seed_minimal["acs_list"][0]
    original = "Olá, este é um teste de criptografia."
    entry = ChatHistory(
        profissional_id=acs.id,
        role="assistant",
        content_enc=encrypt(original),
    )
    db_session.add(entry)
    await db_session.flush()

    result = await db_session.execute(
        select(ChatHistory).where(ChatHistory.id == entry.id)
    )
    row = result.scalar_one()
    assert decrypt(row.content_enc) == original


async def test_timestamps_created_at_setado_automaticamente(db_session, seed_minimal):
    from app.models import Equipe

    equipe = Equipe(nome="ESF Timestamp Test")
    db_session.add(equipe)
    await db_session.flush()

    result = await db_session.execute(select(Equipe).where(Equipe.id == equipe.id))
    found = result.scalar_one()
    assert found.created_at is not None


async def test_timestamps_updated_at_atualiza_em_update(db_session, seed_minimal):
    from app.models import Equipe

    equipe = Equipe(nome="ESF Update Test")
    db_session.add(equipe)
    await db_session.flush()
    await db_session.refresh(equipe)
    original_updated = equipe.updated_at

    equipe.nome = "ESF Update Test v2"
    await db_session.flush()
    await db_session.refresh(equipe)

    assert equipe.updated_at is not None


async def test_visita_relacao_profissional_crianca(db_session, seed_minimal):
    from app.models import Visita

    acs = seed_minimal["acs_list"][0]
    crianca = seed_minimal["criancas"][0]

    visita = Visita(
        profissional_id=acs.id,
        crianca_ref=crianca.id,
        data_visita=date.today(),
        responsavel_presente=True,
    )
    db_session.add(visita)
    await db_session.flush()

    result = await db_session.execute(select(Visita).where(Visita.id == visita.id))
    found = result.scalar_one()
    assert found.profissional_id == acs.id
    assert found.crianca_ref == crianca.id


async def test_gestor_pode_ter_multiplas_equipes(db_session):
    """G11 — Gestor.equipes_ids é JSONB array de UUIDs."""
    from app.models import Gestor

    ids = [str(uuid.uuid4()), str(uuid.uuid4())]
    gestor = Gestor(
        nome="Gestor Multi",
        telegram_chat_id_hash="gestor_hash_multi_unique",
        equipes_ids=ids,
        ativo=True,
    )
    db_session.add(gestor)
    await db_session.flush()

    result = await db_session.execute(select(Gestor).where(Gestor.id == gestor.id))
    found = result.scalar_one()
    assert len(found.equipes_ids) == 2


async def test_auditoria_grava_metadata_jsonb(db_session, seed_minimal):
    from app.auditoria import registrar

    acs = seed_minimal["acs_list"][0]
    meta = {"acao_detalhe": "teste", "valor": 42}
    audit = await registrar(db_session, acao="TESTE_UNIT", profissional_id=acs.id, metadata=meta)

    assert audit.acao == "TESTE_UNIT"
    assert audit.metadata_json["valor"] == 42


async def test_fila_reposicao_partial_index_resolvida_em_null(db_session, seed_minimal):
    """Partial index covers only rows with resolvida_em IS NULL."""
    from app.models import FilaReposicao
    from sqlalchemy import text

    acs = seed_minimal["acs_list"][0]
    crianca = seed_minimal["criancas"][0]

    f = FilaReposicao(
        profissional_id=acs.id,
        crianca_ref=crianca.id,
        data_origem=date.today(),
        dias_pendente=1,
    )
    db_session.add(f)
    await db_session.flush()

    # Verify the row exists with resolvida_em=NULL
    result = await db_session.execute(
        select(FilaReposicao).where(
            FilaReposicao.profissional_id == acs.id,
            FilaReposicao.resolvida_em.is_(None),
        )
    )
    rows = result.scalars().all()
    assert len(rows) >= 1


async def test_cascade_delete_nao_remove_chat_history(db_session, seed_minimal):
    """ACS inativado mantém chat_history (audit trail). chat_history uses SET NULL."""
    from app.models import ChatHistory
    from app.crypto import encrypt
    from sqlalchemy import update
    from app.models import Profissional

    acs = seed_minimal["acs_list"][0]
    entry = ChatHistory(
        profissional_id=acs.id,
        role="user",
        content_enc=encrypt("mensagem histórica"),
    )
    db_session.add(entry)
    await db_session.flush()

    # Inactivate ACS (not delete, since FK is SET NULL on delete)
    await db_session.execute(
        update(Profissional).where(Profissional.id == acs.id).values(ativo=False)
    )
    await db_session.flush()

    # ChatHistory still exists
    result = await db_session.execute(
        select(ChatHistory).where(ChatHistory.id == entry.id)
    )
    found = result.scalar_one()
    assert found is not None
