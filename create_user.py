import sys
import getpass
import uuid
from datetime import datetime, timezone
 
def main():
    print("\n" + "="*50)
    print("   Creazione nuovo utente - Unical Support")
    print("="*50 + "\n")
 
    # Email
    email = input("Email: ").strip()
    if not email or "@" not in email:
        print(" Email non valida.")
        sys.exit(1)
 
    # Password (nascosta, con conferma)
    while True:
        password = getpass.getpass("Password: ")
        if len(password) < 8:
            print("La password deve essere di almeno 8 caratteri.")
            continue
        confirm = getpass.getpass("Conferma password: ")
        if password != confirm:
            print(" Le password non coincidono. Riprova.\n")
            continue
        break
 
    # Ruolo
    print("\nRuolo:")
    print("  1) admin")
    print("  2) user")
    scelta = input("Scelta [1]: ").strip() or "1"
    role = "admin" if scelta == "1" else "user"
 
    # Hash della password
    try:
        from app.api.password_handler import get_password_hash
    except ImportError:
        print("\n Errore: esegui lo script dalla root del progetto (dove si trova la cartella 'app/').")
        sys.exit(1)
 
    hashed = get_password_hash(password)
    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
 
    # Connessione al DB
    try:
        from app.core.config import settings
        from app.db.database import SessionLocal
        from app.models.user import User
        from app.models.enumerators.enumerators import UserRole
        from sqlalchemy.exc import IntegrityError
    except Exception as e:
        print(f"\n Errore di importazione: {e}")
        print("Assicurati di aver attivato il venv e di essere nella root del progetto.")
        sys.exit(1)
 
    db = SessionLocal()
    try:
        # Controlla se esiste già
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            print(f"\n Esiste già un utente con email '{email}'.")
            sys.exit(1)
 
        user = User(
            id=uuid.UUID(user_id),
            email=email,
            hashed_password=hashed,
            is_active=True,
            role=UserRole.admin if role == "admin" else UserRole.user,
        )
        user.apply_audit_fields(is_create=True)
 
        db.add(user)
        db.commit()
 
        print(f"\nUtente creato con successo!")
        print(f"   Email: {email}")
        print(f"   Ruolo: {role}")
        print(f"   ID:    {user_id}")
        print("\nPuoi ora accedere a http://localhost:4200 con queste credenziali.\n")
 
    except IntegrityError:
        db.rollback()
        print(f"\n Errore: email già presente nel database.")
        sys.exit(1)
    except Exception as e:
        db.rollback()
        print(f"\n Errore durante la creazione: {e}")
        sys.exit(1)
    finally:
        db.close()
 
 
if __name__ == "__main__":
    main()