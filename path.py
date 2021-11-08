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
from wtforms import (Form, StringField, TextAreaField,
                     validators, SelectField)

from wtforms.validators import Optional, Required, ValidationError



class Path(Form):

    def iso_date_validator(form, field):
        """
        validation for date in ISO8601 format (YYYY, YYYY-MM, YYYY-MM-DD)
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
    sampling_season = StringField("Sampling season", [])

    completeness  = StringField("Completeness", validators=[integer_validator,])
    #numero_segni_trovati  = StringField("Numero di segni trovati", validators=[integer_validator,])
    #numero_campioni  = StringField("Numero di campioni", validators=[integer_validator,])

    operatore = StringField("Operatore", [])
    note = TextAreaField("Note", [])

