"""
WolfDB web service
(c) Olivier Friard

flask blueprint for scats management
"""



import flask
from flask import Flask, render_template, redirect, request, Markup, flash, session
import psycopg2
import psycopg2.extras
from config import config

import functions as fn

app = flask.Blueprint("genetic", __name__, template_folder="templates")

app.debug = True


params = config()

@app.route("/add_genetic/<wa_code>")
def add_genetic(wa_code):
    return render_template("transects.html")

