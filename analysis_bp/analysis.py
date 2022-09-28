"""
WolfDB web service
(c) Olivier Friard

flask blueprint for data analysis
"""


import flask
from flask import render_template, redirect, request, Markup, flash, make_response, session
import psycopg2
import psycopg2.extras
from config import config
import pathlib as pl
import os
import functions as fn
import paths_completeness
import datetime as dt
import copy
import uuid
import sys
import subprocess
import time
import zipfile
import fiona

# from . import cell_occupancy as cell_occupancy_module

app = flask.Blueprint("analysis", __name__, template_folder="templates", static_url_path="/static")

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


@app.route("/analysis")
@fn.check_login
def analysis():
    """
    analysis home page
    """

    return render_template("analysis.html", header_title="Analysis")


@app.route("/path_completeness")
@fn.check_login
def path_completeness():
    """
    create shapefile with paths completeness
    """

    # remove files older than 24h
    for path in pl.Path("static").glob("paths_completeness*.zip"):
        if time.time() - os.path.getctime(path) > 86400:
            os.remove(path)

    dir_name = f"static/paths_completeness_{dt.datetime.now():%Y-%m-%d_%H%M%S}"

    zip_path = paths_completeness.paths_completeness_shapefile(
        dir_path=dir_name,
        log_file="/tmp/paths_completeness.log",
        start_date=session["start_date"],
        end_date=session["end_date"],
    )

    return redirect(f"{app.static_url_path}/{pl.Path(zip_path).name}")


@app.route("/transects_n_samples/<year_init>/<year_end>")
@fn.check_login
def transects_n_samples(year_init, year_end):

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # check if path based on transect exist
    cursor.execute("SELECT * FROM transects ORDER BY transect_id")
    transects = cursor.fetchall()

    out = {}
    template = {}
    header = "Transect ID\t"
    # check max number of sampling by year
    cursor.execute(
        "SELECT MAX(c) AS n_paths FROM (SELECT COUNT(*) AS c FROM paths WHERE transect_id != '' GROUP BY transect_id) x"
    )
    result = cursor.fetchone()
    template = ["NA"] * result["n_paths"]
    for i in range(result["n_paths"]):
        header += f"{year_init}-{i + 1}\t"

    for transect in transects:

        row_out = copy.deepcopy(template)

        cursor.execute(
            (
                "SELECT path_id FROM paths "
                "WHERE transect_id = %s "
                "AND EXTRACT(YEAR FROM date) BETWEEN %s AND %s "
                "ORDER BY date"
            ),
            [transect["transect_id"], year_init, year_end],
        )
        paths = cursor.fetchall()

        idx = 0
        for path in paths:
            cursor.execute(
                ("SELECT count(*) AS n_scats FROM scats WHERE path_id = %s "),
                [path["path_id"]],
            )
            scats = cursor.fetchone()
            row_out[idx] = str(scats["n_scats"])
            idx += 1

        out[transect["transect_id"]] = copy.deepcopy(row_out)

    out_str = header[:-1] + "\n"
    for transect in out:
        out_str += transect + "\t"
        out_str += "\t".join(out[transect])
        out_str += "\t"
        out_str = out_str[:-1] + "\n"

    response = make_response(out_str, 200)
    response.headers["Content-type"] = "'text/tab-separated-values"
    response.headers["Content-disposition"] = "attachment; filename=transects_n-samples.tsv"

    return response


@app.route("/transects_samples_presence/<year_init>/<year_end>")
@fn.check_login
def transects_samples_presence(year_init, year_end):
    """
    return presence of samples on transects
    """

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # check if path based on transect exist
    cursor.execute("SELECT * FROM transects ORDER BY transect_id")
    transects = cursor.fetchall()

    out = {}
    template = {}
    header = "Transect ID\t"
    # check max number of sampling
    cursor.execute(
        "select max(c) as n_paths from (select count(*) as c from paths where transect_id != '' group by transect_id) x"
    )
    result = cursor.fetchone()
    template = ["NA"] * result["n_paths"]
    for i in range(result["n_paths"]):
        header += f"{year_init}-{i + 1}\t"

    for transect in transects:

        row_out = copy.deepcopy(template)

        cursor.execute(
            (
                "SELECT path_id FROM paths "
                "WHERE transect_id = %s "
                "AND EXTRACT(YEAR FROM date) BETWEEN %s AND %s "
                "ORDER BY date"
            ),
            [transect["transect_id"], year_init, year_end],
        )
        paths = cursor.fetchall()

        idx = 0
        for path in paths:
            cursor.execute(
                ("SELECT count(*) AS n_scats FROM scats WHERE path_id = %s "),
                [path["path_id"]],
            )
            scats = cursor.fetchone()
            row_out[idx] = str(1 if scats["n_scats"] > 0 else 0)
            idx += 1

        out[transect["transect_id"]] = copy.deepcopy(row_out)

    out_str = header[:-1] + "\n"
    for transect in out:
        out_str += transect + "\t"
        out_str += "\t".join(out[transect])
        out_str += "\t"
        out_str = out_str[:-1] + "\n"

    response = make_response(out_str, 200)
    response.headers["Content-type"] = "'text/tab-separated-values"
    response.headers["Content-disposition"] = "attachment; filename=transects_samples_presence.tsv"

    return response


@app.route("/transects_dates/<year_init>/<year_end>")
@fn.check_login
def transects_dates(year_init, year_end):

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # check if path based on transect exist
    cursor.execute("SELECT * FROM transects ORDER BY transect_id")
    transects = cursor.fetchall()

    sampling_years = range(int(year_init), int(year_end) + 1)

    out = {}
    template = {}
    header = "Transect ID\t"
    # check max number of sampling
    cursor.execute(
        (
            "SELECT max(c) AS n_paths FROM "
            "      (SELECT count(*) AS c FROM paths WHERE transect_id != '' GROUP BY transect_id) x"
        )
    )
    result = cursor.fetchone()
    template = ["NA"] * result["n_paths"]
    for i in range(result["n_paths"]):
        header += f"{year_init}-{i + 1}\t"

    for transect in transects:

        row_out = copy.deepcopy(template)

        cursor.execute(
            (
                "SELECT path_id, date::date as date FROM paths "
                "WHERE transect_id = %s "
                "AND EXTRACT(YEAR FROM date) BETWEEN %s AND %s "
                "ORDER BY date"
            ),
            [transect["transect_id"], year_init, year_end],
        )
        paths = cursor.fetchall()
        idx = 0
        for path in paths:
            row_out[idx] = str(path["date"])
            idx += 1

        out[transect["transect_id"]] = copy.deepcopy(row_out)

    out_str = header[:-1] + "\n"
    for transect in out:
        out_str += transect + "\t"
        out_str += "\t".join(out[transect])
        out_str += "\t"
        out_str = out_str[:-1] + "\n"

    response = make_response(out_str, 200)
    response.headers["Content-type"] = "'text/tab-separated-values"
    response.headers["Content-disposition"] = "attachment; filename=transects_dates.tsv"

    return response


@app.route("/transects_completeness/<year_init>/<year_end>")
@fn.check_login
def transects_completeness(year_init, year_end):

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # check if path based on transect exist
    cursor.execute("SELECT * FROM transects ORDER BY transect_id")
    transects = cursor.fetchall()

    out = {}
    template = {}
    header = "Transect ID\t"
    # check max number of sampling
    cursor.execute(
        "SELECT max(c) AS n_paths FROM (SELECT count(*) AS c from paths where transect_id != '' group by transect_id) x"
    )
    result = cursor.fetchone()
    template = ["NA"] * result["n_paths"]
    for i in range(result["n_paths"]):
        header += f"{year_init}-{i + 1}\t"

    for transect in transects:

        row_out = copy.deepcopy(template)

        cursor.execute(
            (
                "SELECT completeness FROM paths "
                "WHERE transect_id = %s "
                "AND EXTRACT(YEAR FROM date) BETWEEN %s AND %s "
                "ORDER BY date"
            ),
            [transect["transect_id"], year_init, year_end],
        )
        paths = cursor.fetchall()
        idx = 0
        for path in paths:
            row_out[idx] = str(path["completeness"])
            idx += 1

        out[transect["transect_id"]] = copy.deepcopy(row_out)

    out_str = header[:-1] + "\n"
    for transect in out:
        out_str += transect + "\t"
        out_str += "\t".join(out[transect])
        out_str += "\t"
        out_str = out_str[:-1] + "\n"

    response = make_response(out_str, 200)
    response.headers["Content-type"] = "'text/tab-separated-values"
    response.headers["Content-disposition"] = "attachment; filename=transects_completeness.tsv"

    return response


@app.route("/cell_occupancy/<year_init>/<year_end>", methods=("GET", "POST"))
@fn.check_login
def cell_occupancy(year_init: str, year_end: str):
    """
    grid occupancy by cell (from shapefile) by path
    """

    if request.method == "GET":

        # remove files older than 24h
        for path in pl.Path("static").glob("cell_occupancy_*.zip"):
            if time.time() - os.path.getctime(path) > 86400:
                os.remove(path)

        return render_template(
            "upload_shapefile.html", header_title="Cell occupancy", year_init=year_init, year_end=year_end
        )

    if request.method == "POST":

        new_file = request.files["new_file"]

        # check file extension
        if pl.Path(new_file.filename).suffix.upper() not in [".ZIP"]:
            flash(fn.alert_danger("The uploaded file does not have an allowed extension (must be <b>.zip</b>)"))
            return redirect(f"/cell_occupancy/{year_init}/{year_end}")

        # save uploaded file
        try:
            filename = pl.Path(params["upload_folder"]) / pl.Path(
                str(uuid.uuid4()) + str(pl.Path(new_file.filename).suffix)
            )
            new_file.save(filename)
        except Exception:
            flash(fn.alert_danger("Error saving the uploaded file") + f"({error_info(sys.exc_info())})")
            return redirect(f"/cell_occupancy/{year_init}/{year_end}")

        # extract zip file
        try:
            extracted_dir = pl.Path(params["temp_folder"]) / pl.Path(filename).stem
            with zipfile.ZipFile(filename, "r") as zip_ref:
                zip_ref.extractall(extracted_dir)
        except Exception:
            flash(fn.alert_danger("Error during zip extraction") + f"({error_info(sys.exc_info())})")
            return redirect(f"/cell_occupancy/{year_init}/{year_end}")

        # remove uploaded file
        pl.Path(filename).unlink()

        # check if zip contains .shp
        if len(list(extracted_dir.glob("*.shp"))) != 1:
            flash(fn.alert_danger(".shp file not found in ZIP archive"))
            return redirect(f"/cell_occupancy/{year_init}/{year_end}")

        # retrieve .shp file name
        shp_file_path = str(list(extracted_dir.glob("*.shp"))[0])

        # check shp file
        shapes = fiona.open(shp_file_path)
        # check CRS / SRID
        try:
            int(shapes.crs["init"].replace("epsg:", ""))
        except Exception:
            flash(fn.alert_danger(f"The CRS/SRID was not found: {shapes.crs['init']}"))
            return redirect(f"/cell_occupancy/{year_init}/{year_end}")

        # check geometry
        for shape in shapes:
            if shape["geometry"]["type"] not in ["Polygon", "MultiPolygon"]:
                flash(fn.alert_danger("All elements must have a Polygon or MultiPolygon geometry"))
                return redirect(f"/cell_occupancy/{year_init}/{year_end}")

        # ouput_path
        output_path = f"cell_occupancy_{dt.datetime.now():%Y-%m-%d_%H%M%S}.zip"

        _ = subprocess.Popen(["python3", "cell_occupancy.py", shp_file_path, year_init, year_end, output_path])

        return redirect(f"/cell_occupancy_check_results/{output_path}")


@app.route("/cell_occupancy_check_results/<output_path>")
@fn.check_login
def cell_occupancy_check_results(output_path):
    """
    display page waiting fo results to be ready
    the page autoreload every 20 seconds until results file is found
    """

    if (pl.Path("static") / pl.Path(output_path)).is_file():
        return render_template(
            "cell_occupancy_result.html",
            header_title="Cell occupancy results",
            output_path=Markup(
                f'<p>The results are ready to be downloaded:<br><a href="{app.static_url_path}/{output_path}">{output_path}</a></p>'
            ),
            autoreload="",
        )
    else:
        return render_template(
            "cell_occupancy_result.html",
            header_title="Cell occupancy results",
            output_path=Markup(
                "<p><b>The results are not ready</b>.<br>Please wait, this page will reload automatically every 20 seconds...</p>"
            ),
            autoreload=Markup('<meta http-equiv="refresh" content="20">'),
        )
