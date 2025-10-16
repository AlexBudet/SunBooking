#appl/routes/clients.py
from flask import Blueprint, request, jsonify, abort
from ..models import db, Client, Appointment, AppointmentStatus

# Blueprint per le rotte dei clienti
clients_bp = Blueprint('clients', __name__)

@clients_bp.route('/', methods=['GET'])
def list_clients():
    clients = Client.query.filter(
    Client.cliente_nome != "Booking",
    Client.cliente_cognome != "Online"
).all()
    response = []
    for client in clients:
        num_passaggi = Appointment.query.filter(
            Appointment.client_id == client.id,
            Appointment.stato.in_([0, 1, 2])
        ).count()
        response.append({
            "id": client.id,
            "nome": client.cliente_nome,
            "cognome": client.cliente_cognome,
            "cellulare": client.cliente_cellulare,
            "email": client.cliente_email,
            "data_nascita": client.cliente_data_nascita,
            "created_at": client.created_at,
            "num_passaggi": num_passaggi
        })
    return jsonify(response)

@clients_bp.route('/', methods=['POST'])
def create_client():
    """Crea un nuovo cliente."""
    data = request.json

    new_client = Client(
        cliente_nome=data['nome'],
        cliente_cognome=data['cognome'],
        cliente_cellulare=data['cellulare'],
        cliente_email=data.get('email'),  # Campo opzionale
        cliente_data_nascita=data.get('data_nascita')  # Campo opzionale
    )

    db.session.add(new_client)
    db.session.commit()

    return jsonify({"message": "Cliente creato con successo!", "id": new_client.id}), 201

@clients_bp.route('/<int:client_id>', methods=['GET'])
def get_client(client_id):
    """Restituisce i dettagli di un singolo cliente."""
    client = db.session.get(Client, client_id)
    if not client:
        abort(404)
    response = {
        "id": client.id,
        "nome": client.cliente_nome,
        "cognome": client.cliente_cognome,
        "cellulare": client.cliente_cellulare,
        "email": client.cliente_email,
        "data_nascita": client.cliente_data_nascita
    }
    return jsonify(response)

@clients_bp.route('/<int:client_id>', methods=['PUT'])
def update_client(client_id):
    """Aggiorna i dettagli di un cliente."""
    data = request.json
    client = db.session.get(Client, client_id)
    if not client:
        abort(404)

    client.cliente_nome = data.get('nome', client.cliente_nome)
    client.cliente_cognome = data.get('cognome', client.cliente_cognome)
    client.cliente_cellulare = data.get('cellulare', client.cliente_cellulare)
    client.cliente_email = data.get('email', client.cliente_email)  # Campo opzionale
    client.cliente_data_nascita = data.get('data_nascita', client.cliente_data_nascita)  # Campo opzionale

    db.session.commit()

    return jsonify({"message": "Cliente aggiornato con successo!"}), 200

@clients_bp.route('/<int:client_id>', methods=['DELETE'])
def delete_client(client_id):
    """Elimina un cliente."""
    client = db.session.get(Client, client_id)
    if not client:
        abort(404)
    db.session.delete(client)
    db.session.commit()

    return jsonify({"message": "Cliente eliminato con successo!"}), 200