"""
WolfDB web service
(c) Olivier Friard

flask blueprint for transects management
"""



import flask
from flask import Flask, render_template, redirect, request, Markup, flash, session
import psycopg2
import psycopg2.extras
from config import config
import json


from .transect_form import Transect
import functions as fn
from italian_regions import regions

app = flask.Blueprint("transects", __name__, template_folder="templates")

app.debug = True


params = config()

@app.route("/transects")
def transects():
    return render_template("transects.html")




@app.route("/view_transect/<transect_id>")
def view_transect(transect_id):
    """
    Display transect data
    """
    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute("SELECT *, ST_AsGeoJSON(st_transform(points_utm, 4326)) AS transect_geojson, ROUND(ST_Length(points)) AS transect_length FROM transects WHERE transect_id = %s", [transect_id])

    transect = cursor.fetchone()

    if transect is None:

        return render_template("view_transect.html",
                            transect={},
                            paths={},
                            snowtracks={},
                            transect_id=transect_id,
                            n_scats=0,
                            map=""
                            )

    transect_geojson = json.loads(transect["transect_geojson"])

    transect_feature = {"type": "Feature",
                        "geometry": dict(transect_geojson),
                        "properties": {
                        "popupContent": transect_id
                                      },
                        "id": 1
                       }
    transect_features = [transect_feature]

    center = f"{transect_geojson['coordinates'][0][1]}, {transect_geojson['coordinates'][0][0]}"

    # path
    cursor.execute("SELECT *, (select count(*) from scats where scats.path_id = paths.path_id) AS n_scats FROM paths WHERE transect_id = %s ORDER BY date ASC",
                   [transect_id])
    results_paths = cursor.fetchall()


    # number of scats
    cursor.execute("SELECT COUNT(*) AS n_scats FROM scats WHERE path_id LIKE %s", [f"{transect_id}\_%"])
    n_scats = cursor.fetchone()["n_scats"]


    # snow tracks
    cursor.execute("SELECT * FROM snow_tracks WHERE (transect_id = %s OR transect_id LIKE %s) ORDER BY date DESC",
                   [transect_id, f"%{transect_id};%"])
    results_snowtracks = cursor.fetchall()

    return render_template("view_transect.html",
                            transect=transect,
                            paths=results_paths,
                            snowtracks=results_snowtracks,
                            transect_id=transect_id,
                            n_scats=n_scats,
                            map=Markup(fn.leaflet_geojson(center, [], transect_features)))


@app.route("/transects_list")
def transects_list():
    # get all transects
    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute("SELECT count(*) as n_transects FROM transects")
    n_transects = cursor.fetchone()["n_transects"]

    cursor.execute("SELECT * FROM transects ORDER BY transect_id")

    return render_template("transects_list.html",
                           n_transects=n_transects,
                           results=cursor.fetchall())




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
        default_values["sector"] = "" if default_values["sector"] is None else default_values["sector"]

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
                            request.form["transect_id"].strip(),
                            request.form["sector"] if request.form["sector"] else None,
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



@app.route("/transects_analysis")
def transects_analysis():

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # check if path based on transect exist
    cursor.execute("SELECT * FROM transects ORDER BY region, province, transect_id")
    transects = cursor.fetchall()

    out = """<style>
    table
{
    border-width: 0 0 1px 1px;
    border-style: solid;
}

td
{
    border-width: 1px 1px 0 0;
    border-style: solid;
    margin: 0;

    }
</style>
    """

    out += '<table>'
    out += "<tr><th>Region</th><th>Province</th><th>transect ID</th><th>may</th><th>june</th><th>july</th><th>august</th><th>september</th><th>october</th><th>november</th><th>december</th><th>january</th><th>february</th><th>march</th><th>april</th></tr>"
    for row in transects:
        transect_id = row["transect_id"]


        print(f"{transect_id=}")

        transect_month = {}
        cursor.execute("SELECT * FROM paths WHERE transect_id = %s ", [transect_id])
        paths = cursor.fetchall()
        for row_path in paths:
            cursor.execute("SELECT * FROM scats WHERE path_id = %s ", [row_path["path_id"]])
            scats = cursor.fetchall()
            for row_scat in scats:
                month = int(str(row_scat["date"]).split("-")[1])
                print(f"{month=}")
                if month not in transect_month:
                    transect_month[month] = {"samples": 0}
                transect_month[month]["samples"] += 1


        out += f'<tr><td>{row["region"]}</td><td>{row["province"]}</td><td>{transect_id}</td>'
        season = [5,6,7,8,9,10,11,12,1,2,3,4]
        for month in season:
            if month in transect_month:
                out += f"<td>{transect_month[month]['samples']}</td>"
            else:
                out += f"<td>0</td>"
        out += "</tr>"

    out += "</table>"
    return out
