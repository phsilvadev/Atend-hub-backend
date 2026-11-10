"""Can be scheduled daily; no customer text or secrets in output."""
from app.core.database import SessionLocal
from app.services.support import cleanup

def main():
    with SessionLocal() as db:
        cleanup(db);db.commit()
    print('SUPPORT_RETENTION_CLEANUP_OK')
if __name__=='__main__':main()
