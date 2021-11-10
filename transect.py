"""
WolfDB web service
(c) Olivier Friard
"""


"""
WolfDB web service
(c) Olivier Friard
"""

from flask import Markup
from wtforms import (Form, StringField)

from wtforms.validators import Required, ValidationError


class Transect(Form):

    def integer_validator(form, field):
        if not field.data:
            return
        try:
            int(field.data)
            return
        except:
            raise ValidationError(Markup('<div class="alert alert-danger" role="alert">Not a valid integer value</div>'))


    transect_id = StringField("Transect ID", validators=[Required(),])
    sector = StringField("Sector", validators=[integer_validator])
    place = StringField("Place", [])
    municipality = StringField("Municipality", [])
    province = StringField("Province", [])
    #regione = StringField("Regione", [])

