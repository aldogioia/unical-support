import os
import shutil
import uuid
import socket
import ipaddress
from urllib.parse import urlparse
from uuid import UUID
from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session
from app.models.document import Document
from app.models.category import Category
from app.tasks.document_tasks import process_document_task

UPLOAD_DIR = "/app/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_DOCUMENT_TYPES = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/msword": ".docx",
    "text/plain": ".txt",
    "application/json": ".json",
    "text/json": ".json",
    "application/x-yaml": ".yaml",
    "text/yaml": ".yaml",
    "text/x-yaml": ".yaml",
    "application/yaml": ".yaml",
    "text/markdown": ".md",
    "text/x-markdown": ".md",
}
ALLOWED_EXTENSIONS = {".pdf", ".yaml", ".yml", ".txt", ".json", ".docx", ".md"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

def _validate_url(url: str) -> None:
    """
    Valida l'URL per prevenire attacchi SSRF.
    - Blocca schemi diversi da http/https
    - Blocca indirizzi IP privati, loopback e link-local
    - Blocca hostname interni Docker (db, redis, backend, ecc.)
    - Blocca l'accesso ai metadata cloud (169.254.169.254)
    """
    try:
        parsed = urlparse(url)
    except Exception:
        raise ValueError("URL non valido o malformato.")

    # 1. Solo schemi HTTP e HTTPS sono consentiti
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Schema '{parsed.scheme}' non consentito. Sono ammessi solo 'http' e 'https'.")

    # 2. Il hostname deve essere presente
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL non valido: hostname mancante.")

    # 3. Blocca hostname interni noti della rete Docker e localhost
    BLOCKED_HOSTNAMES = {
        "localhost",
        "db",
        "redis",
        "backend",
        "worker",
        "beat",
        "frontend",
        "host.docker.internal",
    }
    if hostname.lower() in BLOCKED_HOSTNAMES:
        raise ValueError(f"Hostname '{hostname}' non consentito. Non è possibile accedere a risorse interne.")

    # 4. Risolve il nome DNS e controlla che non punti a un IP privato/riservato
    try:
        ip_str = socket.gethostbyname(hostname)
        ip = ipaddress.ip_address(ip_str)
    except (socket.gaierror, ValueError):
        # Se non si riesce a risolvere, blocca per sicurezza
        raise ValueError(f"Impossibile risolvere l'hostname '{hostname}'. URL non consentito.")

    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
        raise ValueError(
            f"L'URL punta a un indirizzo IP non raggiungibile da Internet ({ip_str}). "
            "Non è possibile caricare risorse da reti private o interne."
        )


def get_document(db: Session, document_id: UUID):
    return db.query(Document).filter(Document.id == document_id).first()

def get_documents(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Document).offset(skip).limit(limit).all()

def process_and_upload_document(db: Session, file: UploadFile | None, url: str | None, category_id: UUID | None, user_id: UUID):
    filename = "Link Web"
    content_type = "text/html"
    document_url = url
    file_path = None

    if file:
        filename = file.filename or "documento"
        content_type = (file.content_type or "").lower()
        file_extension = os.path.splitext(filename)[1].lower()

        # 1. Validazione Tipo di File (MIME Type) ed Estensione
        is_type_valid = content_type in ALLOWED_DOCUMENT_TYPES or content_type.startswith("text/")
        is_ext_valid = file_extension in ALLOWED_EXTENSIONS

        if not is_type_valid and not is_ext_valid:
            raise ValueError(f"Tipo di file '{content_type or file_extension}' non consentito. Formati supportati: PDF, DOCX, TXT, JSON, YAML, MD.")

        # Determina l'estensione sicura da usare su disco
        if file_extension in ALLOWED_EXTENSIONS:
            clean_ext = file_extension
        else:
            clean_ext = ALLOWED_DOCUMENT_TYPES.get(content_type, ".txt" if "text" in content_type else ".bin")

        # 2. Validazione dimensione del file (max 50MB)
        file.file.seek(0, os.SEEK_END)
        file_size = file.file.tell()
        file.file.seek(0)  # Ripristina la posizione dello stream

        if file_size > MAX_FILE_SIZE:
            max_mb = MAX_FILE_SIZE / (1024 * 1024)
            actual_mb = file_size / (1024 * 1024)
            raise ValueError(f"Dimensione del file ({actual_mb:.2f}MB) superiore al limite massimo consentito ({max_mb:.0f}MB).")

        unique_filename = f"{uuid.uuid4()}{clean_ext}"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
    elif url:
        # Validazione sicurezza URL (protezione SSRF)
        _validate_url(url)
    else:
        raise ValueError("Devi fornire un file oppure un URL valido.")

    db_document = Document(
        filename=filename,
        content_type=content_type,
        link=document_url,
        extracted_text="Elaborazione in corso da parte dell'IA...",
        category_id=category_id
    )
    db_document.apply_audit_fields(user_id=user_id, is_create=True)
    db.add(db_document)
    db.commit()
    db.refresh(db_document)

    process_document_task.delay(db_document.id, file_path, url, category_id)

    return db_document, 0

def update_document_category(db: Session, document_id: UUID, category_id, user_id: UUID):
    db_document = get_document(db, document_id)
    if not db_document:
        raise HTTPException(status_code=404, detail="Documento non trovato")

    db_document.category_id = category_id
    db_document.apply_audit_fields(user_id=user_id, is_create=False)
    db.commit()
    db.refresh(db_document)
    return db_document

def delete_document(db: Session, document_id: UUID):
    db_document = get_document(db, document_id)
    if db_document:
        db.delete(db_document)
        db.commit()
    else:
        raise HTTPException(status_code=404, detail="Categoria non trovata")