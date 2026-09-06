from fastapi import FastAPI

from app.api.routes import authentication, decisions, documents, health, search, users

app = FastAPI()

app.include_router(health.router)
app.include_router(authentication.router)
app.include_router(users.router)
app.include_router(documents.router)
app.include_router(search.router)
app.include_router(decisions.router)
