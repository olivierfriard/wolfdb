"""
WolfDB web service
(c) Olivier Friard

flask blueprint for scats management
"""



import flask
from flask import Flask, render_template, redirect, request, Markup, flash, session
import psycopg2
import psycopg2.extras
from config import config
import json
import utm

from transect import Transect
import functions as fn
from italian_regions import regions

app = flask.Blueprint("transects", __name__, template_folder="templates")

app.debug = True


params = config()

@app.route("/transects")
def transects():
    return render_template("transects.html")



def leaflet_line(points_latlon: list) -> str:

    # UTM coord conversion
    '''
    print(points[0:10])
    points_latlon = [list(utm.to_latlon(x, y, 32, "N")) for x, y in points]
    print(points_latlon[0:10])
    '''

    x1, y1 = points_latlon[0]

    map = f"""
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.7.1/dist/leaflet.css"
   integrity="sha512-xodZBNTC5n17Xt2atTPuE1HxjVMSvLVW9ocqUKLsCC5CXdbqCmblAshOMAS6/keqq/sMZMZ19scR4PsZChSR7A=="
   crossorigin=""/>

<script src="https://unpkg.com/leaflet@1.7.1/dist/leaflet.js"
   integrity="sha512-XQoYMqMTK8LvdxXYG3nZ448hOEQiglfqkJs1NOQV44cWnUrBc8PkAOcXy20w0vlaXaVUearIOBhiXZ5V3ynxwA=="
   crossorigin=""></script>

    <script>
	var map = L.map('map').setView([{x1}, {y1}], 13);

L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
}}).addTo(map);



var polylinePoints = {points_latlon};

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


@app.route("/view_transect/<transect_id>")
def view_transect(transect_id):
    """
    Display transect data
    """
    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT *, ST_AsGeoJSON(points) AS points, ROUND(ST_Length(points)) AS transect_length FROM transects WHERE transect_id = %s",
                   [transect_id])
    transect = cursor.fetchone()

    points = json.loads(transect["points"])['coordinates']


    # path
    cursor.execute("SELECT * FROM paths WHERE transect_id = %s ORDER BY date DESC",
                   [transect_id])
    results_paths = cursor.fetchall()

    # snow tracks
    cursor.execute("SELECT * FROM snow_tracks WHERE path_id LIKE %s ORDER BY date DESC",
                   [f"{transect_id} %"])
    results_snowtracks = cursor.fetchall()


    return render_template("view_transect.html",
                           transect=transect,
                           paths=results_paths,
                           snowtracks=results_snowtracks,
                           transect_id=transect_id,
                           map=Markup(leaflet_line(points)))


@app.route("/transects_list")
def transects_list():
    # get all transects
    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT * FROM transects ORDER BY transect_id")

    results = cursor.fetchall()

    return render_template("transects_list.html",
                           results=results)




@app.route("/new_transect", methods=("GET", "POST"))
def new_transect():

    def not_valid(msg):
        # default values
        default_values = {}
        for k in request.form:
            default_values[k] = request.form[k]

        flash(Markup(f"<b>{msg}</b>"))

        return render_template("new_transect.html",
                            title="New transect",
                            action=f"/new_transect",
                            form=form,
                            default_values=default_values)


    if request.method == "GET":
        form = Transect()
        return render_template('new_transect.html',
                               title="New transect",
                               action=f"/new_transect",
                            form=form,
                            default_values={})


    if request.method == "POST":
        form = Transect(request.form)

        if form.validate():

            transect_regions = fn.get_regions(request.form["province"])
            if request.form["province"] and transect_regions == "":
                return not_valid("Check the province field!")

            connection = fn.get_connection()
            cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

            sql = ("INSERT INTO transects (transect_id, sector, location, municipality, province, region) "
                   "VALUES (%s, %s, %s, %s, %s, %s)")
            cursor.execute(sql,
                           [
                            request.form["transect_id"], request.form["sector"],
                            request.form["location"].strip(), request.form["municipality"].strip(),
                            request.form["province"].strip().upper(),
                            transect_regions
                           ]
                           )

            connection.commit()

            return redirect("/transects_list")
        else:
            return not_valid("Transect form NOT validated")



@app.route("/edit_transect/<transect_id>", methods=("GET", "POST"))
def edit_transect(transect_id):

    def not_valid(msg):
        # default values
        default_values = {}
        for k in request.form:
            default_values[k] = request.form[k]

        flash(Markup(f"<b>{msg}</b>"))

        return render_template("new_transect.html",
                            title="Edit transect",
                            action=f"/edit_transect/{transect_id}",
                            form=form,
                            default_values=default_values)


    if request.method == "GET":
        connection = fn.get_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("SELECT * FROM transects WHERE transect_id = %s",
                    [transect_id])
        default_values = cursor.fetchone()

        form = Transect()

        return render_template("new_transect.html",
                            title="Edit transect",
                            action=f"/edit_transect/{transect_id}",
                            form=form,
                            default_values=default_values)

    if request.method == "POST":

        form = Transect(request.form)
        if form.validate():

            transect_regions = fn.get_regions(request.form["province"])
            if request.form["province"] and transect_regions == "":
                return not_valid("Check the province field!")


            connection = fn.get_connection()
            cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

            sql = ("UPDATE transects SET transect_id = %s, sector =%s, location = %s, municipality = %s, province = %s, region = %s "
                   "WHERE transect_id = %s")
            cursor.execute(sql,
                           [
                            request.form["transect_id"].strip(), request.form["sector"],
                            request.form["location"].strip(), request.form["municipality"].strip(),
                            request.form["province"].strip().upper(), transect_regions,
                            transect_id
                           ]
                           )

            connection.commit()

            return redirect(f"/view_transect/{transect_id}")
        else:
            return not_valid("Transect form NOT validated")


@app.route("/del_transect/<transect_id>")
def del_scat(transect_id):

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # check if path based on transect exist
    cursor.execute("SELECT COUNT(*) AS n_paths FROM paths WHERE transect_id = %s", [transect_id])
    result = cursor.fetchone()
    if result["n_paths"] > 0:
        return "Some paths are based on this transect. Please remove them before"

    cursor.execute("DELETE FROM transects WHERE transect_id = %s",
                   [transect_id])
    connection.commit()
    return redirect("/transects_list")
