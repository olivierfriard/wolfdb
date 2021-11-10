"""
WolfDB web service
(c) Olivier Friard
"""



from flask import Markup
import datetime
from wtforms import (Form, StringField,
                     TextAreaField, SelectField)

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
        validation for date in ISO8601 format (YYYY-MM-DD)
        """
        try: # YYYY
            datetime.datetime.strptime(field.data, '%Y-%m-%d')
            return
        except ValueError:
            raise ValidationError(Markup('<div class="alert alert-danger" role="alert">The date is not valid. Use the YYY-MM-DD fomat</div>'))


    snowtrack_id = StringField("Snow-tracking ID", validators=[Required(),])
    path_id = SelectField("Path ID")
    #date = StringField("Date", validators=[Required(), iso_date_validator])
    #sampling_season = StringField("Sampling season", [])

    place = StringField("Place", [])
    municipality = StringField("Municipality", [])
    province = StringField("Province", [])

    observer = StringField("Observer", [])
    institution = StringField("Institution", [])

    scalp_category = SelectField("SCALP category", choices=[('C1', 'C1'), ('C2', 'C2'), ('C3', 'C3')], default="C2")

    sampling_type = SelectField("Sampling type", choices=[('', ''),
                                                          ('Opportunistic', 'Opportunistic'),
                                                          ('Systematic', 'Systematic')],
                                default="")

    nb_days_after_snowing = StringField("nb of days after snowing", validators=[integer_validator])
    min_number_subjects = StringField("Minimum number of subjects", validators=[integer_validator])
    track_format = StringField("Track format", [])

    note = TextAreaField("Note", [])