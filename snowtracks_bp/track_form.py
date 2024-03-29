"""
WolfDB web service
(c) Olivier Friard
"""


from markupsafe import Markup

import datetime
from wtforms import Form, StringField, TextAreaField, SelectField

from wtforms.validators import Optional, DataRequired, ValidationError


class Track(Form):
    def integer_validator(form, field):
        if not field.data:
            return
        try:
            int(field.data)
            return
        except Exception:
            raise ValidationError(
                Markup('<div class="alert alert-danger" role="alert">Not a valid integer value</div>')
            )

    def iso_date_validator(form, field):
        """
        validation for date in ISO8601 format (YYYY-MM-DD)
        """
        try:  # YYYY
            datetime.datetime.strptime(field.data, "%Y-%m-%d")
            return
        except ValueError:
            raise ValidationError(
                Markup(
                    '<div class="alert alert-danger" role="alert">The date is not valid. Use the YYY-MM-DD fomat</div>'
                )
            )

    snowtrack_id = StringField(
        "Track ID",
        validators=[
            DataRequired(),
        ],
    )
    transect_id = StringField("Transect ID")

    # path_id = SelectField("Path ID")

    # date = StringField("Date", validators=[DataRequired(), iso_date_validator])
    # sampling_season = StringField("Sampling season", [])

    location = StringField("Location", [])
    municipality = StringField("Municipality", [])
    province = StringField("Province", [])

    observer = StringField("Operator", [])
    institution = StringField("Institution", [])

    scalp_category = SelectField("SCALP category", choices=[("C1", "C1"), ("C2", "C2"), ("C3", "C3")], default="C2")

    sampling_type = SelectField(
        "Sampling type",
        choices=[("", ""), ("Opportunistic", "Opportunistic"), ("Systematic", "Systematic")],
        default="",
    )

    days_after_snowfall = StringField("Days after snowfall", validators=[])
    minimum_number_of_wolves = StringField("Minimum number of wolves", validators=[])

    track_format = StringField("Track format", [])

    track_type = SelectField("Track type", choices=[("", ""), ("Snow", "Snow"), ("Mud", "Mud")], default="")

    notes = TextAreaField("Notes", [])

    multilines = TextAreaField("MultiLineString (WKT)", [])
