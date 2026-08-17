from fastapi import FastAPI
from app.api.routes import documents, health
app = FastAPI()

app.include_router(health.router)
app.include_router(documents.router)





