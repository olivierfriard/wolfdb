"""
WolfDB web service
(c) Olivier Friard
"""


"""
WolfDB web service
(c) Olivier Friard
"""


from flask import Markup
import datetime
from wtforms import (Form, StringField, TextAreaField, SelectField)

from wtforms.validators import Required, ValidationError



class Path(Form):

    def iso_date_validator(form, field):
        """
        validation for date in ISO8601 format (YYYY-MM-DD)
        """
        try: # YYYY
            datetime.datetime.strptime(field.data, '%Y-%m-%d')
            return
        except ValueError:
            raise ValidationError(Markup('<div class="alert alert-danger" role="alert">The date is not valid. The format must be YYYY-MM-DD.</div>'))

    def integer_validator(form, field):
        if not field.data:
            return
        try:
            int(field.data)
            return
        except:
            raise ValidationError(Markup('<div class="alert alert-danger" role="alert">Not a valid integer value</div>'))


    transect_id = SelectField("Transect ID", validators=[Required()])

    date = StringField("Date", validators=[Required(), iso_date_validator])

    completeness  = StringField("Completeness", validators=[integer_validator,])
    completeness = SelectField("Completeness", choices=[('', ''),('25', '25'), ('50', '50'), ('100', '100')], default="")

    observer = StringField("Observer", [])
    institution = StringField("Institution", [])

    notes = TextAreaField("Notes", [])

