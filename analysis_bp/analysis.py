"""
WolfDB web service
(c) Olivier Friard

flask blueprint for data analysis
"""


import flask
from flask import render_template, redirect, request, Markup, flash, session, make_response
import psycopg2
import psycopg2.extras
from config import config
import json
import pathlib as pl
import os
import sys
import uuid
import functions as fn
import paths_completeness

app = flask.Blueprint("analysis", __name__, template_folder="templates")

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

    if pl.Path("static/paths_completeness.zip").is_file():
        os.remove("static/paths_completeness.zip")

    zip_path = paths_completeness.paths_completeness_shapefile(
        "static/paths_completeness", "/tmp/paths_completeness.log"
    )

    zip_file_name = pl.Path(zip_path).name

    return redirect(f"/static/{zip_file_name}")
