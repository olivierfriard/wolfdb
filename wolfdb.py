"""
WolfDB web service
(c) Olivier Friard
"""

from flask import Flask, render_template, redirect, request, Markup, flash, session
import psycopg2
import psycopg2.extras
from config import config


from track import Track

import functions as fn

# blueprints
from scats_bp import scats
from paths_bp import paths
from transects_bp import transects
from snowtracks_bp import snowtracks
from genetic_bp import genetic

__version__ = "1"

app = Flask(__name__)

app.debug = True

app.secret_key = "dfhsdlfsdhflsdfhsnqq45"

app.register_blueprint(scats.app)
app.register_blueprint(paths.app)
app.register_blueprint(transects.app)
app.register_blueprint(snowtracks.app)
app.register_blueprint(genetic.app)




@app.route("/")
def home():
    return render_template("home.html")

@app.route("/version")
def version():
    return __version__



@app.route("/test")
def test():
    return render_template("test.html")


@app.route("/test_action", methods=("POST",))
def test_action():
    print(request.form)
    return f"""
<input id="date" type="text" value="{request.form["path_id"].split(" ")[-1]}">
"""














if __name__ == "__main__":
    app.run(host="127.0.0.1")


