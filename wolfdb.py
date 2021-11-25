"""
WolfDB web service
(c) Olivier Friard
"""

from flask import Flask, render_template, redirect, request, Markup, flash, session
import psycopg2
import psycopg2.extras
from config import config
import functions as fn
import utm

# blueprints
from scats_bp import scats
from paths_bp import paths
from transects_bp import transects
from snowtracks_bp import snowtracks
from genetic_bp import genetic
from dead_wolves_bp import dead_wolves
#from wa_bp import wa

__version__ = "1"

app = Flask(__name__)

app.secret_key = "dfhsdlfsdhflsdfhsnqq45"

app.register_blueprint(scats.app)
app.register_blueprint(paths.app)
app.register_blueprint(transects.app)
app.register_blueprint(snowtracks.app)
app.register_blueprint(genetic.app)
app.register_blueprint(dead_wolves.app)
#app.register_blueprint(wa.app)

params = config()
app.debug = params["debug"]

@app.route("/")
def home():
    return render_template("home.html", mode=params["mode"])

@app.route("/version")
def version():
    return __version__


@app.route("/rev_geocoding/<east>/<north>/<zone>")
def rev_geocoding(east, north ,zone):
    lat_lon = utm.to_latlon(int(east), int(north), int(zone.replace("N", "")), zone[-1])
    r = fn.reverse_geocoding(lat_lon[::-1])
    return r



@app.route("/delete_scats")
def delete_scats():

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("DELETE FROM scats")
    connection.commit()
    return redirect("/")

@app.route("/delete_paths")
def delete_paths():

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("DELETE FROM paths")
    connection.commit()
    return redirect("/")



'''
@app.route("/test_action", methods=("POST",))
def test_action():
    print(request.form)
    return f"""
<input id="date" type="text" value="{request.form["path_id"].split(" ")[-1]}">
"""

'''








if __name__ == "__main__":
    app.run(host="127.0.0.1")


