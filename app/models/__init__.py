"""SQLAlchemy models — all models must be imported here so Base.metadata is populated.

This is critical: conftest.py calls Base.metadata.create_all() which requires all
model classes to be imported (they register themselves on import via DeclarativeBase).
"""

from app.models.auditoria import Auditoria
from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.chat_history import ChatHistory
from app.models.crianca import Crianca
from app.models.equipe import Equipe
from app.models.fila_reposicao import FilaReposicao
from app.models.gestor import Gestor
from app.models.lista_sugestoes import ListaSugestoes
from app.models.profissional import Profissional
from app.models.visita import Visita

__all__ = [
    "Base",
    "TimestampMixin",
    "UUIDMixin",
    "Auditoria",
    "ChatHistory",
    "Crianca",
    "Equipe",
    "FilaReposicao",
    "Gestor",
    "ListaSugestoes",
    "Profissional",
    "Visita",
]
