"""
WolfDB web service
(c) Olivier Friard
"""

from markupsafe import Markup
from wtforms import Form, StringField, TextAreaField

from wtforms.validators import DataRequired, ValidationError


class Transect(Form):
    def integer_validator(form, field):
        if not field.data:
            return
        try:
            int(field.data)
            return
        except Exception:
            raise ValidationError(Markup('<div class="alert alert-danger" role="alert">Not a valid integer value</div>'))

    transect_id = StringField(
        "Transect ID",
        validators=[
            DataRequired(),
        ],
    )
    sector = StringField("Sector", validators=[integer_validator])
    location = StringField("Location", [])
    municipality = StringField("Municipality", [])
    province_code = StringField("Province code", [])
    # regione = StringField("Regione", [])

    multilines = TextAreaField("MultiLineString (WKT)", [])
