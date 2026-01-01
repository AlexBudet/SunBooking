import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import os
from dotenv import load_dotenv
from appl import create_app, db

# Carica .env (solo per le migrazioni)
load_dotenv()

import appl.models  # forza il popolamento di db.metadata

def create_migration_app():
    """
    Crea una Flask app MINIMA per Alembic.
    Usa la stessa app factory, ma solo per esporre metadata.
    """
    db_uri = os.getenv("SQLALCHEMY_DATABASE_URI")
    if not db_uri:
        raise RuntimeError(
            "SQLALCHEMY_DATABASE_URI non impostata: necessaria per le migrazioni"
        )

    app = create_app(db_uri)

    # IMPORTANTISSIMO:
    # nessun server, nessuna route aggiuntiva, nessun create_all
    return app


# App usata da Alembic
app = create_migration_app()

# Metadata che Alembic deve vedere
target_metadata = db.metadata
