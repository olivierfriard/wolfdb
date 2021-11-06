"""
WolfDB web service
(c) Olivier Friard
"""



from flask import Markup
import datetime
from wtforms import (Form, StringField,
                     validators, SelectField)

from wtforms.validators import Optional, Required, ValidationError


class Scat(Form):

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
            try:  # YYYY-MM
                datetime.datetime.strptime(field.data, '%Y-%m')
                return
            except ValueError:
                try:  # YYYY-MM-DD
                    datetime.datetime.strptime(field.data, '%Y')
                    return
                except ValueError:
                    raise ValidationError(Markup('<div class="alert alert-danger" role="alert">The date is not valid (YYYY or YYYY-MM or YYY-MM-DD)</div>'))


    scat_id = StringField("Scat ID", validators=[Required(),])
    # genetic_id = StringField('Genetic ID', [])
    # genetic_id = StringField('Genetic ID', [])
    date = StringField("Date", validators=[Required(), iso_date_validator])
    sampling_season = StringField("Sampling season", [])
    sampling_type = SelectField("Sampling type", choices=[('-', '-'),
                                                          ('Opportunistico', 'Opportunistico'),
                                                          ('Sistematico', 'Sistematico')],
                                default="-")
    transect_id = SelectField("Transect ID")
    snowtrack_id = SelectField("Snow-tracking ID")
    localita = StringField("Località", [])
    comune = StringField("Comune", [])
    provincia = StringField("Provincia", [])
    deposition = SelectField("Deposition", choices=[('-', '-'),('fresca', 'fresca'), ('vecchia', 'vecchia')], default="-")
    matrix = SelectField("Matrix", choices=[('-', '-'),('Yes', 'Yes'), ('No', 'No')], default="-")
    collected_scat = SelectField("Collected scat", choices=[('-', '-'),('Yes', 'Yes'), ('No', 'No')], default="-")
    sample_genetic = SelectField("Sample genetic", choices=[('-', '-'),('Yes', 'Yes'), ('No', 'No')], default="-")
    coord_east = StringField("Coordinate East (UTM 32N WGS84)", validators=[integer_validator,])
    coord_north  = StringField("Coordinate North (UTM 32N WGS84)", validators=[integer_validator,])
    rilevatore_ente = StringField("Rilevatore / Ente", [])
    scalp_category = StringField("SCALP category", [])
