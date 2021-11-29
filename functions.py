"""
WolfDB web service
(c) Olivier Friard

functions module

"""


from flask import Flask, request, Markup
import psycopg2
import psycopg2.extras
from config import config
import urllib.request
import json

from italian_regions import regions, province_codes

params = config()

def get_connection():
    return psycopg2.connect(user=params["user"],
                            password=params["password"],
                            host=params["host"],
                            #port="5432",
                            database=params["database"])

def alert_danger(text: str):
    return Markup(f'<div class="alert alert-danger" role="alert">{text}</div>')


def alert_success(text: str):
    return Markup(
        f'<div class="alert alert-success" role="alert">{text}</div>')


def get_path_id(transect_id: str, date: str) -> str:
    """
    returns path_id
    date must be in ISO8601 format
    """
    return str(transect_id) + "_" + date[2:].replace("-", "")


def all_transect_id():
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT transect_id FROM transects ORDER BY transect_id")
    return [x[0].strip() for x in cursor.fetchall()]

def all_path_id():
    """
    return all path ID (transect ID and date)
    """
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT CONCAT(transect_id, ' ',  date) FROM paths ORDER BY date DESC")
    return [x[0].strip() for x in cursor.fetchall()]


def all_snow_tracks_id():
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT snowtrack_id FROM snow_tracks ORDER BY snowtrack_id")
    return [x[0].strip() for x in cursor.fetchall()]


def sampling_season(date):
    """
    Extract sampnig season from date in ISO 8601 format
    """
    try:
        month = int(date[5:6+1])
        year = int(date[0:3+1])
        if 5 <= month <= 12:
            return f"{year}-{year + 1}"
        if 1 <= month <= 4:
            return f"{year - 1}-{year}"
    except Exception:
        return f"Error {date}"


def province_name2code(province_name):
    for code in province_codes:
        if province_name.upper() == province_codes[code]["nome"].upper():
            return code
    return ""


def get_region(province):
    """
    get region by province code
    """
    scat_region = ""
    if province:
        for region in regions:
            if province.upper() in region["province"]:
                scat_region = region["nome"]
                break

    return scat_region


def get_regions(provinces):

    transect_region = []
    if provinces:
        for region in regions:
            for x in provinces.split(" "):
                if x.upper() in region["province"]:
                    transect_region.append(region["nome"])

    return " ".join(list(set(transect_region)))


def leaflet_geojson(center, scat_features, transect_features, zoom=13) -> str:

    map = """

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

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
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
				fillColor: "#ff7800",
				color: "#red",
				weight: 1,
				opacity: 1,
				fillOpacity: 0.8
			});
		}
	}).addTo(map);

	L.geoJSON(transects, {

		filter: function (feature, layer) {
			if (feature.properties) {
				// If the property "underConstruction" exists and is true, return false (don't render features under construction)
				return feature.properties.underConstruction !== undefined ? !feature.properties.underConstruction : true;
			}
			return false;
		},

		onEachFeature: onEachFeature
	}).addTo(map);

	

</script>
    
    
    """.replace("###SCAT_FEATURES###", str(scat_features)).replace("###CENTER###", center).replace("###TRANSECT_FEATURES###", str(transect_features)).replace("###ZOOM###", str(zoom))




    return map


def reverse_geocoding(lon_lat: list) -> dict:
    """
    get place from GPS coordinates with nominatum (OSM)
    """

    longitude, latitude = lon_lat

    URL = f"https://nominatim.openstreetmap.org/reverse.php?lat={latitude}&lon={longitude}&zoom=14&format=json&namedetails=1&accept-language=en"

    continents = {
        "Africa": [
            "Egypt", "Algeria", "Angola", "Benin", "Botswana", "Burkina Faso",
            "Burundi", "Cameroon", "Cameroun", "Cape Verde",
            "Central African Republic", "Chad", "Tchad", "Comoros",
            "Republic of the Congo", "Congo-Brazzaville",
            "Democratic Republic of the Congo", "Côte d'Ivoire", "Ivory Coast",
            "Djibouti", "Equatorial Guinea", "Eritrea", "Ethiopia",
            "Abyssinia", "Gabon", "The Gambia", "Ghana", "Guinea",
            "Guinea-Bissau", "Kenya", "Lesotho", "Liberia", "Libya",
            "Madagascar", "Malawi", "Mali", "Mauritania", "Mauritius",
            "Morocco", "Al Maghrib", "Mozambique", "Namibia", "Niger",
            "Nigeria", "Rwanda", "São Tomé and Príncipe", "Senegal",
            "Seychelles", "Sierra Leone", "Somalia", "South Africa",
            "South Sudan", "Swaziland", "Eswatini", "Tanzania", "Togo",
            "Tunisia", "Uganda", "Western Sahara", "Zambia", "Sudan",
            "Zimbabwe"
        ],
        "Oceania": [
            "Australia", "Fiji", "New Zealand",
            "Federated States of Micronesia", "Kiribati", "Marshall Islands",
            "Nauru", "Palau", "Papua New Guinea", "Samoa", "Solomon Islands",
            "Tonga", "Tuvalu", "Vanuatu"
        ],
        "South America": [
            "Brazil", "Brasil", "Argentina", "Bolivia", "Chile", "Colombia",
            "Ecuador", "Falkland Islands", "French Guiana", "Guyana",
            "Paraguay", "Peru", "South Georgia and the South Sandwich Islands",
            "Suriname", "Uruguay", "Venezuela"
        ],
        "North America": [
            "Canada", "United States of America", "Mexico", "Belize",
            "Antigua and Barbuda", "Anguilla", "Aruba", "The Bahamas",
            "Barbados", "Bermuda", "Bonaire", "British Virgin Islands",
            "Cayman Islands", "Clipperton Island", "Costa Rica", "Cuba",
            "Curaçao", "Dominica", "Dominican Republic",
            "Republica Dominicana", "El Salvador", "Greenland", "Grenada",
            "Guadeloupe", "Guatemala", "Haiti", "Honduras", "Jamaica",
            "Martinique", "Montserrat", "Navassa Island", "Nicaragua",
            "Panama", "Panamá", "Puerto Rico", "Saba", "Saint Barthelemy",
            "Saint Kitts and Nevis", "Saint Lucia", "Saint Martin",
            "Saint Pierre and Miquelon", "Saint Vincent and the Grenadines",
            "Sint Eustatius", "Sint Maarten", "Trinidad and Tobago",
            "Turks and Caicos", "US Virgin Islands"
        ],
        "Europe": [
            "Albania", "Shqipëria", "Andorra", "Austria", "Österreich",
            "Belarus", "Беларусь", "Belgium", "Bosnia and Herzegovina",
            "Bulgaria", "България", "Croatia", "Hrvatska", "Cyprus", "Κύπρος",
            "Czech Republic", "Česko", "Denmark", "Danmark", "Estonia",
            "Finland", "Suomi", "Georgia", "Germany", "Greece", "Hungary",
            "Iceland", "Ireland", "Republic of Ireland", "Italy", "Kazakhstan",
            "Kosovo", "Latvia", "Liechtenstein", "Lithuania", "Luxembourg",
            "North Macedonia", "Malta", "Moldova", "Monaco", "Montenegro",
            "Netherlands", "Norway", "Poland", "Portugal", "Romania", "Russia",
            "San Marino", "Serbia", "Slovakia", "Slovenia", "France", "Spain",
            "Sweden", "Switzerland", "Turkey", "Ukraine", "United Kingdom",
            "Vatican City"
        ],
        "Asia": [
            "Afghanistan", "Armenia", "Azerbaijan", "Bahrain", "Bangladesh",
            "Bhutan", "Brunei", "Cambodia", "Kampuchea", "China", "East Timor",
            "Georgia", "India", "Indonesia", "Iran", "Iraq", "Israel", "Japan",
            "Jordan", "Al Urdun", "Kazakhstan", "Kuwait", "Kyrgyzstan", "Laos",
            "Lebanon", "Malaysia", "Maldives", "Mongolia", "Myanmar", "Nepal",
            "North Korea", "Oman", "Pakistan", "Philippines", "Qatar",
            "Russia", "Saudi Arabia", "Singapore", "South Korea", "Sri Lanka",
            "Syria", "Tajikistan", "Thailand", "Turkey", "Turkmenistan",
            "Taiwan", "United Arab Emirates", "Uzbekistan", "Vietnam", "Yemen"
        ],
    }

    response = urllib.request.urlopen(URL).read().strip().decode("utf-8")

    d = json.loads(response)

    if "address" not in d:
        return None
    print(d)

    country = d['address'].get('country', "")

    for kw in ['region', 'state', 'state_district', 'county']:
        region = d['address'].get(kw, "")
        if region:
            break

    for kw in ['county']:
        province =  d['address'].get(kw, "")

    for kw in ['hamlet', 'town', 'city', 'village']:
        city = d['address'].get(kw, "")
        if city:
            break

    for kw in [ 'croft', 'isolated_dwelling', 'suburb']:
        place = d['address'].get(kw, "")
        if place:
            break

    geocoded_continent: str = ""
    if country:
        for continent in continents:
            if country.lower() in [x.lower() for x in continents[continent]]:
                geocoded_continent = continent
                break

    return {
        "continent": geocoded_continent,
        "country": country,
        "region": region,
        "province": province,
        "municipality": city,
        "location": place
    }



