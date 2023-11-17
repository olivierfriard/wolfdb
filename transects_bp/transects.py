"""
WolfDB web service
(c) Olivier Friard

flask blueprint for transects management
"""


import flask
from flask import render_template, redirect, request, flash, make_response
from markupsafe import Markup
import psycopg2
import psycopg2.extras
from config import config
import json
import calendar
import datetime as dt

from .transect_form import Transect
import functions as fn
from . import transects_export
from italian_regions import province_codes

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

    scats_color = params["scat_color"]
    transects_color = params["transect_color"]
    tracks_color = params["track_color"]

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
        flash(fn.alert_danger(f"<b>Transect {transect_id} not found</b>"))
        return redirect("/transects_list")

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
            "properties": {
                # "style": {"stroke": transects_color, "stroke-width": 2, "stroke-opacity": 1},
                "popupContent": f"Transect ID: {transect_id}",
            },
            "geometry": dict(transect_geojson),
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

    # scats

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
                # "style": {"color": color, "fillColor": color },
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
        (
            "SELECT *, "
            "ST_AsGeoJSON(st_transform(multilines, 4326)) AS track_geojson "
            "FROM snow_tracks WHERE (transect_id = %s OR transect_id LIKE %s) ORDER BY date DESC"
        ),
        [transect_id, f"%{transect_id};%"],
    )
    tracks = cursor.fetchall()

    track_features = []
    for row in tracks:
        if row["track_geojson"] is not None:
            track_geojson = json.loads(row["track_geojson"])

            for line in track_geojson["coordinates"]:
                latitudes = [lat for _, lat in line]
                longitudes = [lon for lon, _ in line]

                min_lat = min(min_lat, min(latitudes))
                max_lat = max(max_lat, max(latitudes))

                min_lon = min(min_lon, min(longitudes))
                max_lon = max(max_lon, max(longitudes))

            track_feature = {
                "geometry": dict(track_geojson),
                "type": "Feature",
                "properties": {
                    "popupContent": (
                        f"""Track ID: <a href="/view_snowtrack/{row['snowtrack_id']}" target="_blank">{row['snowtrack_id']}</a><br>"""
                    ),
                },
                "id": row["snowtrack_id"],
            }
            track_features.append(track_feature)

    return render_template(
        "view_transect.html",
        header_title=f"Transect {transect_id}",
        transect=transect,
        paths=results_paths,
        snowtracks=tracks,
        transect_id=transect_id,
        n_scats=n_scats,
        map=Markup(
            fn.leaflet_geojson2(
                {
                    "scats": scat_features,
                    "scats_color": scats_color,
                    "transects": transect_features,
                    "transects_color": transects_color,
                    "tracks": track_features,
                    "tracks_color": tracks_color,
                    "fit": [[min_lat, min_lon], [max_lat, max_lon]],
                }
            )
        ),
        scat_color=params["scat_color"],
        dead_wolf_color=params["dead_wolf_color"],
        transect_color=params["transect_color"],
        track_color=params["track_color"],
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
    response.headers["Content-disposition"] = f"attachment; filename=transects_{dt.datetime.now():%Y-%m-%d_%H%M%S}.xlsx"

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

            # check province code
            transect_province_code = fn.check_province_code(request.form["province"])
            if transect_province_code is None:
                # check province name
                transect_province_code = fn.province_name2code(request.form["province"])
                if transect_province_code is None:
                    return not_valid("The province was not found")

            transect_region = fn.province_code2region(transect_province_code)

            if request.form["multilines"]:
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
                            transect_province_code,
                            transect_region,
                            request.form["multilines"].strip(),
                        ],
                    )
                    connection.commit()

                except Exception:
                    return not_valid(f"Check the MultiLineString field")

            else:
                sql = (
                    "INSERT INTO transects (transect_id, sector, location, municipality, province, region) "
                    "VALUES (%s, %s, %s, %s, %s, %s)"
                )

                cursor.execute(
                    sql,
                    [
                        request.form["transect_id"].upper().strip(),
                        request.form["sector"].strip(),
                        request.form["location"].strip(),
                        request.form["municipality"].strip(),
                        transect_province_code,
                        transect_region,
                    ],
                )
                connection.commit()

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

            # convert province code in province name
            if request.form["province"].upper() in province_codes:
                transect_province_name = province_codes[request.form["province"].upper()]["nome"]
                transect_region = province_codes[request.form["province"].upper()]["regione"]
            else:
                transect_province_name = request.form["province"].strip().upper()
                transect_region = fn.province_name2region(request.form["province"])

            sql = (
                "UPDATE transects SET transect_id = %s, sector =%s, location = %s, municipality = %s, province = %s, region = %s "
                "WHERE transect_id = %s"
            )

            cursor.execute(
                sql,
                [
                    request.form["transect_id"].strip(),
                    request.form["sector"] if request.form["sector"] else None,
                    request.form["location"].strip(),
                    request.form["municipality"].strip(),
                    transect_province_name,
                    transect_region,
                    transect_id,
                ],
            )
            connection.commit()

            if request.form["multilines"].strip():
                try:
                    sql = "UPDATE transects SET multilines = ST_GeomFromText(%s , 32632) WHERE transect_id = %s"
                    cursor.execute(
                        sql,
                        [
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
    transects_color = params["transect_color"]

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute("SELECT transect_id, ST_AsGeoJSON(st_transform(multilines, 4326)) AS transect_lonlat FROM transects")

    transects_features = []
    tot_min_lat, tot_min_lon = 90, 90
    tot_max_lat, tot_max_lon = -90, -90

    for row in cursor.fetchall():
        if row["transect_lonlat"] is not None:
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
                    "popupContent": f"""Transect ID: <a href="/view_transect/{row['transect_id']}" target="_blank">{row['transect_id']}</a>"""
                },
                "id": row["transect_id"],
            }

            transects_features.append(dict(transect_feature))

        else:
            print(f"{row['transect_id']} WITHOUT coordinates")

    return render_template(
        "plot_transects.html",
        header_title="Plot of transects",
        map=Markup(
            fn.leaflet_geojson2(
                {
                    "transects": transects_features,
                    "transects_color": transects_color,
                    "fit": [[tot_min_lat, tot_min_lon], [tot_max_lat, tot_max_lon]],
                }
            )
        ),
        scat_color=params["scat_color"],
        dead_wolf_color=params["dead_wolf_color"],
        transect_color=params["transect_color"],
        track_color=params["track_color"],
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


@app.route("/transects_n_samples_by_month/<year_init>/<year_end>")
@fn.check_login
def transects_n_samples_by_month(year_init, year_end):

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # check if path based on transect exist
    cursor.execute("SELECT * FROM transects ORDER BY transect_id")
    transects = cursor.fetchall()

    sampling_years = range(int(year_init), int(year_end) + 1)
    season_months = [5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3, 4]

    out = []

    # header
    row = ["path_id"]
    for year in sampling_years:
        for month in season_months:
            row.append(f"{year}-{month:02}")
    out.append(row)

    for transect in transects:

        transect_id = transect["transect_id"]
        row = [transect_id]

        for year in sampling_years:
            for month in season_months:
                cursor.execute(
                    (
                        "SELECT path_id FROM paths "
                        "WHERE transect_id = %s "
                        "AND EXTRACT(YEAR FROM date) = %s"
                        "AND EXTRACT(MONTH FROM date) = %s"
                    ),
                    [transect_id, year, month],
                )
                paths = cursor.fetchall()
                if len(paths):
                    cursor.execute(
                        "SELECT count(*) AS n_scats FROM scats where path_id IN (SELECT path_id FROM paths WHERE transect_id = %s AND EXTRACT(YEAR FROM date) = %s AND EXTRACT(MONTH FROM date) = %s)",
                        [transect_id, year, month],
                    )
                    scats = cursor.fetchone()
                    row.append(str(scats["n_scats"]))
                else:
                    row.append("NA")
        out.append(row)

    out_str = "\n".join([z for z in ["\t".join(x) for x in out]])

    response = make_response(out_str, 200)
    response.headers["Content-type"] = "'text/tab-separated-values"
    response.headers[
        "Content-disposition"
    ] = f"attachment; filename=transects_n-samples_{dt.datetime.now():%Y-%m-%d_%H%M%S}.tsv"

    return response
