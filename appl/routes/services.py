#appl/routes/services.py
from flask import Blueprint, request, jsonify, abort
from .. import db
from ..models import Service

# Blueprint per le rotte dei servizi
services_bp = Blueprint('services', __name__)

@services_bp.route('/services', methods=['GET'])
def list_services():
    """Restituisce la lista di tutti i servizi."""
    services = Service.query.all()
    response = [
        {
            "id": service.id,
            "nome": service.servizio_nome,
            "tag": service.servizio_tag,
            "durata": service.servizio_durata,
            "prezzo": service.servizio_prezzo,
            "operator_ids": service.operator_ids
        }
        for service in services
    ]
    return jsonify(response)

@services_bp.route('/services', methods=['POST'])
def create_service():
    """Crea un nuovo servizio."""
    data = request.json

    new_service = Service(
        servizio_nome=data['nome'],
        servizio_tag=data['tag'],
        servizio_durata=data['durata'],
        servizio_prezzo=data['prezzo'],
        operator_ids=data.get('operator_ids', [])
    )

    db.session.add(new_service)
    db.session.commit()

    return jsonify({"message": "Servizio creato con successo!", "id": new_service.id}), 201

@services_bp.route('/services/<int:service_id>', methods=['GET'], endpoint='get_service')
def get_service(service_id):
    """Restituisce i dettagli di un singolo servizio."""
    service = db.session.get(Service, service_id)
    if not service:
        abort(404)
    response = {
        "id": service.id,
        "nome": service.servizio_nome,
        "tag": service.servizio_tag,
        "durata": service.servizio_durata,
        "prezzo": service.servizio_prezzo,
        "operator_ids": service.operator_ids
    }
    return jsonify(response)

@services_bp.route('/services/<int:service_id>', methods=['PUT'], endpoint='update_service')
def update_service(service_id):
    """Aggiorna i dettagli di un servizio."""
    data = request.json
    service = db.session.get(Service, service_id)
    if not service:
        abort(404)

    service.servizio_nome = data.get('nome', service.servizio_nome)
    service.servizio_tag = data.get('tag', service.servizio_tag)
    service.servizio_durata = data.get('durata', service.servizio_durata)
    service.servizio_prezzo = data.get('prezzo', service.servizio_prezzo)
    service.operator_ids = data.get('operator_ids', service.operator_ids)

    db.session.commit()

    return jsonify({"message": "Servizio aggiornato con successo!"}), 200

@services_bp.route('/services/<int:service_id>', methods=['DELETE'])
def delete_service(service_id):
    """Elimina un servizio."""
    service = db.session.get(Service, service_id)
    if not service:
        abort(404)
    db.session.delete(service)
    db.session.commit()

    return jsonify({"message": "Servizio eliminato con successo!"}), 200