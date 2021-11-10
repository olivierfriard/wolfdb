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
        validation for date in ISO 8601 format (YYYY-MM-DD)
        """
        try: # YYYY
            datetime.datetime.strptime(field.data, '%Y-%m-%d')
            return
        except ValueError:
            raise ValidationError(Markup('<div class="alert alert-danger" role="alert">The date is not valid. Uset the YYY-MM-DD format</div>'))


    scat_id = StringField("Scat ID", validators=[Required(),])
    #date = StringField("Date", validators=[Required(), iso_date_validator])
    #sampling_season = StringField("Sampling season", [])
    sampling_type = SelectField("Sampling type", choices=[('', ''),
                                                          ('Opportunistic', 'Opportunistic'),
                                                          ('Systematic', 'Systematic')],
                                default="")
    path_id = SelectField("Path ID")
    snowtrack_id = SelectField("Snow-tracking ID")

    place = StringField("Place", [])
    municipality = StringField("Municipality", [])
    province = StringField("Province", [])


    deposition = SelectField("Deposition", choices=[('', ''),('fresh', 'fresh'), ('old', 'old')], default="")
    matrix = SelectField("Matrix", choices=[('', ''),('Yes', 'Yes'), ('No', 'No')], default="")
    collected_scat = SelectField("Collected scat", choices=[('', ''),('Yes', 'Yes'), ('No', 'No')], default="")
    scalp_category = SelectField("SCALP category", choices=[('C1', 'C1'), ('C2', 'C2'), ('C3', 'C3')], default="C2")
    sample_genetic = SelectField("Sample genetic", choices=[('-', '-'),('Yes', 'Yes'), ('No', 'No')], default="-")
    coord_east = StringField("Coordinate East", validators=[Required(), integer_validator])
    coord_north  = StringField("Coordinate North", validators=[Required(), integer_validator])
    coord_zone = SelectField("Zone", choices=[('32N', '32N'), ('33N', '33N')], default="32N")

    observer = StringField("Observer", [])
    institution = StringField("Institution", [])

