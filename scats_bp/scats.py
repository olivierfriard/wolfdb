"""
WolfDB web service
(c) Olivier Friard

flask blueprint for scats management
"""



import flask
from flask import Flask, render_template, redirect, request, Markup, flash, session, current_app
import psycopg2
import psycopg2.extras
from config import config

from .scat_form import Scat
import functions as fn
import utm
import json
import pathlib as pl
import pandas as pd
import uuid
import os
import sys
import subprocess

app = flask.Blueprint("scats", __name__, template_folder="templates")

app.debug = True

params = config()

ALLOWED_EXTENSIONS = [".TSV"]
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

    _, exc_obj, exc_tb = exc_info
    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]

    error_type, error_file_name, error_lineno = exc_obj, fname, exc_tb.tb_lineno

    return f"Error {error_type} in {error_file_name} at line #{error_lineno}"


@app.route("/scats")
@fn.check_login
def scats():
    return render_template("scats.html",
                           header_title="Scats")


@app.route("/wa_form", methods=("POST",))
@fn.check_login
def wa_form():

    data = request.form

    return (f'<form action="/add_wa" method="POST" style="padding-top:30px; padding-bottom:30px">'
            f'<input type="hidden" id="scat_id" name="scat_id" value="{request.form["scat_id"]}">'
            '<div class="form-group">'
            '<label for="usr">WA code</label>'
            '<input type="text" class="form-control" id="wa" name="wa">'
            '</div>'
            '<button type="submit" class="btn btn-primary">Add code</button>'
            '</form>'
            )


@app.route("/add_wa", methods=("POST",))
@fn.check_login
def add_wa():

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute("UPDATE scats SET wa_code = %s WHERE scat_id = %s",
                   [request.form['wa'].upper(), request.form['scat_id']])

    connection.commit()
    return redirect(f"/view_scat/{request.form['scat_id']}")


@app.route("/view_scat/<scat_id>")
@fn.check_login
def view_scat(scat_id):
    """
    Display scat info
    """
    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute(("SELECT *, ST_AsGeoJSON(st_transform(geometry_utm, 4326)) AS scat_lonlat, "
                    "ROUND(st_x(st_transform(geometry_utm, 4326))::numeric, 6) as longitude, "
                    "ROUND(st_y(st_transform(geometry_utm, 4326))::numeric, 6) as latitude "
                    "FROM scats WHERE scat_id = %s"
                   ),
                   [scat_id])

    results = dict(cursor.fetchone())

    scat_geojson = json.loads(results["scat_lonlat"])

    scat_feature = {"geometry": dict(scat_geojson),
                    "type": "Feature",
                    "properties": {
                                   "popupContent": f"Scat ID: {scat_id}"
                                  },
                    "id": scat_id
                   }

    scat_features = [scat_feature]

    center = f"{results['latitude']}, {results['longitude']}"

    # transect
    if results["path_id"]:  # Systematic sampling
        transect_id = results["path_id"].split("|")[0]

        cursor.execute("SELECT ST_AsGeoJSON(st_transform(points_utm, 4326)) AS transect_geojson FROM transects WHERE transect_id = %s",
                    [transect_id])
        transect = cursor.fetchone()

        if transect is not None:

            transect_geojson = json.loads(transect["transect_geojson"])

            transect_feature = {
                    "type": "Feature",
                    "geometry": dict(transect_geojson),
                    "properties": {
                        "popupContent": f"Transect ID: {transect_id}"
                    },
                    "id": 1
                }
            transect_features = [transect_feature]
        else:
            transect_id = ""
            transect_features = []

    else:
        # opportunistic sampling
        transect_id = ""
        transect_features = []

    return render_template("view_scat.html",
                           header_title=f"Scat ID: {scat_id}",
                           results=results,
                           transect_id=transect_id,
                           map=Markup(fn.leaflet_geojson(center, scat_features, transect_features))
                           )


@app.route("/plot_all_scats")
@fn.check_login
def plot_all_scats():
    """
    plot all scats
    """

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

        scat_feature = {"geometry": dict(scat_geojson),
                        "type": "Feature",
                        "properties": {"style": {"color": "orange", "fillColor": "orange", "fillOpacity": 1},
                                       "popupContent": f"""Scat ID: <a href="/view_scat/{row['scat_id']}" target="_blank">{row['scat_id']}</a>"""
                                      },
                        "id": row["scat_id"]
                   }

        scat_features.append(dict(scat_feature))

    center = f"45 , 9"

    return render_template("plot_all_scats.html",
                           header_title="Plot of scats",
                           map=Markup(fn.leaflet_geojson(center, scat_features, [],
                                      fit=str([[tot_min_lat, tot_min_lon], [tot_max_lat, tot_max_lon]])
                           ))
                          )




@app.route("/scats_list")
@fn.check_login
def scats_list():
    """
    Display all scats
    """

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute("SELECT count(*) as n_scats FROM scats")
    n_scats = cursor.fetchone()["n_scats"]

    cursor.execute("SELECT * FROM scats ORDER BY scat_id")

    return render_template("scats_list.html",
                           header_title="List of scats",
                            n_scats=n_scats,
                            results=cursor.fetchall())


@app.route("/new_scat", methods=("GET", "POST"))
@fn.check_login
def new_scat():

    def not_valid(msg):
        # default values
        default_values = {}
        for k in request.form:
            default_values[k] = request.form[k]

        #flash(Markup(f"<b>{msg}</b>"))

        flash(fn.alert_danger(f"<b>{msg}</b>"))

        return render_template("new_scat.html",
                               header_title="New scat",
                               title="New scat",
                               action=f"/new_scat",
                               form=form,
                               default_values=default_values)


    if request.method == "GET":
        form = Scat()
        # get id of all paths
        form.path_id.choices = [("", "")] + [(x, x) for x in fn.all_path_id()]
        # get id of all snow tracks
        form.snowtrack_id.choices = [("", "")] + [(x, x) for x in fn.all_snow_tracks_id()]

        return render_template("new_scat.html",
                               title="New scat",
                               action=f"/new_scat",
                               form=form,
                               default_values={"coord_zone": "32N"})

    if request.method == "POST":
        form = Scat(request.form)

        # get id of all transects
        form.path_id.choices = [("", "")] + [(x, x) for x in fn.all_path_id()]

        # get id of all snow tracks
        form.snowtrack_id.choices = [("", "")] + [(x, x) for x in fn.all_snow_tracks_id()]

        if form.validate():

            # date
            try:
                year = int(request.form["scat_id"][1:2+1]) + 2000
                month = int(request.form["scat_id"][3:4+1])
                day = int(request.form["scat_id"][5:6+1])
                date = f"{year}-{month}-{day}"
            except Exception:
                return not_valid("The scat ID value is not correct")

            # path id
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

            sql = ("INSERT INTO scats (scat_id, date, sampling_season, sampling_type, path_id, snowtrack_id, "
                   "location, municipality, province, region, "
                   "deposition, matrix, collected_scat, scalp_category, "
                   "coord_east, coord_north, coord_zone, "
                   "observer, institution,"
                   #"geo, "
                   "geometry_utm) "
                   "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)")
            cursor.execute(sql,
                           [
                            request.form["scat_id"],
                            date,
                            fn.sampling_season(date),
                            request.form["sampling_type"],
                            path_id,
                            request.form["snowtrack_id"],
                            request.form["location"], request.form["municipality"], province, scat_region,
                            request.form["deposition"], request.form["matrix"], request.form["collected_scat"], request.form["scalp_category"],
                            request.form["coord_east"], request.form["coord_north"], "32N",
                            request.form["observer"], request.form["institution"],
                            #f"SRID=4326;POINT({coord_latlon[1]} {coord_latlon[0]})",
                            f"SRID=32632;POINT({request.form['coord_east']} {request.form['coord_north']})"
                           ]
                           )

            connection.commit()

            return redirect("/scats_list")
        else:
            return not_valid("Some values are not set or are wrong. Please check and submit again")



@app.route("/edit_scat/<scat_id>", methods=("GET", "POST"))
@fn.check_login
def edit_scat(scat_id):

    def not_valid(msg):
            # default values
            default_values = {}
            for k in request.form:
                default_values[k] = request.form[k]

            flash(Markup(f"<b>{msg}</b>"))

            return render_template("new_scat.html",
                                   title="Edit scat",
                                   action=f"/edit_scat/{scat_id}",
                                   form=form,
                                   default_values=default_values)


    if request.method == "GET":
        connection = fn.get_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("SELECT * FROM scats WHERE scat_id = %s",
                    [scat_id])
        default_values = cursor.fetchone()

        form = Scat(path_id=default_values["path_id"],
                    snowtrack_id=default_values["snowtrack_id"],
                    sampling_type=default_values["sampling_type"],
                    deposition=default_values["deposition"],
                    matrix=default_values["matrix"],
                    collected_scat=default_values["collected_scat"],
                    scalp_category=default_values["scalp_category"])

        # get id of all paths
        form.path_id.choices = [("", "")] + [(x, x) for x in fn.all_path_id()]
        # get id of all snow tracks
        form.snowtrack_id.choices = [("", "")] + [(x, x) for x in fn.all_snow_tracks_id()]

        return render_template("new_scat.html",
                            title="Edit scat",
                            action=f"/edit_scat/{scat_id}",
                            form=form,
                            default_values=default_values)


    if request.method == "POST":

        form = Scat(request.form)

        # get id of all paths
        form.path_id.choices = [("", "")] + [(x, x) for x in fn.all_path_id()]

        # get id of all snow tracks
        form.snowtrack_id.choices = [("", "")] + [(x, x) for x in fn.all_snow_tracks_id()]

        if form.validate():

            # date
            try:
                year = int(request.form['scat_id'][1:2+1]) + 2000
                month = int(request.form['scat_id'][3:4+1])
                day = int(request.form['scat_id'][5:6+1])
                date = f"{year}-{month:02}-{day:02}"
            except Exception:
                return not_valid("The scat_id value is not correct")

            # path id
            if request.form["sampling_type"] == "Systematic":
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

            # UTM coord conversion
            coord_latlon = utm.to_latlon(int(request.form["coord_east"]), int(request.form["coord_north"]), 32, "N")

            connection = fn.get_connection()
            cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

            sql = ("UPDATE scats SET scat_id = %s, "
                   "                date = %s,"
                   "                sampling_season = %s,"
                   "                sampling_type = %s,"
                   "                path_id = %s, "
                   "                snowtrack_id = %s, "
                   "                location = %s, "
                   "                municipality = %s, "
                   "                province = %s, "
                   "                region = %s, "
                   "                deposition = %s, "
                   "                matrix = %s, "
                   "                collected_scat = %s, "
                   "                scalp_category = %s, "
                   "                coord_east = %s, "
                   "                coord_north = %s, "
                   #"                coord_zone = %s, "
                   "                observer = %s, "
                   "                institution = %s, "
                   #"                geo = %s, "
                   "                geometry_utm = %s "
                   "WHERE scat_id = %s")
            cursor.execute(sql,
                           [
                            request.form["scat_id"],
                            date,
                            fn.sampling_season(date),
                            request.form["sampling_type"],
                            path_id,
                            request.form["snowtrack_id"],
                            request.form["location"], request.form["municipality"], province, scat_region,
                            request.form["deposition"], request.form["matrix"], request.form["collected_scat"], request.form["scalp_category"],
                            request.form["coord_east"], request.form["coord_north"], #request.form["coord_zone"],
                            request.form["observer"], request.form["institution"],
                            #f"SRID=4326;POINT({coord_latlon[1]} {coord_latlon[0]})",
                            f"SRID=32632;POINT({request.form['coord_east']} {request.form['coord_north']})",
                            scat_id
                           ]
                           )

            connection.commit()

            return redirect(f"/view_scat/{scat_id}")
        else:
            return not_valid("Some values are not set or are wrong. Please check and submit again")


@app.route("/del_scat/<scat_id>")
@fn.check_login
def del_scat(scat_id):
    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("DELETE FROM scats WHERE scat_id = %(scat_id)s",
                   {"scat_id": scat_id})
    connection.commit()
    return redirect("/scats_list")



def extract_data_from_xlsx(filename):
    """
    Extract and check data from a XLSX file
    """

    if pl.Path(filename).suffix == ".XLSX":
        engine = "openpyxl"
    if pl.Path(filename).suffix == ".ODS":
        engine = "odf"


    out = ""

    try:
        df = pd.read_excel(pl.Path(UPLOAD_FOLDER) / pl.Path(filename), sheet_name=None, engine=engine)
    except Exception:
        return True, fn.alert_danger(f"Error reading the file. Check your XLSX/ODS file"), {}, {}, {}


    if "Scats" not in df.keys():
        return True, fn.alert_danger(f"Scats sheet not found in workbook"), {}, {}, {}

    scats_df = df["Scats"]

    # check columns
    for column in ['scat_id', 'date', 'wa_code', 'genotype_id', 'sampling_type', 'transect_id', 'snowtrack_id',
                    'location', 'municipality', 'province',
                    'deposition', 'matrix', 'collected_scat', 'scalp_category',
                    'genetic_sample',
                    'coord_east', 'coord_north', 'coord_zone',
                    'operator', 'institution', 'notes']:

        if column not in list(scats_df.columns):
            return True, fn.alert_danger(f"Column {column} is missing"), {}, {}, {}

    scats_data = {}
    for index, row in scats_df.iterrows():
        data = {}
        for column in list(scats_df.columns):
            data[column] = row[column]
            if isinstance(data[column], float) and str(data[column]) == "nan":
                data[column] = ""

        # date
        try:
            year = int(data['scat_id'][1:2+1]) + 2000
            month = int(data['scat_id'][3:4+1])
            day = int(data['scat_id'][5:6+1])
            date = f"{year}-{month:02}-{day:02}"
        except Exception:
            out += fn.alert_danger(f"The scat ID is not valid at row {index + 2}: {data['scat_id']}")

        # check date
        try:
            date_from_file = str(data["date"]).split(" ")[0].strip()
        except Exception:
            date_from_file = ""

        if date != date_from_file:
            out += fn.alert_danger(f"Check the scat ID and the date at row {index + 2}: {data['scat_id']}  {date_from_file}")

        data["date"] = date_from_file

        # path_id
        path_id = fn.get_path_id(data['transect_id'], date)
        data["path_id"] = path_id

        # region
        scat_region = fn.get_region(data["province"])
        data["region"] = scat_region

        # UTM coord conversion
        # check zone
        if data["coord_zone"].upper() != "32N":
            out += fn.alert_danger(f"The UTM zone is not 32N. Only WGS 84 / UTM zone 32N are accepted (row {index + 2}): found {data['coord_zone']}")

        try:
            coord_latlon = utm.to_latlon(int(data["coord_east"]), int(data["coord_north"]), 32, "N")
            data["coord_latlon"] = f"SRID=4326;POINT({coord_latlon[1]} {coord_latlon[0]})"
        except Exception:
            out += fn.alert_danger(f'Check the UTM coordinates at row {index + 2}: {data["coord_east"]} {data["coord_north"]} {data["coord_zone"]}')

        data["geometry_utm"] = f"SRID=32632;POINT({data['coord_east']} {data['coord_north']})"

        # sampling_type
        data["sampling_type"] = str(data["sampling_type"]).capitalize().strip()
        if data["sampling_type"] not in ["Opportunistic", "Systematic", ""]:
            out += fn.alert_danger(f'Sampling type must be <b>Opportunistic</b>, <b>Systematic</b> or empty at row {index + 2}: found {data["sampling_type"]}')

        # no path ID if scat is opportunistc
        if data["sampling_type"] == "Opportunistic":
            data["path_id"] = ""

        # deposition
        data["deposition"] = str(data["deposition"]).capitalize().strip()
        if data["deposition"] == "Fresca":
            data["deposition"] = "Fresh"
        if data["deposition"] == "Vecchia":
            data["deposition"] = "Old"
        if data["deposition"] not in ["Fresh", "Old", ""]:
            out += fn.alert_danger(f'The deposition value must be <b>Fresh</b>, <b>Old</b> or empty at row {index + 2}: found {data["deposition"]}')

        # matrix
        data["matrix"] = str(data["matrix"]).capitalize().strip()
        if data["matrix"] in ["Si", "Sì"]:
            data["matrix"] = "Yes"
        if data["matrix"] == "No":
            data["matrix"] = "No"
        if data["matrix"] not in ["Yes", "No", ""]:
            out +=  fn.alert_danger(f'The matrix value must be <b>Yes</b> or <b>No</b> or empty at row {index + 2}: found {data["matrix"]}')

        # collected_scat
        data["collected_scat"] = str(data["collected_scat"]).capitalize().strip()
        if data["collected_scat"] in ["Si", "Sì"]:
            data["collected_scat"] = "Yes"
        if data["collected_scat"] == "No":
            data["collected_scat"] = "No"
        if data["collected_scat"] not in ["Yes", "No", ""]:
            out += fn.alert_danger(f'The collected_scat value must be <b>Yes</b> or <b>No</b> or empty at row {index + 2}: found {data["collected_scat"]}')

        # scalp_category
        data["scalp_category"] = str(data["scalp_category"]).capitalize().strip()
        if data["scalp_category"] not in ["C1", "C2", "C3", "C4", ""]:
            out += fn.alert_danger(f'The scalp category value must be <b>C1, C2, C3, C4</b> or empty at row {index + 2}: found {data["scalp_category"]}')

        # genetic_sample
        data["genetic_sample"] = str(data["genetic_sample"]).capitalize().strip()
        if data["genetic_sample"] in ["Si", "Sì"]:
            data["genetic_sample"] = "Yes"
        if data["genetic_sample"] == "No":
            data["genetic_sample"] = "No"
        if data["genetic_sample"] not in ["Yes", "No", ""]:
            out += fn.alert_danger(f'The genetic_sample value must be <b>Yes</b>, <b>No</b> or empty at row {index + 2}: found {data["genetic_sample"]}')

        # notes
        data["notes"] = str(data["notes"]).strip()

        data["operator"] = str(data["operator"]).strip()
        data["institution"] = str(data["institution"]).strip()

        scats_data[index] = dict(data)

    if out:
        return True, out, {}, {}, {}

    # extract paths
    all_paths = {}
    if "Paths" in df.keys():
        paths_df = df["Paths"]
        for index, row in paths_df.iterrows():
            data = {}
            for column in list(paths_df.columns):
                data[column] = row[column]
                if isinstance(data[column], float) and str(data[column]) == "nan":
                    data[column] = ""

            data["date"] = str(data["date"]).split(" ")[0]
            if data["completeness"] == "":
                data["completeness"] = None

            all_paths[index] = dict(data)

    else:  # no Paths sheet found. Construct from scats

        index = 0
        for idx in scats_data:
            if not scats_data[idx]["path_id"]:
                continue
            data = {}
            data["path_id"] = scats_data[idx]["path_id"]
            data["transect_id"] = scats_data[idx]["transect_id"]
            data["date"] = scats_data[idx]["date"]
            data["sampling_season"] = fn.sampling_season(scats_data[idx]["date"])
            data["completeness"] = None
            data["operator"] = scats_data[idx]["operator"]
            data["institution"] = scats_data[idx]["institution"]
            data["notes"] = ""

            all_paths[index] = dict(data)
            index += 1

    # extract tracks
    all_tracks = {}
    if "Tracks" in df.keys():
        tracks_df = df["Tracks"]
        for index, row in tracks_df.iterrows():
            data = {}
            for column in list(scats_df.columns):
                if isinstance(data[column], float) and str(data[column]) == "nan":
                    data[column] = ""
                else:
                    data[column] = row[column]

            all_tracks[index] = dict(data)

    return False, "", scats_data, all_paths, all_tracks


@app.route("/load_scats_xlsx", methods=("GET", "POST",))
@fn.check_login
def load_scats_xlsx():

    if request.method == "GET":
        return render_template("load_scats_xlsx.html")

    if request.method == "POST":

        new_file = request.files["new_file"]

        # check file extension
        if pl.Path(new_file.filename).suffix.upper() not in EXCEL_ALLOWED_EXTENSIONS:
            flash(fn.alert_danger("The uploaded file does not have an allowed extension (must be <b>.xlsx</b> or <b>.ods</b>)"))
            return redirect(f"/load_scats_xlsx")

        try:
            filename = str(uuid.uuid4()) + str(pl.Path(new_file.filename).suffix.upper())
            new_file.save(pl.Path(UPLOAD_FOLDER) / pl.Path(filename))
        except Exception:
            flash(fn.alert_danger("Error with the uploaded file"))
            return redirect(f"/load_scats_xlsx")

        r, msg, all_data, all_paths, all_tracks = extract_data_from_xlsx(filename)
        if r:
            msg = Markup(f"File name: {new_file.filename}<br>" + msg)
            flash(msg)
            return redirect(f"/load_scats_xlsx")

        else:
            # check if scat_id already in DB
            connection = fn.get_connection()
            cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
            scats_list = "','".join([all_data[idx]['scat_id'] for idx in all_data])
            sql = f"SELECT scat_id FROM scats WHERE scat_id IN ('{scats_list}')"
            cursor.execute(sql)
            scats_to_update = [row["scat_id"] for row in cursor.fetchall()]

            return render_template("confirm_load_scats_xlsx.html",
                                   n_scats = len(all_data),
                                   n_scats_to_update=scats_to_update,
                                   all_data=all_data,
                                   filename=filename)


@app.route("/confirm_load_xlsx/<filename>/<mode>")
@fn.check_login
def confirm_load_xlsx(filename, mode):

    if mode not in ["new", "all"]:
        flash(fn.alert_danger("Error: mode not allowed"))
        return redirect(f"/load_scats_xlsx")

    r, msg, all_data, all_paths, all_tracks = extract_data_from_xlsx(filename)
    if r:
        flash(msg)
        return redirect(f"/load_scats_xlsx")

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # check if scat_id already in DB
    scats_list = "','".join([all_data[idx]['scat_id'] for idx in all_data])
    sql = f"select scat_id from scats where scat_id in ('{scats_list}')"
    cursor.execute(sql)
    scats_to_update = [row["scat_id"] for row in cursor.fetchall()]

    sql = ("UPDATE scats SET scat_id = %(scat_id)s, "
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
            #"                geo = %(geo)s, "
            "                geometry_utm = %(geometry_utm)s, "
            "                notes = %(notes)s "
            "WHERE scat_id = %(scat_id)s;"

            "INSERT INTO scats (scat_id, date, wa_code, genotype_id, sampling_season, sampling_type, path_id, snowtrack_id, "
            "location, municipality, province, region, "
            "deposition, matrix, collected_scat, scalp_category, genetic_sample, "
            "coord_east, coord_north, coord_zone, "
            "observer, institution,"
            #"geo, "
            "geometry_utm, notes) "
            "SELECT %(scat_id)s, %(date)s, %(wa_code)s, %(genotype_id)s, "
            " %(sampling_season)s, %(sampling_type)s, %(path_id)s, %(snowtrack_id)s, "
            "%(location)s, %(municipality)s, %(province)s, %(region)s, "
            "%(deposition)s, %(matrix)s, %(collected_scat)s, %(scalp_category)s, %(genetic_sample)s,"
            " %(coord_east)s, %(coord_north)s, %(coord_zone)s, %(operator)s, %(institution)s, "
            #"%(geo)s, "
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
            cursor.execute(sql,
                           {"scat_id": data["scat_id"].strip(),
                            "date": data["date"],
                            "wa_code": data["wa_code"].strip(),
                            "genotype_id": data["genotype_id"].strip(),
                            "sampling_season": fn.sampling_season(data["date"]),
                            "sampling_type": data["sampling_type"],
                            "path_id": data["path_id"],
                            "snowtrack_id": data["snowtrack_id"].strip(),
                            "location": data["location"].strip(), "municipality": data["municipality"].strip(),
                            "province": data["province"].strip().upper(), "region": data["region"],
                            "deposition": data["deposition"], "matrix": data["matrix"],
                            "collected_scat": data["collected_scat"], "scalp_category": data["scalp_category"].strip(),
                            "genetic_sample": data["genetic_sample"],
                            "coord_east": data["coord_east"], "coord_north": data["coord_north"], "coord_zone": data["coord_zone"].strip(),
                            "operator": data["operator"], "institution": data["institution"],
                            "geo": data["coord_latlon"],
                            "geometry_utm": data["geometry_utm"],
                            "notes": data["notes"]
                           }
                           )
        except Exception:
            return "An error occured during the loading of scats. Contact the administrator.<br>" + error_info(sys.exc_info())

    connection.commit()


    # paths
    if all_paths:
        sql = ("UPDATE paths SET path_id = %(path_id)s, "
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
                cursor.execute(sql,
                                {"path_id": data["path_id"],
                                "transect_id": data["transect_id"].strip(),
                                "date": data["date"],
                                "sampling_season": fn.sampling_season(data["date"]),
                                "completeness": data["completeness"],
                                "operator": data["operator"].strip(), "institution": data["institution"].strip(),
                                "notes": data["notes"],
                                }
                                )
            except Exception:
                return "An error occured during the loading of paths. Contact the administrator.<br>" + error_info(sys.exc_info())

        connection.commit()

    # snow tracks
    if all_tracks:
        sql = ("UPDATE snow_tracks SET snowtrack_id = %(snowtrack_id)s, "
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
                cursor.execute(sql,
                                {"path_id": data["path_id"],
                                "snowtrack_id": data["snowtrack_id"].strip(),
                                "date": data["date"],
                                "sampling_season": fn.sampling_season(data["date"]),
                                "operator": data["operator"].strip(), "institution": data["institution"].strip(),
                                "notes": data["notes"],
                                }
                                )
            except Exception:
                return "An error occured during the loading of tracks. Contact the administrator.<br>" + error_info(sys.exc_info())

        connection.commit()



    msg = f"XLSX/ODS file successfully loaded. {count_added} scats added, {count_updated} scats updated."
    flash(fn.alert_success(msg))

    return redirect(f'/scats')


def check_systematic_scats_transect_location():
    """
    Check location of scats from systematic sampling
    Create file in
    """

    out = "<table>\n"

    sql = """
    SELECT transect_id, st_distance(ST_GeomFromText('POINT(XXX YYY)',32632), points_utm)::integer AS distance
    FROM transects
    WHERE st_distance(ST_GeomFromText('POINT(XXX YYY)',32632), points_utm) = (select min(st_distance(ST_GeomFromText('POINT(XXX YYY)',32632), points_utm)) FROM transects);
    """

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute("SELECT scat_id, sampling_type, path_id, st_x(geometry_utm)::integer AS x, st_y(geometry_utm)::integer AS y FROM scats WHERE sampling_type = 'Systematic'")
    scats = cursor.fetchall()
    for row in scats:

        sql2 = sql.replace("XXX", str(row["x"])).replace("YYY", str(row["y"]))

        cursor.execute(sql2)
        transect = cursor.fetchone()

        path_id = row["path_id"].replace(" ", "|")

        if path_id.startswith(transect["transect_id"] + "|"):
            match = "OK"
        else:
            match = "NO"


        out += f'<tr><td>{row["scat_id"]}</td><td>{row["sampling_type"]}</td><td>{path_id}</td><td>{transect["transect_id"]}</td><td>{transect["distance"]}</td><td>{match}</td></tr>\n'

    out += "</table>\n"

    with open("static/systematic_scats_transects_location", "w") as f_out:
        f_out.write(out)

    return True





@app.route("/systematic_scats_transect_location")
@fn.check_login
def systematic_scats_transect_location():
    """
    Create file with locations for systematic scats
    
    !require the check_systematic_scats_transect_location.py script
    """

    process = subprocess.Popen(["python3", "check_systematic_scats_transect_location.py"])

    return 'The analysis will be available soon. Please wait for 5 minutes. <a href="/scats">Go to Scats page</a>'

