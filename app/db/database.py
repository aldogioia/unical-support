from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

# Creazione dell'engine di SQLAlchemy
engine = create_engine(settings.DATABASE_URL, echo=False)

# SessionLocal è l'equivalente dell'EntityManager di JPA
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class da cui erediteranno tutti i nostri modelli
Base = declarative_base()

# Dependency Injection per FastAPI (equivalente a @Autowired per il db)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()