import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.api.endpoints import categories, templates, documents, emails, auth, ai_settings, feedback
from app.db.database import engine, Base

Base.metadata.create_all(bind=engine)
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API Gateway per Unical Support (Email Responder)",
    version="1.0.0",
    docs_url=None,   # Disattivato in produzione
    redoc_url=None   # Disattivato in produzione
)

origins = [origin.strip() for origin in settings.ALLOWED_ORIGINS.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(categories.router, prefix="/api/categories", tags=["Categories"])
app.include_router(templates.router, prefix="/api/templates", tags=["Templates"])
app.include_router(documents.router, prefix="/api/documents", tags=["Documents"])
app.include_router(emails.router, prefix="/api/emails", tags=["Emails"])
app.include_router(ai_settings.router, prefix="/api/ai-settings", tags=["AI Settings"])
app.include_router(feedback.router, prefix="/api/feedback", tags=["Feedback"])

# Mount static uploads
os.makedirs("/app/uploads", exist_ok=True)
app.mount("/static", StaticFiles(directory="/app/uploads"), name="static")

@app.get("/")
def read_root():
    return {"message": "Benvenuto in Unical Support API", "status": "Online"}