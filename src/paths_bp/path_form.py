"""
WolfDB web service
(c) Olivier Friard
"""


from markupsafe import Markup
import datetime
from wtforms import Form, StringField, TextAreaField, SelectField

from wtforms.validators import DataRequired, ValidationError


class Path(Form):
    def iso_date_validator(form, field):
        """
        validation for date in ISO8601 format (YYYY-MM-DD)
        """
        try:
            datetime.datetime.strptime(field.data, "%Y-%m-%d")
            return
        except ValueError:
            raise ValidationError(
                Markup(
                    (
                        '<div class="alert alert-danger" role="alert">The date is not valid.'
                        "The format must be YYYY-MM-DD.</div>"
                    )
                )
            )

    def required_integer_validator(form, field):
        """
        validation for a required integer value
        """
        try:
            int(field.data)
            return
        except Exception:
            raise ValidationError(
                Markup('<div class="alert alert-danger" role="alert">Not a valid integer value</div>')
            )

    transect_id = SelectField(
        "Transect ID *",
        validators=[
            DataRequired(),
        ],
    )

    date = StringField("Date *", validators=[DataRequired(), iso_date_validator])

    completeness = StringField(
        "% of completeness *",
        validators=[
            required_integer_validator,
        ],
    )
    # completeness = SelectField("Completeness", choices=[('', ''),('25', '25'), ('50', '50'), ('100', '100')], default="")

    observer = StringField("Observer", [])
    institution = StringField("Institution", [])

    category = SelectField(
        "Category",
        choices=[
            ("", ""),
            ("Università", "Università"),
            ("Provincia", "Provincia"),
            ("Forestali", "Forestali"),
            ("Volontari", "Volontari"),
            ("Aree Protette", "Aree Protette"),
            ("Altre istituzioni", "Altre istituzioni"),
        ],
        default="",
    )

    notes = TextAreaField("Notes", [])
