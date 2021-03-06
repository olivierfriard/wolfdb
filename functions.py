"""
WolfDB web service
(c) Olivier Friard

functions module

"""

from functools import wraps
from flask import Flask, request, Markup, redirect, session
import psycopg2
import psycopg2.extras
from config import config
import urllib.request
import json

from jinja2 import Template

from italian_regions import regions, prov_name2prov_code

params = config()


def check_login(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect("/login")
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


def get_wa_loci_values(wa_code: str, loci_list: list) -> dict:

    connection = get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    has_loci_notes = False

    loci_values = {}
    for locus in loci_list:
        loci_values[locus] = {}
        loci_values[locus]["a"] = {"value": "-", "notes": "", "user_id": ""}
        loci_values[locus]["b"] = {"value": "-", "notes": "", "user_id": ""}

    for locus in loci_list:

        for allele in ["a", "b"][: loci_list[locus]]:

            cursor.execute(
                (
                    "SELECT val, notes, extract(epoch from timestamp)::integer AS epoch, user_id, "
                    "to_char(timestamp, 'YYYY-MM-DD HH24:MI:SS') AS formatted_timestamp "
                    "FROM wa_locus "
                    "WHERE wa_code = %(wa_code)s AND locus = %(locus)s AND allele = %(allele)s "
                    "ORDER BY timestamp DESC LIMIT 1"
                ),
                {"wa_code": wa_code, "locus": locus, "allele": allele},
            )

            row2 = cursor.fetchone()

            if row2 is not None:
                val = row2["val"] if row2["val"] is not None else "-"
                notes = row2["notes"] if row2["notes"] is not None else ""
                user_id = row2["user_id"] if row2["user_id"] is not None else ""
                if notes:
                    has_loci_notes = True
                epoch = row2["epoch"] if row2["epoch"] is not None else ""
                date = row2["formatted_timestamp"] if row2["formatted_timestamp"] is not None else ""

            else:
                val = "-"
                notes = ""
                epoch = ""
                user_id = ""
                date = ""

            loci_values[locus][allele] = {
                "value": val,
                "notes": notes,
                "epoch": epoch,
                "user_id": user_id,
                "date": date,
            }

    return loci_values, has_loci_notes


def get_loci_value(genotype_id: str, loci_list: list) -> dict:
    """
    get genotype loci values
    """

    connection = get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    loci_values = {}
    for locus in loci_list:
        loci_values[locus] = {}
        loci_values[locus]["a"] = {"value": "-", "notes": "", "user_id": ""}
        loci_values[locus]["b"] = {"value": "-", "notes": "", "user_id": ""}

    for locus in loci_list:

        """
        cursor.execute(
            (
                "SELECT val, allele, notes, user_id, extract(epoch from timestamp)::integer AS epoch "
                "FROM genotype_locus "
                "WHERE genotype_id = %(genotype_id)s AND locus = %(locus)s AND allele = 'a' "
                "UNION "
                "SELECT val, allele, notes, user_id, extract(epoch from timestamp)::integer AS epoch "
                "FROM genotype_locus "
                "WHERE genotype_id = %(genotype_id)s AND locus = %(locus)s AND allele = 'b' "
            ),
            {"genotype_id": genotype_id, "locus": locus},
        )
        """
        for allele in ["a", "b"]:
            cursor.execute(
                (
                    "SELECT val, notes, user_id, extract(epoch from timestamp)::integer AS epoch "
                    "FROM genotype_locus "
                    "WHERE genotype_id = %(genotype_id)s AND locus = %(locus)s AND allele = %(allele)s "
                    "ORDER BY timestamp DESC LIMIT 1"
                ),
                {"allele": allele, "genotype_id": genotype_id, "locus": locus},
            )

            locus_val = cursor.fetchone()
            if locus_val is None:
                val = "-"
                notes = ""
                user_id = ""
                epoch = ""
            else:
                val = locus_val["val"] if locus_val["val"] is not None else "-"
                notes = locus_val["notes"] if locus_val["notes"] is not None else ""
                user_id = locus_val["user_id"] if locus_val["user_id"] is not None else ""
                epoch = locus_val["epoch"] if locus_val["epoch"] is not None else ""

            loci_values[locus][allele] = {"value": val, "notes": notes, "user_id": user_id, "epoch": epoch}

    return loci_values


def alert_danger(text: str) -> str:
    return Markup(f'<div class="alert alert-danger" role="alert">{text}</div>')


def alert_success(text: str) -> str:
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
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT transect_id FROM transects ORDER BY transect_id")
    return [x[0].strip() for x in cursor.fetchall()]


def all_path_id() -> list:
    """
    return all path ID (transect ID and date)
    """
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute(
        (
            "SELECT CONCAT(transect_id, ' ',  date) "
            "FROM paths "
            "WHERE transect_id != '' "
            "ORDER BY transect_id, date DESC"
        )
    )
    return [x[0].strip() for x in cursor.fetchall()]


def all_snow_tracks_id() -> list:
    """
    returns a list of all snowtrack_id in the snow_tracks table
    """
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute("SELECT snowtrack_id FROM snow_tracks ORDER BY snowtrack_id")
    return [x[0].strip() for x in cursor.fetchall()]


def sampling_season(date: str) -> str:
    """
    Extract sampling season from date in ISO 8601 format
    """
    try:
        month = int(date[5 : 6 + 1])
        year = int(date[0 : 3 + 1])
        if 5 <= month <= 12:
            return f"{year}-{year + 1}"
        if 1 <= month <= 4:
            return f"{year - 1}-{year}"
    except Exception:
        return f"Error {date}"


def check_province_code(province_code):
    """
    check if province code exists
    using geo_info table
    """
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute(
        "SELECT UPPER(province_code) AS province_code FROM geo_info WHERE UPPER(province_code) = %s",
        [province_code.upper()],
    )
    result = cursor.fetchone()
    if result is None:
        return None
    else:
        return result["province_code"]


def province_name2code(province_name):
    """
    returns province code from province name
    using geo_info table
    """
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute(
        "SELECT province_code FROM geo_info WHERE UPPER(province_name) = %s", [province_name.upper().strip()]
    )
    result = cursor.fetchone()
    if result is None:
        return None
    else:
        return result["province_code"]

    """
    for code in province_codes:
        if province_name.upper() == province_codes[code]["nome"].upper():
            return code
    return ""
    """


def province_code2region(province_code):
    """
    get region from province code
    """
    if province_code is None:
        return None

    connection = get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute("SELECT region FROM geo_info WHERE UPPER(province_code) = %s", [province_code.upper().strip()])
    result = cursor.fetchone()
    if result is None:
        return None
    else:
        return result["region"]

    region_out = ""
    if province_code:
        for region in regions:
            if province_code.upper() in region["province"]:
                region_out = region["nome"]
                break

    return region_out


def province_name2region(province_name):
    """
    get region by province name
    """
    region_out = ""
    if province_name:
        for region in regions:
            if province_name.upper() in [x.upper() for x in region["capoluoghi"]]:
                region_out = region["nome"]
                break

    return region_out


def get_regions(provinces):

    transect_region = []
    if provinces:
        for region in regions:
            for x in provinces.split(" "):
                if x.upper() in region["province"]:
                    transect_region.append(region["nome"])

    return " ".join(list(set(transect_region)))


def leaflet_geojson(center, scat_features, transect_features, fit="", zoom=13) -> str:

    map = (
        """

 <link rel="stylesheet" href="https://unpkg.com/leaflet@1.7.1/dist/leaflet.css"
   integrity="sha512-xodZBNTC5n17Xt2atTPuE1HxjVMSvLVW9ocqUKLsCC5CXdbqCmblAshOMAS6/keqq/sMZMZ19scR4PsZChSR7A=="
   crossorigin=""/>

<script src="https://unpkg.com/leaflet@1.7.1/dist/leaflet.js"
   integrity="sha512-XQoYMqMTK8LvdxXYG3nZ448hOEQiglfqkJs1NOQV44cWnUrBc8PkAOcXy20w0vlaXaVUearIOBhiXZ5V3ynxwA=="
   crossorigin=""></script>

<script>

var transects = {
    "type": "FeatureCollection",
    "features": ###TRANSECT_FEATURES###
};


var scats = {
    "type": "FeatureCollection",
    "features": ###SCAT_FEATURES###
};


var map = L.map('map').setView([###CENTER###], ###ZOOM###);

/*
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
}).addTo(map);
*/


L.tileLayer('https://a.tile.opentopomap.org/{z}/{x}/{y}.png', {
	attribution: 'Map data: &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, <a href="http://viewfinderpanoramas.org">SRTM</a> | Map style: &copy; <a href="https://opentopomap.org">OpenTopoMap</a> (<a href="https://creativecommons.org/licenses/by-sa/3.0/">CC-BY-SA</a>)'
}).addTo(map);


function onEachFeature(feature, layer) {
    var popupContent = "";

    if (feature.properties && feature.properties.popupContent) {
        popupContent += feature.properties.popupContent;
    }

    layer.bindPopup(popupContent);
}

L.geoJSON([scats], {

    style: function (feature) {
        return feature.properties && feature.properties.style;
    },

    onEachFeature: onEachFeature,

    pointToLayer: function (feature, latlng) {
        return L.circleMarker(latlng, {
            radius: 8,
            weight: 1,
            opacity: 1,
            fillOpacity: 0.8
        });
    }
}).addTo(map);


L.geoJSON(transects, {
    onEachFeature: onEachFeature,
    style: function(){
    return { color: 'red' }
  }

}).addTo(map);


var scale = L.control.scale(); // Creating scale control
         scale.addTo(map); // Adding scale control to the map


var markerBounds = L.latLngBounds([###FIT###]);
map.fitBounds(markerBounds);

</script>

    """.replace(
            "###SCAT_FEATURES###", str(scat_features)
        )
        .replace("###CENTER###", center)
        .replace("###TRANSECT_FEATURES###", str(transect_features))
        .replace("###ZOOM###", str(zoom))
        .replace("###FIT###", fit)
    )

    return map


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
            "C??te d'Ivoire",
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
            "S??o Tom?? and Pr??ncipe",
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
            "Cura??ao",
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
            "Panam??",
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
            "Shqip??ria",
            "Andorra",
            "Austria",
            "??sterreich",
            "Belarus",
            "????????????????",
            "Belgium",
            "Bosnia and Herzegovina",
            "Bulgaria",
            "????????????????",
            "Croatia",
            "Hrvatska",
            "Cyprus",
            "????????????",
            "Czech Republic",
            "??esko",
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


def leaflet_geojson2(data: dict) -> str:
    """
    plot geoJSON features on Leaflet map
    """

    SCATS_COLOR_DEFAULT = params["scat_color"]
    TRANSECTS_COLOR_DEFAULT = params["transect_color"]
    TRACKS_COLOR_DEFAULT = params["track_color"]
    DEAD_WOLVES_COLOR_DEFAULT = params["dead_wolf_color"]
    CENTER_DEFAULT = "45, 7"

    map = Template(
        """

 <link rel="stylesheet" href="https://unpkg.com/leaflet@1.7.1/dist/leaflet.css"
   integrity="sha512-xodZBNTC5n17Xt2atTPuE1HxjVMSvLVW9ocqUKLsCC5CXdbqCmblAshOMAS6/keqq/sMZMZ19scR4PsZChSR7A=="
   crossorigin=""/>

<script src="https://unpkg.com/leaflet@1.7.1/dist/leaflet.js"
   integrity="sha512-XQoYMqMTK8LvdxXYG3nZ448hOEQiglfqkJs1NOQV44cWnUrBc8PkAOcXy20w0vlaXaVUearIOBhiXZ5V3ynxwA=="
   crossorigin=""></script>

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

var map = L.map('map').setView([{{ center }}], {{ zoom }});

/*
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
}).addTo(map);
*/


L.tileLayer('https://a.tile.opentopomap.org/{z}/{x}/{y}.png', {
	attribution: 'Map data: &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, <a href="http://viewfinderpanoramas.org">SRTM</a> | Map style: &copy; <a href="https://opentopomap.org">OpenTopoMap</a> (<a href="https://creativecommons.org/licenses/by-sa/3.0/">CC-BY-SA</a>)'
}).addTo(map);


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
            fillOpacity: 1
        });
    }
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


def leaflet_geojson3(data: dict) -> str:
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
 <link rel="stylesheet" href="https://unpkg.com/leaflet@1.7.1/dist/leaflet.css"
   integrity="sha512-xodZBNTC5n17Xt2atTPuE1HxjVMSvLVW9ocqUKLsCC5CXdbqCmblAshOMAS6/keqq/sMZMZ19scR4PsZChSR7A=="
   crossorigin="">

<script src="https://unpkg.com/leaflet@1.7.1/dist/leaflet.js"
   integrity="sha512-XQoYMqMTK8LvdxXYG3nZ448hOEQiglfqkJs1NOQV44cWnUrBc8PkAOcXy20w0vlaXaVUearIOBhiXZ5V3ynxwA=="
   crossorigin="">
</script>


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

var map = L.map('map').setView([{{ center }}], {{ zoom }});

/*
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
}).addTo(map);
*/


L.tileLayer('https://a.tile.opentopomap.org/{z}/{x}/{y}.png', {
	attribution: 'Map data: &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, <a href="http://viewfinderpanoramas.org">SRTM</a> | Map style: &copy; <a href="https://opentopomap.org">OpenTopoMap</a> (<a href="https://creativecommons.org/licenses/by-sa/3.0/">CC-BY-SA</a>)'
}).addTo(map);


function onEachFeature(feature, layer) {
    var popupContent = "";
    if (feature.properties && feature.properties.popupContent) {
        popupContent += feature.properties.popupContent;
    }
    layer.bindPopup(popupContent);
}

/*
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
            fillOpacity: 1
        });
    }
}).addTo(map);
*/


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
