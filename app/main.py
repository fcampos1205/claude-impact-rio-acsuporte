from fastapi import FastAPI

from app.bot.webhook import router as webhook_router
from app.observabilidade import router as obs_router

app = FastAPI(title="ACS Primeira Infância")
app.include_router(webhook_router)
app.include_router(obs_router)
