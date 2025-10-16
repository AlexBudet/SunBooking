import pandas as pd
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

# Configurazione DB
DATABASE_URI = 'postgresql+psycopg2://sunexp3:30012010@sunbooking.postgres.database.azure.com:5432/sunexp3'
engine = create_engine(DATABASE_URI)
Session = sessionmaker(bind=engine)
session = Session()

# Modello Client semplificato per l'import
Base = declarative_base()

class Client(Base):
    __tablename__ = 'clienti'
    id = Column(Integer, primary_key=True, autoincrement=True)
    cliente_nome = Column(String, nullable=False)
    cliente_cognome = Column(String, nullable=False)
    cliente_cellulare = Column(String, nullable=False)
    cliente_sesso = Column(String(1), nullable=False)
    is_deleted = Column(Boolean, default=False)
    note = Column(String(1000), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

# Percorso del file Excel (cambia se necessario)
excel_file = 'ClientiSE.xlsx'  # Assumo che sia nella stessa cartella

# Leggi Excel
df = pd.read_excel(excel_file)

# Uniforma cellulare (togli spazi)
df['Cel'] = df['Cel'].astype(str).str.replace(' ', '')

# Mappa colonne
clients_to_insert = []
for _, row in df.iterrows():
    # Salta righe vuote o incomplete
    if pd.isna(row['Nome']) or pd.isna(row['Cognome']) or pd.isna(row['Cel']):
        continue
    
    # Converti Ingresso a datetime se possibile
    created_at = None
    if not pd.isna(row['Ingresso']):
        try:
            created_at = pd.to_datetime(row['Ingresso'])
        except:
            created_at = datetime.utcnow()
    
    # Crea oggetto Client
    client = Client(
        cliente_nome=str(row['Nome']).strip(),
        cliente_cognome=str(row['Cognome']).strip(),
        cliente_cellulare=str(row['Cel']).strip(),
        cliente_sesso=str(row['Sesso']).strip() if not pd.isna(row['Sesso']) else 'M',  # Default 'M' se vuoto
        note=str(row['Note']).strip() if not pd.isna(row['Note']) else None,
        created_at=created_at
    )
    clients_to_insert.append(client)

# Inserisci nel DB
try:
    for client in clients_to_insert:
        # Controlla duplicati (nome + cognome + cellulare)
        existing = session.query(Client).filter_by(
            cliente_nome=client.cliente_nome,
            cliente_cognome=client.cliente_cognome,
            cliente_cellulare=client.cliente_cellulare
        ).first()
        if not existing:
            session.add(client)
            print(f"Inserito: {client.cliente_nome} {client.cliente_cognome}")
        else:
            print(f"Duplicato saltato: {client.cliente_nome} {client.cliente_cognome}")
    
    session.commit()
    print(f"Import completato! Inseriti {len(clients_to_insert)} clienti.")
except Exception as e:
    session.rollback()
    print(f"Errore durante l'import: {e}")
finally:
    session.close()