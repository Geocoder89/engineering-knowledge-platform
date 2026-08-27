from fastapi import FastAPI

from app.api.routes import documents, health, search

app = FastAPI()

app.include_router(health.router)
app.include_router(documents.router)
app.include_router(search.router)
