"""
WolfDB web service
(c) Olivier Friard

flask blueprint for service administration
"""


import flask
from flask import render_template, session, current_app

from config import config

import functions as fn

app = flask.Blueprint("admin", __name__, template_folder="templates")

params = config()

app.debug = params["debug"]


@app.route("/admin")
@fn.check_login
def admin():
    current_app.db_log.info(f"{session.get('user_name', session['email'])} accessed to admin page")

    return render_template("admin.html", header_title="Administration page", mode=params["mode"], debug=params["debug"])
