"""
WolfDB web service
(c) Olivier Friard

functions module

"""

from functools import wraps
from flask import redirect, session, url_for
from markupsafe import Markup
from sqlalchemy import text
import psycopg2
import psycopg2.extras
from config import config
import urllib.request
import json
import redis
from typing import Union
from sqlalchemy import create_engine
from jinja2 import Template

from italian_regions import regions, prov_name2prov_code

params = config()

rdis = redis.Redis(db=(0 if params["database"] == "wolf" else 1))


def check_login(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "google_id" not in session:
            return redirect(url_for("google_auth.login"))
        return f(*args, **kwargs)

    return decorated_function


def get_connection():
    return psycopg2.connect(
        user=params["user"],
        password=params["password"],
        host=params["host"],
        # port="5432",
        database=params["database"],
    )


def conn_alchemy():
    return create_engine(
        f"postgresql+psycopg://{params['user']}:{params['password']}@{params['host']}:5432/{params['database']}",
        isolation_level="AUTOCOMMIT",
    )


def get_loci_list() -> dict:
    """
    get list of loci
    """

    with conn_alchemy().connect() as con:
        loci_list: dict = {}
        for row in con.execute(text("SELECT name, n_alleles FROM loci ORDER BY position ASC")).mappings().all():
            loci_list[row["name"]] = row["n_alleles"]
    return loci_list


def get_allele_modifier(email: str) -> bool:
    """
    check if current user can modify allele value (allele modifier)
    """

    with conn_alchemy().connect() as con:
        return (
            con.execute(text("SELECT allele_modifier FROM users WHERE email = :email"), {"email": email})
            .mappings()
            .fetchone()["allele_modifier"]
        )


def get_wa_loci_values_redis(wa_code: str) -> dict | None:
    """
    get WA code loci values from redis
    """
    r = rdis.get(wa_code)
    if r is not None:
        return json.loads(r)
    else:
        return get_wa_loci_values(wa_code, get_loci_list())[0]


def get_wa_loci_values(wa_code: str, loci_list: list) -> tuple[dict, bool]:
    """
    get WA code loci values from postgresql
    """
    with conn_alchemy().connect() as con:
        has_loci_notes = False

        loci_values: dict = {}

        for locus in loci_list:
            loci_values[locus] = {}

            for allele in ("a", "b")[: loci_list[locus]]:  # select number of alleles
                # get last locus value and the last notes (if any)
                row = (
                    con.execute(
                        text(
                            (
                                "SELECT val, notes, "
                                "extract(epoch from timestamp)::integer AS epoch, "
                                "user_id, "
                                "definitive, "
                                "to_char(timestamp, 'YYYY-MM-DD HH24:MI:SS') AS formatted_timestamp, "
                                "(SELECT COUNT(*) FROM wa_locus "
                                "WHERE wa_code=wl.wa_code "
                                "      AND locus=wl.locus "
                                "      AND allele=wl.allele "
                                "      AND user_id IS NOT NULL) AS has_history  "
                                "FROM wa_locus wl "
                                "WHERE wa_code = :wa_code AND locus = :locus AND allele = :allele "
                                "ORDER BY timestamp DESC LIMIT 1"
                            )
                        ),
                        {"wa_code": wa_code, "locus": locus, "allele": allele},
                    )
                    .mappings()
                    .fetchone()
                )

                if row is not None:
                    val = row["val"] if row["val"] is not None else "-"
                    notes = row["notes"] if not None else ""
                    has_history = row["has_history"]
                    has_loci_notes = has_history != 0
                    epoch = row["epoch"] if row["epoch"] is not None else ""
                    date = row["formatted_timestamp"] if row["formatted_timestamp"] is not None else ""
                    user_id = row["user_id"] if row["user_id"] is not None else ""
                    definitive = row["definitive"]

                else:
                    val = "-"
                    notes = ""
                    has_history = 0
                    epoch = ""
                    user_id = ""
                    date = ""
                    definitive = False

                loci_values[locus][allele] = {
                    "value": val,
                    "notes": notes,
                    "has_history": has_history,
                    "epoch": epoch,
                    "user_id": user_id,
                    "date": date,
                    "definitive": definitive,
                }

    return loci_values, has_loci_notes


def get_genotype_loci_values_redis(genotype_id: str) -> dict | None:
    """
    get genotype loci values from redis
    """
    r = rdis.get(genotype_id)
    if r is not None:
        return json.loads(r)
    else:
        return get_genotype_loci_values(genotype_id, get_loci_list())


def get_genotype_loci_values(genotype_id: str, loci_list: list) -> dict:
    """
    get genotype loci values from postgresql db
    """

    loci_values: dict = {}

    with conn_alchemy().connect() as con:
        for locus in loci_list:
            loci_values[locus] = {}

            for allele in ("a", "b")[: loci_list[locus]]:
                locus_val = (
                    con.execute(
                        text(
                            (
                                "SELECT val, notes, validated, user_id, extract(epoch from timestamp)::integer AS epoch, "
                                "(SELECT COUNT(*) FROM genotype_locus "
                                "WHERE genotype_id=gl.genotype_id "
                                "      AND locus=gl.locus "
                                "      AND allele=gl.allele "
                                "      AND user_id IS NOT NULL) AS has_history "
                                # "(SELECT notes FROM genotype_locus "
                                # "WHERE genotype_id=gl.genotype_id "
                                # "      AND locus=gl.locus "
                                # "      AND allele=gl.allele "
                                # "      AND notes != '' "
                                # "      AND notes IS NOT NULL "
                                # "      ORDER BY timestamp DESC LIMIT 1) AS last_note "  # last note
                                "FROM genotype_locus gl "
                                "WHERE genotype_id = :genotype_id AND locus = :locus AND allele = :allele "
                                "ORDER BY timestamp DESC LIMIT 1"
                            )
                        ),
                        {"allele": allele, "genotype_id": genotype_id, "locus": locus},
                    )
                    .mappings()
                    .fetchone()
                )

                # if genotype_id == "BI-18" and locus == "SRY":
                #    print(f"{locus_val=}")
                #    print(f"{locus_val["val"] is None=}")

                if locus_val is None:
                    val: str = "-"
                    notes: str = ""
                    has_history: int = 0
                    validated: bool = False
                    user_id: str = ""
                    epoch: str = ""

                else:
                    val = locus_val["val"] if locus_val["val"] is not None else "-"
                    notes = locus_val["notes"] if locus_val["notes"] is not None else ""
                    has_history = locus_val["has_history"]
                    validated = locus_val["validated"] if locus_val["validated"] is not None else ""
                    user_id = locus_val["user_id"] if locus_val["user_id"] is not None else ""
                    epoch = locus_val["epoch"] if locus_val["epoch"] is not None else ""

                loci_values[locus][allele] = {
                    "value": val,
                    "notes": notes,
                    "has_history": has_history,
                    "validated": validated,
                    "user_id": user_id,
                    "epoch": epoch,
                }

    # if genotype_id == "BI-18":
    #    print(f"{loci_values=}")

    return loci_values


def alert_danger(text: str) -> str:
    """
    Danger message
    """
    return Markup(f'<div class="alert alert-danger" role="alert">{text}</div>')


def alert_success(text: str) -> str:
    """
    Success message
    """
    return Markup(f'<div class="alert alert-success" role="alert">{text}</div>')


def get_path_id(transect_id: str, date: str) -> str:
    """
    returns path_id
    date must be in ISO8601 format
    """
    return str(transect_id) + "|" + date[2:].replace("-", "")


def all_transect_id() -> list:
    """
    returns a list of all transect_id in the transects table
    """
    with conn_alchemy().connect() as con:
        return [
            x["transect_id"].strip() for x in con.execute(text("SELECT transect_id FROM transects ORDER BY transect_id")).mappings().all()
        ]


def all_path_id() -> list:
    """
    return all path ID (transect ID and date)
    """
    with conn_alchemy().connect() as con:
        return [
            x["transect_date"].strip()
            for x in con.execute(
                text(
                    "SELECT CONCAT(transect_id, ' ',  date) AS transect_date FROM paths WHERE transect_id != '' ORDER BY transect_id, date DESC"
                )
            )
            .mappings()
            .all()
        ]


def all_snow_tracks_id() -> list:
    """
    returns a list of all snowtrack_id in the snow_tracks table
    """
    with conn_alchemy().connect() as con:
        return [
            x["snowtrack_id"].strip()
            for x in con.execute(text("SELECT snowtrack_id FROM snow_tracks ORDER BY snowtrack_id")).mappings().all()
        ]


def sampling_season(date: str) -> str:
    """
    Extract sampling season from date in ISO 8601 format
    """
    try:
        month = int(date[5 : 6 + 1])
        year = int(date[0 : 3 + 1])
        if 5 <= month <= 12:
            return f"{year}-{year + 1}"
        elif 1 <= month <= 4:
            return f"{year - 1}-{year}"
        else:
            return f"Error {date}"
    except Exception:
        return f"Error {date}"


def province_code_list() -> list:
    """
    return list of upper case province code
    (using geo_info table)
    """
    with conn_alchemy().connect() as con:
        return [
            row["province_code"] for row in con.execute(text("SELECT UPPER(province_code) AS province_code FROM geo_info")).mappings().all()
        ]


def check_province_code(province_code) -> Union[None, str]:
    """
    check if province code exists.
    Returns province code or None if not found
    using geo_info table
    """
    with conn_alchemy().connect() as con:
        result = (
            con.execute(
                text("SELECT UPPER(province_code) AS province_code FROM geo_info WHERE UPPER(province_code) = :province_code"),
                {"province_code": province_code.upper()},
            )
            .mappings()
            .fetchone()
        )
    return result["province_code"] if result is not None else None


def prov_code2prov_name(province_code: str) -> str:
    """
    returns the province name for the province code provided (None if not found)
    """
    with conn_alchemy().connect() as con:
        result = (
            con.execute(
                text("SELECT province_name FROM geo_info WHERE UPPER(province_code) = :province_code"),
                {"province_code": province_code.upper().strip()},
            )
            .mappings()
            .fetchone()
        )

    return result["province_name"] if result else None


def province_code2region_dict() -> dict:
    with conn_alchemy().connect() as con:
        return dict(
            [
                (row["province_code"].upper(), row["region"])
                for row in con.execute(text("SELECT province_code, region FROM geo_info")).mappings().all()
            ]
        )


def province_code2region(province_code):
    """
    get region from province code
    """
    if province_code is None:
        return None

    with conn_alchemy().connect() as con:
        result = (
            con.execute(
                text("SELECT region FROM geo_info WHERE UPPER(province_code) = :province_code"),
                {"province_code": province_code.upper().strip()},
            )
            .mappings()
            .fetchone()
        )

    return result["region"] if result else None


def province_name_list() -> list:
    """
    return list of upper case province name
    (using geo_info table)
    """
    with conn_alchemy().connect() as con:
        return [row["province_name"].upper() for row in con.execute(text("SELECT province_name FROM geo_info")).mappings().all()]


def province_name2code(province_name: str) -> str:
    """
    returns province code from province name
    using geo_info table
    """
    with conn_alchemy().connect() as con:
        result = (
            con.execute(
                text("SELECT province_code FROM geo_info WHERE UPPER(province_name) = :province_name"),
                {"province_name": province_name.upper().strip()},
            )
            .mappings()
            .fetchone()
        )

    return result["province_code"] if result else None


def province_name2code_dict() -> dict:
    """
    returns dict of upper case province code for upper case province name
    (using geo_info table)
    """
    with conn_alchemy().connect() as con:
        return dict(
            [
                (row["province_name"], row["province_code"])
                for row in con.execute(
                    text("SELECT UPPER(province_name) as province_name, UPPER(province_code) as province_code FROM geo_info")
                )
                .mappings()
                .all()
            ]
        )


def province_name2region(province_name) -> str:
    """
    get region by province name
    """
    region_out: str = ""
    if province_name:
        for region in regions:
            if province_name.upper() in [x.upper() for x in region["capoluoghi"]]:
                region_out = region["nome"]
                break

    return region_out


def get_regions(provinces: list) -> str:
    """
    returns list of regions (as str) corresponding to the list of provinces
    """

    transect_region: list = []
    if provinces:
        for region in regions:
            for x in provinces.split(" "):
                if x.upper() in region["province"]:
                    transect_region.append(region["nome"])

    return " ".join(list(set(transect_region)))


def reverse_geocoding(lon_lat: list) -> dict:
    """
    get place from GPS coordinates with nominatum (OSM)
    """

    longitude, latitude = lon_lat

    URL = f"https://nominatim.openstreetmap.org/reverse.php?lat={latitude}&lon={longitude}&zoom=14&format=json&namedetails=1&accept-language=it"

    continents = {
        "Africa": [
            "Egypt",
            "Algeria",
            "Angola",
            "Benin",
            "Botswana",
            "Burkina Faso",
            "Burundi",
            "Cameroon",
            "Cameroun",
            "Cape Verde",
            "Central African Republic",
            "Chad",
            "Tchad",
            "Comoros",
            "Republic of the Congo",
            "Congo-Brazzaville",
            "Democratic Republic of the Congo",
            "Côte d'Ivoire",
            "Ivory Coast",
            "Djibouti",
            "Equatorial Guinea",
            "Eritrea",
            "Ethiopia",
            "Abyssinia",
            "Gabon",
            "The Gambia",
            "Ghana",
            "Guinea",
            "Guinea-Bissau",
            "Kenya",
            "Lesotho",
            "Liberia",
            "Libya",
            "Madagascar",
            "Malawi",
            "Mali",
            "Mauritania",
            "Mauritius",
            "Morocco",
            "Al Maghrib",
            "Mozambique",
            "Namibia",
            "Niger",
            "Nigeria",
            "Rwanda",
            "São Tomé and Príncipe",
            "Senegal",
            "Seychelles",
            "Sierra Leone",
            "Somalia",
            "South Africa",
            "South Sudan",
            "Swaziland",
            "Eswatini",
            "Tanzania",
            "Togo",
            "Tunisia",
            "Uganda",
            "Western Sahara",
            "Zambia",
            "Sudan",
            "Zimbabwe",
        ],
        "Oceania": [
            "Australia",
            "Fiji",
            "New Zealand",
            "Federated States of Micronesia",
            "Kiribati",
            "Marshall Islands",
            "Nauru",
            "Palau",
            "Papua New Guinea",
            "Samoa",
            "Solomon Islands",
            "Tonga",
            "Tuvalu",
            "Vanuatu",
        ],
        "South America": [
            "Brazil",
            "Brasil",
            "Argentina",
            "Bolivia",
            "Chile",
            "Colombia",
            "Ecuador",
            "Falkland Islands",
            "French Guiana",
            "Guyana",
            "Paraguay",
            "Peru",
            "South Georgia and the South Sandwich Islands",
            "Suriname",
            "Uruguay",
            "Venezuela",
        ],
        "North America": [
            "Canada",
            "United States of America",
            "Mexico",
            "Belize",
            "Antigua and Barbuda",
            "Anguilla",
            "Aruba",
            "The Bahamas",
            "Barbados",
            "Bermuda",
            "Bonaire",
            "British Virgin Islands",
            "Cayman Islands",
            "Clipperton Island",
            "Costa Rica",
            "Cuba",
            "Curaçao",
            "Dominica",
            "Dominican Republic",
            "Republica Dominicana",
            "El Salvador",
            "Greenland",
            "Grenada",
            "Guadeloupe",
            "Guatemala",
            "Haiti",
            "Honduras",
            "Jamaica",
            "Martinique",
            "Montserrat",
            "Navassa Island",
            "Nicaragua",
            "Panama",
            "Panamá",
            "Puerto Rico",
            "Saba",
            "Saint Barthelemy",
            "Saint Kitts and Nevis",
            "Saint Lucia",
            "Saint Martin",
            "Saint Pierre and Miquelon",
            "Saint Vincent and the Grenadines",
            "Sint Eustatius",
            "Sint Maarten",
            "Trinidad and Tobago",
            "Turks and Caicos",
            "US Virgin Islands",
        ],
        "Europe": [
            "Albania",
            "Shqipëria",
            "Andorra",
            "Austria",
            "Österreich",
            "Belarus",
            "Беларусь",
            "Belgium",
            "Bosnia and Herzegovina",
            "Bulgaria",
            "България",
            "Croatia",
            "Hrvatska",
            "Cyprus",
            "Κύπρος",
            "Czech Republic",
            "Česko",
            "Denmark",
            "Danmark",
            "Estonia",
            "Finland",
            "Suomi",
            "Georgia",
            "Germany",
            "Greece",
            "Hungary",
            "Iceland",
            "Ireland",
            "Republic of Ireland",
            "Italy",
            "Kazakhstan",
            "Kosovo",
            "Latvia",
            "Liechtenstein",
            "Lithuania",
            "Luxembourg",
            "North Macedonia",
            "Malta",
            "Moldova",
            "Monaco",
            "Montenegro",
            "Netherlands",
            "Norway",
            "Poland",
            "Portugal",
            "Romania",
            "Russia",
            "San Marino",
            "Serbia",
            "Slovakia",
            "Slovenia",
            "France",
            "Spain",
            "Sweden",
            "Switzerland",
            "Turkey",
            "Ukraine",
            "United Kingdom",
            "Vatican City",
        ],
        "Asia": [
            "Afghanistan",
            "Armenia",
            "Azerbaijan",
            "Bahrain",
            "Bangladesh",
            "Bhutan",
            "Brunei",
            "Cambodia",
            "Kampuchea",
            "China",
            "East Timor",
            "Georgia",
            "India",
            "Indonesia",
            "Iran",
            "Iraq",
            "Israel",
            "Japan",
            "Jordan",
            "Al Urdun",
            "Kazakhstan",
            "Kuwait",
            "Kyrgyzstan",
            "Laos",
            "Lebanon",
            "Malaysia",
            "Maldives",
            "Mongolia",
            "Myanmar",
            "Nepal",
            "North Korea",
            "Oman",
            "Pakistan",
            "Philippines",
            "Qatar",
            "Russia",
            "Saudi Arabia",
            "Singapore",
            "South Korea",
            "Sri Lanka",
            "Syria",
            "Tajikistan",
            "Thailand",
            "Turkey",
            "Turkmenistan",
            "Taiwan",
            "United Arab Emirates",
            "Uzbekistan",
            "Vietnam",
            "Yemen",
        ],
    }

    response = urllib.request.urlopen(URL).read().strip().decode("utf-8")

    d = json.loads(response)

    if "address" not in d:
        return None

    location, municipality, province, province_code, region = "", "", "", "", ""

    country = d["address"].get("country", "")

    for kw in ["state"]:
        region = d["address"].get(kw, "")
        if region:
            break

    for kw in ["county"]:
        province = d["address"].get(kw, "")
        province_code = prov_name2prov_code(province)

    if province == "":
        for kw in ["province"]:
            province = d["address"].get(kw, "")
            province_code = prov_name2prov_code(province)

    for kw in ["town", "city", "village", "municipality"]:
        municipality = d["address"].get(kw, "")
        if municipality:
            break

    for kw in ["hamlet", "croft", "isolated_dwelling", "suburb"]:
        if d["address"].get(kw, ""):
            if location:
                location += "; " + d["address"].get(kw, "")
            else:
                location = d["address"].get(kw, "")

    geocoded_continent: str = ""
    if country:
        for continent in continents:
            if country.lower() in [x.lower() for x in continents[continent]]:
                geocoded_continent = continent
                break

    # exception (AO provincia soppressa)
    if not province:
        if region == "Valle d'Aosta":
            province = "Valle d'Aosta"
            province_code = "AO"

    if province == "Provincia di Trento":
        province_code = "TN"
        province = "Trento"

    if province == "La Spezia":
        province_code = "SP"

    if province == "Verbano-Cusio-Ossola":
        province_code = "VB"

    if province_code == "" and country == "Francia":
        province = d["address"].get("county", "")
        # extract 2 first digits from postcode
        province_code = d["address"].get("postcode", "  ")[:2].strip()

    if province == "Distretto di Locarno":
        province_code = "CH-TI"

    return {
        "continent": geocoded_continent,
        "country": country,
        "region": region,
        "province": province,
        "province_code": province_code,
        "municipality": municipality,
        "location": location,
    }


def leaflet_geojson(data: dict, add_polygon: bool = False, samples: str = "genotypes") -> str:
    """
    plot geoJSON features on Leaflet map

    Args:
        add_polygon (bool): True for adding tools for drawing polygon
        samples (str): 'genotypes' show info about genotypes contained in polygon
                       'wa' show info about wa contained in polygon
    """

    SCATS_COLOR_DEFAULT = params["scat_color"]
    TRANSECTS_COLOR_DEFAULT = params["transect_color"]
    TRACKS_COLOR_DEFAULT = params["track_color"]
    DEAD_WOLVES_COLOR_DEFAULT = params["dead_wolf_color"]
    CENTER_DEFAULT = "45, 7"

    map = Template(
        """
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
     integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
     crossorigin=""/>
 

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
     integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
     crossorigin="">
</script>

{% if add_polygon %}
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.4/leaflet.draw.css" />
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.4/leaflet.draw.js"></script>
{% endif %}

<script>
var transects = {
    "type": "FeatureCollection",
    "features": {{ transects}}
};

var tracks = {
    "type": "FeatureCollection",
    "features": {{ tracks}}
};

var scats = {
    "type": "FeatureCollection",
    "features": {{ scats }}
};

var dead_wolves = {
    "type": "FeatureCollection",
    "features": {{ dead_wolves }}
};

var Esri_WorldImagery = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
	attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community'
});

var Stadia_AlidadeSatellite = L.tileLayer('https://tiles.stadiamaps.com/tiles/alidade_satellite/{z}/{x}/{y}{r}.{ext}', {
	minZoom: 0,
	maxZoom: 20,
	attribution: '&copy; CNES, Distribution Airbus DS, © Airbus DS, © PlanetObserver (Contains Copernicus Data) | &copy; <a href="https://www.stadiamaps.com/" target="_blank">Stadia Maps</a> &copy; <a href="https://openmaptiles.org/" target="_blank">OpenMapTiles</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
	ext: 'jpg'
});

var osm = L.tileLayer('http://{s}.tile.osm.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="http://osm.org/copyright">OpenStreetMap</a> contributors'})

var opentopomap = L.tileLayer('https://a.tile.opentopomap.org/{z}/{x}/{y}.png', {
	attribution: 'Map data: &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, <a href="http://viewfinderpanoramas.org">SRTM</a> | Map style: &copy; <a href="https://opentopomap.org">OpenTopoMap</a> (<a href="https://creativecommons.org/licenses/by-sa/3.0/">CC-BY-SA</a>)'
})

var map = L.map('map', {center: [{{ center }}], zoom: {{ zoom }}, layers: [Esri_WorldImagery, Stadia_AlidadeSatellite, osm, opentopomap]});

var baseMaps = {
    "ESRI World Imagery": Esri_WorldImagery,
    "Stadia map": Stadia_AlidadeSatellite,
    "OpenStreetMap": osm,
    "OpenTopoMap": opentopomap,
};

var layerControl = L.control.layers(baseMaps).addTo(map);

function onEachFeature(feature, layer) {
    var popupContent = "";
    if (feature.properties && feature.properties.popupContent) {
        popupContent += feature.properties.popupContent;
    }
    layer.bindPopup(popupContent);
}

L.geoJSON([dead_wolves], {

    style: function (feature) { return feature.properties && feature.properties.style; },

    onEachFeature: onEachFeature,

    pointToLayer: function (feature, latlng) {
        return L.circleMarker(latlng, {
            color: '{{ dead_wolves_color }}',
            fillcolor: '{{ dead_wolves_color }}',
            radius: 8,
            weight: 1,
            opacity: 1,
            fillOpacity: 1
        });
    }
}).addTo(map);



L.geoJSON(transects, {
    style: function(feature) { return { color: '{{ transects_color }}' } },
    onEachFeature: onEachFeature,
}).addTo(map);


L.geoJSON(tracks, {
    style: function(feature) { return { color: '{{ tracks_color }}' } },
    onEachFeature: onEachFeature,
}).addTo(map);


L.geoJSON([scats], {
    style: function (feature) { return feature.properties && feature.properties.style; },
    onEachFeature: onEachFeature,
    pointToLayer: function (feature, latlng) {
        return L.circleMarker(latlng, {
            color: '{{ scats_color }}',
            fillcolor: '{{ scats_color }}',
            radius: 8,
            weight: 1,
            opacity: 1,
            fillOpacity: 1,
        });
    }
}).addTo(map);


 // Creating scale control
var scale = L.control.scale();
scale.addTo(map);

var markerBounds = L.latLngBounds([{{ fit }}]);
map.fitBounds(markerBounds);


{% if add_polygon %}
// Initialise draw tools
var drawnItems = new L.FeatureGroup();
map.addLayer(drawnItems);

var drawControl = new L.Control.Draw({
    edit: {
        featureGroup: drawnItems
    },
    draw: {
        polygon: true,  
        polyline: false, 
        rectangle: false, 
        circle: false,    
        marker: false,     
        circlemarker: false, 
        edit: false,

    }
});
map.addControl(drawControl);

// event triggered when user finish a draw
map.on('draw:created', function (event) {
    var layer = event.layer;
    drawnItems.addLayer(layer);

    var coords = layer.getLatLngs()[0].map(function(latlng) {
        return [latlng.lng, latlng.lat];
    });

    // send coordinates via POST AJAX

{% if samples == 'genotypes' %}
    fetch('/select_on_map/genotypes',
{% endif %}     
{% if samples == 'wa' %}
    fetch('/select_on_map/wa',
{% endif %}     

         {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ coordinates: coords })
    })
    .then(response => response.json())
    .then(data => {
        if (data['status'] == 'error')
            {
            alert(data['message']);
            console.log('server Response:', data);
            drawnItems.clearLayers();
            }
        else
            {
{% if samples == 'genotypes' %}
            window.location.href = "/wa_analysis_group/" + data['message'] + "/web";
{% endif %}
{% if samples == 'wa' %}
            window.location.href = "/view_wa_polygon/" + data['message'] + "/web";
{% endif %}

            };
        

    })
    .catch(error => {
        console.error('Error:', error);
    });
});
{% endif %}

</script>
"""
    )

    return map.render(
        {
            "transects": data.get("transects", []),
            "transects_color": data.get("transects_color", TRANSECTS_COLOR_DEFAULT),
            "tracks": data.get("tracks", []),
            "tracks_color": data.get("tracks_color", TRACKS_COLOR_DEFAULT),
            "scats": data.get("scats", []),
            "scats_color": data.get("scats_color", SCATS_COLOR_DEFAULT),
            "dead_wolves": data.get("dead_wolves", []),
            "dead_wolves_color": data.get("dead_wolves_color", DEAD_WOLVES_COLOR_DEFAULT),
            "center": data.get("center", CENTER_DEFAULT),
            "zoom": data.get("zoom", 13),
            "fit": data.get("fit", ""),
            "add_polygon": add_polygon,
            "samples": samples,
        }
    )


def leaflet_geojson_label(data: dict, add_polygon: bool = False, samples: str = "genotypes") -> str:
    """
    plot geoJSON features on Leaflet map

    Args:
        add_polygon (bool): True for adding tools for drawing polygon
        samples (str): 'genotypes' show info about genotypes contained in polygon
                       'wa' show info about wa contained in polygon
    """

    SCATS_COLOR_DEFAULT = params["scat_color"]
    TRANSECTS_COLOR_DEFAULT = params["transect_color"]
    TRACKS_COLOR_DEFAULT = params["track_color"]
    DEAD_WOLVES_COLOR_DEFAULT = params["dead_wolf_color"]
    CENTER_DEFAULT = "45, 7"

    map = Template(
        """
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
     integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
     crossorigin=""/>
 

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
     integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
     crossorigin="">
</script>

{% if add_polygon %}
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.4/leaflet.draw.css" />
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.4/leaflet.draw.js"></script>
{% endif %}

<script>
var transects = {
    "type": "FeatureCollection",
    "features": {{ transects}}
};

var tracks = {
    "type": "FeatureCollection",
    "features": {{ tracks}}
};

var scats = {
    "type": "FeatureCollection",
    "features": {{ scats }}
};

var scat_markers = {{ scat_markers }};

var dead_wolves = {
    "type": "FeatureCollection",
    "features": {{ dead_wolves }}
};

var Esri_WorldImagery = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
	attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community'
});

var Stadia_AlidadeSatellite = L.tileLayer('https://tiles.stadiamaps.com/tiles/alidade_satellite/{z}/{x}/{y}{r}.{ext}', {
	minZoom: 0,
	maxZoom: 20,
	attribution: '&copy; CNES, Distribution Airbus DS, © Airbus DS, © PlanetObserver (Contains Copernicus Data) | &copy; <a href="https://www.stadiamaps.com/" target="_blank">Stadia Maps</a> &copy; <a href="https://openmaptiles.org/" target="_blank">OpenMapTiles</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
	ext: 'jpg'
});

var osm = L.tileLayer('http://{s}.tile.osm.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="http://osm.org/copyright">OpenStreetMap</a> contributors'})

var opentopomap = L.tileLayer('https://a.tile.opentopomap.org/{z}/{x}/{y}.png', {
	attribution: 'Map data: &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, <a href="http://viewfinderpanoramas.org">SRTM</a> | Map style: &copy; <a href="https://opentopomap.org">OpenTopoMap</a> (<a href="https://creativecommons.org/licenses/by-sa/3.0/">CC-BY-SA</a>)'
})

var map = L.map('map', {center: [{{ center }}], zoom: {{ zoom }}, layers: [Esri_WorldImagery, Stadia_AlidadeSatellite, osm, opentopomap]});

var baseMaps = {
    "ESRI World Imagery": Esri_WorldImagery,
    "Stadia map": Stadia_AlidadeSatellite,
    "OpenStreetMap": osm,
    "OpenTopoMap": opentopomap,
};

var layerControl = L.control.layers(baseMaps).addTo(map);

function onEachFeature(feature, layer) {
    var popupContent = "";
    if (feature.properties && feature.properties.popupContent) {
        popupContent += feature.properties.popupContent;
    }
    layer.bindPopup(popupContent);
}

L.geoJSON([dead_wolves], {

    style: function (feature) { return feature.properties && feature.properties.style; },

    onEachFeature: onEachFeature,

    pointToLayer: function (feature, latlng) {
        return L.circleMarker(latlng, {
            color: '{{ dead_wolves_color }}',
            fillcolor: '{{ dead_wolves_color }}',
            radius: 8,
            weight: 1,
            opacity: 1,
            fillOpacity: 1
        });
    }
}).addTo(map);



L.geoJSON(transects, {
    style: function(feature) { return { color: '{{ transects_color }}' } },
    onEachFeature: onEachFeature,
}).addTo(map);


L.geoJSON(tracks, {
    style: function(feature) { return { color: '{{ tracks_color }}' } },
    onEachFeature: onEachFeature,
}).addTo(map);

var markerLayers = [];
// Ajouter les markers à la carte
scat_markers.forEach(function(data) {
    var marker = L.circleMarker(data.coords, {
        color: '#ff00ff',
        fillColor: '#ff00ff',
        fillOpacity: 1,
        weight: 1,
        opacity: 1,
        radius: 8 
    }).addTo(map);

    if (data.label) {
    var tooltip = L.tooltip({
        permanent: true,
        direction: "top",
        opacity: 1
    }).setContent(data.label);
    marker.bindTooltip(tooltip);
}
    var popup = L.popup().setContent(data.popup);
    marker.bindPopup(popup);

    markerLayers.push({ marker: marker, tooltip: tooltip });

});



 // Creating scale control
var scale = L.control.scale();
scale.addTo(map);

var markerBounds = L.latLngBounds([{{ fit }}]);
map.fitBounds(markerBounds);

var zoomThreshold = 12;
// Fonction pour afficher/masquer les étiquettes selon le niveau de zoom
function updateTooltipVisibility() {
    var currentZoom = map.getZoom();
    markerLayers.forEach(function(layer) {
        if (currentZoom >= zoomThreshold) {
            layer.marker.openTooltip(); // Affiche l'étiquette
        } else {
            layer.marker.closeTooltip(); // Cache l'étiquette
        }
    });
}

// Vérifier l'affichage des étiquettes au chargement
updateTooltipVisibility();

// Écouter l'événement de zoom pour mettre à jour l'affichage
map.on('zoomend', updateTooltipVisibility);



{% if add_polygon %}
// Initialise draw tools
var drawnItems = new L.FeatureGroup();
map.addLayer(drawnItems);

var drawControl = new L.Control.Draw({
    edit: {
        featureGroup: drawnItems
    },
    draw: {
        polygon: true,  
        polyline: false, 
        rectangle: false, 
        circle: false,    
        marker: false,     
        circlemarker: false, 
        edit: false,

    }
});
map.addControl(drawControl);

// event triggered when user finish a draw
map.on('draw:created', function (event) {
    var layer = event.layer;
    drawnItems.addLayer(layer);

    var coords = layer.getLatLngs()[0].map(function(latlng) {
        return [latlng.lng, latlng.lat];
    });

    // send coordinates via POST AJAX

{% if samples == 'genotypes' %}
    fetch('/select_on_map/genotypes',
{% endif %}     
{% if samples == 'wa' %}
    fetch('/select_on_map/wa',
{% endif %}     

         {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ coordinates: coords })
    })
    .then(response => response.json())
    .then(data => {
        if (data['status'] == 'error')
            {
            alert(data['message']);
            console.log('server Response:', data);
            drawnItems.clearLayers();
            }
        else
            {
{% if samples == 'genotypes' %}
            window.location.href = "/wa_analysis_group/" + data['message'] + "/web";
{% endif %}
{% if samples == 'wa' %}
            window.location.href = "/view_wa_polygon/" + data['message'] + "/web";
{% endif %}

            };
        

    })
    .catch(error => {
        console.error('Error:', error);
    });
});
{% endif %}

</script>
"""
    )

    return map.render(
        {
            "transects": data.get("transects", []),
            "transects_color": data.get("transects_color", TRANSECTS_COLOR_DEFAULT),
            "tracks": data.get("tracks", []),
            "tracks_color": data.get("tracks_color", TRACKS_COLOR_DEFAULT),
            "scats": data.get("scats", []),
            "scat_markers": data.get("scat_markers", ""),
            "scats_color": data.get("scats_color", SCATS_COLOR_DEFAULT),
            "dead_wolves": data.get("dead_wolves", []),
            "dead_wolves_color": data.get("dead_wolves_color", DEAD_WOLVES_COLOR_DEFAULT),
            "center": data.get("center", CENTER_DEFAULT),
            "zoom": data.get("zoom", 13),
            "fit": data.get("fit", ""),
            "add_polygon": add_polygon,
            "samples": samples,
        }
    )


def leaflet_markercluster_geojson(data: dict) -> str:
    """
    plot geoJSON features  on Leaflet map using MarkerCluster
    """

    SCATS_COLOR_DEFAULT = params["scat_color"]
    TRANSECTS_COLOR_DEFAULT = params["transect_color"]
    TRACKS_COLOR_DEFAULT = params["track_color"]
    DEAD_WOLVES_COLOR_DEFAULT = params["dead_wolf_color"]
    CENTER_DEFAULT = "45, 7"

    map = Template(
        """
 <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
     integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
     crossorigin=""/>
 
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
     integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
     crossorigin=""></script>


<link rel="stylesheet" href="/static/MarkerCluster.Default.css">
<script src="/static/leaflet.markercluster.js"></script>

<script>

var transects = {
    "type": "FeatureCollection",
    "features": {{ transects}}
};

var tracks = {
    "type": "FeatureCollection",
    "features": {{ tracks}}
};

var scats = {
    "type": "FeatureCollection",
    "features": {{ scats }}
};

var dead_wolves = {
    "type": "FeatureCollection",
    "features": {{ dead_wolves }}
};

var Esri_WorldImagery = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
	attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community'
});

var Stadia_AlidadeSatellite = L.tileLayer('https://tiles.stadiamaps.com/tiles/alidade_satellite/{z}/{x}/{y}{r}.{ext}', {
	minZoom: 0,
	maxZoom: 20,
	attribution: '&copy; CNES, Distribution Airbus DS, © Airbus DS, © PlanetObserver (Contains Copernicus Data) | &copy; <a href="https://www.stadiamaps.com/" target="_blank">Stadia Maps</a> &copy; <a href="https://openmaptiles.org/" target="_blank">OpenMapTiles</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
	ext: 'jpg'
});


var osm = L.tileLayer('http://{s}.tile.osm.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="http://osm.org/copyright">OpenStreetMap</a> contributors'})

var opentopomap = L.tileLayer('https://a.tile.opentopomap.org/{z}/{x}/{y}.png', {
	attribution: 'Map data: &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, <a href="http://viewfinderpanoramas.org">SRTM</a> | Map style: &copy; <a href="https://opentopomap.org">OpenTopoMap</a> (<a href="https://creativecommons.org/licenses/by-sa/3.0/">CC-BY-SA</a>)'
})

var map = L.map('map', {center: [{{ center }}], zoom: {{ zoom }}, layers: [Esri_WorldImagery, Stadia_AlidadeSatellite, osm, opentopomap]});

var baseMaps = {
    "ESRI World Imagery": Esri_WorldImagery,
    "Stadia map": Stadia_AlidadeSatellite,
    "OpenStreetMap": osm,
    "OpenTopoMap": opentopomap,
};

var layerControl = L.control.layers(baseMaps).addTo(map);


function onEachFeature(feature, layer) {
    var popupContent = "";
    if (feature.properties && feature.properties.popupContent) {
        popupContent += feature.properties.popupContent;
    }
    layer.bindPopup(popupContent);
}


var scat_markers = L.geoJson(scats,
                       {onEachFeature: onEachFeature,
                        pointToLayer: function(feature, latlng)
                                          {
                                          return L.circleMarker(latlng, {
                                                            color: '{{ scats_color }}',
                                                            fillcolor: '{{ scats_color }}',
                                                            radius: 8,
                                                            weight: 1,
                                                            opacity: 1,
                                                            fillOpacity: 1
                                                  });
                                          }
                        }
                      );

var scats_clusters = L.markerClusterGroup();
scats_clusters.addLayer(scat_markers);
map.addLayer(scats_clusters);


L.geoJSON([dead_wolves], {

    style: function (feature) { return feature.properties && feature.properties.style; },

    onEachFeature: onEachFeature,

    pointToLayer: function (feature, latlng) {
        return L.circleMarker(latlng, {
            color: '{{ dead_wolves_color }}',
            fillcolor: '{{ dead_wolves_color }}',
            radius: 8,
            weight: 1,
            opacity: 1,
            fillOpacity: 1
        });
    }
}).addTo(map);





L.geoJSON(transects, {

    style: function(feature) { return { color: '{{ transects_color }}' } },

    onEachFeature: onEachFeature,

}).addTo(map);


L.geoJSON(tracks, {

    style: function(feature) { return { color: '{{ tracks_color }}' } },

    onEachFeature: onEachFeature,

}).addTo(map);


 // Creating scale control
var scale = L.control.scale();
scale.addTo(map);

var markerBounds = L.latLngBounds([{{ fit }}]);
map.fitBounds(markerBounds);

</script>
"""
    )

    return map.render(
        {
            "transects": data.get("transects", []),
            "transects_color": data.get("transects_color", TRANSECTS_COLOR_DEFAULT),
            "tracks": data.get("tracks", []),
            "tracks_color": data.get("tracks_color", TRACKS_COLOR_DEFAULT),
            "scats": data.get("scats", []),
            "scats_color": data.get("scats_color", SCATS_COLOR_DEFAULT),
            "dead_wolves": data.get("dead_wolves", []),
            "dead_wolves_color": data.get("dead_wolves_color", DEAD_WOLVES_COLOR_DEFAULT),
            "center": data.get("center", CENTER_DEFAULT),
            "zoom": data.get("zoom", 13),
            "fit": data.get("fit", ""),
        }
    )
