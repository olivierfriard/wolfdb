"""
WolfDB web service
(c) Olivier Friard

functions module

"""


from flask import Flask, request, Markup
import psycopg2
import psycopg2.extras
from config import config

from italian_regions import regions

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



def all_transect_id():
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT transect_id FROM transects ORDER BY transect_id")
    return [x[0].strip() for x in cursor.fetchall()]

def all_path_id():
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
    try:
        month = int(date[5:6+1])
        year = int(date[0:3+1])
        if 5 <= month <= 12:
            return f"{year}-{year + 1}"
        if 1 <= month <= 4:
            return f"{year - 1}-{year}"
    except Exception:
        return f"Error {date}"


def get_region(province):
    if province:
        for region in regions:
            if province.upper() in region["province"]:
                scat_region = region["nome"]
                break
    else:
        scat_region = ""

    return scat_region


def get_regions(provinces):

    transect_region = []
    if provinces:
        for region in regions:
            for x in provinces.split(" "):
                if x.upper() in region["province"]:
                    transect_region.append(region["nome"])

    return " ".join(list(set(transect_region)))


def leaflet_point(point_lonlat: list, scat_id: str) -> str:

    lon, lat = point_lonlat

    map = f"""
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.7.1/dist/leaflet.css"
   integrity="sha512-xodZBNTC5n17Xt2atTPuE1HxjVMSvLVW9ocqUKLsCC5CXdbqCmblAshOMAS6/keqq/sMZMZ19scR4PsZChSR7A=="
   crossorigin=""/>

<script src="https://unpkg.com/leaflet@1.7.1/dist/leaflet.js"
   integrity="sha512-XQoYMqMTK8LvdxXYG3nZ448hOEQiglfqkJs1NOQV44cWnUrBc8PkAOcXy20w0vlaXaVUearIOBhiXZ5V3ynxwA=="
   crossorigin=""></script>

    <script>
	var map = L.map('map').setView([{lat}, {lon}], 13);

L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
}}).addTo(map);


var blueIcon = L.icon({{ iconUrl: '/static/marker-icon-blue.png', iconAnchor: [7, 20] }});

var marker = L.marker([{lat},  {lon}], {{icon: blueIcon}}).addTo(map);
marker.bindPopup("{scat_id}");

/*
function onMapClick(e) {{
		popup
			.setLatLng(e.latlng)
			.setContent("You clicked the map at " + e.latlng.toString())
			.openOn(map);
	}}

	map.on('click', onMapClick);
*/
var popup = L.popup();
	</script>
    """

    return map




def leaflet_line(points_lonlat: list) -> str:

    # UTM coord conversion
    '''
    print(points[0:10])
    points_latlon = [list(utm.to_latlon(x, y, 32, "N")) for x, y in points]
    print(points_latlon[0:10])
    '''

    lon_org, lat_orig = points_lonlat[0]

    points_latlong = [[lat, lon] for lon, lat in points_lonlat]

    map = f"""
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.7.1/dist/leaflet.css"
   integrity="sha512-xodZBNTC5n17Xt2atTPuE1HxjVMSvLVW9ocqUKLsCC5CXdbqCmblAshOMAS6/keqq/sMZMZ19scR4PsZChSR7A=="
   crossorigin=""/>

<script src="https://unpkg.com/leaflet@1.7.1/dist/leaflet.js"
   integrity="sha512-XQoYMqMTK8LvdxXYG3nZ448hOEQiglfqkJs1NOQV44cWnUrBc8PkAOcXy20w0vlaXaVUearIOBhiXZ5V3ynxwA=="
   crossorigin=""></script>

    <script>
	var map = L.map('map').setView([{lat_orig}, {lon_org}], 13);

L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
}}).addTo(map);



var polylinePoints = {points_latlong};

var firstpolyline = L.polyline(polylinePoints, {{
    color: 'red',
    opacity: 0.75,
    smoothFactor: 1

    }}).addTo(map);

function onMapClick(e) {{
		popup
			.setLatLng(e.latlng)
			.setContent("You clicked the map at " + e.latlng.toString())
			.openOn(map);
	}}

	map.on('click', onMapClick);
var popup = L.popup();
	</script>
    """

    return map
