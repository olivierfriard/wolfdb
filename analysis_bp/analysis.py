"""
WolfDB web service
(c) Olivier Friard

flask blueprint for data analysis
"""


import flask
from flask import render_template, redirect, request, flash, make_response, session
from sqlalchemy import text
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
    require paths_completeness module
    """

    dir_prefix = pl.Path(pl.Path(app.static_url_path).name) / pl.Path("results") / pl.Path(session["email"])
    # create dir if not exists
    dir_prefix.mkdir(exist_ok=True)

    # remove files older than 48 hours
    for path in dir_prefix.glob("paths_completeness*.zip"):
        if time.time() - os.path.getctime(path) > 86400 * 2:
            os.remove(path)

    dir_path = dir_prefix / pl.Path(
        (
            f"paths_completeness_"
            f'from_{session["start_date"]}_to_{session["end_date"]}'
            f"_requested_at_{dt.datetime.now():%Y-%m-%d_%H%M%S}"
        )
    )

    zip_file_name = paths_completeness.paths_completeness_shapefile(
        dir_path=dir_path,
        log_file="/tmp/paths_completeness.log",
        start_date=session["start_date"],
        end_date=session["end_date"],
    )

    return redirect("/my_results")


@app.route("/transects_n_samples/<mode>")
@fn.check_login
def transects_samples(mode: str):
    """
    return the number of samples on transects

    Args:
        mode (str): "number": number of samples
                    "presence": presence of samples (1/0)
    """

    sep = ";"

    year_init = session["start_date"][:4]

    con = fn.conn_alchemy().connect()

    # check if path based on transect exist
    transects = con.execute(text("SELECT * FROM transects ORDER BY transect_id")).mappings().all()

    out: dict = {}
    template: dict = {}
    header = f"Transect ID{sep}"
    # check max number of sampling by year
    result = (
        con.execute(
            text(
                "SELECT MAX(c) AS n_paths "
                "FROM "
                "(SELECT COUNT(*) AS c FROM paths "
                "      WHERE transect_id != '' "
                "            AND date BETWEEN :start_date AND :end_date "
                "      GROUP BY transect_id "
                ") x"
            ),
            {"start_date": session["start_date"], "end_date": session["end_date"]},
        )
        .mappings()
        .fetchone()
    )
    template = ["NA"] * result["n_paths"]
    for i in range(result["n_paths"]):
        header += f"{year_init}-{i + 1}{sep}"

    for transect in transects:
        row_out = copy.deepcopy(template)

        paths = (
            con.execute(
                text("SELECT path_id FROM paths WHERE transect_id = :transect_id AND date BETWEEN :start_date AND :end_date ORDER BY date"),
                {"transect_id": transect["transect_id"], "start_date": session["start_date"], "end_date": session["end_date"]},
            )
            .mappings()
            .all()
        )

        idx = 0
        for path in paths:
            scats = (
                con.execute(text("SELECT count(*) AS n_scats FROM scats WHERE path_id = :path_id"), {"path_id": path["path_id"]})
                .mappings()
                .fetchone()
            )
            if mode == "number":
                row_out[idx] = str(scats["n_scats"])
            if mode == "presence":
                row_out[idx] = str(1 if scats["n_scats"] > 0 else 0)
            idx += 1

        out[transect["transect_id"]] = copy.deepcopy(row_out)

    out_str = header[:-1] + "\n"
    for transect in out:
        out_str += transect + sep
        out_str += sep.join(out[transect])
        out_str += sep
        out_str = out_str[:-1] + "\n"

    response = make_response(out_str, 200)

    if mode == "number":
        file_name = "transects_n-samples"
    if mode == "presence":
        file_name = "transects_samples_presence-samples"

    if sep == "\t":
        response.headers["Content-type"] = "text/tab-separated-values"
        extension = "tsv"
    if sep in (",", ";"):
        response.headers["Content-type"] = "text/csv"
        extension = "csv"

    response.headers["Content-disposition"] = f"attachment; filename={file_name}.{extension}"

    return response


@app.route("/transects_dates")
@fn.check_login
def transects_dates():
    sep = ";"

    year_init = session["start_date"][:4]

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # check if path based on transect exist
    cursor.execute("SELECT * FROM transects ORDER BY transect_id")
    transects = cursor.fetchall()

    out: dict = {}
    template: dict = {}
    header = f"Transect ID{sep}"
    # check max number of sampling
    cursor.execute(
        (
            "SELECT MAX(c) AS n_paths "
            "FROM "
            "(SELECT COUNT(*) AS c FROM paths "
            "      WHERE transect_id != '' "
            "            AND date BETWEEN %s AND %s "
            "      GROUP BY transect_id "
            ") x"
        ),
        (
            session["start_date"],
            session["end_date"],
        ),
    )
    result = cursor.fetchone()
    template = ["NA"] * result["n_paths"]
    for i in range(result["n_paths"]):
        header += f"{year_init}-{i + 1}{sep}"

    for transect in transects:
        row_out = copy.deepcopy(template)

        cursor.execute(
            ("SELECT path_id, date::date as date FROM paths " "WHERE transect_id = %s " "AND date BETWEEN %s AND %s " "ORDER BY date"),
            (transect["transect_id"], session["start_date"], session["end_date"]),
        )
        paths = cursor.fetchall()
        idx = 0
        for path in paths:
            row_out[idx] = str(path["date"])
            idx += 1

        out[transect["transect_id"]] = copy.deepcopy(row_out)

    out_str = header[:-1] + "\n"
    for transect in out:
        out_str += transect + sep
        out_str += sep.join(out[transect])
        out_str += sep
        out_str = out_str[:-1] + "\n"

    response = make_response(out_str, 200)
    if sep == "\t":
        response.headers["Content-type"] = "text/tab-separated-values"
        response.headers["Content-disposition"] = "attachment; filename=transects_dates.tsv"

    if sep in (",", ";"):
        response.headers["Content-type"] = "text/csv"
        response.headers["Content-disposition"] = "attachment; filename=transects_dates.csv"

    return response


@app.route("/transects_completeness")
@fn.check_login
def transects_completeness():
    sep = ";"
    year_init = session["start_date"][:4]

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # check if path based on transect exist
    cursor.execute("SELECT * FROM transects ORDER BY transect_id")
    transects = cursor.fetchall()

    out = {}
    template = {}
    header = f"Transect ID{sep}"
    # check max number of sampling
    cursor.execute(
        (
            "SELECT MAX(c) AS n_paths "
            "FROM "
            "(SELECT COUNT(*) AS c FROM paths "
            "      WHERE transect_id != '' "
            "            AND date BETWEEN %s AND %s "
            "      GROUP BY transect_id "
            ") x"
        ),
        (
            session["start_date"],
            session["end_date"],
        ),
    )

    result = cursor.fetchone()
    template = ["NA"] * result["n_paths"]
    for i in range(result["n_paths"]):
        header += f"{year_init}-{i + 1}{sep}"

    for transect in transects:
        row_out = copy.deepcopy(template)

        cursor.execute(
            ("SELECT completeness FROM paths " "WHERE transect_id = %s " "AND date BETWEEN %s AND %s " "ORDER BY date"),
            [transect["transect_id"], session["start_date"], session["end_date"]],
        )
        paths = cursor.fetchall()
        idx = 0
        for path in paths:
            row_out[idx] = str(path["completeness"])
            idx += 1

        out[transect["transect_id"]] = copy.deepcopy(row_out)

    out_str = header[:-1] + "\n"
    for transect in out:
        out_str += transect + sep
        out_str += sep.join(out[transect])
        out_str += sep
        out_str = out_str[:-1] + "\n"

    response = make_response(out_str, 200)

    if sep == "\t":
        response.headers["Content-type"] = "text/tab-separated-values"
        extension = "tsv"
    if sep in (",", ";"):
        response.headers["Content-type"] = "text/csv"
        extension = "csv"
    response.headers["Content-disposition"] = f"attachment; filename=transects_completeness.{extension}"

    return response


@app.route("/cell_occupancy", methods=("GET", "POST"))
@fn.check_login
def cell_occupancy():
    """
    grid occupancy by cell (from shapefile) by path
    """

    year_init = session["start_date"][:4]
    year_end = session["end_date"][:4]

    if request.method == "GET":
        # remove files older than 24h
        for path in pl.Path("static").glob("cell_occupancy_*.zip"):
            if time.time() - os.path.getctime(path) > 86400:
                os.remove(path)

        return render_template(
            "upload_shapefile.html",
            header_title="Cell occupancy",
            start_date=session["start_date"],
            end_date=session["end_date"],
        )

    if request.method == "POST":
        new_file = request.files["new_file"]

        # check file extension
        if pl.Path(new_file.filename).suffix.upper() not in [".ZIP"]:
            flash(fn.alert_danger("The uploaded file does not have an allowed extension (must be <b>.zip</b>)"))
            return redirect(f"/cell_occupancy/{year_init}/{year_end}")

        # save uploaded file
        try:
            filename = pl.Path(params["upload_folder"]) / pl.Path(str(uuid.uuid4()) + str(pl.Path(new_file.filename).suffix))
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
        output_path_prefix = pl.Path(pl.Path(app.static_url_path).name) / pl.Path("results") / pl.Path(session["email"])
        # create dir if not exists
        output_path_prefix.mkdir(exist_ok=True)

        # remove files older than 48 hours
        for path in output_path_prefix.glob("cell_occupancy*.zip"):
            if time.time() - os.path.getctime(path) > 86400 * 2:
                os.remove(path)

        output_path = output_path_prefix / pl.Path(
            f'cell_occupancy_from_{session["start_date"]}_to_{session["end_date"]}_requested_at_{dt.datetime.now():%Y-%m-%d_%H%M%S}.zip'
        )

        _ = subprocess.Popen(
            [
                "python3",
                "cell_occupancy.py",
                shp_file_path,
                session["start_date"],
                session["end_date"],
                str(output_path),
            ]
        )

        return redirect("/my_results")
        """return redirect(f"/cell_occupancy_check_results/{str(output_path).replace('/', '@@@')}")"""


'''
@app.route("/cell_occupancy_check_results/<output_path>")
@fn.check_login
def cell_occupancy_check_results(output_path):
    """
    display page waiting fo results to be ready
    the page autoreload every 20 seconds until results file is found
    """

    # @ is used to encode the slash in url parameter
    output_path = output_path.replace("@@@", "/")

    if (pl.Path(output_path)).is_file():
        return render_template(
            "cell_occupancy_result.html",
            header_title="Cell occupancy results",
            output_path=Markup(
                f'<p>The results are ready to be downloaded:<br><a href="/{output_path}">{pl.Path(output_path).name}</a></p>'
            ),
            autoreload="",
            start_date=session["start_date"],
            end_date=session["end_date"],
        )
    else:
        return render_template(
            "cell_occupancy_result.html",
            header_title="Cell occupancy results",
            output_path=Markup(
                "<p><b>The results are not ready</b>.<br>Please wait, this page will reload automatically every 20 seconds...</p>"
            ),
            autoreload=Markup('<meta http-equiv="refresh" content="20">'),
            start_date=session["start_date"],
            end_date=session["end_date"],
        )
'''
