"""
WolfDB web service
(c) Olivier Friard
"""


from flask import Markup
import datetime

from wtforms import (Form, StringField, SelectField)
from wtforms.validators import Required, ValidationError


class Dead_wolf(Form):

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
        try:
            datetime.datetime.strptime(field.data, '%Y-%m-%d')
            return
        except ValueError:
            raise ValidationError(Markup('<div class="alert alert-danger" role="alert">The date is not valid. Uset the YYY-MM-DD format</div>'))



    field1 = StringField("ID", [], default="")
    field2 = SelectField("Necroscopy done",
                         choices=[('N.D.', 'N.D.'), ('SI', 'SI'), ('NO', 'NO'), ('In attesa', 'In attesa')],
                         default="N.D."
                         )
    field3 = SelectField("Definitive data", choices=[('NO', 'NO'), ('SI', 'SI')], default="NO")
    field4 = StringField("Genetic sample to recover", [], default="")
    field5 = StringField("Reminder on genetic sample collecting and documentation", [], default="")
    field6 = StringField("Tissue ID", [], default="")
    field7 = StringField("Additional Note on wolf recovery", [], default="")
    field8 = StringField("Presumed death date", [], default="")
    field9 = StringField("Discovery Date", [], default="")
    field10 = StringField("Sampling season", [], default="")
    field11 = StringField("Necroscopy date", [], default="")

    field12 = SelectField("Main cause of mortality", choices=[("", ""),
                                                      ("Indeterminata", "Indeterminata"),
                                                      ("Impatto con veicolo", "Impatto con veicolo"),
                                                      ("Naturale", "Naturale"),
                                                      ("Bracconaggio", "Bracconaggio"),
                                                      ("Probabile bracconaggio", "Probabile bracconaggio"),
                                                      ],
                                                      default="")

    field13 = SelectField("Specific cause of mortality", 
                          choices=[("", ""),
                           ("Indeterminata", "Indeterminata"),
                           ("Inanizione", "Inanizione"),
                           ("Aggressione intra/interspecifica", "Aggressione intra/interspecifica"),
                           ("Possibile avvelenamento", "Possibile avvelenamento"),
                           ("Avvelenamento", "Avvelenamento"),
                           ("Deperimento e pleuroperitonite", "Deperimento e pleuroperitonite"),
                           ("Probabile avvelenamento", "Probabile avvelenamento"),
                           ("Malattia", "Malattia"),
                           ("Laccio", "Laccio"),
                           ("Aggressione interspecifica", "Aggressione interspecifica"),
                           ("Impatto con treno", "Impatto con treno"),
                           ("Aggressione intraspecifica", "Aggressione intraspecifica"),
                           ("Impatto con auto", "Impatto con auto"),
                           ("Valanga", "Valanga"),
                           ("Arma da fuoco", "Arma da fuoco")
                          ],
                        default="")

    field14 = StringField("Note on cause of mortality", [], default="")
    field15 = StringField("Additional events on mortality", [], default="")
    field16 = StringField("Toxic category", [], default="")
    field17 = StringField("Location", [], default="")
    field18 = StringField("Municipality", [], default="")
    field19 = StringField("Valley", [], default="")
    field20 = StringField("Province", [], default="")
    field21 = StringField("Area", [], default="")
    field22 = StringField("Country", [], default="")
    field23 = StringField("Coordinates East (WGS 84 / UTM zone 32N EPSG:32632)", validators=[integer_validator], default="")
    field24 = StringField("Coordinates East (WGS 84 / UTM zone 32N EPSG:32632)", validators=[integer_validator], default="")
    field25 = StringField("UTM zone", [], default="32N")
    field26 = SelectField("Georeference",
                            choices=[("Accurata", "Accurata"),
                            ("N.D.", "N.D."),
                            ("Dedotta, non accurata", "Dedotta, non accurata")
                            ],
                            default="N.D.")
    field27 = StringField("Whole weight", [], default="")
    field28 = StringField("Gutted weight", [], default="")


    field29 = StringField("Note on weight measurement", [], default="")
    field30 = StringField("Estimated age", [], default="")
    field31 = StringField("Minimum Age estimated by genetic recapture", [], default="")

    field32 = StringField("Estimated age with Cementum Anuli", [], default="")
    field33 = StringField("Canine collected", [], default="")
    field34 = SelectField("Age class",
                            choices=[("", ""),
                             ("<1", "<1"),
                             ("Indeterminata", "Indeterminata"),
                             ("1-2", "1-2"),
                             ("Adult (>2)", "Adult (>2)")],
                             default="")
    field35 = StringField("Sex", [], default="")

    field36 = StringField("Genotype ID", [], default="")
    field37 = StringField("Wolf Pack", [], default="")
    field38 = StringField("Status", [], default="")
    field39 = StringField("Recapture", [], default="")
    field40 = StringField("Aplotipe Result", [], default="")
    field41 = StringField("Genetic Result Note", [], default="")
    field42 = StringField("Genetic Lab", [], default="")
    field43 = SelectField("Type of recovery",
                            choices=[("", ""),
                            ("Carcassa", "Carcassa"),
                            ("Cranio ", "Cranio "),
                            ("Cranio", "Cranio"),
                            ("Carcassa ", "Carcassa "),
                            ("Pelo", "Pelo"),
                            ("Sangue", "Sangue"),
                            ("N.D.", "N.D."),
                            ("Resti parziali", "Resti parziali"),
                            ("Pelle", "Pelle")
                            ],
                            default="")
    field44 = StringField("Note on recovery", [], default="")
    field45 = StringField("Box send to USA Genetic Lab", [], default="")
    field46 = StringField("WA", [], default="")
    field47 = StringField("ISPRA Lab", [], default="")
    field48 = StringField("Note on genetic sample", [], default="")
    field49 = StringField("Coded Sample to be sent", [], default="")
    field50 = StringField("Lunghezza totale", [], default="")
    field51 = StringField("Altezza garrese", [], default="")
    field52 = StringField("Piede posteriore", [], default="")
    field53 = StringField("Altezza orecchio", [], default="")
    field54 = StringField("Lunghezza coda", [], default="")
    field55 = StringField("Lunghezza naso-orecchio", [], default="")
    field56 = StringField("Lunghezza orecchio-spalla", [], default="")
    field57 = StringField("Lunghezza spalla-coda", [], default="")
    field58 = StringField("Lunghezza zampa post", [], default="")
    field59 = StringField("Circonferenza torace", [], default="")
    field60 = StringField("Circonferenza collo", [], default="")
    field61 = StringField("FERINO INF DX largh", [], default="")
    field62 = StringField("FERINO INF SX largh", [], default="")
    field63 = StringField("FERINO INF DX alt", [], default="")
    field64 = StringField("FERINO INF SX alt", [], default="")
    field65 = StringField("FERINO SUP DX largh", [], default="")
    field66 = StringField("FERINO SUP SX largh", [], default="")
    field67 = StringField("FERINO SUP DX alt", [], default="")
    field68 = StringField("FERINO SUP SX alt", [], default="")
    field69 = StringField("CANINO INF DX alt", [], default="")
    field70 = StringField("CANINO INF SX alt", [], default="")
    field71 = StringField("CANINO INF distanza", [], default="")
    field72 = StringField("CANINO SUP DX alt", [], default="")
    field73 = StringField("CANINO SUP SX alt", [], default="")
    field74 = StringField("CANINO SUP distanza", [], default="")
    field75 = StringField("Note su rilevamento biometrico", [], default="")
    field76 = StringField("Recovered by", [], default="")
    field77 = StringField("Necroscopy by", [], default="")
    field78 = StringField("In collaboration with", [], default="")
    field79 = StringField("Carcass Disposed", [], default="")
    field80 = StringField("Carcass Embalbed", [], default="")
    field81 = StringField("skeleton assembled", [], default="")
    field82 = SelectField("Skull cleaned",
                          choices=[('', ''), ('N.D.', 'N.D.'), ('SI', 'SI'), ('NO', 'NO')],
                          default=""
                         )
    field83 = SelectField("Recoverable for embalming",
                         choices=[('', ''), ('N.D.', 'N.D.'), ('SI', 'SI'), ('NO', 'NO')],
                         default=""
                         )
    field84 = StringField("Placed in", [], default="")
    field85 = StringField("CITES Code", [], default="")
    field86 = StringField("Marking type", [], default="")
    field87 = StringField("Marking ID", [], default="")
    field88 = StringField("Data Collector", [], default="")
    field89 = StringField("Other Genotype Code from other LAB", [], default="")
    field90 = StringField("Report of necroscopy present", [], default="")
    field91 = StringField("Photos archived", [], default="")
    field92 = StringField("Necropsy result", [], default="")
    field93 = StringField("Remarks", [], default="")
    field94 = StringField("IZS Code", [], default="")
    field95 = StringField("rabbia", [], default="")
    field96 = StringField("cimurro TO (SNC, polmone, vescica, milza)", [], default="")
    field97 = StringField("cimurro AO (SNC, polmone, vescica, milza)", [], default="")
    field98 = StringField("parassiti (feci)", [], default="")
    field99 = StringField("salmonella TO (fegato, intestino)", [], default="")
    field100 = StringField("echinococco AO (retto)", [], default="")
    field101 = StringField("salmonella AO (retto)", [], default="")
    field102 = StringField("yersinia AO (retto)", [], default="")
    field103 = StringField("trichinella ", [], default="")
    field104 = StringField("tox", [], default="")
    field105 = StringField("ISTO AO", [], default="")
    field106 = StringField("Other", [], default="")