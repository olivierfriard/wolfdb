"""
WolfDB web service
(c) Olivier Friard

flask blueprint for service administration
"""

import sys
from flask import render_template, session, current_app, flash, redirect, Blueprint
import subprocess
from sqlalchemy import text

from config import config
import functions as fn

app = Blueprint("admin", __name__, template_folder="templates")

params = config()

app.debug = params["debug"]


@app.route("/admin")
@fn.check_login
def admin():
    current_app.db_log.info(
        f"{session.get('user_name', session['email'])} accessed to admin page"
    )

    if session.get("role", "").lower() == "administrator":
        # users list
        with fn.conn_alchemy().connect() as con:
            users = con.execute(text("SELECT * FROM users")).mappings().all()

        return render_template(
            "admin.html",
            header_title="Administration page",
            title="Administration",
            mode=params["mode"],
            debug=params["debug"],
            users=users,
        )
    else:
        flash(fn.alert_danger("<h2>You are not allowed to access this resource</h2>"))
        return redirect("/")


@app.route("/update_redis")
@fn.check_login
def update_redis():
    """
    update redis with the WA and genotypes loci values

    !require the update_redis.py file
    """
    _ = subprocess.Popen([sys.executable, "update_redis.py"])

    flash(
        fn.alert_success(
            "Redis updating with WA and genotypes loci in progress.<br>It will take several minutes to complete."
        )
    )

    return redirect("/admin")


@app.route("/update_redis_genotypes")
@fn.check_login
def update_redis_with_genotypes_loci():
    """
    web interface to update redis with the genotypes loci values

    !require the update_redis_with_genotypes_loci_values file
    """
    _ = subprocess.Popen([sys.executable, "update_redis_with_genotypes_loci_values.py"])

    flash(
        fn.alert_success(
            "Redis updating with genotypes loci in progress.<br>It will take several minutes to complete."
        )
    )

    return redirect("/admin")


@app.route("/update_redis_wa")
@fn.check_login
def update_redis_with_wa_loci():
    """
    update redis with the WA loci values

    !require the update_redis_with_wa_loci_values.py file
    """
    _ = subprocess.Popen([sys.executable, "update_redis_with_wa_loci_values.py"])

    flash(
        fn.alert_success(
            "Redis updating with WA loci in progress.<br>It will take several minutes to complete."
        )
    )

    return redirect("/admin")
