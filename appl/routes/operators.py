#appl/routes/operators.py
import datetime
from flask import Blueprint, app, request, jsonify, render_template, abort
from .. import db
from ..models import Operator, Service, BusinessInfo, Appointment

# Blueprint per le rotte degli operatori
operators_bp = Blueprint('operators', __name__)

@operators_bp.route('/operators', methods=['GET'])
def list_operators():
    """Restituisce la lista di tutti gli operatori."""
    operators = Operator.query.order_by(Operator.order).all()  # Order by the 'order' column
    response = [
        {
            "id": operator.id,
            "nome": operator.user_nome,
            "cognome": operator.user_cognome,
            "cellulare": operator.user_cellulare,
            "tipo": operator.user_tipo,
            "schedule": operator.user_schedule
        }
        for operator in operators
    ]
    return jsonify(response)

@operators_bp.route('/operators', methods=['POST'])
def create_operator():
    """Crea un nuovo operatore."""
    data = request.json

    new_operator = Operator(
        user_nome=data['nome'],
        user_cognome=data.get('cognome', ''),
        user_cellulare=data.get('cellulare', ''),
        user_tipo=data['tipo'],
        user_schedule=data.get('schedule', {}),
        is_visible=True 
    )

    db.session.add(new_operator)
    db.session.commit()

    return jsonify({"message": "Operatore creato con successo!", "id": new_operator.id}), 201

@operators_bp.route('/operators/<int:operator_id>', methods=['GET'])
def get_operator(operator_id):
    """Restituisce i dettagli di un singolo operatore."""
    operator = db.session.get(Operator, operator_id)
    if not operator:
        abort(404)
    response = {
        "id": operator.id,
        "nome": operator.user_nome,
        "cognome": operator.user_cognome,
        "cellulare": operator.user_cellulare,
        "tipo": operator.user_tipo,
        "schedule": operator.user_schedule
    }
    return jsonify(response)

@operators_bp.route('/operators/<int:operator_id>', methods=['DELETE'])
def delete_operator(operator_id):
    """Elimina un operatore."""
    operator = db.session.get(Operator, operator_id)
    if not operator:
        abort(404)
    db.session.delete(operator)
    db.session.commit()

    return jsonify({"message": "Operatore eliminato con successo!"}), 200

@operators_bp.route('/<int:operator_id>/shifts', methods=['GET'])
def operator_shifts(operator_id):
    """Mostra la pagina di gestione turni per un singolo operatore."""
    operator = db.session.get(Operator, operator_id)
    if not operator:
        abort(404)
    return render_template('operators.html', operator=operator)

@operators_bp.route('/order', methods=['POST'])
def update_operator_order():
    """Aggiorna l'ordine degli operatori nel database."""
    data = request.get_json()
    new_order = data.get('order')

    if not new_order:
        return jsonify({"message": "No order provided"}), 400

    try:
        # Aggiorna l'ordine per tutti gli operatori (non solo quelli visibili)
        filtered_order = new_order
        for index, operator_id in enumerate(filtered_order):
            operator = db.session.get(Operator, operator_id)
            if not operator:
                abort(404)
            operator.order = index

        db.session.commit()
        return jsonify({"message": "Operator order updated successfully!"}), 200
    except Exception as e:
        db.session.rollback()
        app.logger.error("Errore durante l'aggiornamento dell'ordine operatori: %s", str(e))
        return jsonify({"message": "Errore durante l'aggiornamento dell'ordine"}), 500
