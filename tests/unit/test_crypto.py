"""Testes do wrapper Fernet (app/crypto.py) — Fase 1.

5 testes. Veja `docs/architecture/decisoes_design.md` G16 (timestamps) e ADR 003.
"""
import pytest


def test_encrypt_retorna_bytes():
    from app.crypto import encrypt
    resultado = encrypt("mensagem qualquer")
    assert isinstance(resultado, bytes)
    assert len(resultado) > 0


def test_decrypt_recupera_texto_original():
    from app.crypto import encrypt, decrypt
    original = "Olá, ACS! Visita registrada com sucesso."
    cifrado = encrypt(original)
    assert decrypt(cifrado) == original


def test_decrypt_falha_com_chave_errada(monkeypatch):
    """Trocar a chave de criptografia deve fazer o decrypt falhar."""
    from cryptography.fernet import InvalidToken
    from app.crypto import encrypt

    cifrado = encrypt("mensagem")

    # Reload com chave diferente
    from cryptography.fernet import Fernet
    nova_chave = Fernet.generate_key().decode()
    monkeypatch.setenv("ENCRYPTION_KEY", nova_chave)

    # Forçar reload do módulo crypto
    import importlib
    import app.crypto
    importlib.reload(app.crypto)

    with pytest.raises(InvalidToken):
        app.crypto.decrypt(cifrado)


def test_encrypt_mesma_string_gera_bytes_diferentes():
    """Fernet inclui timestamp + IV — mesma entrada gera saídas diferentes."""
    from app.crypto import encrypt
    a = encrypt("mensagem")
    b = encrypt("mensagem")
    assert a != b  # IV diferente em cada call


def test_decrypt_com_payload_corrompido_levanta_erro():
    from cryptography.fernet import InvalidToken
    from app.crypto import decrypt

    with pytest.raises(InvalidToken):
        decrypt(b"isso_nao_e_um_payload_fernet_valido")
