"""
WolfDB web service
(c) Olivier Friard

flask blueprint for service administration
"""

from flask import render_template, session, current_app, flash, redirect, Blueprint

from config import config
import functions as fn

app = Blueprint("admin", __name__, template_folder="templates")

params = config()

app.debug = params["debug"]


@app.route("/admin")
@fn.check_login
def admin():
    current_app.db_log.info(f"{session.get('user_name', session['email'])} accessed to admin page")

    if session.get("role", "").lower() == "administrator":
        return render_template(
            "admin.html", header_title="Administration page", title="Administration", mode=params["mode"], debug=params["debug"]
        )
    else:
        flash(fn.alert_danger("<h2>You are not allowed to access this resource</h2>"))
        return redirect("/")

    return render_template("admin.html", header_title="Administration page", mode=params["mode"], debug=params["debug"])
