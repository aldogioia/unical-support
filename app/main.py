from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.database import engine, Base

from app.api.endpoints import categories, templates, documents, emails

# [SOLO PER MVP]: Crea le tabelle nel database automaticamente se non esistono.
# In produzione useremo Alembic per gestire le versioni e le migrazioni del DB.
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API Gateway per Unical Support (Email Responder)",
    version="1.0.0"
)

# Configurazione CORS per permettere ad Angular (solitamente su porta 4200) di chiamare le API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],  # Permette GET, POST, PUT, DELETE, ecc.
    allow_headers=["*"],
)

app.include_router(categories.router, prefix="/api/categories", tags=["Categories"])
app.include_router(templates.router, prefix="/api/templates", tags=["Templates"])
app.include_router(documents.router, prefix="/api/documents", tags=["Documents"])
app.include_router(emails.router, prefix="/api/emails", tags=["Emails"])

@app.get("/")
def read_root():
    return {"message": "Benvenuto in Unical Support API", "status": "Online"}