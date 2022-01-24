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

# blueprints
from auth import auth as auth_blueprint
from scats_bp import scats
from paths_bp import paths
from transects_bp import transects
from snowtracks_bp import snowtracks
from genetic_bp import genetic
from dead_wolves_bp import dead_wolves

__version__ = "1"

app = Flask(__name__)
SESSION_TYPE = "filesystem"
app.config.from_object(__name__)
Session(app)

app.secret_key = "dfhsdlfsdhflsdfhsnqq45"

app.register_blueprint(auth_blueprint)

app.register_blueprint(scats.app)
app.register_blueprint(paths.app)
app.register_blueprint(transects.app)
app.register_blueprint(snowtracks.app)
app.register_blueprint(genetic.app)
app.register_blueprint(dead_wolves.app)

params = config()
app.debug = params["debug"]



@app.route("/")
@fn.check_login
def home():
    return render_template("home.html",
                           header_title="Home",
                           mode=params["mode"])


@app.route("/version")
def version():
    return __version__



@app.route("/rev_geocoding/<east>/<north>/<zone>")
def rev_geocoding(east, north ,zone):
    try:
        lat_lon = utm.to_latlon(int(east), int(north), int(zone.replace("N", "")), zone[-1])
    except Exception:
        return {"continent": "",
                "country": "",
                "region": "",
                "province": "",
                "province_code": "",
                "municipality": "",
                "location": ""
              }
    r = fn.reverse_geocoding(lat_lon[::-1])

    return r


@app.route("/view_sample/<sample_id>")
@fn.check_login
def view_sample(sample_id):
    """
    View sample: scat (E) or tissue (T)
    """
    if sample_id.startswith("E"):
        return redirect(f"/view_scat/{sample_id}")
    if sample_id.startswith("T"):
        return redirect(f"/view_tissue/{sample_id}")
    flash(Markup("Sample not found"))
    return redirect("/")



'''
@app.route("/delete_scats")
@fn.check_login
def delete_scats():

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("DELETE FROM scats")
    connection.commit()
    return redirect("/")


@app.route("/delete_paths")
@fn.check_login
def delete_paths():

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("DELETE FROM paths")
    connection.commit()
    return redirect("/")
'''


if __name__ == "__main__":
    app.run(host="0.0.0.0")


