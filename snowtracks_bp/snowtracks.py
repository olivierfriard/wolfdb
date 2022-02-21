"""
WolfDB web service
(c) Olivier Friard

flask blueprint for tracks management
"""

import flask
from flask import Flask, render_template, redirect, request, Markup, flash, session
import psycopg2
import psycopg2.extras
from config import config
import sys
import os
import json

from .track import Track
import functions as fn
import uuid
import pathlib as pl
import pandas as pd

app = flask.Blueprint("snowtracks", __name__, template_folder="templates")

params = config()
app.debug = params["debug"]

EXCEL_ALLOWED_EXTENSIONS = [".XLSX", ".ODS"]
UPLOAD_FOLDER = "/tmp"


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
def snow_tracks():
    return render_template("snow_tracks.html")


@app.route("/view_snowtrack/<snowtrack_id>")
def view_snowtrack(snowtrack_id):
    """
    visualize the snow track
    """
    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute(
        (
            "SELECT *, "
            "ST_AsGeoJSON(st_transform(multilines, 4326)) AS track_geojson, "
            "ROUND(ST_Length(multilines)) AS track_length "
            "FROM snow_tracks WHERE snowtrack_id = %s"
        ),
        [snowtrack_id],
    )
    track = cursor.fetchone()

    if track is None:
        flash(fn.alert_danger(f"<b>Track {snowtrack_id} not found</b>"))
        return redirect("/snowtracks_list")

    track_features = []
    min_lat, max_lat = 90, -90
    min_lon, max_lon = 90, -90

    color = "blue"

    if track["track_geojson"] is not None:
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
                "style": {"color": color, "fillColor": color, "fillOpacity": 1},
                "popupContent": snowtrack_id,
            },
            "id": 1,
        }
        track_features = [track_feature]

    # number of scats
    cursor.execute(
        (
            "SELECT *,"
            "ST_AsGeoJSON(st_transform(geometry_utm, 4326)) AS scat_lonlat "
            "FROM scats WHERE snowtrack_id LIKE %s"
        ),
        [f"{snowtrack_id}|%"],
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

    fit = [[min_lat, min_lon], [max_lat, max_lon]]

    return render_template(
        "view_snowtrack.html",
        header_title=f"Track ID: {snowtrack_id}",
        results=track,
        n_scats=n_scats,
        map=Markup(fn.leaflet_geojson(f"45, 7", scat_features, track_features, fit=str(fit))),
    )


@app.route("/snowtracks_list")
@fn.check_login
def snowtracks_list():
    # get  all tracks
    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute("SELECT * FROM snow_tracks ORDER BY region ASC, province ASC, date DESC")

    # split transects (more transects can be specified)
    results = []
    for row in cursor.fetchall():
        results.append(dict(row))
        if results[-1]["transect_id"] is not None:
            results[-1]["transect_id"] = results[-1]["transect_id"].split(";")
        else:
            results[-1]["transect_id"] = ""

    # count tracks
    n_tracks = len(results)

    return render_template("snowtracks_list.html", header_title="Tracks list", n_tracks=n_tracks, results=results)


@app.route("/new_snowtrack", methods=("GET", "POST"))
@fn.check_login
def new_snowtrack():
    """
    insert a new track
    """

    def not_valid(msg):

        # default values
        default_values = {}
        for k in request.form:
            default_values[k] = request.form[k]

        flash(fn.alert_danger(f"<b>{msg}</b>"))

        return render_template(
            "new_snowtrack.html",
            title="New snow track",
            action="/new_snowtrack",
            form=form,
            default_values=default_values,
        )

    if request.method == "GET":
        form = Track()

        # get id of all transects
        form.transect_id.choices = [("", "")] + [(x, x) for x in fn.all_transect_id()]
        return render_template(
            "new_snowtrack.html",
            title="New snow track",
            action="/new_snowtrack",
            form=form,
            default_values={},
        )

    if request.method == "POST":
        form = Track(request.form)

        # get id of all paths
        form.transect_id.choices = [("", "")] + [(x, x) for x in fn.all_transect_id()]

        if form.validate():

            connection = fn.get_connection()
            cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

            # check if track already exists
            cursor.execute(
                "SELECT snowtrack_id FROM snow_tracks WHERE UPPER(snowtrack_id) = UPPER(%s)",
                [request.form["snowtrack_id"]],
            )
            rows = cursor.fetchall()
            if len(rows):
                return not_valid(f"The track ID {request.form['snowtrack_id']} already exists")

            # date
            try:
                year = int(request.form["snowtrack_id"][1 : 2 + 1]) + 2000
                month = int(request.form["snowtrack_id"][3 : 4 + 1])
                day = int(request.form["snowtrack_id"][5 : 6 + 1])
                date = f"{year}-{month:02}-{day:02}"
            except Exception:
                return not_valid("The snowtrack_id value is not correct")

            # region
            track_region = fn.get_region(request.form["province"])

            sql = (
                "INSERT INTO snow_tracks (snowtrack_id, transect_id, date, sampling_season, "
                "location, municipality, province, region,"
                "observer, institution, scalp_category, "
                "sampling_type, track_type, days_after_snowfall, minimum_number_of_wolves,"
                "track_format, notes)"
                "VALUES (%s, %s, %s, %s, "
                "%s, %s, %s, %s, "
                "%s, %s, %s, "
                "%s, %s, %s, %s, "
                "%s, %s)"
            )
            cursor.execute(
                sql,
                [
                    request.form["snowtrack_id"],
                    request.form["transect_id"].upper(),
                    date,
                    fn.sampling_season(date),
                    request.form["location"].strip(),
                    request.form["municipality"].strip(),
                    request.form["province"].strip().upper(),
                    track_region,
                    request.form["observer"],
                    request.form["institution"],
                    request.form["scalp_category"],
                    request.form["sampling_type"],
                    request.form["track_type"],
                    request.form["days_after_snowfall"],
                    request.form["minimum_number_of_wolves"],
                    request.form["track_format"],
                    request.form["notes"],
                ],
            )
            connection.commit()

            return redirect("/snowtracks_list")
        else:
            return not_valid("Some values are not set or are wrong. Please check and submit again")


@app.route("/edit_snowtrack/<snowtrack_id>", methods=("GET", "POST"))
@fn.check_login
def edit_snowtrack(snowtrack_id):
    """
    Edit snow track
    """

    def not_valid(msg):
        # default values
        default_values = {}
        for k in request.form:
            default_values[k] = request.form[k]

        flash(Markup(f"<b>{msg}</b>"))
        return render_template(
            "new_snowtrack.html",
            title="Edit track",
            action=f"/edit_snowtrack/{snowtrack_id}",
            form=form,
            default_values=default_values,
        )

    if request.method == "GET":

        connection = fn.get_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

        cursor.execute(
            "SELECT *, ST_AsText(multilines) AS multilines  FROM snow_tracks WHERE snowtrack_id = %s",
            [snowtrack_id],
        )
        default_values = cursor.fetchone()

        if default_values["location"] is None:
            default_values["location"] = ""
        if default_values["observer"] is None:
            default_values["observer"] = ""

        if default_values["institution"] is None:
            default_values["institution"] = ""

        form = Track(
            transect_id=default_values["transect_id"],
            sampling_type=default_values["sampling_type"],
            track_type=default_values["track_type"],
            scalp_category=default_values["scalp_category"],
        )

        form.multilines.data = default_values["multilines"]

        # get id of all transects
        form.transect_id.choices = [("", "")] + [(x, x) for x in fn.all_transect_id()]
        form.notes.data = default_values["notes"]

        return render_template(
            "new_snowtrack.html",
            header_title=f"Edit track {snowtrack_id}",
            title="Edit track",
            action=f"/edit_snowtrack/{snowtrack_id}",
            form=form,
            default_values=default_values,
        )

    if request.method == "POST":
        form = Track(request.form)

        # get id of all transects
        form.transect_id.choices = [("", "")] + [(x, x) for x in fn.all_transect_id()]

        if form.validate():

            connection = fn.get_connection()
            cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

            # check if snowtrack_id already exists
            if request.form["snowtrack_id"] != snowtrack_id:
                cursor.execute(
                    "SELECT snowtrack_id FROM snow_tracks WHERE UPPER(snowtrack_id) = UPPER(%s)",
                    [request.form["snowtrack_id"]],
                )
                rows = cursor.fetchall()
                if len(rows):
                    return not_valid(f"The snowtrack ID {request.form['snowtrack_id']} already exists")

            # date
            try:
                year = int(request.form["snowtrack_id"][1 : 2 + 1]) + 2000
                month = int(request.form["snowtrack_id"][3 : 4 + 1])
                day = int(request.form["snowtrack_id"][5 : 6 + 1])
                date = f"{year}-{month:02}-{day:02}"
            except Exception:
                return not_valid("The snowtrack_id value is not correct")

            # region
            track_region = fn.get_region(request.form["province"])

            connection = fn.get_connection()
            cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
            sql = (
                "UPDATE snow_tracks SET "
                "snowtrack_id = %s,"
                "track_type = %s,"
                "transect_id = %s,"
                "date = %s,"
                "sampling_season = %s,"
                "location = %s,"
                "municipality = %s,"
                "province = %s,"
                "region = %s,"
                "observer = %s,"
                "institution = %s,"
                "scalp_category = %s,"
                "sampling_type = %s,"
                "days_after_snowfall = %s,"
                "minimum_number_of_wolves = %s,"
                "track_format = %s,"
                "notes = %s"
                "WHERE snowtrack_id = %s"
            )

            cursor.execute(
                sql,
                [
                    request.form["snowtrack_id"],
                    request.form["track_type"],
                    request.form["transect_id"],
                    date,
                    fn.sampling_season(date),
                    request.form["location"],
                    request.form["municipality"],
                    request.form["province"].strip().upper(),
                    track_region,
                    request.form["observer"],
                    request.form["institution"],
                    request.form["scalp_category"],
                    request.form["sampling_type"],
                    request.form["days_after_snowfall"],
                    request.form["minimum_number_of_wolves"],
                    request.form["track_format"],
                    request.form["notes"],
                    snowtrack_id,
                ],
            )
            connection.commit()

            if request.form["multilines"].strip():
                try:
                    sql = "UPDATE snow_tracks SET multilines = ST_GeomFromText(%s , 32632) WHERE snowtrack_id = %s"
                    cursor.execute(
                        sql,
                        [
                            request.form["multilines"].strip(),
                            snowtrack_id,
                        ],
                    )
                    connection.commit()

                except Exception:
                    return not_valid(f"Check the MultiLineString field")

            return redirect(f"/view_snowtrack/{snowtrack_id}")
        else:
            return not_valid("Some values are not set or are wrong. Please check and submit again")


@app.route("/del_snowtrack/<snowtrack_id>")
@fn.check_login
def del_snowtrack(snowtrack_id):
    """
    Delete the track from table
    """
    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("DELETE FROM snow_tracks WHERE snowtrack_id = %s", [snowtrack_id])
    connection.commit()
    return redirect("/snowtracks_list")


def extract_data_from_tracks_xlsx(filename: str):
    """
    Extract and check data from a XLSX file
    """

    if pl.Path(filename).suffix == ".XLSX":
        engine = "openpyxl"
    if pl.Path(filename).suffix == ".ODS":
        engine = "odf"

    out = ""

    try:
        df_all = pd.read_excel(pl.Path(UPLOAD_FOLDER) / pl.Path(filename), sheet_name=None, engine=engine)
    except Exception:
        return (
            True,
            fn.alert_danger(f"Error reading the file. Check your XLSX/ODS file"),
            {},
        )

    """
    if "Tracks" not in df.keys():
        return True, fn.alert_danger(f"Tracks sheet not found in workbook"), {}, {}, {}
    scats_df = df["Tracks"]
    """

    first_sheet_name = list(df_all.keys())[0]

    tracks_df = df_all[first_sheet_name]

    columns = [
        "snowtrack_id",
        "transect_id",
        "date",
        "coord_e",
        "coord_n",
        "location",
        "municipality",
        "province",
        "operator",
        "institution",
        "scalp_category",
        "sampling_type",
        "days_after_snowfall",
        "track_type",
        "minimum_number_of_wolves",
        "track_format",
        "notes",
    ]

    # check columns
    for column in columns:
        if column not in list(tracks_df.columns) and column != "track_type":
            return True, fn.alert_danger(f"Column {column} is missing"), {}

    tracks_data = {}
    for index, row in tracks_df.iterrows():
        data = {}
        for column in list(tracks_df.columns):
            data[column] = row[column]
            if isinstance(data[column], float) and str(data[column]) == "nan":
                data[column] = ""

        # date
        try:
            year = int(data["snowtrack_id"][1 : 2 + 1]) + 2000
            month = int(data["snowtrack_id"][3 : 4 + 1])
            day = int(data["snowtrack_id"][5 : 6 + 1])
            date = f"{year}-{month:02}-{day:02}"
        except Exception:
            out += fn.alert_danger(f"The track ID is not valid at row {index + 2}: {data['snowtrack_id']}")

        # check date
        try:
            date_from_file = str(data["date"]).split(" ")[0].strip()
        except Exception:
            date_from_file = ""

        if date != date_from_file:
            out += fn.alert_danger(
                f"Check the track ID and the date at row {index + 2}: {data['snowtrack_id']}  {date_from_file}"
            )

        data["date"] = date_from_file

        """
        # path_id
        path_id = fn.get_path_id(data['transect_id'], date)
        """

        # region
        track_region = fn.get_region(data["province"])
        data["region"] = track_region

        # data["geometry_utm"] = f"SRID=32632;POINT({data['coord_e']} {data['coord_n']})"

        # sampling_type
        data["sampling_type"] = str(data["sampling_type"]).capitalize().strip()
        if data["sampling_type"] not in ["Opportunistic", "Systematic", ""]:
            out += fn.alert_danger(
                f'Sampling type must be <i>Opportunistic</i>, <i>Systematic</i> or empty at row {index + 2}: found <b>{data["sampling_type"]}</b>'
            )

        # no path ID if scat is opportunistic
        if data["sampling_type"] == "Opportunistic":
            data["transect_id"] = ""

        # scalp_category
        data["scalp_category"] = str(data["scalp_category"]).capitalize().strip()
        if data["scalp_category"] not in ["C1", "C2", "C3", "C4", ""]:
            out += fn.alert_danger(
                f'The scalp category value must be <b>C1, C2, C3, C4</b> or empty at row {index + 2}: found {data["scalp_category"]}'
            )

        data["operator"] = str(data["operator"]).strip()

        data["institution"] = str(data["institution"]).strip()

        data["days_after_snowfall"] = str(data["days_after_snowfall"]).strip()

        if "trcks_type" in tracks_df.columns:
            data["track_type"] = str(data["trcks_type"]).strip()
        else:
            data["track_type"] = ""

        data["minimum_number_of_wolves"] = str(data["minimum_number_of_wolves"]).strip()

        # notes
        data["notes"] = str(data["notes"]).strip()

        tracks_data[index] = dict(data)

    if out:
        return True, out, {}

    return False, "", tracks_data


@app.route(
    "/load_tracks_xlsx",
    methods=(
        "GET",
        "POST",
    ),
)
@fn.check_login
def load_tracks_xlsx():

    if request.method == "GET":
        return render_template("load_tracks_xlsx.html")

    if request.method == "POST":

        new_file = request.files["new_file"]

        # check file extension
        if pl.Path(new_file.filename).suffix.upper() not in EXCEL_ALLOWED_EXTENSIONS:
            flash(
                fn.alert_danger(
                    "The uploaded file does not have an allowed extension (must be <b>.xlsx</b> or <b>.ods</b>)"
                )
            )
            return redirect(f"/load_tracks_xlsx")

        try:
            filename = str(uuid.uuid4()) + str(pl.Path(new_file.filename).suffix.upper())
            new_file.save(pl.Path(UPLOAD_FOLDER) / pl.Path(filename))
        except Exception:
            flash(fn.alert_danger("Error with the uploaded file"))
            return redirect(f"/load_tracks_xlsx")

        r, msg, all_data = extract_data_from_tracks_xlsx(filename)
        if r:
            msg = Markup(f"File name: {new_file.filename}<br>") + msg
            flash(msg)
            return redirect(f"/load_tracks_xlsx")

        else:
            # check if scat_id already in DB
            connection = fn.get_connection()
            cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

            tracks_list = "','".join([all_data[idx]["snowtrack_id"] for idx in all_data])
            sql = f"SELECT snowtrack_id FROM snow_tracks WHERE snowtrack_id IN ('{tracks_list}')"
            cursor.execute(sql)
            tracks_to_update = [row["snowtrack_id"] for row in cursor.fetchall()]

            return render_template(
                "confirm_load_tracks_xlsx.html",
                n_tracks=len(all_data),
                n_tracks_to_update=tracks_to_update,
                all_data=all_data,
                filename=filename,
            )


@app.route("/confirm_load_tracks_xlsx/<filename>/<mode>")
@fn.check_login
def confirm_load_tracks_xlsx(filename, mode):

    if mode not in ["new", "all"]:
        flash(fn.alert_danger("Error: mode not allowed"))
        return redirect(f"/load_tracks_xlsx")

    r, msg, all_data = extract_data_from_tracks_xlsx(filename)
    if r:
        flash(msg)
        return redirect(f"/load_tracks_xlsx")

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # check if scat_id already in DB
    tracks_list = "','".join([all_data[idx]["snowtrack_id"] for idx in all_data])
    sql = f"select snowtrack_id from snow_tracks where snowtrack_id in ('{tracks_list}')"
    cursor.execute(sql)
    tracks_to_update = [row["snowtrack_id"] for row in cursor.fetchall()]

    sql = (
        "UPDATE snow_tracks SET snowtrack_id = %(snowtrack_id)s, "
        "                date = %(date)s,"
        "                sampling_season = %(sampling_season)s,"
        "                track_type = %(track_type)s,"
        "                sampling_type = %(sampling_type)s,"
        "                location = %(location)s, "
        "                municipality = %(municipality)s, "
        "                province = %(province)s, "
        "                region = %(region)s, "
        "                scalp_category = %(scalp_category)s, "
        "                observer = %(operator)s, "
        "                institution = %(institution)s, "
        "                notes = %(notes)s "
        "WHERE snowtrack_id = %(snowtrack_id)s;"
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
        "notes"
        ") "
        "SELECT "
        "%(snowtrack_id)s,"
        "%(date)s,"
        "%(sampling_season)s,"
        "%(track_type)s,"
        "%(sampling_type)s,"
        "%(location)s,"
        "%(municipality)s,"
        "%(province)s,"
        "%(region)s,"
        "%(scalp_category)s, "
        "%(operator)s,"
        "%(institution)s,"
        "%(notes)s "
        "WHERE NOT EXISTS (SELECT 1 FROM snow_tracks WHERE snowtrack_id = %(snowtrack_id)s)"
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
            cursor.execute(
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
                },
            )
        except Exception:
            return "An error occured during the loading of scats. Contact the administrator.<br>" + error_info(
                sys.exc_info()
            )

    connection.commit()

    msg = f"XLSX/ODS file successfully loaded. {count_added} tracks added, {count_updated} tracks updated."
    flash(fn.alert_success(msg))

    return redirect(f"/tracks")
