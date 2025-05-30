"""
WolfDB web service
(c) Olivier Friard


launch with:
export WOLFDB_CONFIG_PATH=PATH_TO/config.ini; python wolfdb.py

"""

from flask import Flask, render_template, redirect, request, flash, session
from markupsafe import Markup
from flask_session import Session
from sqlalchemy import text
from config import config
import functions as fn
import utm
import logging
import secrets
import datetime
import pathlib as pl

# blueprints
import google_auth
from scats_bp import scats
from paths_bp import paths
from packs_bp import packs
from transects_bp import transects
from snowtracks_bp import tracks
from genetic_bp import genetic
from dead_wolves_bp import dead_wolves
from admin_bp import admin
from analysis_bp import analysis

__version__ = "2024-04-11"

DEFAULT_START_DATE = "1990-01-01"
DEFAULT_END_DATE = "2030-12-31"


app = Flask(__name__)

app.secret_key = secrets.token_hex(16)

SESSION_TYPE = "filesystem"
app.config.from_object(__name__)
app.config["SESSION_PERMANENT"] = False
Session(app)


app.register_blueprint(google_auth.app)
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
# @fn.check_login
def home():
    """
    home page
    """
    if "start_date" not in session:
        session["start_date"] = DEFAULT_START_DATE
    if "end_date" not in session:
        session["end_date"] = DEFAULT_END_DATE

    session["default_start_date"] = DEFAULT_START_DATE
    session["default_end_date"] = DEFAULT_END_DATE

    session["background_color"] = params["background_color"]

    return render_template("home.html", header_title="Home", mode=params["mode"])


@app.route("/version")
def version():
    return __version__


@app.route("/settings", methods=("GET", "POST"))
@fn.check_login
def settings():
    """
    selection of the analysis time interval (start_date and end_date)
    """

    def iso_date_validator(s: str) -> bool:
        try:
            datetime.datetime.strptime(s, "%Y-%m-%d")
            return True
        except ValueError:
            return False

    if request.method == "GET":
        # check if current user can modify allele value (allele modifier)
        with fn.conn_alchemy().connect() as con:
            allele_modifier = (
                "Yes"
                if (
                    con.execute(
                        text("SELECT allele_modifier FROM users WHERE email = :email"),
                        {"email": session["email"]},
                    )
                    .mappings()
                    .fetchone()["allele_modifier"]
                )
                else "No"
            )

        return render_template(
            "settings.html",
            header_title="Settings",
            default_start_date=DEFAULT_START_DATE,
            default_end_date=DEFAULT_END_DATE,
            allele_modifier=allele_modifier,
        )

    if request.method == "POST":
        if "enable_date_interval" in request.form:
            if not iso_date_validator(request.form["start_date"]):
                flash(
                    fn.alert_danger(
                        f"The start date <b>{request.form['start_date']}</b> is not correct. Use the YYYY-MM-DD format."
                    )
                )
                return render_template("settings.html", header_title="Settings")

            if not iso_date_validator(request.form["end_date"]):
                flash(
                    fn.alert_danger(
                        f"The end date <b>{request.form['end_date']}</b> is not correct. Use the YYYY-MM-DD format."
                    )
                )
                return render_template("settings.html", header_title="Settings")

            # check if end < start
            if datetime.datetime.strptime(
                request.form["end_date"], "%Y-%m-%d"
            ) < datetime.datetime.strptime(request.form["start_date"], "%Y-%m-%d"):
                flash(fn.alert_danger("The end date cannot be before the start date."))
                return render_template("settings.html", header_title="Settings")

            session["start_date"] = request.form["start_date"]
            session["end_date"] = request.form["end_date"]
        else:
            session["start_date"] = DEFAULT_START_DATE
            session["end_date"] = DEFAULT_END_DATE

        return redirect("/")


@app.route("/rev_geocoding/<int:east>/<int:north>/<zone>")
def rev_geocoding(east: int, north: int, zone: str):
    """
    get location info from UTM coordinates, zone
    """

    try:
        lat_lon = utm.to_latlon(int(east), int(north), int(zone[:-1]), zone[-1])
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

    if r is None:
        return {
            "continent": "",
            "country": "",
            "region": "",
            "province": "",
            "province_code": "",
            "municipality": "",
            "location": "",
        }

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

    results_path = (
        pl.Path(pl.Path(app.static_url_path).name)
        / pl.Path("results")
        / pl.Path(session["email"])
    )
    results_path.mkdir(parents=True, exist_ok=True)
    out = '<table class="table table-striped">'
    for f in sorted(list(results_path.glob("*"))):
        out += f'<tr><td><a href="{f}">{f.name}</a></td></tr>'

    return render_template(
        "results.html",
        header_title="Analysis results",
        title="Analysis results",
        content=Markup(out),
    )


@app.route("/query", methods=("GET", "POST"))
@fn.check_login
def query():
    """
    execute a SQL query and show results
    """
    if request.method == "GET":
        return render_template("query.html")

    if request.method == "POST":
        sql_query = request.form["sql"]

        # **Sanitize Input**: Check if the query is a SELECT query
        if not sql_query.strip().lower().startswith("select"):
            return render_template(
                "query.html",
                sql_query=sql_query,
                error="Error: Only SELECT queries are allowed.",
            )

        if "delete " in sql_query.strip().lower():
            return render_template(
                "query.html",
                sql_query=sql_query,
                error="Error: The query cannot contain 'delete'",
            )

        if "update " in sql_query.strip().lower():
            return render_template(
                "query.html",
                sql_query=sql_query,
                error="Error: The query cannot contain 'update'",
            )

        with fn.conn_alchemy().connect() as con:
            try:
                error = ""
                result = con.execute(text(sql_query))
            except Exception as e:
                error = e
                return render_template("query.html", sql_query=sql_query, error=error)
                # return f"SQL error: {error}"

        return render_template(
            "query.html",
            sql_query=sql_query,
            columns=result.keys(),
            rows=result.mappings().fetchall(),
            error=error,
        )


if __name__ == "__main__":
    app.run(host="0.0.0.0")
