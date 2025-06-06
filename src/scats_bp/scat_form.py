"""
WolfDB web service
(c) Olivier Friard
"""

from markupsafe import Markup
import datetime

from wtforms import Form, StringField, SelectField, TextAreaField

from wtforms.validators import DataRequired, ValidationError


class Scat(Form):
    def integer_validator(form, field):
        if not field.data:
            return
        try:
            int(field.data)
            return
        except Exception:
            raise ValidationError(Markup('<div class="alert alert-danger" role="alert">Not a valid integer value</div>'))

    def iso_date_validator(form, field):
        """
        validation for date in ISO 8601 format (YYYY-MM-DD)
        """
        try:  # YYYY
            datetime.datetime.strptime(field.data, "%Y-%m-%d")
            return
        except ValueError:
            raise ValidationError(
                Markup('<div class="alert alert-danger" role="alert">The date is not valid. Uset the YYYY-MM-DD format</div>')
            )

    def wa_validator(form, field):
        """
        validation of WA code
        """
        if field.data == "":
            return
        """
        DISABLED
        m = re.match("WA.*", field.data)
        if m is None:
            raise ValidationError(Markup('<div class="alert alert-danger" role="alert">Wrong format. The WA code must begin with WA</div>'))
        return
        """

    scat_id = StringField(
        "Scat ID",
        validators=[
            DataRequired(),
        ],
    )

    date = StringField(
        "Date",
        validators=[iso_date_validator],
        render_kw={
            "placeholder": "YYYY-MM-DD",
            "pattern": r"\d{4}-\d{2}-\d{2}",
            "inputmode": "numeric",
        },
    )

    wa_code = StringField("WA code", validators=[wa_validator])

    ispra_id = StringField("ISPRA ID")

    sampling_type = SelectField(
        "Sampling type",
        choices=[
            ("Unknown", "Unknown"),
            ("Opportunistic", "Opportunistic"),
            ("Systematic", "Systematic"),
        ],
        default="",
    )

    sample_type = SelectField(
        "Sample type",
        choices=[
            ("unknown", "Unknown"),
            ("scat", "Excrement"),
            ("tissue", "Tissue"),
            ("saliva", "Saliva"),
            ("blood", "Blood"),
            ("hair", "Hair"),
        ],
        default="",
    )

    path_id = SelectField("Path ID")
    snowtrack_id = SelectField("Track ID")

    location = StringField("Location", [])
    municipality = StringField("Municipality", [])
    province = StringField("Province", [])

    deposition = SelectField("Deposition", choices=[("", ""), ("Fresh", "Fresh"), ("Old", "Old")], default="")
    matrix = SelectField("Matrix", choices=[("", ""), ("Yes", "Yes"), ("No", "No")], default="")
    collected_scat = SelectField("Collected scat", choices=[("", ""), ("Yes", "Yes"), ("No", "No")], default="")
    scalp_category = SelectField(
        "SCALP category",
        choices=[("C1", "C1"), ("C2", "C2"), ("C3", "C3")],
        default="C2",
    )
    genetic_sample = SelectField("Genetic sample", choices=[("", ""), ("Yes", "Yes"), ("No", "No")], default="")
    coord_east = StringField("Easting (X)", validators=[DataRequired(), integer_validator])
    coord_north = StringField("Northing (Y)", validators=[DataRequired(), integer_validator])
    coord_zone = StringField("Zone number", validators=[DataRequired(), integer_validator])
    hemisphere = SelectField("Hemisphere", choices=[("N", "N"), ("S", "S")], default="N")

    observer = StringField("Operator", [])
    institution = StringField("Institution", [])

    notes = TextAreaField("Notes", [])
