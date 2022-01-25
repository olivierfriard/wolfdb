"""
WolfDB web service
(c) Olivier Friard

flask blueprint for service administration
"""



import flask
from flask import Flask, render_template, redirect, request, Markup, flash, session, current_app
import psycopg2
import psycopg2.extras
from config import config
import json

import functions as fn

app = flask.Blueprint("admin", __name__, template_folder="templates")

app.debug = True

params = config()

@app.route("/admin")
@fn.check_login
def admin():

    current_app.db_log.info(f"{session['email']} accessed to admin page")

    return render_template("admin.html")

