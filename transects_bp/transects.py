"""
WolfDB web service
(c) Olivier Friard

flask blueprint for transects management
"""


import flask
from flask import Flask, render_template, redirect, request, Markup, flash, session, make_response
import psycopg2
import psycopg2.extras
from config import config
import json
import calendar

from .transect_form import Transect
import functions as fn
from . import transects_export
from italian_regions import regions

app = flask.Blueprint("transects", __name__, template_folder="templates")

params = config()
app.debug = params["debug"]


@app.route("/transects")
def transects():
    return render_template(
        "transects.html",
        header_title="Transects",
    )


@app.route("/view_transect/<transect_id>")
@fn.check_login
def view_transect(transect_id):
    """
    Display transect data
    """
    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute(
        (
            "SELECT *, "
            "ST_AsGeoJSON(st_transform(multilines, 4326)) AS transect_geojson, "
            "ROUND(ST_Length(multilines)) AS transect_length "
            "FROM transects "
            "WHERE transect_id = %s"
        ),
        [transect_id],
    )

    transect = cursor.fetchone()

    if transect is None:

        return render_template(
            "view_transect.html", transect={}, paths={}, snowtracks={}, transect_id=transect_id, n_scats=0, map=""
        )

    center = f"45, 7"
    transect_features = []
    min_lat, max_lat = 90, -90
    min_lon, max_lon = 90, -90

    if transect["transect_geojson"] is not None:
        transect_geojson = json.loads(transect["transect_geojson"])

        for line in transect_geojson["coordinates"]:
            latitudes = [lat for _, lat in line]
            longitudes = [lon for lon, _ in line]
            min_lat, max_lat = min(latitudes), max(latitudes)
            min_lon, max_lon = min(longitudes), max(longitudes)

        transect_feature = {
            "type": "Feature",
            "geometry": dict(transect_geojson),
            "properties": {"popupContent": transect_id},
            "id": 1,
        }
        transect_features = [transect_feature]

    # path
    cursor.execute(
        (
            "SELECT *,"
            "(SELECT count(*) FROM scats WHERE scats.path_id = paths.path_id) AS n_scats "
            "FROM paths "
            "WHERE transect_id = %s ORDER BY date ASC"
        ),
        [transect_id],
    )
    results_paths = cursor.fetchall()

    # number of scats
    cursor.execute(
        (
            "SELECT *,"
            "ST_AsGeoJSON(st_transform(geometry_utm, 4326)) AS scat_lonlat "
            "FROM scats WHERE path_id LIKE %s"
        ),
        [f"{transect_id}|%"],
    )

    scats = cursor.fetchall()
    n_scats = len(scats)
    scat_features = []
    color = "orange"
    for row in scats:
        scat_geojson = json.loads(row["scat_lonlat"])

        lon, lat = scat_geojson["coordinates"]

        min_lat = min(min_lat, lat)
        max_lat = max(max_lat, lat)
        min_lon = min(min_lon, lon)
        max_lon = max(max_lon, lon)

        scat_feature = {
            "geometry": dict(scat_geojson),
            "type": "Feature",
            "properties": {
                "style": {"color": color, "fillColor": color, "fillOpacity": 1},
                "popupContent": (
                    f"""Scat ID: <a href="/view_scat/{row['scat_id']}" target="_blank">{row['scat_id']}</a><br>"""
                    f"""WA code: <a href="/view_wa/{row['wa_code']}" target="_blank">{row['wa_code']}</a><br>"""
                    f"""Genotype ID: {row['genotype_id']}"""
                ),
            },
            "id": row["scat_id"],
        }
        scat_features.append(scat_feature)

    # snow tracks
    cursor.execute(
        "SELECT * FROM snow_tracks WHERE (transect_id = %s OR transect_id LIKE %s) ORDER BY date DESC",
        [transect_id, f"%{transect_id};%"],
    )
    results_snowtracks = cursor.fetchall()

    fit = [[min_lat, min_lon], [max_lat, max_lon]]

    return render_template(
        "view_transect.html",
        header_title=f"Transect {transect_id}",
        transect=transect,
        paths=results_paths,
        snowtracks=results_snowtracks,
        transect_id=transect_id,
        n_scats=n_scats,
        map=Markup(fn.leaflet_geojson(center, scat_features, transect_features, fit=str(fit))),
    )


@app.route("/transects_list")
@fn.check_login
def transects_list():
    # get all transects
    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute("SELECT count(*) as n_transects FROM transects")
    n_transects = cursor.fetchone()["n_transects"]

    cursor.execute("SELECT * FROM transects ORDER BY transect_id")

    return render_template(
        "transects_list.html", header_title="List of transects", n_transects=n_transects, results=cursor.fetchall()
    )


@app.route("/export_transects")
@fn.check_login
def export_transects():
    """
    export all transects in XLSX
    """

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute("SELECT * FROM transects ORDER BY transect_id")

    file_content = transects_export.export_transects(cursor.fetchall())

    response = make_response(file_content, 200)
    response.headers["Content-type"] = "application/application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    response.headers["Content-disposition"] = "attachment; filename=transects.xlsx"

    return response


@app.route("/new_transect", methods=("GET", "POST"))
@fn.check_login
def new_transect():
    """
    Insert a new transect
    """

    def not_valid(msg):
        # default values
        default_values = {}
        for k in request.form:
            default_values[k] = request.form[k]

        flash(fn.alert_danger(f"<b>{msg}</b>"))

        return render_template(
            "new_transect.html",
            header_title="Insert a new transect",
            title="New transect",
            action=f"/new_transect",
            form=form,
            default_values=default_values,
        )

    if request.method == "GET":
        form = Transect()
        return render_template(
            "new_transect.html",
            header_title="Insert a new transect",
            title="New transect",
            action=f"/new_transect",
            form=form,
            default_values={},
        )

    if request.method == "POST":

        form = Transect(request.form)

        if form.validate():

            connection = fn.get_connection()
            cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

            # check if transect_id already exists
            cursor.execute(
                "SELECT transect_id FROM transects WHERE UPPER(transect_id) = UPPER(%s)", [request.form["transect_id"]]
            )
            rows = cursor.fetchall()
            if len(rows):
                return not_valid(f"The transect ID {request.form['transect_id']} already exists")

            transect_regions = fn.get_regions(request.form["province"])
            if request.form["province"] and transect_regions == "":
                return not_valid("Check the province field!")

            sql = (
                "INSERT INTO transects (transect_id, sector, location, municipality, province, region, multilines) "
                "VALUES (%s, %s, %s, %s, %s, %s, ST_GeomFromText(%s , 32632))"
            )

            try:
                cursor.execute(
                    sql,
                    [
                        request.form["transect_id"].upper().strip(),
                        request.form["sector"].strip(),
                        request.form["location"].strip(),
                        request.form["municipality"].strip(),
                        request.form["province"].strip().upper(),
                        transect_regions,
                        request.form["multilines"].strip(),
                    ],
                )

                connection.commit()

            except Exception:
                return not_valid(f"Check the MultiLineString field")

            return redirect("/transects_list")
        else:
            return not_valid("Transect form NOT validated")


@app.route("/edit_transect/<transect_id>", methods=("GET", "POST"))
@fn.check_login
def edit_transect(transect_id):
    def not_valid(msg):
        # default values
        default_values = {}
        for k in request.form:
            default_values[k] = request.form[k]

        flash(fn.alert_danger(f"<b>{msg}</b>"))

        return render_template(
            "new_transect.html",
            title="Edit transect",
            action=f"/edit_transect/{transect_id}",
            form=form,
            default_values=default_values,
        )

    if request.method == "GET":

        connection = fn.get_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

        cursor.execute(
            (
                "SELECT transect_id, sector, location, municipality, province, "
                "ST_AsText(multilines) AS multilines "
                "FROM transects "
                "WHERE transect_id = %s"
            ),
            [transect_id],
        )
        default_values = cursor.fetchone()

        default_values["sector"] = "" if default_values["sector"] is None else default_values["sector"]

        form = Transect()

        form.multilines.data = default_values["multilines"]

        return render_template(
            "new_transect.html",
            header_title=f"Edit transect {transect_id}",
            title="Edit transect",
            action=f"/edit_transect/{transect_id}",
            form=form,
            default_values=default_values,
        )

    if request.method == "POST":

        form = Transect(request.form)
        if form.validate():

            connection = fn.get_connection()
            cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

            # check if transect_id already exists
            if request.form["transect_id"] != transect_id:
                cursor.execute(
                    "SELECT transect_id FROM transects WHERE UPPER(transect_id) = UPPER(%s)",
                    [request.form["transect_id"]],
                )
                rows = cursor.fetchall()
                if len(rows):
                    return not_valid(f"The transect ID {request.form['transect_id']} already exists")

            transect_regions = fn.get_regions(request.form["province"])
            if request.form["province"] and transect_regions == "":
                return not_valid("Check the province field!")

            sql = (
                "UPDATE transects SET transect_id = %s, sector =%s, location = %s, municipality = %s, province = %s, region = %s, multilines = ST_GeomFromText(%s , 32632) "
                "WHERE transect_id = %s"
            )
            try:
                cursor.execute(
                    sql,
                    [
                        request.form["transect_id"].strip(),
                        request.form["sector"] if request.form["sector"] else None,
                        request.form["location"].strip(),
                        request.form["municipality"].strip(),
                        request.form["province"].strip().upper(),
                        transect_regions,
                        request.form["multilines"].strip(),
                        transect_id,
                    ],
                )
                connection.commit()
            except Exception:
                return not_valid(f"Check the MultiLineString field")

            return redirect(f"/view_transect/{transect_id}")
        else:
            return not_valid("Transect form NOT validated")


@app.route("/del_transect/<transect_id>")
@fn.check_login
def del_transect(transect_id):

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # check if path based on transect exist
    cursor.execute("SELECT COUNT(*) AS n_paths FROM paths WHERE transect_id = %s", [transect_id])
    result = cursor.fetchone()
    if result["n_paths"] > 0:
        return "Some paths are based on this transect. Please remove them before"

    cursor.execute("DELETE FROM transects WHERE transect_id = %s", [transect_id])
    connection.commit()
    return redirect("/transects_list")


@app.route("/plot_transects")
@fn.check_login
def plot_transects():
    """
    Plot all transects
    """

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute("SELECT transect_id, ST_AsGeoJSON(st_transform(multilines, 4326)) AS transect_lonlat FROM transects")

    transects_features = []
    tot_min_lat, tot_min_lon = 90, 90
    tot_max_lat, tot_max_lon = -90, -90

    for row in cursor.fetchall():
        transect_geojson = json.loads(row["transect_lonlat"])

        for line in transect_geojson["coordinates"]:

            # bounding box
            latitudes = [lat for _, lat in line]
            longitudes = [lon for lon, _ in line]
            tot_min_lat = min([tot_min_lat, min(latitudes)])
            tot_max_lat = max([tot_max_lat, max(latitudes)])
            tot_min_lon = min([tot_min_lon, min(longitudes)])
            tot_max_lon = max([tot_max_lon, max(longitudes)])

        transect_feature = {
            "geometry": dict(transect_geojson),
            "type": "Feature",
            "properties": {
                # "style": {"color": "orange", "fillColor": "orange", "fillOpacity": 1},
                "popupContent": f"""Transect ID: <a href="/view_transect/{row['transect_id']}" target="_blank">{row['transect_id']}</a>"""
            },
            "id": row["transect_id"],
        }

        transects_features.append(dict(transect_feature))

    center = f"45 , 7"

    return render_template(
        "plot_transects.html",
        header_title="Plot of transects",
        map=Markup(
            fn.leaflet_geojson(
                center, [], transects_features, fit=str([[tot_min_lat, tot_min_lon], [tot_max_lat, tot_max_lon]])
            )
        ),
    )


@app.route("/transects_analysis")
@fn.check_login
def transects_analysis():

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # check if path based on transect exist
    cursor.execute("SELECT * FROM transects ORDER BY region, province, transect_id")
    transects = cursor.fetchall()

    out = """<style>    table{    border-width: 0 0 1px 1px;    border-style: solid;} td{    border-width: 1px 1px 0 0;    border-style: solid;    margin: 0;    }</style>    """

    season = [5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3, 4]

    out += "<table>"
    out += "<tr><th>Region</th><th>Province</th><th>transect ID</th>"
    for month in season:
        out += f"<th>{calendar.month_abbr[month]}</th>"
    out += "</tr>"

    for row in transects:
        transect_id = row["transect_id"]

        # print(f"{transect_id=}")

        transect_month = {}
        dates_list = {}
        completeness_list = {}

        cursor.execute("SELECT * FROM paths WHERE transect_id = %s ", [transect_id])
        paths = cursor.fetchall()
        for row_path in paths:

            # add date of path
            path_date = str(row_path["date"])
            path_month = int(path_date.split("-")[1])
            if path_month not in dates_list:
                dates_list[path_month] = []
            dates_list[path_month].append(path_date)

            # add completeness
            path_completeness = str(row_path["completeness"])
            path_month = int(path_date.split("-")[1])
            if path_month not in completeness_list:
                completeness_list[path_month] = []
            completeness_list[path_month].append(path_completeness)

            cursor.execute("SELECT * FROM scats WHERE path_id = %s ", [row_path["path_id"]])
            scats = cursor.fetchall()

            for row_scat in scats:
                month = int(str(row_scat["date"]).split("-")[1])

                # print(f"{month=}")

                if month not in transect_month:
                    transect_month[month] = {"samples": 0}

                transect_month[month]["samples"] += 1

        out += f'<tr><td>{row["region"]}</td><td>{row["province"]}</td><td>{transect_id}</td>'

        # print(dates_list)

        for month in season:
            flag_path = False
            # date
            if month in dates_list:
                out += f"<td>{', '.join(dates_list[month])}<br>"
                flag_path = True
            else:
                out += "<td>"

            if month in completeness_list:

                out += f"{', '.join(completeness_list[month])}<br>"

            if month in transect_month:
                out += f"{transect_month[month]['samples']}<br>"
            else:
                if flag_path:
                    out += f"0<br>"
                else:
                    out += f"<br>"

            out += "</td>"
        out += "</tr>"

    out += "</table>"
    return out
