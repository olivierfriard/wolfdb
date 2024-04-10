"""
WolfDB web service
(c) Olivier Friard

flask blueprint for tracks management
"""

import flask
from flask import render_template, redirect, request, flash, make_response, session
from markupsafe import Markup
import psycopg2
import psycopg2.extras
from config import config
import sys
import os
import json
import datetime as dt
from . import tracks_import
from . import tracks_export
from .track_form import Track
import functions as fn
import uuid
import pathlib as pl
import time
from sqlalchemy import text


app = flask.Blueprint("tracks", __name__, template_folder="templates", static_url_path="/static")

params = config()
app.debug = params["debug"]


def error_info(exc_info: tuple) -> tuple:
    """
    return details about error
    usage: error_info(sys.exc_info())

    Args:
        sys.exc_info() (tuple):

    Returns:
        tuple: error type, error file name, error line number
    """

    exc_type, exc_obj, exc_tb = exc_info
    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]

    error_type, error_file_name, error_lineno = exc_obj, fname, exc_tb.tb_lineno

    return f"Error {error_type} in {error_file_name} at line #{error_lineno}"


@app.route("/snow_tracks")
@app.route("/tracks")
@fn.check_login
def tracks():
    """
    Tracks home page
    """
    return render_template("tracks.html", header_title="Tracks")


@app.route("/view_snowtrack/<snowtrack_id>")
@app.route("/view_track/<snowtrack_id>")
def view_track(snowtrack_id):
    """
    visualize the track
    """

    with fn.conn_alchemy().connect() as con:
        track = dict(
            (
                con.execute(
                    text(
                        (
                            "SELECT *, "
                            "case when (SELECT lower(mtdna) FROM wa_scat_dw_mat  "
                            " WHERE "
                            "   lower(mtdna) LIKE '%%wolf%%' "
                            "   AND wa_code in (select wa_code from scats WHERE snowtrack_id = t.snowtrack_id)  "
                            "LIMIT 1 "
                            ") LIKE '%%wolf%%' THEN 'C1' "
                            "ELSE t.scalp_category "
                            "END, "
                            "ST_AsGeoJSON(st_transform(multilines, 4326)) AS track_geojson, "
                            "ROUND(st_x(st_transform(geometry_utm, 4326))::numeric, 6) as longitude, "
                            "ROUND(st_y(st_transform(geometry_utm, 4326))::numeric, 6) as latitude, "
                            "ROUND(ST_Length(multilines)) AS track_length "
                            "FROM snow_tracks t WHERE snowtrack_id = :track_id"
                        )
                    ),
                    {"track_id": snowtrack_id},
                )
                .mappings()
                .one()
            )
        )

        if track is None:
            flash(fn.alert_danger(f"<b>Track {snowtrack_id} not found</b>"))
            return redirect("/snowtracks_list")

        # eventually split transect_id
        if track["transect_id"] is not None:
            track["transect_id"] = track["transect_id"].split(";")

        track_features: list = []
        min_lat, max_lat = 90, -90
        min_lon, max_lon = 90, -90

        if track["track_geojson"] is not None:
            has_coordinates = True
            track_geojson = json.loads(track["track_geojson"])

            for line in track_geojson["coordinates"]:
                latitudes = [lat for _, lat in line]
                longitudes = [lon for lon, _ in line]
                min_lat, max_lat = min(latitudes), max(latitudes)
                min_lon, max_lon = min(longitudes), max(longitudes)

            track_feature = {
                "type": "Feature",
                "geometry": dict(track_geojson),
                "properties": {
                    # "style": {"color": color, "fillColor": color, "fillOpacity": 1},
                    "popupContent": f"Track ID: {snowtrack_id}",
                },
                "id": snowtrack_id,
            }
            track_features = [track_feature]
        else:
            has_coordinates = False

        # number of scats
        scats = (
            con.execute(
                text(
                    (
                        "SELECT *,"
                        "(SELECT genotype_id FROM wa_results WHERE wa_code = scats.wa_code) AS genotype_id, "
                        "ST_AsGeoJSON(st_transform(geometry_utm, 4326)) AS scat_lonlat "
                        "FROM scats WHERE snowtrack_id LIKE :snowtrack_id"
                    )
                ),
                {"snowtrack_id": snowtrack_id},
            )
            .mappings()
            .all()
        )

        n_scats = len(scats)
        scat_features: list = []

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
                    "popupContent": (
                        f"""Sample ID: <a href="/view_scat/{row['scat_id']}" target="_blank">{row['scat_id']}</a><br>"""
                        f"""WA code: <a href="/view_wa/{row['wa_code']}" target="_blank">{row['wa_code']}</a><br>"""
                        f"""Genotype ID: <a href="/view_genotype/{row['genotype_id']}" target="_blank">{row['genotype_id']}</a>"""
                    ),
                },
                "id": row["scat_id"],
            }
            scat_features.append(scat_feature)

        return render_template(
            "view_track.html",
            header_title=f"Track ID: {snowtrack_id}",
            results=track,
            has_coordinates=has_coordinates,
            n_scats=n_scats,
            map=Markup(
                fn.leaflet_geojson2(
                    {
                        "scats": scat_features,
                        "scats_color": params["scat_color"],
                        "tracks": track_features,
                        "tracks_color": params["track_color"],
                        "fit": [[min_lat, min_lon], [max_lat, max_lon]],
                    }
                )
            ),
            scat_color=params["scat_color"],
            dead_wolf_color=params["dead_wolf_color"],
            transect_color=params["transect_color"],
            track_color=params["track_color"],
        )


@app.route("/tracks_list")
@app.route("/snowtracks_list")
@fn.check_login
def tracks_list():
    """
    list of tracks
    """

    with fn.conn_alchemy().connect() as con:
        # split transects (more transects can be specified)
        results: list = []
        for row in (
            con.execute(
                text(
                    (
                        "SELECT *, "
                        "CASE "
                        "WHEN (SELECT LOWER(mtdna) FROM wa_scat_dw_mat "
                        " WHERE "
                        "   LOWER(mtdna) LIKE '%%wolf%%' "
                        "   AND wa_code IN (SELECT wa_code FROM scats WHERE snowtrack_id = t.snowtrack_id)  "
                        "LIMIT 1 "
                        ") LIKE '%%wolf%%' THEN 'C1' "
                        "ELSE t.scalp_category "
                        "END "
                        "FROM snow_tracks t "
                        "WHERE date BETWEEN :start_date AND :end_date OR date is NULL "
                        "ORDER BY region ASC, province ASC, date DESC"
                    )
                ),
                {
                    "start_date": session["start_date"],
                    "end_date": session["end_date"],
                },
            )
            .mappings()
            .all()
        ):
            results.append(dict(row))
            if results[-1]["transect_id"] is not None:
                results[-1]["transect_id"] = results[-1]["transect_id"].split(";")
            else:
                results[-1]["transect_id"] = ""

        # count tracks
        n_tracks = len(results)

        return render_template("tracks_list.html", header_title="Tracks list", n_tracks=n_tracks, results=results)


@app.route("/plot_tracks")
@fn.check_login
def plot_tracks():
    """
    Plot all tracks
    """

    with fn.conn_alchemy().connect() as con:
        features = []
        tot_min_lat, tot_min_lon = 90, 90
        tot_max_lat, tot_max_lon = -90, -90

        for row in (
            con.execute(
                text(
                    (
                        "SELECT snowtrack_id, ST_AsGeoJSON(st_transform(multilines, 4326)) AS track_lonlat "
                        "FROM snow_tracks "
                        "WHERE date BETWEEN :start_date AND :end_date "
                    )
                ),
                {
                    "start_date": session["start_date"],
                    "end_date": session["end_date"],
                },
            )
            .mappings()
            .all()
        ):
            if row["track_lonlat"] is not None:
                geojson = json.loads(row["track_lonlat"])

                for line in geojson["coordinates"]:
                    # bounding box
                    latitudes = [lat for _, lat in line]
                    longitudes = [lon for lon, _ in line]
                    tot_min_lat = min([tot_min_lat, min(latitudes)])
                    tot_max_lat = max([tot_max_lat, max(latitudes)])
                    tot_min_lon = min([tot_min_lon, min(longitudes)])
                    tot_max_lon = max([tot_max_lon, max(longitudes)])

                feature = {
                    "geometry": dict(geojson),
                    "type": "Feature",
                    "properties": {
                        "popupContent": f"""Track ID: <a href="/view_track/{row['snowtrack_id']}" target="_blank">{row['snowtrack_id']}</a>"""
                    },
                    "id": row["snowtrack_id"],
                }

                features.append(dict(feature))

        return render_template(
            "plot_tracks.html",
            header_title="Plot of tracks",
            map=Markup(
                fn.leaflet_geojson2(
                    {
                        "tracks": features,
                        "tracks_color": params["track_color"],
                        "fit": [[tot_min_lat, tot_min_lon], [tot_max_lat, tot_max_lon]],
                    }
                )
            ),
            scat_color=params["scat_color"],
            dead_wolf_color=params["dead_wolf_color"],
            transect_color=params["transect_color"],
            track_color=params["track_color"],
        )


@app.route("/new_track", methods=("GET", "POST"))
@app.route("/new_snowtrack", methods=("GET", "POST"))
@fn.check_login
def new_track():
    """
    insert a new track manually
    """

    def not_valid(msg):
        # default values
        default_values = {}
        for k in request.form:
            default_values[k] = request.form[k]

        flash(fn.alert_danger(f"<b>{msg}</b>"))

        return render_template(
            "new_track.html",
            title="New snow track",
            action="/new_snowtrack",
            form=form,
            default_values=default_values,
        )

    if request.method == "GET":
        form = Track()

        """
        automatic selection not possible because many transects can be selected
        # get id of all transects
        form.transect_id.choices = [("", "")] + [(x, x) for x in fn.all_transect_id()]
        """

        """
        # get id of all paths
        form.path_id.choices = [("", "")] + [(x, x) for x in fn.all_path_id()]
        """

        return render_template(
            "new_track.html",
            header_title="New track",
            title="New track",
            action="/new_track",
            form=form,
            default_values={},
        )

    if request.method == "POST":
        form = Track(request.form)

        """
        # get id of all transects
        form.transect_id.choices = [("", "")] + [(x, x) for x in fn.all_transect_id()]
        """

        """
        # get id of all paths
        form.path_id.choices = [("", "")] + [(x, x) for x in fn.all_path_id()]
        """

        if form.validate():
            with fn.conn_alchemy().connect() as con:
                # check if track already exists
                rows = (
                    con.execute(
                        text("SELECT snowtrack_id FROM snow_tracks WHERE UPPER(snowtrack_id) = UPPER(:track_id)"),
                        {"track_id": request.form["snowtrack_id"]},
                    )
                    .mappings()
                    .all()
                )
                if len(rows):
                    return not_valid(f"The track ID {request.form['snowtrack_id']} already exists")

                # check sampling type
                if request.form["sampling_type"] == "":
                    return not_valid("You must select a sampling type (Systematic or Opportunistic)")

                # check transect ID
                if request.form["sampling_type"] == "Systematic":
                    if request.form["transect_id"] == "":
                        return not_valid("You must specify a transect ID for a systematic sampling")
                    all_transects = fn.all_transect_id()
                    transects_id = request.form["transect_id"].upper().replace(" ", "")
                    for transect_id in transects_id.split(";"):
                        if transect_id not in all_transects:
                            return not_valid(f"The transect ID <b>{transect_id}</b> is not in the database")

                if request.form["sampling_type"] == "Opportunistic":
                    transects_id = ""

                # date
                try:
                    year = int(request.form["snowtrack_id"][1 : 2 + 1]) + 2000
                    month = int(request.form["snowtrack_id"][3 : 4 + 1])
                    day = int(request.form["snowtrack_id"][5 : 6 + 1])
                    date = f"{year}-{month:02}-{day:02}"
                    try:
                        dt.datetime.strptime(date, "%Y-%m-%d")
                    except Exception:
                        return not_valid("The date of the track ID is not valid. Use the YYMMDD format")
                except Exception:
                    return not_valid("The track ID value is not correct")

                # check province code
                province_code = fn.check_province_code(request.form["province"])
                if province_code is None:
                    # check province name
                    province_code = fn.province_name2code(request.form["province"])
                    if province_code is None:
                        return not_valid("The province was not found")

                # add region from province code
                track_region = fn.province_code2region(province_code)

                sql = text(
                    (
                        "INSERT INTO snow_tracks (snowtrack_id, transect_id, date, sampling_season, "
                        "location, municipality, province, region,"
                        "observer, institution, scalp_category, "
                        "sampling_type, track_type, days_after_snowfall, minimum_number_of_wolves,"
                        "track_format, notes)"
                        "VALUES (:track_id, :transects_id, :date, :sampling_season, "
                        ":location, :municipality, :province, :region, "
                        ":observer, :institution, :scalp_category, "
                        ":sampling_type, :track_type, :days_after_snowfall, :minimum_number_of_wolves, "
                        ":track_format, :notes)"
                    )
                )
                con.execute(
                    sql,
                    {
                        "track_id": request.form["snowtrack_id"],
                        "transects_id": transects_id,
                        "date": date,
                        "sampling_season": fn.sampling_season(date),
                        "location": request.form["location"].strip(),
                        "municipality": request.form["municipality"].strip(),
                        "province": province_code,
                        "region": track_region,
                        "observer": request.form["observer"],
                        "institution": request.form["institution"],
                        "scalp_category": request.form["scalp_category"],
                        "sampling_type": request.form["sampling_type"],
                        "track_type": request.form["track_type"],
                        "days_after_snowfall": request.form["days_after_snowfall"],
                        "minimum_number_of_wolves": request.form["minimum_number_of_wolves"],
                        "track_format": request.form["track_format"],
                        "notes": request.form["notes"],
                    },
                )

                return redirect("/snowtracks_list")
        else:
            return not_valid("Some values are not set or are wrong. Please check and submit again")


@app.route("/edit_snowtrack/<track_id>", methods=("GET", "POST"))
@app.route("/edit_track/<track_id>", methods=("GET", "POST"))
@fn.check_login
def edit_track(track_id):
    """
    Edit track
    """

    def not_valid(msg):
        # default values
        default_values = {}
        for k in request.form:
            default_values[k] = request.form[k]

        flash(Markup(f"<b>{msg}</b>"))
        return render_template(
            "new_track.html",
            title="Edit track",
            action=f"/edit_snowtrack/{track_id}",
            form=form,
            default_values=default_values,
        )

    if request.method == "GET":
        with fn.conn_alchemy().connect() as con:
            default_val = (
                con.execute(
                    text("SELECT *, ST_AsText(multilines) AS multilines  FROM snow_tracks WHERE snowtrack_id = :track_id"),
                    {"track_id": track_id},
                )
                .mappings()
                .fetchone()
            )

        default_values: dict = {}
        for field in default_val:
            default_values[field] = default_val[field]

        for field in [
            "location",
            "observer",
            "institution",
            "days_after_snowfall",
            "minimum_number_of_wolves",
            "track_format",
        ]:
            if default_values[field] is None:
                default_values[field] = ""

        # default values for select
        form = Track(
            transect_id=default_values["transect_id"],
            sampling_type=default_values["sampling_type"],
            track_type=default_values["track_type"],
            scalp_category=default_values["scalp_category"],
        )

        form.multilines.data = default_values["multilines"]

        """
        # get id of all transects
        form.transect_id.choices = [("", "")] + [(x, x) for x in fn.all_transect_id()]
        """
        form.notes.data = default_values["notes"]

        return render_template(
            "new_track.html",
            header_title=f"Edit track {track_id}",
            title=f"Edit track {track_id}",
            action=f"/edit_snowtrack/{track_id}",
            form=form,
            default_values=default_values,
        )

    if request.method == "POST":
        form = Track(request.form)

        """
        # get id of all transects
        form.transect_id.choices = [("", "")] + [(x, x) for x in fn.all_transect_id()]
        """

        if form.validate():
            with fn.conn_alchemy().connect() as con:
                # check if snowtrack_id already exists
                if request.form["snowtrack_id"] != track_id:
                    rows = (
                        con.execute(
                            text("SELECT snowtrack_id FROM snow_tracks WHERE UPPER(snowtrack_id) = UPPER(:track_id)"),
                            {"track_id": request.form["snowtrack_id"]},
                        )
                        .mappings()
                        .all()
                    )
                    if len(rows):
                        return not_valid(f"The snowtrack ID {request.form['snowtrack_id']} already exists")

            # check transect ID
            if request.form["sampling_type"] == "Systematic":
                if request.form["transect_id"] == "":
                    return not_valid("You must specify a transect ID for a systematic sampling")
                all_transects = fn.all_transect_id()
                transects_id = request.form["transect_id"].upper().replace(" ", "")
                for transect_id in transects_id.split(";"):
                    if transect_id not in all_transects:
                        return not_valid(f"The transect ID <b>{transect_id}</b> is not in the database")

            else:
                transects_id = ""

            # date
            try:
                year = int(request.form["snowtrack_id"][1 : 2 + 1]) + 2000
                month = int(request.form["snowtrack_id"][3 : 4 + 1])
                day = int(request.form["snowtrack_id"][5 : 6 + 1])
                date = f"{year}-{month:02}-{day:02}"
                try:
                    dt.datetime.strptime(date, "%Y-%m-%d")
                except Exception:
                    return not_valid("The date of the track ID is not valid. Use the YYMMDD format")

            except Exception:
                return not_valid("The track ID value is not correct")

            # check province code
            province = fn.check_province_code(request.form["province"])
            if province is None:
                # check province name
                province = fn.province_name2code(request.form["province"])
                if province is None:
                    return not_valid("The province was not found")

            # add region from province code
            track_region = fn.province_code2region(province)

            """# region
            track_region = fn.get_region(request.form["province"])
            """

            with fn.conn_alchemy().connect() as con:
                sql = text(
                    "UPDATE snow_tracks SET "
                    "snowtrack_id = :new_track_id,"
                    "track_type = :track_type,"
                    "transect_id = :transect_id,"
                    "date = :date,"
                    "sampling_season = :sampling_season,"
                    "location = :location,"
                    "municipality = :municipality,"
                    "province = :province,"
                    "region = :region,"
                    "observer = :observer,"
                    "institution = :institution,"
                    "scalp_category = :scalp_category,"
                    "sampling_type = :sampling_type,"
                    "days_after_snowfall = :days_after_snowfall,"
                    "minimum_number_of_wolves = :minimum_number_of_wolves,"
                    "track_format = :track_format,"
                    "notes = :notes "
                    "WHERE snowtrack_id = :track_id"
                )

                con.execute(
                    sql,
                    {
                        "new_track_id": request.form["snowtrack_id"],
                        "track_type": request.form["track_type"],
                        "transect_id": transects_id,
                        "date": date,
                        "sampling_season": fn.sampling_season(date),
                        "location": request.form["location"],
                        "municipality": request.form["municipality"],
                        "province": province,
                        "region": track_region,
                        "observer": request.form["observer"],
                        "institution": request.form["institution"],
                        "scalp_category": request.form["scalp_category"],
                        "sampling_type": request.form["sampling_type"],
                        "days_after_snowfall": request.form["days_after_snowfall"],
                        "minimum_number_of_wolves": request.form["minimum_number_of_wolves"],
                        "track_format": request.form["track_format"],
                        "notes": request.form["notes"],
                        "track_id": track_id,
                    },
                )

                if request.form["multilines"].strip():
                    try:
                        sql = text(
                            "UPDATE snow_tracks SET multilines = ST_GeomFromText(:multilines , 32632) WHERE snowtrack_id = :track_id"
                        )
                        con.execute(
                            sql,
                            {
                                "multilines": request.form["multilines"].strip(),
                                "track_id": track_id,
                            },
                        )
                    except Exception:
                        return not_valid("Check the MultiLineString field")

            return redirect(f"/view_snowtrack/{track_id}")
        else:
            return not_valid("Some values are not set or are wrong. Please check and submit again")


@app.route("/del_snowtrack/<track_id>")
@fn.check_login
def del_snowtrack(track_id):
    """
    Delete the track from table
    """
    with fn.conn_alchemy().connect() as con:
        con.execute(text("DELETE FROM snow_tracks WHERE snowtrack_id = :track_id"), {"track_id": track_id})
    return redirect("/snowtracks_list")


@app.route(
    "/load_tracks_xlsx",
    methods=(
        "GET",
        "POST",
    ),
)
@fn.check_login
def load_tracks_xlsx():
    """
    load tracks from xlsx file into DB
    """
    if request.method == "GET":
        return render_template("load_tracks_xlsx.html", header_title="Load tracks from XLSX/ODS")

    if request.method == "POST":
        new_file = request.files["new_file"]

        # check file extension
        if pl.Path(new_file.filename).suffix.upper() not in params["excel_allowed_extensions"]:
            flash(fn.alert_danger("The uploaded file does not have an allowed extension (must be <b>.xlsx</b> or <b>.ods</b>)"))
            return redirect("/load_tracks_xlsx")

        try:
            filename = str(uuid.uuid4()) + str(pl.Path(new_file.filename).suffix.upper())
            new_file.save(pl.Path(params["upload_folder"]) / pl.Path(filename))
        except Exception:
            flash(fn.alert_danger("Error with the uploaded file"))
            return redirect("/load_tracks_xlsx")

        r, msg, tracks_data = tracks_import.extract_data_from_tracks_xlsx(filename)
        if r:
            flash(Markup(f"File name: <b>{new_file.filename}</b>") + Markup("<hr><br>") + msg)
            return redirect("/load_tracks_xlsx")

        # check if scat_id already in DB

        with fn.conn_alchemy().connect() as con:
            tracks_list = "','".join([tracks_data[idx]["snowtrack_id"] for idx in tracks_data])
            sql = text(f"SELECT snowtrack_id FROM snow_tracks WHERE snowtrack_id IN ('{tracks_list}')")

            tracks_to_update = [row["snowtrack_id"] for row in con.execute(sql).mappings().all()]

        return render_template(
            "confirm_load_tracks_xlsx.html",
            n_tracks=len(tracks_data),
            n_tracks_to_update=tracks_to_update,
            all_data=tracks_data,
            filename=filename,
        )


@app.route("/confirm_load_tracks_xlsx/<filename>/<mode>")
@fn.check_login
def confirm_load_tracks_xlsx(filename, mode):
    """
    confirm load of tracks from xlsx file
    """

    if mode not in ["new", "all"]:
        flash(fn.alert_danger("Error: mode not allowed"))
        return redirect("/load_tracks_xlsx")

    r, msg, all_data = tracks_import.extract_data_from_tracks_xlsx(filename)
    if r:
        flash(Markup(f"File name: <b>{filename}</b>") + Markup("<hr><br>") + msg)
        return redirect("/load_tracks_xlsx")

    with fn.conn_alchemy().connect() as con:
        # check if scat_id already in DB
        tracks_list = "','".join([all_data[idx]["snowtrack_id"] for idx in all_data])
        sql = text(f"SELECT snowtrack_id FROM snow_tracks WHERE snowtrack_id IN ('{tracks_list}')")

        tracks_to_update = [row["snowtrack_id"] for row in con.execute(sql).mappings().all()]

        sql = text(
            "UPDATE snow_tracks SET "
            "snowtrack_id = :snowtrack_id, "
            "date = :date,"
            "sampling_season = :sampling_season,"
            "track_type = :track_type,"
            "sampling_type = :sampling_type,"
            "location = :location, "
            "municipality = :municipality, "
            "province = :province, "
            "region = :region, "
            "scalp_category = :scalp_category, "
            "observer = :operator, "
            "institution = :institution, "
            "notes = :notes, "
            "coord_east = :coord_east, "
            "coord_north = :coord_north, "
            "coord_zone = :coord_zone, "
            "geometry_utm = :geometry_utm "
            "WHERE snowtrack_id = :snowtrack_id;"
            "INSERT INTO snow_tracks ("
            "snowtrack_id,"
            "date,"
            "sampling_season,"
            "track_type,"
            "sampling_type,"
            "location,"
            "municipality,"
            "province,"
            "region,"
            "scalp_category,"
            "observer,"
            "institution,"
            "notes,"
            "coord_east, coord_north, coord_zone, "
            "geometry_utm"
            ") "
            "SELECT "
            ":snowtrack_id,"
            ":date,"
            ":sampling_season,"
            ":track_type,"
            ":sampling_type,"
            ":location,"
            ":municipality,"
            ":province,"
            ":region,"
            ":scalp_category, "
            ":operator,"
            ":institution,"
            ":notes, "
            ":coord_east, :coord_north, :coord_zone,"
            ":geometry_utm "
            "WHERE NOT EXISTS (SELECT 1 FROM snow_tracks WHERE snowtrack_id = :snowtrack_id)"
        )
        count_added = 0
        count_updated = 0
        for idx in all_data:
            data = dict(all_data[idx])

            if mode == "new" and (data["snowtrack_id"] in tracks_to_update):
                continue
            if data["snowtrack_id"] in tracks_to_update:
                count_updated += 1
            else:
                count_added += 1
            print(f"{data=}")
            try:
                con.execute(
                    sql,
                    {
                        "snowtrack_id": data["snowtrack_id"].strip(),
                        "date": data["date"],
                        "track_type": data["track_type"],
                        "sampling_season": fn.sampling_season(data["date"]),
                        "sampling_type": data["sampling_type"],
                        "scalp_category": data["scalp_category"].strip(),
                        "location": data["location"].strip(),
                        "municipality": data["municipality"].strip(),
                        "province": data["province"].strip().upper(),
                        "region": data["region"],
                        "operator": data["operator"],
                        "institution": data["institution"],
                        "notes": data["notes"],
                        "coord_east": data["coord_east"],
                        "coord_north": data["coord_north"],
                        "coord_zone": data["coord_zone"],
                        "geometry_utm": data["geometry_utm"],
                    },
                )
            except Exception:
                return "An error occured during the import of tracks. Contact the administrator.<br>" + error_info(sys.exc_info())

    msg = f"XLSX/ODS file successfully loaded. {count_added} tracks added, {count_updated} tracks updated."
    flash(fn.alert_success(msg))

    return redirect("/tracks")


@app.route("/export_tracks")
@fn.check_login
def export_tracks():
    """
    export tracks in XLSX file
    """
    with fn.conn_alchemy().connect() as con:
        file_content = tracks_export.export_tracks(
            con.execute(
                text("SELECT * FROM snow_tracks WHERE date BETWEEN :start_date AND :end_date OR date is NULL ORDER BY snowtrack_id ASC "),
                {
                    "start_date": session["start_date"],
                    "end_date": session["end_date"],
                },
            )
            .mappings()
            .all()
        )

    response = make_response(file_content, 200)
    response.headers["Content-type"] = "application/application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    response.headers["Content-disposition"] = f"attachment; filename=tracks_{dt.datetime.now():%Y-%m-%d_%H%M%S}.xlsx"

    return response


@app.route("/export_tracks_shapefile")
@fn.check_login
def export_tracks_shapefile():
    """
    create shapefile with tracks
    """

    # delete files older than 24h
    for file_path in pl.Path("static").glob("tracks_*.zip"):
        if time.time() - os.path.getmtime(file_path) > 86400:
            os.remove(file_path)

    time_stamp = f"{dt.datetime.now():%Y-%m-%d_%H%M%S}"

    zip_path = tracks_export.export_shapefile(
        f"{params['temp_folder']}/tracks_{time_stamp}", f"static/tracks_{time_stamp}", "/tmp/tracks_shapefile.log"
    )

    zip_file_name = pl.Path(zip_path).name

    return redirect(f"{app.static_url_path}/{zip_file_name}")


@app.route("/check_tracks_location")
@fn.check_login
def check_tracks_location():
    """
    check_tracks_location
    """

    with fn.conn_alchemy().connect() as con:
        tracks = (
            con.execute(
                text(
                    "SELECT snowtrack_id,  "
                    "(select concat(transect_id, '|', ROUND(st_distance(s.multilines, multilines))) FROM transects  "
                    "   WHERE st_distance(s.multilines, multilines) = "
                    "                 (select min(st_distance(s.multilines, multilines)) from transects) LIMIT 1) AS transect_dist "
                    "FROM snow_tracks s "
                    "WHERE sampling_type != 'Opportunistic' "
                    "AND transect_id is null "
                    "AND s.multilines IS NOT NULL "
                    "AND (date BETWEEN :start_date AND :end_date OR date is NULL)"
                ),
                {
                    "start_date": session["start_date"],
                    "end_date": session["end_date"],
                },
            )
            .mappings()
            .all()
        )

    return render_template(
        "check_tracks_location.html",
        header_title="Check tracks location",
        n_tracks=len(tracks),
        tracks=tracks,
    )
