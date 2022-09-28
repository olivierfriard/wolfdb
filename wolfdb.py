"""
WolfDB web service
(c) Olivier Friard
"""
from functools import wraps
from flask import Flask, render_template, redirect, request, Markup, flash, session
from flask_session import Session

import psycopg2
import psycopg2.extras
from config import config
import functions as fn
import utm
import logging
import secrets
import datetime
import pathlib as pl

# blueprints
from auth import auth as auth_blueprint
from scats_bp import scats
from paths_bp import paths
from packs_bp import packs
from transects_bp import transects
from snowtracks_bp import tracks
from genetic_bp import genetic
from dead_wolves_bp import dead_wolves
from admin_bp import admin
from analysis_bp import analysis

__version__ = "2022-09-28"

app = Flask(__name__)

app.secret_key = secrets.token_hex(16)

SESSION_TYPE = "filesystem"
app.config.from_object(__name__)
Session(app)

app.register_blueprint(auth_blueprint)

app.register_blueprint(scats.app)
app.register_blueprint(paths.app)
app.register_blueprint(packs.app)
app.register_blueprint(transects.app)
app.register_blueprint(tracks.app)
app.register_blueprint(genetic.app)
app.register_blueprint(dead_wolves.app)
app.register_blueprint(admin.app)
app.register_blueprint(analysis.app)

params = config()
app.debug = params["debug"]

app.db_log = logging.getLogger("db_activity")

# Create handlers
log_handler = logging.FileHandler(params["log_path"])
log_handler.setLevel(logging.DEBUG)

# Create formatters and add it to handlers
log_format = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
log_handler.setFormatter(log_format)

# Add handlers to the logger
app.db_log.addHandler(log_handler)

# set INFO otherwise WARNING (?)
app.db_log.setLevel(logging.INFO)


@app.route("/")
@fn.check_login
def home():
    if "start_date" not in session:
        session["start_date"] = "1900-01-01"
    if "end_date" not in session:
        session["end_date"] = "2100-01-01"

    return render_template("home.html", header_title="Home", mode=params["mode"])


@app.route("/version")
def version():
    return __version__


@app.route("/settings", methods=("GET", "POST"))
def settings():
    """
    selection of the analysis time interval (start_date and end_date)
    """

    def iso_date_validator(s: str) -> bool:
        try:
            datetime.datetime.strptime(s, "%Y-%m-%d")
            return True
        except ValueError:
            raise False

    if request.method == "GET":
        return render_template("settings.html", header_title="Settings")

    if request.method == "POST":

        if not iso_date_validator(request.form["start_date"]) or not iso_date_validator(request.form["end_date"]):
            return render_template("settings.html", header_title="Settings")

        session["start_date"] = request.form["start_date"]
        session["end_date"] = request.form["end_date"]

        return redirect("/")


@app.route("/rev_geocoding/<east>/<north>/<zone>")
def rev_geocoding(east, north, zone):
    try:
        lat_lon = utm.to_latlon(int(east), int(north), int(zone.replace("N", "")), zone[-1])
    except Exception:
        return {
            "continent": "",
            "country": "",
            "region": "",
            "province": "",
            "province_code": "",
            "municipality": "",
            "location": "",
        }
    r = fn.reverse_geocoding(lat_lon[::-1])

    return r


@app.route("/view_sample/<sample_id>")
@fn.check_login
def view_sample(sample_id):
    """
    View sample: scat (E) or tissue (T, M)
    """
    if sample_id.startswith("E"):
        return redirect(f"/view_scat/{sample_id}")

    if sample_id.startswith("T") or sample_id.startswith("M"):
        return redirect(f"/view_tissue/{sample_id}")

    flash(Markup("Sample not found"))
    return redirect("/")


@app.route("/my_results")
@fn.check_login
def my_results():
    """
    display all result files
    """

    results_path = pl.Path(pl.Path(app.static_url_path).name) / pl.Path("results") / pl.Path(session["email"])
    results_path.mkdir(parents=True, exist_ok=True)
    out = "<h1>Analysis results</a>"
    out += '<table class="table table-striped">'
    for f in results_path.glob("*"):
        out += f'<tr><td><a href="{f}">{f.name}</a></td></tr>'
    return out


if __name__ == "__main__":
    app.run(host="0.0.0.0")
