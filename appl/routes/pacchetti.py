# appl/routes/pacchetti.py
from flask import Blueprint, render_template

pacchetti_bp = Blueprint('pacchetti', __name__)

@pacchetti_bp.route('/')
def pacchetti_home():
    # Pagina principale Pacchetti - da espandere con logica CRUD
    return render_template('pacchetti.html')