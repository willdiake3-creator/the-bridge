from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import auth, catalog, applications, essays, referees, wallet, documents

app = FastAPI(
    title="Passage API",
    description="Backend for the university & scholarship application platform.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:5500", "http://127.0.0.1:5500"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(catalog.router)
app.include_router(applications.router)
app.include_router(essays.router)
app.include_router(referees.router)
app.include_router(wallet.router)
app.include_router(documents.router)


@app.get("/health")
def health():
    return {"status": "ok", "environment": settings.environment}
