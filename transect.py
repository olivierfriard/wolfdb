"""
WolfDB web service
(c) Olivier Friard
"""


"""
WolfDB web service
(c) Olivier Friard
"""


from wtforms import (Form, StringField)

from wtforms.validators import Required


class Transect(Form):
 
    transect_id = StringField("Transect ID", validators=[Required(),])
    sector = StringField("Sector", [])
    localita = StringField("Località", [])
    provincia = StringField("Provincia", [])
    regione = StringField("Regione", [])

