"""
auth
from:
https://www.digitalocean.com/community/tutorials/how-to-add-authentication-to-your-app-with-flask-login
"""


from flask import Blueprint, render_template, request, redirect, flash, session, current_app
from markupsafe import Markup
from werkzeug.security import check_password_hash
import psycopg2
import psycopg2.extras

import functions as fn


auth = Blueprint("auth", __name__)


@auth.route("/login")
def login():
    return render_template("login.html")


@auth.route("/login_post", methods=["POST"])
def login_post():

    email = request.form.get("email")
    password = request.form.get("password")

    if not email or not password:
        flash("Input email and password")
        return redirect("/login")

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT * FROM users WHERE email = %s", [email])
    result = cursor.fetchone()

    if check_password_hash(result["password"], password, method='pbkdf2:sha256'):
        session["user_id"] = result["id"]
        session["firstname"] = result["firstname"]
        session["lastname"] = result["lastname"]
        session["email"] = result["email"]

        current_app.db_log.info(f"Login of {session['firstname']} {session['lastname']} ({session['email']})")

        flash(Markup(f"<h2>Welcome {session['firstname']} {session['lastname']}</h2>"))
        return redirect("/")
    else:
        flash("Please retry")
        return redirect("/login")


@auth.route("/logout")
@fn.check_login
def logout():

    try:
        current_app.db_log.info(f"Logout of {session['firstname']} {session['lastname']} ({session['email']})")
    except Exception:
        pass

    try:
        session.pop("user_id", None)
        session.pop("firstname", None)
        session.pop("lastname", None)
        session.pop("email", None)
    except Exception:
        pass

    return redirect("/")
