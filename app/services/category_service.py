import json
import logging
from typing import List, Dict, Any
from uuid import UUID
from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.models.category import Category
from app.schemas.category import CategoryCreate, CategoryUpdate
from app.services import document_service

logger = logging.getLogger(__name__)

MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024  # 2 MB
MAX_CATEGORIES_BATCH = 500


def get_category(db: Session, category_id: UUID):
    return db.query(Category).filter(Category.id == category_id).first()

def get_category_by_name(db: Session, name: str):
    return db.query(Category).filter(Category.name == name).first()

def get_categories(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Category).offset(skip).limit(limit).all()

def create_category(db: Session, category: CategoryCreate, user_id: UUID):
    db_category = get_category_by_name(db, name=category.name)
    if db_category:
        raise HTTPException(status_code=400, detail="Categoria già esistente")

    db_category = Category(
        name=category.name,
        description=category.description
    )

    db_category.apply_audit_fields(user_id=user_id, is_create=True)

    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category

def update_category(db: Session, category_id: UUID, category_data: CategoryUpdate, user_id: UUID):
    db_category = get_category(db, category_id)
    if not db_category:
        raise HTTPException(status_code=404, detail="Categoria non trovata")
    
    update_dict = category_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(db_category, key, value)
    db_category.apply_audit_fields(user_id=user_id)
        
    db.commit()
    db.refresh(db_category)
    return db_category

def delete_category(db: Session, category_id: UUID):
    db_category = get_category(db, category_id)
    if db_category:
        for doc in list(db_category.documents):
            document_service.delete_document(db, doc.id)
        db.delete(db_category)
        db.commit()
    else:
        raise HTTPException(status_code=404, detail="Categoria non trovata")


def import_categories_from_list(
    db: Session,
    categories_data: List[CategoryCreate],
    user_id: UUID,
    skip_duplicates: bool = True
) -> Dict[str, Any]:
    """
    Importa una lista di categorie già validate tramite Pydantic.
    Garantisce unicità dei nomi, applica campi di audit e gestisce le transazioni in modo sicuro.
    """
    if not categories_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La lista delle categorie da importare non può essere vuota."
        )

    if len(categories_data) > MAX_CATEGORIES_BATCH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Numero di categorie ({len(categories_data)}) superiore al limite consentito di {MAX_CATEGORIES_BATCH}."
        )

    # Recupera i nomi già presenti a DB per verifica case-insensitive rapida
    existing_db_names = {c.name.strip().lower() for c in db.query(Category.name).all()}

    seen_in_batch = set()
    created_categories: List[Category] = []
    skipped_categories: List[str] = []
    errors: List[str] = []

    for index, cat_in in enumerate(categories_data, start=1):
        clean_name = cat_in.name.strip()
        lower_name = clean_name.lower()

        if len(clean_name) < 2 or len(clean_name) > 50:
            errors.append(f"Elemento #{index} ('{clean_name}'): la lunghezza del nome deve essere tra 2 e 50 caratteri.")
            continue

        # Controllo duplicati all'interno dello stesso batch
        if lower_name in seen_in_batch:
            skipped_categories.append(f"{clean_name} (duplicato nel batch)")
            continue

        seen_in_batch.add(lower_name)

        # Controllo duplicati già presenti nel database
        if lower_name in existing_db_names:
            if not skip_duplicates:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"La categoria '{clean_name}' esiste già nel database."
                )
            skipped_categories.append(f"{clean_name} (già presente nel database)")
            continue

        clean_description = cat_in.description.strip() if cat_in.description else None
        db_category = Category(
            name=clean_name,
            description=clean_description
        )
        db_category.apply_audit_fields(user_id=user_id, is_create=True)
        db.add(db_category)
        created_categories.append(db_category)
        existing_db_names.add(lower_name)

    try:
        db.commit()
        for cat in created_categories:
            db.refresh(cat)
    except Exception as e:
        db.rollback()
        logger.error(f"Errore durante il salvataggio nel database delle categorie: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Errore interno durante il salvataggio delle categorie nel database."
        )

    logger.info(
        f"Importazione categorie completata con successo dall'admin {user_id}: "
        f"{len(created_categories)} create, {len(skipped_categories)} saltate, {len(errors)} anomalie."
    )

    return {
        "total_processed": len(categories_data),
        "created_count": len(created_categories),
        "skipped_count": len(skipped_categories),
        "created_categories": created_categories,
        "skipped_categories": skipped_categories,
        "errors": errors
    }


def import_categories_from_json_bytes(
    db: Session,
    content: bytes,
    user_id: UUID,
    skip_duplicates: bool = True
) -> Dict[str, Any]:
    """
    Decodifica, valida il formato del JSON ed effettua l'importazione sicura delle categorie.
    Supporta sia un array `[...]` sia un oggetto con chiave `{"categories": [...]}`.
    """
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Il file caricato è vuoto."
        )

    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"La dimensione del file supera il limite massimo consentito di {MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB."
        )

    try:
        decoded_text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Codifica file non valida. Il file deve essere un documento UTF-8 valido."
        )

    try:
        data = json.loads(decoded_text)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Sintassi JSON non valida (riga {e.lineno}, colonna {e.colno}): {e.msg}"
        )

    if isinstance(data, dict) and "categories" in data and isinstance(data["categories"], list):
        items = data["categories"]
    elif isinstance(data, list):
        items = data
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Struttura JSON non valida. Deve essere un array di categorie o un oggetto con chiave 'categories'."
        )

    if not items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Il file JSON non contiene alcuna categoria da importare."
        )

    if len(items) > MAX_CATEGORIES_BATCH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Numero di elementi ({len(items)}) superiore al limite massimo consentito di {MAX_CATEGORIES_BATCH}."
        )

    validated_categories: List[CategoryCreate] = []
    pre_errors: List[str] = []

    for index, raw_item in enumerate(items, start=1):
        if not isinstance(raw_item, dict):
            pre_errors.append(f"Elemento #{index}: formato non valido, deve essere un oggetto JSON.")
            continue
        try:
            validated_categories.append(CategoryCreate(**raw_item))
        except ValidationError as ve:
            error_details = ", ".join([f"{err['loc'][-1]}: {err['msg']}" for err in ve.errors()])
            item_name = raw_item.get("name", "N/D") if isinstance(raw_item, dict) else "N/D"
            pre_errors.append(f"Elemento #{index} ('{item_name}'): {error_details}")

    if not validated_categories and pre_errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Nessuna categoria valida trovata nel file. Errori riscontrati: {'; '.join(pre_errors[:5])}"
        )

    result = import_categories_from_list(
        db=db,
        categories_data=validated_categories,
        user_id=user_id,
        skip_duplicates=skip_duplicates
    )

    result["total_processed"] = len(items)
    result["errors"] = pre_errors + result["errors"]

    return result