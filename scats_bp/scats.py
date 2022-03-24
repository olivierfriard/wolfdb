"""
WolfDB web service
(c) Olivier Friard

flask blueprint for scats management
"""


import flask
from flask import render_template, redirect, request, Markup, flash, session, current_app, make_response
import psycopg2
import psycopg2.extras
from config import config

from .scat_form import Scat
import functions as fn
import utm
import json
import pathlib as pl

import uuid
import os
import sys
import subprocess
import time
from . import scats_export, scats_import


app = flask.Blueprint("scats", __name__, template_folder="templates")

params = config()

params["excel_allowed_extensions"] = json.loads(params["excel_allowed_extensions"])

app.debug = params["debug"]

LOCK_FILE_NAME_PATH = "check_location.lock"


def error_info(exc_info: tuple) -> tuple:
    """
    return details about error
    usage: error_info(sys.exc_info())

    Args:
        sys.exc_info() (tuple):

    Returns:
        tuple: error type, error file name, error line number
    """

    _, exc_obj, exc_tb = exc_info
    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]

    error_type, error_file_name, error_lineno = exc_obj, fname, exc_tb.tb_lineno

    return f"Error {error_type} in {error_file_name} at line #{error_lineno}"


@app.route("/scats")
@fn.check_login
def scats():
    """
    Scats home page
    """

    if os.path.exists(LOCK_FILE_NAME_PATH):
        check_location_creation_time = "Check location is running. Please wait."
    else:
        if os.path.exists("static/systematic_scats_transects_location.html"):
            check_location_creation_time = time.ctime(
                os.path.getctime("static/systematic_scats_transects_location.html")
            )
        else:
            check_location_creation_time = "File not found"

    return render_template(
        "scats.html", header_title="Scats", check_location_creation_time=check_location_creation_time
    )


@app.route("/wa_form", methods=("POST",))
@fn.check_login
def wa_form():

    data = request.form

    return (
        f'<form action="/add_wa" method="POST" style="padding-top:30px; padding-bottom:30px">'
        f'<input type="hidden" id="scat_id" name="scat_id" value="{request.form["scat_id"]}">'
        '<div class="form-group">'
        '<label for="usr">WA code</label>'
        '<input type="text" class="form-control" id="wa" name="wa">'
        "</div>"
        '<button type="submit" class="btn btn-primary">Add code</button>'
        "</form>"
    )


@app.route("/add_wa", methods=("POST",))
@fn.check_login
def add_wa():

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute(
        "UPDATE scats SET wa_code = %s WHERE scat_id = %s", [request.form["wa"].upper(), request.form["scat_id"]]
    )

    connection.commit()
    return redirect(f"/view_scat/{request.form['scat_id']}")


@app.route("/view_scat/<scat_id>")
@fn.check_login
def view_scat(scat_id):
    """
    Display scat info
    """

    scat_color = params["scat_color"]
    transect_color = params["transect_color"]

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute(
        (
            "SELECT *, "
            "(SELECT genotype_id FROM wa_scat_dw WHERE wa_code=scats.wa_code LIMIT 1) AS genotype_id2, "
            "(SELECT path_id FROM paths WHERE path_id = scats.path_id) AS path_id_verif, "
            "(SELECT snowtrack_id FROM snow_tracks WHERE snowtrack_id = scats.snowtrack_id) AS snowtrack_id_verif, "
            "CASE "
            "WHEN (SELECT lower(mtdna) FROM wa_scat_dw WHERE wa_code=scats.wa_code LIMIT 1) LIKE '%%wolf%%' THEN 'C1' "
            "ELSE scats.scalp_category "
            "END, "
            "ST_AsGeoJSON(st_transform(geometry_utm, 4326)) AS scat_lonlat, "
            "ROUND(st_x(st_transform(geometry_utm, 4326))::numeric, 6) as longitude, "
            "ROUND(st_y(st_transform(geometry_utm, 4326))::numeric, 6) as latitude "
            "FROM scats "
            "WHERE scat_id = %s"
        ),
        [scat_id],
    )

    results = cursor.fetchone()
    if results is None:
        return f"Scat {scat_id} not found"
    else:
        results = dict(results)

    scat_geojson = json.loads(results["scat_lonlat"])

    scat_feature = {
        "geometry": dict(scat_geojson),
        "type": "Feature",
        "properties": {"popupContent": f"Scat ID: {scat_id}"},
        "id": scat_id,
    }

    scat_features = [scat_feature]
    center = f"{results['latitude']}, {results['longitude']}"

    # transect
    if results["path_id"]:
        # Systematic sampling
        transect_id = results["path_id"].split("|")[0]

        cursor.execute(
            (
                "SELECT ST_AsGeoJSON(st_transform(multilines, 4326)) AS transect_geojson "
                "FROM transects WHERE transect_id = %s"
            ),
            [transect_id],
        )
        transect = cursor.fetchone()

        if transect is not None:

            transect_geojson = json.loads(transect["transect_geojson"])

            transect_feature = {
                "type": "Feature",
                "geometry": dict(transect_geojson),
                "properties": {
                    "popupContent": f"""Transect ID: <a href="/view_transect/{transect_id}">{transect_id}</a>"""
                },
                "id": 1,
            }
            transect_features = [transect_feature]
        else:
            transect_id = ""
            transect_features = []

    else:
        # opportunistic sampling
        transect_id = ""
        transect_features = []

    return render_template(
        "view_scat.html",
        header_title=f"Scat ID: {scat_id}",
        results=results,
        transect_id=transect_id,
        map=Markup(
            fn.leaflet_geojson2(
                {
                    "scats": scat_features,
                    "scats_color": scat_color,
                    "transects": transect_features,
                    "transects_color": transect_color,
                    "center": center,
                }
            )
        ),
        scat_color=params["scat_color"],
        dead_wolf_color=params["dead_wolf_color"],
        transect_color=params["transect_color"],
        track_color=params["track_color"],
    )


@app.route("/plot_all_scats")
@fn.check_login
def plot_all_scats():
    """
    plot all scats
    """

    scats_color = params["scat_color"]

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT scat_id, ST_AsGeoJSON(st_transform(geometry_utm, 4326)) AS scat_lonlat FROM scats")

    scat_features = []

    tot_min_lat, tot_min_lon = 90, 90
    tot_max_lat, tot_max_lon = -90, -90

    for row in cursor.fetchall():
        scat_geojson = json.loads(row["scat_lonlat"])

        # bounding box
        lon, lat = scat_geojson["coordinates"]

        tot_min_lat = min([tot_min_lat, lat])
        tot_max_lat = max([tot_max_lat, lat])
        tot_min_lon = min([tot_min_lon, lon])
        tot_max_lon = max([tot_max_lon, lon])

        scat_feature = {
            "geometry": dict(scat_geojson),
            "type": "Feature",
            "properties": {
                "popupContent": f"""Scat ID: <a href="/view_scat/{row['scat_id']}" target="_blank">{row['scat_id']}</a>""",
            },
            "id": row["scat_id"],
        }

        scat_features.append(dict(scat_feature))

    return render_template(
        "plot_all_scats.html",
        header_title="Plot of scats",
        map=Markup(
            fn.leaflet_geojson2(
                {
                    "scats": scat_features,
                    "scats_color": scats_color,
                    "fit": [[tot_min_lat, tot_min_lon], [tot_max_lat, tot_max_lon]],
                }
            )
        ),
        scat_color=params["scat_color"],
        dead_wolf_color=params["dead_wolf_color"],
        transect_color=params["transect_color"],
        track_color=params["track_color"],
    )


@app.route("/plot_all_scats_markerclusters")
@fn.check_login
def plot_all_scats_markerclusters():
    """
    plot all scats using the markercluster plugin
    see https://github.com/Leaflet/Leaflet.markercluster#usage
    """

    scats_color = params["scat_color"]

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT scat_id, ST_AsGeoJSON(st_transform(geometry_utm, 4326)) AS scat_lonlat FROM scats")

    scat_features = []

    tot_min_lat, tot_min_lon = 90, 90
    tot_max_lat, tot_max_lon = -90, -90

    for row in cursor.fetchall():
        scat_geojson = json.loads(row["scat_lonlat"])

        # bounding box
        lon, lat = scat_geojson["coordinates"]

        tot_min_lat = min([tot_min_lat, lat])
        tot_max_lat = max([tot_max_lat, lat])
        tot_min_lon = min([tot_min_lon, lon])
        tot_max_lon = max([tot_max_lon, lon])

        scat_feature = {
            "geometry": dict(scat_geojson),
            "type": "Feature",
            "properties": {
                "popupContent": f"""Scat ID: <a href="/view_scat/{row['scat_id']}" target="_blank">{row['scat_id']}</a>""",
            },
            "id": row["scat_id"],
        }

        scat_features.append(dict(scat_feature))

    return render_template(
        "plot_all_scats.html",
        header_title="Plot of scats",
        map=Markup(
            fn.leaflet_geojson3(
                {
                    "scats": scat_features,
                    "scats_color": scats_color,
                    "fit": [[tot_min_lat, tot_min_lon], [tot_max_lat, tot_max_lon]],
                }
            )
        ),
    )


@app.route("/scats_list")
@fn.check_login
def scats_list():
    """
    Display all scats
    """

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute("SELECT COUNT(scat_id) AS n_scats FROM scats")
    n_scats = cursor.fetchone()["n_scats"]

    cursor.execute(
        (
            "SELECT *,"
            "(SELECT genotype_id FROM wa_scat_dw WHERE wa_code=scats.wa_code LIMIT 1) AS genotype_id2, "
            "CASE "
            "WHEN (SELECT lower(mtdna) FROM wa_scat_dw WHERE wa_code=scats.wa_code LIMIT 1) LIKE '%wolf%' THEN 'C1' "
            "ELSE scats.scalp_category "
            "END "
            "FROM scats "
            "ORDER BY scat_id"
        )
    )

    return render_template("scats_list.html", header_title="List of scats", n_scats=n_scats, results=cursor.fetchall())


@app.route("/export_scats")
@fn.check_login
def export_scats():
    """
    export all scats in XLSX
    """

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute(
        (
            "SELECT *,"
            "(SELECT genotype_id FROM wa_scat_dw WHERE wa_code=scats.wa_code LIMIT 1) AS genotype_id2, "
            "CASE "
            "WHEN (SELECT lower(mtdna) FROM wa_scat_dw WHERE wa_code=scats.wa_code LIMIT 1) LIKE '%wolf%' THEN 'C1' "
            "ELSE scats.scalp_category "
            "END "
            "FROM scats "
            "ORDER BY scat_id"
        )
    )

    file_content = scats_export.export_scats(cursor.fetchall())

    response = make_response(file_content, 200)
    response.headers["Content-type"] = "application/application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    response.headers["Content-disposition"] = "attachment; filename=scats.xlsx"

    return response


@app.route("/new_scat", methods=("GET", "POST"))
@fn.check_login
def new_scat():
    def not_valid(msg):
        # default values
        default_values = {}
        for k in request.form:
            default_values[k] = request.form[k]

        flash(fn.alert_danger(f"<b>{msg}</b>"))

        return render_template(
            "new_scat.html",
            header_title="New scat",
            title="New scat",
            action=f"/new_scat",
            form=form,
            default_values=default_values,
        )

    if request.method == "GET":

        form = Scat()

        # get id of all paths
        form.path_id.choices = [("", "")] + [(x, x) for x in fn.all_path_id()]
        # get id of all snow tracks
        form.snowtrack_id.choices = [("", "")] + [(x, x) for x in fn.all_snow_tracks_id()]

        return render_template(
            "new_scat.html",
            header_title="New scat",
            title="New scat",
            action=f"/new_scat",
            form=form,
            default_values={"coord_zone": "32N"},
        )

    if request.method == "POST":

        form = Scat(request.form)

        # get id of all transects
        form.path_id.choices = [("", "")] + [(x, x) for x in fn.all_path_id()]

        # get id of all snow tracks
        form.snowtrack_id.choices = [("", "")] + [(x, x) for x in fn.all_snow_tracks_id()]

        if form.validate():

            # date
            try:
                year = int(request.form["scat_id"][1 : 2 + 1]) + 2000
                month = int(request.form["scat_id"][3 : 4 + 1])
                day = int(request.form["scat_id"][5 : 6 + 1])
                date = f"{year:04}-{month:02}-{day:02}"
            except Exception:
                return not_valid("The scat ID value is not correct")

            # path id
            # if "|" not in request.form["path_id"]:
            #    return not_valid("The path ID does not have a correct value (must be XX_NN YYYY-MM-DD)")
            path_id = request.form["path_id"].split(" ")[0] + "|" + date[2:].replace("-", "")

            # region
            if len(request.form["province"]) == 2:
                province = request.form["province"].upper()
                scat_region = fn.get_region(request.form["province"])
            else:
                province = fn.province_name2code(request.form["province"])
                scat_region = fn.get_region(province)

            # test the UTM to lat long conversion to validate the UTM coordiantes
            try:
                _ = utm.to_latlon(int(request.form["coord_east"]), int(request.form["coord_north"]), 32, "N")
            except Exception:
                return not_valid("Error in UTM coordinates")

            connection = fn.get_connection()
            cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

            sql = (
                "INSERT INTO scats (scat_id, date, sampling_season, sampling_type, path_id, snowtrack_id, "
                "location, municipality, province, region, "
                "deposition, matrix, collected_scat, scalp_category, "
                "coord_east, coord_north, coord_zone, "
                "observer, institution,"
                "geometry_utm) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            )
            cursor.execute(
                sql,
                [
                    request.form["scat_id"],
                    date,
                    fn.sampling_season(date),
                    request.form["sampling_type"],
                    path_id,
                    request.form["snowtrack_id"],
                    request.form["location"],
                    request.form["municipality"],
                    province,
                    scat_region,
                    request.form["deposition"],
                    request.form["matrix"],
                    request.form["collected_scat"],
                    request.form["scalp_category"],
                    request.form["coord_east"],
                    request.form["coord_north"],
                    "32N",
                    request.form["observer"],
                    request.form["institution"],
                    f"SRID=32632;POINT({request.form['coord_east']} {request.form['coord_north']})",
                ],
            )

            connection.commit()

            return redirect("/scats_list")
        else:
            return not_valid("Some values are not set or are wrong. Please check and submit again")


@app.route("/edit_scat/<scat_id>", methods=("GET", "POST"))
@fn.check_login
def edit_scat(scat_id):
    """
    Let user edit a scat
    """

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    def not_valid(form, msg):
        # default values
        default_values = {}
        for k in request.form:
            default_values[k] = request.form[k]

        flash(Markup(f'<div class="alert alert-danger" role="alert"><b>{msg}</b></div>'))

        return render_template(
            "new_scat.html",
            header_title=f"Edit scat {scat_id}",
            title="Edit scat",
            action=f"/edit_scat/{scat_id}",
            form=form,
            default_values=default_values,
        )

    if request.method == "GET":

        cursor.execute("SELECT * FROM scats WHERE scat_id = %s", [scat_id])
        default_values = cursor.fetchone()
        if default_values["notes"] is None:
            default_values["notes"] = ""

        # convert convert XX_NN|YYMMDD to XX_NN YYYY-MM-DD
        if "|" in default_values["path_id"]:
            transect_id, date = default_values["path_id"].split("|")
            date = f"20{date[:2]}-{date[2:4]}-{date[4:]}"
            default_values["path_id"] = f"{transect_id} {date}"

        form = Scat(
            path_id=default_values["path_id"],
            snowtrack_id=default_values["snowtrack_id"],
            sampling_type=default_values["sampling_type"],
            deposition=default_values["deposition"],
            matrix=default_values["matrix"],
            collected_scat=default_values["collected_scat"],
            scalp_category=default_values["scalp_category"],
        )

        # get id of all paths
        form.path_id.choices = [("", "")] + [(x, x) for x in fn.all_path_id()]

        # get id of all snow tracks
        all_tracks = [("", "")] + [(x, x) for x in fn.all_snow_tracks_id()]
        # check if current track_id is in the list of all_tracks

        # print((default_values["snowtrack_id"], default_values["snowtrack_id"]) in all_tracks)

        if (default_values["snowtrack_id"], default_values["snowtrack_id"]) not in all_tracks:
            # add current track_id to list
            all_tracks = [(default_values["snowtrack_id"], default_values["snowtrack_id"])] + all_tracks
            # all_tracks.append((default_values["snowtrack_id"], default_values["snowtrack_id"]))

        # print((default_values["snowtrack_id"], default_values["snowtrack_id"]) in all_tracks)
        # print(all_tracks[:10])

        form.snowtrack_id.choices = list(all_tracks)

        # form.snowtrack_id.choices = [("", "")] + [(x, x) for x in fn.all_snow_tracks_id()]

        # default values
        form.notes.data = default_values["notes"]

        return render_template(
            "new_scat.html",
            header_title=f"Edit scat {scat_id}",
            title=f"Edit scat {scat_id}",
            action=f"/edit_scat/{scat_id}",
            form=form,
            default_values=default_values,
        )

    if request.method == "POST":

        print("post")
        print(f'{request.form["snowtrack_id"]}=')

        form = Scat(request.form)

        # get id of all paths
        form.path_id.choices = [("", "")] + [(x, x) for x in fn.all_path_id()]

        # get id of all snow tracks
        all_tracks = [("", "")] + [(x, x) for x in fn.all_snow_tracks_id()]
        all_tracks = [(request.form["snowtrack_id"], request.form["snowtrack_id"])] + all_tracks
        form.snowtrack_id.choices = list(all_tracks)

        # form.snowtrack_id.choices = [("", "")] + [(x, x) for x in fn.all_snow_tracks_id()]

        if not form.validate():
            return not_valid(form, "Some values are not set or are wrong. Please check and submit again")

        # check if scat id already exists
        if scat_id != request.form["scat_id"]:
            cursor.execute("SELECT scat_id FROM scats WHERE scat_id = %s", [request.form["scat_id"]])
            if len(cursor.fetchall()):
                return not_valid(
                    form,
                    (
                        f"Another sample has the same scat ID (<b>{request.form['scat_id']}</b>). "
                        "Please check and submit again"
                    ),
                )

        # date
        try:
            year = int(request.form["scat_id"][1 : 2 + 1]) + 2000
            month = int(request.form["scat_id"][3 : 4 + 1])
            day = int(request.form["scat_id"][5 : 6 + 1])
            date = f"{year}-{month:02}-{day:02}"
        except Exception:
            return not_valid("The scat_id value is not correct")

        # path id
        if request.form["sampling_type"] == "Systematic":
            # convert XX_NN YYYY-MM-DD to XX_NN|YYMMDD
            path_id = request.form["path_id"].split(" ")[0] + "|" + date[2:].replace("-", "")
        else:
            path_id = ""

        # region
        if len(request.form["province"]) == 2:
            province = request.form["province"].upper()
            scat_region = fn.get_region(request.form["province"])
        else:
            province = fn.province_name2code(request.form["province"])
            scat_region = fn.get_region(province)

        # check UTM coord conversion
        try:
            coord_latlon = utm.to_latlon(int(request.form["coord_east"]), int(request.form["coord_north"]), 32, "N")
        except Exception:
            return not_valid(form, "The UTM coordinates are not valid. Please check and submit again")

        # check if WA code exists for another sample
        if request.form["wa_code"]:
            cursor.execute(
                ("SELECT sample_id FROM wa_scat_dw WHERE sample_id != %s AND wa_code = %s"),
                [scat_id, request.form["wa_code"]],
            )
            if len(cursor.fetchall()):
                return not_valid(
                    form,
                    (
                        f"Another sample has the same WA code ({request.form['wa_code']}). "
                        "Please check and submit again"
                    ),
                )

        sql = (
            "UPDATE scats SET "
            " scat_id = %s, "
            " wa_code = %s,"
            " date = %s,"
            " sampling_season = %s,"
            " sampling_type = %s,"
            " path_id = %s, "
            " snowtrack_id = %s, "
            " location = %s, "
            " municipality = %s, "
            " province = %s, "
            " region = %s, "
            " deposition = %s, "
            " matrix = %s, "
            " collected_scat = %s, "
            " scalp_category = %s, "
            " coord_east = %s, "
            " coord_north = %s, "
            #  coord_zone = %s, "
            " observer = %s, "
            " institution = %s, "
            " notes = %s, "
            " geometry_utm = %s "
            "WHERE scat_id = %s"
        )
        cursor.execute(
            sql,
            [
                request.form["scat_id"],
                request.form["wa_code"],
                date,
                fn.sampling_season(date),
                request.form["sampling_type"],
                path_id,
                request.form["snowtrack_id"],
                request.form["location"],
                request.form["municipality"],
                province,
                scat_region,
                request.form["deposition"],
                request.form["matrix"],
                request.form["collected_scat"],
                request.form["scalp_category"],
                request.form["coord_east"],
                request.form["coord_north"],  # request.form["coord_zone"],
                request.form["observer"],
                request.form["institution"],
                request.form["notes"],
                f"SRID=32632;POINT({request.form['coord_east']} {request.form['coord_north']})",
                scat_id,
            ],
        )

        connection.commit()

        return redirect(f"/view_scat/{request.form['scat_id']}")


@app.route("/del_scat/<scat_id>")
@fn.check_login
def del_scat(scat_id):
    """
    Delete scat
    """
    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("DELETE FROM scats WHERE scat_id = %(scat_id)s", {"scat_id": scat_id})
    connection.commit()
    return redirect("/scats_list")


@app.route("/set_path_id/<scat_id>/<path_id>")
@fn.check_login
def set_path_id(scat_id, path_id):
    """
    Set path_id for scat
    """
    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute(
        "UPDATE scats SET path_id = %(path_id)s WHERE scat_id = %(scat_id)s", {"path_id": path_id, "scat_id": scat_id}
    )
    connection.commit()

    return redirect("/static/systematic_scats_transects_location.html")


@app.route(
    "/load_scats_xlsx",
    methods=(
        "GET",
        "POST",
    ),
)
@fn.check_login
def load_scats_xlsx():

    if request.method == "GET":
        return render_template("load_scats_xlsx.html", header_title="Load scats from XLSX/ODS file")

    if request.method == "POST":

        new_file = request.files["new_file"]

        # check file extension
        if pl.Path(new_file.filename).suffix.upper() not in params["excel_allowed_extensions"]:
            flash(
                fn.alert_danger(
                    "The uploaded file does not have an allowed extension (must be <b>.xlsx</b> or <b>.ods</b>)"
                )
            )
            return redirect(f"/load_scats_xlsx")

        try:
            filename = str(uuid.uuid4()) + str(pl.Path(new_file.filename).suffix.upper())
            new_file.save(pl.Path(params["upload_folder"]) / pl.Path(filename))
        except Exception:
            flash(fn.alert_danger("Error with the uploaded file") + f"({error_info(sys.exc_info())})")
            return redirect(f"/load_scats_xlsx")

        r, msg, all_data, _, _ = scats_import.extract_data_from_xlsx(filename)
        if r:
            flash(Markup(f"File name: <b>{new_file.filename}</b>") + Markup("<hr><br>") + msg)
            return redirect(f"/load_scats_xlsx")

        else:
            # check if scat_id already in DB
            connection = fn.get_connection()
            cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
            scats_list = "','".join([all_data[idx]["scat_id"] for idx in all_data])
            sql = f"SELECT scat_id FROM scats WHERE scat_id IN ('{scats_list}')"
            cursor.execute(sql)
            scats_to_update = [row["scat_id"] for row in cursor.fetchall()]

            return render_template(
                "confirm_load_scats_xlsx.html",
                n_scats=len(all_data),
                n_scats_to_update=scats_to_update,
                all_data=all_data,
                filename=filename,
            )


@app.route("/confirm_load_xlsx/<filename>/<mode>")
@fn.check_login
def confirm_load_xlsx(filename, mode):

    if mode not in ["new", "all"]:
        flash(fn.alert_danger("Error: mode not allowed"))
        return redirect(f"/load_scats_xlsx")

    r, msg, all_data, all_paths, all_tracks = scats_import.extract_data_from_xlsx(filename)
    if r:
        flash(msg)
        return redirect(f"/load_scats_xlsx")

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # check if scat_id already in DB
    scats_list = "','".join([all_data[idx]["scat_id"] for idx in all_data])
    sql = f"select scat_id from scats where scat_id in ('{scats_list}')"
    cursor.execute(sql)
    scats_to_update = [row["scat_id"] for row in cursor.fetchall()]

    sql = (
        "UPDATE scats SET scat_id = %(scat_id)s, "
        "                date = %(date)s,"
        "                wa_code = %(wa_code)s,"
        "                genotype_id = %(genotype_id)s,"
        "                sampling_season = %(sampling_season)s,"
        "                sampling_type = %(sampling_type)s,"
        "                path_id = %(path_id)s, "
        "                snowtrack_id = %(snowtrack_id)s, "
        "                location = %(location)s, "
        "                municipality = %(municipality)s, "
        "                province = %(province)s, "
        "                region = %(region)s, "
        "                deposition = %(deposition)s, "
        "                matrix = %(matrix)s, "
        "                collected_scat = %(collected_scat)s, "
        "                scalp_category = %(scalp_category)s, "
        "                genetic_sample = %(genetic_sample)s, "
        "                coord_east = %(coord_east)s, "
        "                coord_north = %(coord_north)s, "
        "                coord_zone = %(coord_zone)s, "
        "                observer = %(operator)s, "
        "                institution = %(institution)s, "
        # "                geo = %(geo)s, "
        "                geometry_utm = %(geometry_utm)s, "
        "                notes = %(notes)s "
        "WHERE scat_id = %(scat_id)s;"
        "INSERT INTO scats (scat_id, date, wa_code, genotype_id, sampling_season, sampling_type, path_id, snowtrack_id, "
        "location, municipality, province, region, "
        "deposition, matrix, collected_scat, scalp_category, genetic_sample, "
        "coord_east, coord_north, coord_zone, "
        "observer, institution,"
        # "geo, "
        "geometry_utm, notes) "
        "SELECT %(scat_id)s, %(date)s, %(wa_code)s, %(genotype_id)s, "
        " %(sampling_season)s, %(sampling_type)s, %(path_id)s, %(snowtrack_id)s, "
        "%(location)s, %(municipality)s, %(province)s, %(region)s, "
        "%(deposition)s, %(matrix)s, %(collected_scat)s, %(scalp_category)s, %(genetic_sample)s,"
        " %(coord_east)s, %(coord_north)s, %(coord_zone)s, %(operator)s, %(institution)s, "
        # "%(geo)s, "
        "%(geometry_utm)s, %(notes)s "
        "WHERE NOT EXISTS (SELECT 1 FROM scats WHERE scat_id = %(scat_id)s)"
    )
    count_added = 0
    count_updated = 0
    for idx in all_data:
        data = dict(all_data[idx])

        if mode == "new" and (data["scat_id"] in scats_to_update):
            continue
        if data["scat_id"] in scats_to_update:
            count_updated += 1
        else:
            count_added += 1

        try:
            cursor.execute(
                sql,
                {
                    "scat_id": data["scat_id"].strip(),
                    "date": data["date"],
                    "wa_code": data["wa_code"].strip(),
                    "genotype_id": data["genotype_id"].strip(),
                    "sampling_season": fn.sampling_season(data["date"]),
                    "sampling_type": data["sampling_type"],
                    "path_id": data["path_id"],
                    "snowtrack_id": data["snowtrack_id"].strip(),
                    "location": data["location"].strip(),
                    "municipality": data["municipality"].strip(),
                    "province": data["province"].strip().upper(),
                    "region": data["region"],
                    "deposition": data["deposition"],
                    "matrix": data["matrix"],
                    "collected_scat": data["collected_scat"],
                    "scalp_category": data["scalp_category"].strip(),
                    "genetic_sample": data["genetic_sample"],
                    "coord_east": data["coord_east"],
                    "coord_north": data["coord_north"],
                    "coord_zone": data["coord_zone"].strip(),
                    "operator": data["operator"],
                    "institution": data["institution"],
                    "geo": data["coord_latlon"],
                    "geometry_utm": data["geometry_utm"],
                    "notes": data["notes"],
                },
            )
        except Exception:
            return "An error occured during the loading of scats. Contact the administrator.<br>" + error_info(
                sys.exc_info()
            )

    connection.commit()

    # paths
    if all_paths:
        sql = (
            "UPDATE paths SET path_id = %(path_id)s, "
            "                 transect_id = %(transect_id)s, "
            "                date = %(date)s, "
            "                sampling_season = %(sampling_season)s,"
            "                completeness = %(completeness)s, "
            "                observer = %(operator)s, "
            "                institution = %(institution)s, "
            "                notes = %(notes)s "
            "WHERE path_id = %(path_id)s;"
            "INSERT INTO paths (path_id, transect_id, date, sampling_season, completeness, "
            "observer, institution, notes) "
            "SELECT %(path_id)s, %(transect_id)s, %(date)s, "
            " %(sampling_season)s, %(completeness)s, "
            " %(operator)s, %(institution)s, %(notes)s "
            "WHERE NOT EXISTS (SELECT 1 FROM paths WHERE path_id = %(path_id)s)"
        )
        for idx in all_paths:
            data = dict(all_paths[idx])
            try:
                cursor.execute(
                    sql,
                    {
                        "path_id": data["path_id"],
                        "transect_id": data["transect_id"].strip(),
                        "date": data["date"],
                        "sampling_season": fn.sampling_season(data["date"]),
                        "completeness": data["completeness"],
                        "operator": data["operator"].strip(),
                        "institution": data["institution"].strip(),
                        "notes": data["notes"],
                    },
                )
            except Exception:
                return "An error occured during the loading of paths. Contact the administrator.<br>" + error_info(
                    sys.exc_info()
                )

        connection.commit()

    # snow tracks
    if all_tracks:
        sql = (
            "UPDATE snow_tracks SET snowtrack_id = %(snowtrack_id)s, "
            "                 path_id = %(path_id)s, "
            "                date = %(date)s, "
            "                sampling_season = %(sampling_season)s,"
            "                observer = %(operator)s, "
            "                institution = %(institution)s, "
            "                notes = %(notes)s "
            "WHERE snow_tracks = %(snow_tracks)s;"
            "INSERT INTO snow_tracks (snowtrack_id, path_id, date, "
            "sampling_season,  "
            "observer, institution, notes) "
            "SELECT %(snowtrack_id)s, %(path_id)s, %(date)s, "
            "       %(sampling_season)s, "
            "       %(operator)s, %(institution)s, %(notes)s "
            "WHERE NOT EXISTS (SELECT 1 FROM snow_tracks WHERE snowtrack_id = %(snowtrack_id)s)"
        )
        for idx in all_tracks:
            data = dict(all_paths[idx])

            try:
                cursor.execute(
                    sql,
                    {
                        "path_id": data["path_id"],
                        "snowtrack_id": data["snowtrack_id"].strip(),
                        "date": data["date"],
                        "sampling_season": fn.sampling_season(data["date"]),
                        "operator": data["operator"].strip(),
                        "institution": data["institution"].strip(),
                        "notes": data["notes"],
                    },
                )
            except Exception:
                return "An error occured during the loading of tracks. Contact the administrator.<br>" + error_info(
                    sys.exc_info()
                )

        connection.commit()

    msg = f"XLSX/ODS file successfully loaded. {count_added} scats added, {count_updated} scats updated."
    flash(fn.alert_success(msg))

    return redirect(f"/scats")


@app.route("/systematic_scats_transect_location")
@fn.check_login
def systematic_scats_transect_location():
    """
    Create file with locations for systematic scats

    !require the check_systematic_scats_transect_location.py script
    """

    _ = subprocess.Popen(["python3", "check_systematic_scats_transect_location.py"])

    time.sleep(2)

    flash(fn.alert_danger(f"The Check location for scats results will be available soon.<br>Please wait for 5 min"))

    return redirect("/scats")
