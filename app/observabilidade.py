"""Prometheus metrics and health check endpoints."""
from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

router = APIRouter()

# Counters
acs_sugestoes_total = Counter(
    "acs_sugestoes_total", "Total de sugestões de visita", ["status"]
)
acs_visitas_total = Counter("acs_visitas_total", "Total de visitas registradas")
acs_llm_fallback_total = Counter(
    "acs_llm_fallback_total", "Total de vezes que o fallback LLM foi ativado"
)

# Gauges
acs_fila_reposicao_ativa = Gauge(
    "acs_fila_reposicao_ativa", "Itens ativos na fila de reposição"
)
acs_taxa_cobertura = Gauge(
    "acs_taxa_cobertura", "Taxa de cobertura de visitas", ["equipe_id"]
)

# Histograms
acs_batch_duration_seconds = Histogram(
    "acs_batch_duration_seconds", "Duração dos batches em segundos", ["batch_type"]
)


@router.get("/metrics")
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "db": "connected", "scheduler": "running"}
