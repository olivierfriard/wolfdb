"""
WolfDB web service
(c) Olivier Friard
"""

from markupsafe import Markup
import datetime
import re

from wtforms import Form, StringField, SelectField
from wtforms.validators import ValidationError


class Dead_wolf(Form):
    """
    form to insert or modifiy a dead wolf

    """

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
        if field.data == "":
            return
        try:
            datetime.datetime.strptime(field.data, "%Y-%m-%d")
            return
        except ValueError:
            raise ValidationError(
                Markup('<div class="alert alert-danger" role="alert">The date is not valid. Use the YYYY-MM-DD format</div>')
            )

    def sampling_season_validator(form, field):
        """
        validation of YYYY-YYYY format
        """

        if field.data == "":
            return
        m = re.match("(\d{4})-(\d{4})", field.data)
        if m is None:
            raise ValidationError(Markup('<div class="alert alert-danger" role="alert">Wrong format. Use the YYYY-YYYY format</div>'))
        try:
            y1, y2 = m.group().split("-")
            if int(y1) >= int(y2):
                raise ValidationError(Markup('<div class="alert alert-danger" role="alert">First year must be < than second year</div>'))
        except Exception:
            raise ValidationError(Markup('<div class="alert alert-danger" role="alert">Check the format (YYYY-YYYY)</div>'))
        return

    field1 = StringField("ID", [], default="")

    tissue_id = StringField("Tissue ID", [], default="")

    genotype_id = StringField("Genotype ID", [], default="")

    wa_code = StringField("WA code", [], default="")

    discovery_date = StringField(
        "Discovery Date",
        validators=[iso_date_validator],
        render_kw={
            "placeholder": "YYYY-MM-DD",
            "pattern": r"\d{4}-\d{2}-\d{2}",
            "inputmode": "numeric",
        },
        default="",
    )

    location = StringField("Location", [], default="")
    municipality = StringField("Municipality", [], default="")

    province = SelectField(
        "Province",
        choices=[
            ("", ""),
            ("AG", "Agrigento"),
            ("AL", "Alessandria"),
            ("06", "Alpi Marittime"),
            ("AN", "Ancona"),
            ("AO", "Aosta"),
            ("AR", "Arezzo"),
            ("AP", "Ascoli"),
            ("AT", "Asti"),
            ("AV", "Avellino"),
            ("BA", "Bari"),
            ("BT", "Barletta-Andria-Trani"),
            ("BL", "Belluno"),
            ("BN", "Benevento"),
            ("BG", "Bergamo"),
            ("BI", "Biella"),
            ("BO", "Bologna"),
            ("BZ", "Bolzano"),
            ("BS", "Brescia"),
            ("BR", "Brindisi"),
            ("CA", "Cagliari"),
            ("CL", "Caltanissetta"),
            ("CB", "Campobasso"),
            ("CI", "Carbonia Iglesias"),
            ("CE", "Caserta"),
            ("CT", "Catania"),
            ("CZ", "Catanzaro"),
            ("CH", "Chieti"),
            ("CO", "Como"),
            ("CS", "Cosenza"),
            ("CR", "Cremona"),
            ("KR", "Crotone"),
            ("CN", "Cuneo"),
            ("EN", "Enna"),
            ("FM", "Fermo"),
            ("FE", "Ferrara"),
            ("FI", "Firenze"),
            ("FG", "Foggia"),
            ("FC", "Forli-Cesena"),
            ("FR", "Frosinone"),
            ("GE", "Genova"),
            ("GO", "Gorizia"),
            ("GR", "Grosseto"),
            ("IM", "Imperia"),
            ("IS", "Isernia"),
            ("AQ", "L'Aquila"),
            ("SP", "La Spezia"),
            ("LT", "Latina"),
            ("LE", "Lecce"),
            ("LC", "Lecco"),
            ("LI", "Livorno"),
            ("TI", "Locarno"),
            ("LO", "Lodi"),
            ("LU", "Lucca"),
            ("MC", "Macerata"),
            ("MN", "Mantova"),
            ("MS", "Massa-Carrara"),
            ("MT", "Matera"),
            ("VS", "Medio Campidano"),
            ("ME", "Messina"),
            ("MI", "Milano"),
            ("MO", "Modena"),
            ("MB", "Monza e Brianza"),
            ("NA", "Napoli"),
            ("NO", "Novara"),
            ("NU", "Nuoro"),
            ("OG", "Ogliastra"),
            ("OT", "Olbia Tempio"),
            ("OR", "Oristano"),
            ("PD", "Padova"),
            ("PA", "Palermo"),
            ("PR", "Parma"),
            ("PV", "Pavia"),
            ("PG", "Perugia"),
            ("PU", "Pesaro e Urbino"),
            ("PE", "Pescara"),
            ("PC", "Piacenza"),
            ("PI", "Pisa"),
            ("PT", "Pistoia"),
            ("PN", "Pordenone"),
            ("PZ", "Potenza"),
            ("PO", "Prato"),
            ("RG", "Ragusa"),
            ("RA", "Ravenna"),
            ("RC", "Reggio Calabria"),
            ("RE", "Reggio Emilia"),
            ("RI", "Rieti"),
            ("RN", "Rimini"),
            ("Roma", "Roma"),
            ("RO", "Rovigo"),
            ("SA", "Salerno"),
            ("SV", "Savona"),
            ("SO", "Sondrio"),
            ("TA", "Taranto"),
            ("TE", "Teramo"),
            ("TR", "Terni"),
            ("TO", "Torino"),
            ("TP", "Trapani"),
            ("TN", "Trento"),
            ("TV", "Treviso"),
            ("TS", "Trieste"),
            ("UD", "Udine"),
            ("VA", "Varese"),
            ("VE", "Venezia"),
            ("VB", "Verbano-Cusio-Ossola"),
            ("VC", "Vercelli"),
            ("VR", "Verona"),
            ("VV", "Vibo Valentia"),
            ("VI", "Vicenza"),
            ("VT", "Viterbo"),
        ],
        default="",
    )

    field21 = StringField("Area", [], default="")
    field22 = StringField("Country", [], default="")
    field26 = SelectField(
        "Georeference",
        choices=[("Accurata", "Accurata"), ("N.D.", "N.D."), ("Dedotta, non accurata", "Dedotta, non accurata")],
        default="N.D.",
    )

    # coordinates
    utm_east = StringField("Coordinates East (WGS 84 / UTM zone 32N EPSG:32632)", validators=[integer_validator], default="")
    utm_north = StringField("Coordinates East (WGS 84 / UTM zone 32N EPSG:32632)", validators=[integer_validator], default="")
    utm_zone = StringField("UTM zone", validators=[integer_validator], default="32")
    hemisphere = SelectField("Hemisphere", choices=[("N", "N"), ("S", "S")], default="N")

    # SCALP category
    field230 = SelectField(
        "SCALP category",
        choices=[("C1", "C1"), ("C2", "C2"), ("C3", "C3")],
        default="C1",
    )

    field2 = SelectField(
        "Necroscopy done",
        choices=[("N.D.", "N.D."), ("SI", "SI"), ("NO", "NO"), ("In attesa", "In attesa")],
        default="N.D.",
    )
    field3 = SelectField("Definitive data", choices=[("NO", "NO"), ("SI", "SI")], default="NO")
    field4 = StringField("Genetic sample to recover", [], default="")
    field5 = StringField("Reminder on genetic sample collecting and documentation", [], default="")

    field7 = StringField("Additional Note on wolf recovery", [], default="")
    field8 = StringField(
        "Presumed death date",
        validators=[iso_date_validator],
        render_kw={
            "placeholder": "YYYY-MM-DD",
            "pattern": r"\d{4}-\d{2}-\d{2}",
            "inputmode": "numeric",
        },
        default="",
    )
    field10 = StringField("Sampling season", validators=[sampling_season_validator], default="")
    field11 = StringField(
        "Necroscopy date",
        validators=[iso_date_validator],
        render_kw={
            "placeholder": "YYYY-MM-DD",
            "pattern": r"\d{4}-\d{2}-\d{2}",
            "inputmode": "numeric",
        },
        default="",
    )

    field12 = SelectField(
        "Main cause of mortality",
        choices=[
            ("", ""),
            ("Indeterminata", "Indeterminata"),
            ("Impatto con veicolo", "Impatto con veicolo"),
            ("Naturale", "Naturale"),
            ("Bracconaggio", "Bracconaggio"),
            ("Probabile bracconaggio", "Probabile bracconaggio"),
        ],
        default="",
    )

    field13 = SelectField(
        "Specific cause of mortality",
        choices=[
            ("", ""),
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
            ("Arma da fuoco", "Arma da fuoco"),
        ],
        default="",
    )

    field14 = StringField("Note on cause of mortality", [], default="")
    field15 = StringField("Additional events on mortality", [], default="")
    field16 = StringField("Toxic category", [], default="")

    field19 = StringField("Valley", [], default="")

    field27 = StringField("Whole weight", [], default="")
    field28 = StringField("Gutted weight", [], default="")

    field29 = StringField("Note on weight measurement", [], default="")
    field30 = StringField("Estimated age", [], default="")
    field31 = StringField("Minimum Age estimated by genetic recapture", [], default="")

    field32 = StringField("Estimated age with Cementum Anuli", [], default="")
    field33 = StringField("Canine collected", [], default="")

    field34 = SelectField(
        "Age class",
        choices=[
            ("", ""),
            ("<1", "<1"),
            ("Indeterminata", "Indeterminata"),
            ("1-2", "1-2"),
            ("Adult (>2)", "Adult (>2)"),
        ],
        default="",
    )
    field35 = StringField("Sex", [], default="")

    field37 = StringField("Wolf Pack", [], default="")
    field38 = StringField("Status", [], default="")
    field39 = StringField("Recapture", [], default="")
    field40 = StringField("Aplotipe Result", [], default="")
    field41 = StringField("Genetic Result Note", [], default="")
    field42 = StringField("Genetic Lab", [], default="")

    field43 = SelectField(
        "Type of recovery",
        choices=[
            ("", ""),
            ("Carcassa", "Carcassa"),
            ("Cranio ", "Cranio "),
            ("Cranio", "Cranio"),
            ("Carcassa ", "Carcassa "),
            ("Pelo", "Pelo"),
            ("Sangue", "Sangue"),
            ("N.D.", "N.D."),
            ("Resti parziali", "Resti parziali"),
            ("Pelle", "Pelle"),
        ],
        default="",
    )
    field44 = StringField("Note on recovery", [], default="")
    field45 = StringField("Box send to USA Genetic Lab", [], default="")

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

    field82 = SelectField("Skull cleaned", choices=[("", ""), ("N.D.", "N.D."), ("SI", "SI"), ("NO", "NO")], default="")

    field83 = SelectField("Recoverable for embalming", choices=[("", ""), ("N.D.", "N.D."), ("SI", "SI"), ("NO", "NO")], default="")

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
