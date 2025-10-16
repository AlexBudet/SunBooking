# appl/forms.py
from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, IntegerField, SubmitField
from wtforms.validators import DataRequired

class AppointmentForm(FlaskForm):
    client_id = SelectField('Cliente', coerce=int, validators=[DataRequired()])
    service_id = SelectField('Servizio', coerce=int, validators=[DataRequired()])
    start_time = StringField('Ora di Inizio', validators=[DataRequired()])  # Puoi usare un DateTimeField se necessario
    duration = IntegerField('Durata (minuti)', validators=[DataRequired()])
    submit = SubmitField('Aggiorna')