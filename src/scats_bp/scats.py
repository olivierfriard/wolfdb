"""
WolfDB web service
(c) Olivier Friard

flask blueprint for scats management
"""

import flask
from flask import render_template, redirect, request, flash, make_response, session
from markupsafe import Markup
from sqlalchemy import text


from .scat_form import Scat
import functions as fn
import utm
import json
import pathlib as pl
import datetime as dt

import uuid
import os
import sys
import subprocess
import datetime
from . import scats_export, scats_import

from config import config


app = flask.Blueprint("scats", __name__, template_folder="templates", static_url_path="/static")

params = config()

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


@app.route("/wa_form", methods=("POST",))
@fn.check_login
def wa_form():
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
    with fn.conn_alchemy().connect() as con:
        con.execute(
            text("UPDATE scats SET wa_code = :wa_code WHERE scat_id = :scat_id"),
            {"wa_code": request.form["wa"].upper(), "scat_id": request.form["scat_id"]},
        )

    return redirect(f"/view_scat/{request.form['scat_id']}")


@app.route("/view_scat/<path:scat_id>")
@fn.check_login
def view_scat(scat_id):
    """
    Display scat info
    """

    session["view_scat_id"] = scat_id

    scat_color = params["scat_color"]
    transect_color = params["transect_color"]

    with fn.conn_alchemy().connect() as con:
        results = (
            con.execute(
                text(
                    "SELECT *, "
                    "(SELECT genotype_id FROM wa_scat_dw_mat WHERE wa_code=scats.wa_code LIMIT 1) AS genotype_id, "
                    "(SELECT path_id FROM paths WHERE path_id = scats.path_id) AS path_id_verif, "
                    "(SELECT snowtrack_id FROM snow_tracks WHERE snowtrack_id = scats.snowtrack_id) AS snowtrack_id_verif, "
                    "CASE "
                    "WHEN (SELECT lower(mtdna) FROM wa_scat_dw_mat WHERE wa_code=scats.wa_code LIMIT 1) LIKE '%wolf%' THEN 'C1' "
                    "ELSE scats.scalp_category "
                    "END, "
                    "ST_AsGeoJSON(st_transform(geometry_utm, 4326)) AS scat_lonlat, "
                    "ROUND(st_x(st_transform(geometry_utm, 4326))::numeric, 6) as longitude, "
                    "ROUND(st_y(st_transform(geometry_utm, 4326))::numeric, 6) as latitude "
                    "FROM scats "
                    "WHERE scat_id = :scat_id"
                ),
                {"scat_id": scat_id},
            )
            .mappings()
            .fetchone()
        )

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
        with fn.conn_alchemy().connect() as con:
            transect = (
                con.execute(
                    text(
                        "SELECT ST_AsGeoJSON(st_transform(multilines, 4326)) AS transect_geojson "
                        "FROM transects WHERE transect_id = :transect_id"
                    ),
                    {"transect_id": transect_id},
                )
                .mappings()
                .fetchone()
            )

        if transect is not None:
            transect_geojson = json.loads(transect["transect_geojson"])

            transect_feature = {
                "type": "Feature",
                "geometry": dict(transect_geojson),
                "properties": {"popupContent": f"""Transect ID: <a href="/view_transect/{transect_id}">{transect_id}</a>"""},
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
            fn.leaflet_geojson(
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


'''
@app.route("/plot_all_scats_old")
@fn.check_login
def plot_all_scats():
    """
    plot all scats
    """

    scats_color = params["scat_color"]

    with fn.conn_alchemy().connect() as con:
        scat_features: list = []

        tot_min_lat, tot_min_lon = 90, 90
        tot_max_lat, tot_max_lon = -90, -90

        count_scats: int = 0

        for row in (
            con.execute(text("SELECT scat_id, ST_AsGeoJSON(st_transform(geometry_utm, 4326)) AS scat_lonlat FROM scats ")).mappings().all()
        ):
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
            count_scats += 1

        print(count_scats)

        return render_template(
            "plot_all_scats.html",
            header_title="Plot of scats",
            map=Markup(
                fn.leaflet_geojson(
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
            count_scats=count_scats,
        )
'''


@app.route("/plot_all_scats")
@fn.check_login
def plot_all_scats_markerclusters():
    """
    plot all scats using the markercluster plugin
    see https://github.com/Leaflet/Leaflet.markercluster#usage
    """

    scats_color = params["scat_color"]

    with fn.conn_alchemy().connect() as con:
        scat_features: list = []

        tot_min_lat, tot_min_lon = 90, 90
        tot_max_lat, tot_max_lon = -90, -90
        count_scats: int = 0
        for row in (
            con.execute(
                text(
                    "SELECT scat_id,"
                    "ST_X(st_transform(geometry_utm, 4326)) as longitude, "
                    "ST_Y(st_transform(geometry_utm, 4326)) as latitude "
                    "FROM scats "
                    "WHERE date BETWEEN :start_date AND :end_date"
                ),
                {
                    "start_date": session["start_date"],
                    "end_date": session["end_date"],
                },
            )
            .mappings()
            .all()
        ):
            # bounding box
            tot_min_lat = min([tot_min_lat, row["latitude"]])
            tot_max_lat = max([tot_max_lat, row["latitude"]])
            tot_min_lon = min([tot_min_lon, row["longitude"]])
            tot_max_lon = max([tot_max_lon, row["longitude"]])

            scat_feature = {
                "geometry": {
                    "type": "Point",
                    "coordinates": [row["longitude"], row["latitude"]],
                },
                "type": "Feature",
                "properties": {
                    "popupContent": f"""Scat ID: <a href="/view_scat/{row["scat_id"]}" target="_blank">{row["scat_id"]}</a>""",
                },
                "id": row["scat_id"],
            }

            scat_features.append(dict(scat_feature))
            count_scats += 1

        return render_template(
            "plot_all_scats.html",
            header_title="Plot of scats",
            map=Markup(
                fn.leaflet_markercluster_geojson(
                    {
                        "scats": scat_features,
                        "scats_color": scats_color,
                        "fit": [[tot_min_lat, tot_min_lon], [tot_max_lat, tot_max_lon]],
                    }
                )
            ),
            scat_color=params["scat_color"],
            count_scats=count_scats,
        )


@app.route(
    "/scats_list_limit/<int:offset>/<limit>",
    methods=(
        "GET",
        "POST",
    ),
)
@fn.check_login
def scats_list_limit(offset: int, limit: int | str):
    """
    Display list of scats
    """

    # test limit value: must be ALL or int
    if limit != "ALL":
        try:
            limit = int(limit)
        except Exception:
            return "An error has occured. Check the URL"

    if limit == "ALL":
        offset = 0

    # check if wa code is specified to scroll the table
    if "view_scat_id" in session:
        view_scat_id = session["view_scat_id"]
        del session["view_scat_id"]
    else:
        view_scat_id = None

    with fn.conn_alchemy().connect() as con:
        sql_search = text(
            (
                "SELECT *, count(*) OVER() AS n_scats FROM scats_list_mat WHERE ("
                "scat_id ILIKE :search "
                "OR date::text ILIKE :search "
                "OR sampling_type ILIKE :search "
                "OR sample_type ILIKE :search "
                "OR wa_code ILIKE :search "
                "OR genotype_id2 ILIKE :search "
                "OR location ILIKE :search "
                "OR municipality ILIKE :search "
                "OR province ILIKE :search "
                "OR region ILIKE :search "
                "OR observer ILIKE :search "
                "OR institution ILIKE :search "
                "OR notes ILIKE :search "
                ") "
                "AND (date BETWEEN :start_date AND :end_date) "
            )
        )

        sql_all = text(
            (
                "SELECT *, count(*) OVER() AS n_scats FROM scats_list_mat WHERE date BETWEEN :start_date AND :end_date "
                f"LIMIT {limit} "
                f"OFFSET {offset}"
            )
        )

        if request.method == "POST":
            offset = 0
            limit = "ALL"
            if request.args.get("search") is None:
                search_term = request.form["search"].strip()
            else:
                search_term = request.args.get("search")

            results = (
                con.execute(
                    sql_search,
                    {
                        "search": f"%{search_term}%",
                        "start_date": session["start_date"],
                        "end_date": session["end_date"],
                    },
                )
                .mappings()
                .all()
            )

        elif request.method == "GET":
            if request.args.get("search") is not None:
                search_term: str = request.args.get("search").strip()
            else:
                search_term: str = ""

            results = (
                con.execute(
                    sql_all if not search_term else sql_search,
                    {
                        "search": f"%{search_term}%",
                        "start_date": session["start_date"],
                        "end_date": session["end_date"],
                    },
                )
                .mappings()
                .all()
            )

    session["url_scats_list"] = f"/scats_list_limit/{offset}/{limit}?search={search_term}"
    if "url_wa_list" in session:
        del session["url_wa_list"]

    if results:
        title = f"List of {results[0]['n_scats']} scat{'s' if results[0]['n_scats'] > 1 else ''}"
    else:
        title = "No scat found"

    return render_template(
        "scats_list_limit.html",
        title=title,
        header_title="List of scats",
        n_scats=results[0]["n_scats"] if results else 0,
        limit=limit,
        offset=offset,
        results=results,
        search_term=search_term,
        view_scat_id=view_scat_id,
    )


@app.route("/export_scats")
@fn.check_login
def export_scats():
    """
    export all scats in XLSX
    """

    with fn.conn_alchemy().connect() as con:
        file_content = scats_export.export_scats(
            con.execute(
                text("SELECT * FROM scats_list_mat WHERE date BETWEEN :start_date AND :end_date"),
                {"start_date": session["start_date"], "end_date": session["end_date"]},
            )
            .mappings()
            .all()
        )

    response = make_response(file_content, 200)
    response.headers["Content-type"] = "application/application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    response.headers["Content-disposition"] = f"attachment; filename=scats_{datetime.datetime.now():%Y-%m-%d_%H%M%S}.xlsx"

    return response


@app.route("/new_scat", methods=("GET", "POST"))
@fn.check_login
def new_scat():
    """
    let user insert a new scat manually
    """

    def not_valid(msg):
        # default values
        default_values: dict = {}
        for k in request.form:
            default_values[k] = request.form[k]

        flash(fn.alert_danger(f"<b>{msg}</b>"))

        return render_template(
            "new_scat.html",
            header_title="New scat",
            title="New scat",
            action="/new_scat",
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
            action="/new_scat",
            form=form,
            default_values={"coord_zone": params["default_utm_zone"]},
        )

    if request.method == "POST":
        form = Scat(request.form)

        # get id of all transects
        form.path_id.choices = [("", "")] + [(x, x) for x in fn.all_path_id()]

        # get id of all snow tracks
        form.snowtrack_id.choices = [("", "")] + [(x, x) for x in fn.all_snow_tracks_id()]

        if not form.validate():
            return not_valid("Some values are not set or are wrong. Please check and submit again")
        # date
        """ DISABLED
        try:
            year = int(request.form["scat_id"][1 : 2 + 1]) + 2000
            month = int(request.form["scat_id"][3 : 4 + 1])
            day = int(request.form["scat_id"][5 : 6 + 1])
            date = f"{year:04}-{month:02}-{day:02}"
            try:
                datetime.datetime.strptime(date, "%Y-%m-%d")
            except Exception:
                return not_valid("The date of the track ID is not valid. Use the YYMMDD format")

        except Exception:
            return not_valid("The scat ID value is not correct")
        """
        # date
        date = request.form["date"]

        # path id
        path_id = request.form["path_id"].split(" ")[0] + "|" + date[2:].replace("-", "")

        # check province code
        province_code = fn.check_province_code(request.form["province"])
        if province_code is None:
            # check province name
            province_code = fn.province_name2code(request.form["province"])
            if province_code is None:
                return not_valid("The province was not found")

        scat_region = fn.province_code2region(province_code)

        # test the UTM to lat long conversion to validate the UTM coordiantes
        try:
            _ = utm.to_latlon(
                int(request.form["coord_east"]),
                int(request.form["coord_north"]),
                int(request.form["coord_zone"]),
                request.form["hemisphere"],
            )
        except Exception:
            return not_valid("Error in UTM coordinates")

        with fn.conn_alchemy().connect() as con:
            sql = text(
                "INSERT INTO scats (scat_id, wa_code, ispra_id, date, sampling_season, sampling_type, path_id, snowtrack_id, "
                "location, municipality, province, region, "
                "deposition, matrix, collected_scat, scalp_category, "
                "coord_east, coord_north, coord_zone, "
                "observer, institution,"
                "geometry_utm) "
                "VALUES (:scat_id, :wa_code, :ispra_id, :date, :sampling_season, :sampling_type, :path_id, :snowtrack_id, "
                ":location, :municipality, :province, :region, "
                ":deposition, :matrix, :collected_scat, :scalp_category, "
                ":coord_east, :coord_north, :coord_zone, ST_GeomFromText(:wkt_point, :srid),"
                ":observer, :institution, "
                "ST_GeomFromText(:wkt_point, :srid))"
            )
            con.execute(
                sql,
                {
                    "scat_id": request.form["scat_id"],
                    "wa_code": request.form["wa_code"],
                    "ispra_id": request.form["ispra_id"],
                    "date": date,
                    "sampling_season": fn.sampling_season(date),
                    "sampling_type": request.form["sampling_type"],
                    "path_id": path_id,
                    "snowtrack_id": request.form["snowtrack_id"],
                    "location": request.form["location"],
                    "municipality": request.form["municipality"],
                    "province": province_code,
                    "region": scat_region,
                    "deposition": request.form["deposition"],
                    "matrix": request.form["matrix"],
                    "collected_scat": request.form["collected_scat"],
                    "scalp_category": request.form["scalp_category"],
                    "coord_east": request.form["coord_east"],
                    "coord_north": request.form["coord_north"],
                    "coord_zone": request.form["coord_zone"] + request.form["hemisphere"],
                    "observer": request.form["observer"],
                    "institution": request.form["institution"],
                    "wkt_point": f"POINT({request.form['coord_east']} {request.form['coord_north']})",
                    "srid": int(request.form["coord_zone"]) + (32600 if request.form["hemisphere"] == "N" else 32700),
                },
            )

        return redirect(f"/view_scat/{request.form['scat_id']}")


@app.route("/edit_scat/<path:scat_id>", methods=("GET", "POST"))
@fn.check_login
def edit_scat(scat_id):
    """
    Let user edit a scat
    """

    def not_valid(form, msg):
        # default values
        default_values: dict = {}
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
        with fn.conn_alchemy().connect() as con:
            default_values = dict(
                con.execute(
                    text("SELECT * FROM scats WHERE scat_id = :scat_id"),
                    {"scat_id": scat_id},
                )
                .mappings()
                .fetchone()
            )

        for field in ("notes", "location", "institution", "ispra_id"):
            if default_values[field] is None:
                default_values[field] = ""

        # convert convert XX_NN|YYMMDD to XX_NN YYYY-MM-DD
        if default_values["path_id"] is None:
            default_path_id = ""
        else:
            if "|" in default_values["path_id"]:
                transect_id, date = default_values["path_id"].split("|")
                date = f"20{date[:2]}-{date[2:4]}-{date[4:]}"
                default_path_id = f"{transect_id} {date}"
            else:
                default_path_id = default_values["path_id"]

        default_values["coord_zone"] = default_values["coord_zone"][:-1]

        form = Scat(
            date=default_values["date"],
            path_id=default_path_id,
            snowtrack_id=default_values["snowtrack_id"],
            sampling_type=default_values["sampling_type"],
            sample_type=default_values["sample_type"],
            deposition=default_values["deposition"],
            matrix=default_values["matrix"],
            collected_scat=default_values["collected_scat"],
            scalp_category=default_values["scalp_category"],
            coord_zone=default_values["coord_zone"],
            hemisphere=default_values["coord_zone"][-1],
        )

        # get id of all paths
        form.path_id.choices = [("", "")] + [(x, x) for x in fn.all_path_id()]

        # get id of all snow tracks
        all_tracks = [("", "")] + [(x, x) for x in fn.all_snow_tracks_id()]
        # check if current track_id is in the list of all_tracks

        # print((default_values["snowtrack_id"], default_values["snowtrack_id"]) in all_tracks)

        if (
            default_values["snowtrack_id"],
            default_values["snowtrack_id"],
        ) not in all_tracks:
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
        form = Scat(request.form)

        # get id of all paths
        form.path_id.choices = [("", "")] + [(x, x) for x in fn.all_path_id()]

        # get id of all snow tracks
        all_tracks = [("", "")] + [(x, x) for x in fn.all_snow_tracks_id()]
        all_tracks = [(request.form["snowtrack_id"], request.form["snowtrack_id"])] + all_tracks
        form.snowtrack_id.choices = list(all_tracks)

        if not form.validate():
            return not_valid(
                form,
                "Some values are not set or are wrong. Please check and submit again",
            )

        with fn.conn_alchemy().connect() as con:
            # check if scat id already exists
            if scat_id != request.form["scat_id"]:
                if len(
                    con.execute(
                        text("SELECT scat_id FROM scats WHERE scat_id = :scat_id"),
                        {"scat_id": request.form["scat_id"]},
                    )
                    .mappings()
                    .all()
                ):
                    return not_valid(
                        form,
                        (f"Another sample has the same scat ID (<b>{request.form['scat_id']}</b>). Please check and submit again"),
                    )

            # check date in scat ID
            """
            DISABLED
            try:
                year = int(request.form["scat_id"][1 : 2 + 1]) + 2000
                month = int(request.form["scat_id"][3 : 4 + 1])
                day = int(request.form["scat_id"][5 : 6 + 1])
                date = f"{year:04}-{month:02}-{day:02}"
                try:
                    datetime.datetime.strptime(date, "%Y-%m-%d")
                except Exception:
                    return not_valid(form,"The date of the track ID is not valid. Use the YYMMDD format")
            except Exception:
                return not_valid(form,"The scat_id value is not correct")
            """

            # path id
            if request.form["sampling_type"] == "Systematic":
                # convert XX_NN YYYY-MM-DD to XX_NN|YYMMDD
                path_id = request.form["path_id"].split(" ")[0] + "|" + date[2:].replace("-", "")
            else:
                path_id = ""

            # check province code
            province_code = fn.check_province_code(request.form["province"])
            if province_code is None:
                # check province name
                province_code = fn.province_name2code(request.form["province"])
                if province_code is None:
                    return not_valid(form, "The province was not found")

            # add region from province code
            scat_region = fn.province_code2region(province_code)

            # check UTM coord conversion
            try:
                _ = utm.to_latlon(
                    int(request.form["coord_east"]),
                    int(request.form["coord_north"]),
                    int(request.form["coord_zone"]),
                    request.form["hemisphere"],
                )

            except Exception:
                return not_valid(
                    form,
                    "The UTM coordinates are not valid. Please check and submit again",
                )

            # check if WA code exists for another sample
            if request.form["wa_code"]:
                if len(
                    con.execute(
                        text("SELECT sample_id FROM wa_scat_dw_mat WHERE sample_id !=:scat_id AND wa_code = :wa_code"),
                        {"scat_id": scat_id, "wa_code": request.form["wa_code"]},
                    )
                    .mappings()
                    .all()
                ):
                    return not_valid(
                        form,
                        (f"Another sample has the same WA code ({request.form['wa_code']}). Please check and submit again"),
                    )

            sql = text(
                "UPDATE scats SET "
                " scat_id = :scat_id, "
                " ispra_id = :ispra_id, "
                " wa_code = :wa_code,"
                " date = :date,"
                " sampling_season = :sampling_season,"
                " sampling_type = :sampling_type,"
                " sample_type = :sample_type,"
                " path_id = :path_id, "
                " snowtrack_id = :snowtrack_id, "
                " location = :location, "
                " municipality = :municipality, "
                " province = :province, "
                " region = :region, "
                " deposition = :deposition, "
                " matrix = :matrix, "
                " collected_scat = :collected_scat, "
                " scalp_category = :scalp_category, "
                " coord_east = :coord_east, "
                " coord_north = :coord_north, "
                " coord_zone = :coord_zone, "
                " observer = :observer, "
                " institution = :institution, "
                " notes = :notes, "
                " geometry_utm = ST_GeomFromText(:wkt_point, :srid) "
                "WHERE scat_id = :scat_id"
            )
            con.execute(
                sql,
                {
                    "scat_id": request.form["scat_id"],
                    "ispra_id": request.form["ispra_id"],
                    "wa_code": request.form["wa_code"],
                    "date": request.form["date"],
                    "sampling_season": fn.sampling_season(request.form["date"]),
                    "sampling_type": request.form["sampling_type"] if request.form["sampling_type"] else None,
                    "sample_type": request.form["sample_type"],
                    "path_id": path_id,
                    "snowtrack_id": request.form["snowtrack_id"],
                    "location": request.form["location"],
                    "municipality": request.form["municipality"],
                    "province": province_code,
                    "region": scat_region,
                    "deposition": request.form["deposition"],
                    "matrix": request.form["matrix"],
                    "collected_scat": request.form["collected_scat"],
                    "scalp_category": request.form["scalp_category"],
                    "coord_east": request.form["coord_east"],
                    "coord_north": request.form["coord_north"],
                    "coord_zone": request.form["coord_zone"] + request.form["hemisphere"],
                    "observer": request.form["observer"],
                    "institution": request.form["institution"],
                    "notes": request.form["notes"],
                    "wkt_point": f"POINT({request.form['coord_east']} {request.form['coord_north']})",
                    "srid": int(request.form["coord_zone"]) + (32600 if request.form["hemisphere"] == "N" else 32700),
                },
            )

        return redirect(f"/view_scat/{request.form['scat_id']}")


@app.route("/del_scat/<path:scat_id>")
@fn.check_login
def del_scat(scat_id):
    """
    Delete scat
    """
    with fn.conn_alchemy().connect() as con:
        con.execute(text("DELETE FROM scats WHERE scat_id = :scat_id"), {"scat_id": scat_id})

    return redirect("/scats_list_limit/0/20")


@app.route("/set_path_id/<scat_id>/<path_id>")
@fn.check_login
def set_path_id(scat_id, path_id):
    """
    Set path_id for scat
    """

    with fn.conn_alchemy().connect() as con:
        con.execute(
            text("UPDATE scats SET path_id = :path_id WHERE scat_id = :scat_id"),
            {"path_id": path_id, "scat_id": scat_id},
        )

    flash(fn.alert_danger("The path ID was updated. "))
    return redirect("/")


@app.route(
    "/load_scats_xlsx",
    methods=(
        "GET",
        "POST",
    ),
)
@fn.check_login
def load_scats_xlsx():
    """
    Select a file for uploading scats from XLSX
    """

    if request.method == "GET":
        return render_template("load_scats_xlsx.html", header_title="Load scats from XLSX/ODS file")

    if request.method == "POST":
        new_file = request.files["new_file"]

        # check file extension
        if pl.Path(new_file.filename).suffix.upper() not in params["excel_allowed_extensions"]:
            flash(fn.alert_danger("The uploaded file does not have an allowed extension (must be <b>.xlsx</b> or <b>.ods</b>)"))
            return redirect("/load_scats_xlsx")

        try:
            filename = str(uuid.uuid4()) + str(pl.Path(new_file.filename).suffix.upper())
            new_file.save(pl.Path(params["upload_folder"]) / pl.Path(filename))
        except Exception:
            flash(fn.alert_danger("Error with the uploaded file") + f"({error_info(sys.exc_info())})")
            return redirect("/load_scats_xlsx")

        r, msg, all_data, _, _ = scats_import.extract_data_from_xlsx(filename)
        if r:
            flash(Markup(f"File name: <b>{new_file.filename}</b>") + Markup("<hr><br>") + msg)
            return redirect("/load_scats_xlsx")

        else:
            # check if scat_id already in DB
            with fn.conn_alchemy().connect() as con:
                scats_list = "','".join([all_data[idx]["scat_id"] for idx in all_data])
                sql = text(f"SELECT scat_id FROM scats WHERE scat_id IN ('{scats_list}')")
                scats_to_update = [row["scat_id"] for row in con.execute(sql).mappings().all()]

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
    """
    Confirm upload of scats from XLSX file
    """

    if mode not in ["new", "all"]:
        flash(fn.alert_danger("Error: mode not allowed"))
        return redirect("/load_scats_xlsx")

    r, msg, all_data, all_paths, all_tracks = scats_import.extract_data_from_xlsx(filename)
    if r:
        flash(msg)
        return redirect("/load_scats_xlsx")

    with fn.conn_alchemy().connect() as con:
        # check if scat_id already in DB
        scats_list = "','".join([all_data[idx]["scat_id"] for idx in all_data])
        sql = text(f"SELECT scat_id FROM scats WHERE scat_id in ('{scats_list}')")

        scats_to_update = [row["scat_id"] for row in con.execute(sql).mappings().all()]

        sql = text(
            "UPDATE scats SET scat_id = :scat_id, "
            "                date = :date,"
            "                wa_code = :wa_code,"
            "                genotype_id = :genotype_id,"
            "                sampling_season = :sampling_season,"
            "                sampling_type = :sampling_type,"
            "                path_id = :path_id, "
            "                snowtrack_id = :snowtrack_id, "
            "                location = :location, "
            "                municipality = :municipality, "
            "                province = :province, "
            "                region = :region, "
            "                deposition = :deposition, "
            "                matrix = :matrix, "
            "                collected_scat = :collected_scat, "
            "                scalp_category = :scalp_category, "
            "                genetic_sample = :genetic_sample, "
            "                coord_east = :coord_east, "
            "                coord_north = :coord_north, "
            "                coord_zone = :coord_zone, "
            "                observer = :operator, "
            "                institution = :institution, "
            # "                geo = %(geo)s, "
            "                geometry_utm = :geometry_utm, "
            "                notes = :notes "
            "WHERE scat_id = :scat_id;"
            "INSERT INTO scats (scat_id, date, wa_code, genotype_id, sampling_season, sampling_type, path_id, snowtrack_id, "
            "location, municipality, province, region, "
            "deposition, matrix, collected_scat, scalp_category, genetic_sample, "
            "coord_east, coord_north, coord_zone, "
            "observer, institution,"
            # "geo, "
            "geometry_utm, notes) "
            "SELECT :scat_id, :date, :wa_code, :genotype_id, "
            ":sampling_season, :sampling_type, :path_id, :snowtrack_id, "
            ":location, :municipality, :province, :region, "
            ":deposition, :matrix, :collected_scat, :scalp_category, :genetic_sample,"
            ":coord_east, :coord_north, :coord_zone, :operator, :institution, "
            # "%(geo)s, "
            ":geometry_utm, :notes "
            "WHERE NOT EXISTS (SELECT 1 FROM scats WHERE scat_id = :scat_id)"
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
                con.execute(
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
                        # "geo": data["coord_latlon"],
                        "geometry_utm": data["geometry_utm"],
                        "notes": data["notes"],
                    },
                )
            except Exception:
                return "An error occured during the loading of scats. Contact the administrator.<br>" + error_info(sys.exc_info())

        # paths
        if all_paths:
            sql = text(
                "UPDATE paths SET path_id = :path_id, "
                "                 transect_id = :transect_id, "
                "                date = :date,"
                "                sampling_season = :sampling_season,"
                "                completeness = :completeness,"
                "                observer = :operator,"
                "                institution = :institution,"
                "                notes = :notes "
                "WHERE path_id = :path_id;"
                "INSERT INTO paths (path_id, transect_id, date, sampling_season, completeness, "
                "observer, institution, notes) "
                "SELECT :path_id, :transect_id, :date,"
                ":sampling_season, :completeness, "
                ":operator, :institution, :notes "
                "WHERE NOT EXISTS (SELECT 1 FROM paths WHERE path_id = :path_id)"
            )
            for idx in all_paths:
                data = dict(all_paths[idx])
                try:
                    con.execute(
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
                    return "An error occured during the loading of paths. Contact the administrator.<br>" + error_info(sys.exc_info())

        # snow tracks
        if all_tracks:
            sql = text(
                "UPDATE snow_tracks SET snowtrack_id = :snowtrack_id, "
                "                 path_id = :path_id, "
                "                date = :date, "
                "                sampling_season = :sampling_season,"
                "                observer = :operator,"
                "                institution = :institution,"
                "                notes = :notes "
                "WHERE snow_tracks = :snow_tracks;"
                "INSERT INTO snow_tracks (snowtrack_id, path_id, date, "
                "sampling_season,  "
                "observer, institution, notes) "
                "SELECT :snowtrack_id, :path_id, :date, "
                "       :sampling_season, "
                "       :operator, :institution, :notes "
                "WHERE NOT EXISTS (SELECT 1 FROM snow_tracks WHERE snowtrack_id = :snowtrack_id)"
            )
            for idx in all_tracks:
                data = dict(all_paths[idx])

                try:
                    con.execute(
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
                    return "An error occured during the loading of tracks. Contact the administrator.<br>" + error_info(sys.exc_info())

        con.execute(text("CALL refresh_materialized_views()"))

    msg = f"XLSX/ODS file successfully loaded. {count_added} scats added, {count_updated} scats updated."
    flash(fn.alert_success(msg))

    return redirect("/scats")


@app.route("/systematic_scats_transect_location")
@fn.check_login
def systematic_scats_transect_location():
    """
    Create file with locations for systematic scats

    !require the check_systematic_scats_transect_location.py script
    """

    _ = subprocess.Popen(
        [
            "python3",
            "check_systematic_scats_transect_location.py",
            session["start_date"],
            session["end_date"],
            str(
                pl.Path(pl.Path(app.static_url_path).name)
                / pl.Path("results")
                / pl.Path(session["email"])
                / pl.Path(
                    (
                        f"location_of_systematic_scats_on_transects_and_tracks"
                        f"_from_{session['start_date']}_to_{session['end_date']}"
                        f"_requested_at_{dt.datetime.now():%Y-%m-%d_%H%M%S}.html"
                    )
                )
            ),
        ]
    )

    return redirect("/my_results")
