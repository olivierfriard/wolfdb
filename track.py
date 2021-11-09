"""
WolfDB web service
(c) Olivier Friard
"""



from flask import Markup
import datetime
from wtforms import (Form, StringField,
                     validators, SelectField)

from wtforms.validators import Optional, Required, ValidationError


class Track(Form):

    def integer_validator(form, field):
        if not field.data:
            return
        try:
            int(field.data)
            return
        except:
            raise ValidationError(Markup('<div class="alert alert-danger" role="alert">Not a valid integer value</div>'))


    def iso_date_validator(form, field):
        """
        validation for date in ISO8601 format (YYYY, YYYY-MM, YYYY-MM-DD)
        """
        try: # YYYY
            datetime.datetime.strptime(field.data, '%Y-%m-%d')
            return
        except ValueError:
            raise ValidationError(Markup('<div class="alert alert-danger" role="alert">The date is not valid. Use the YYY-MM-DD fomat</div>'))


    snowtrack_id = StringField("Snow-tracking ID", validators=[Required(),])
    path_id = SelectField("Path ID")
    date = StringField("Date", validators=[Required(), iso_date_validator])
    sampling_season = StringField("Sampling season", [])

    comune = StringField("Comune", [])
    provincia = StringField("Provincia", [])
    regione = StringField("Regione", [])

    rilevatore = StringField("Rilevatore", [])
    scalp_category = StringField("SCALP category", [])
    systematic_sampling = SelectField("Systematic sampling", choices=[('-', '-'),('Yes', 'Yes'), ('No', 'No')], default="-")

    giorni_dopo_nevicata = StringField("Numero di giorni dopo nevicata", [])
    n_minimo_individui = StringField("numero minimo di individui", [])
    track_format = StringField("Track format", [])

