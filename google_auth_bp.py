"""
https://geekyhumans.com/how-to-implement-google-login-in-flask-app/
2022-02-22
"""

import flask
import os
import requests
from flask import session, abort, redirect, request, flash
from markupsafe import Markup
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
from pip._vendor import cachecontrol
import google.auth.transport.requests
from sqlalchemy import text

from config import config
import functions as fn

params = config()

app = flask.Blueprint("google_auth", __name__)

app.secret_key = "GeekyHgdfgdumxcxccxggfan.com"

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = params["oauthlib_insecure_transport"]

GOOGLE_CLIENT_ID = params["google_client_id"]

flow = Flow.from_client_secrets_file(  # Flow is OAuth 2.0 a class that stores all the information on how we want to authorize our users
    client_secrets_file=str(params["config_dir"] / "client_secret.json"),
    scopes=[
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/userinfo.email",
        "openid",
    ],  # here we are specifing what do we get after the authorization
    redirect_uri=params["redirect_uri"],  # and the redirect URI is the point where the user will end up after the authorization
)


def login_is_required(function):  # a function to check if the user is authorized or not
    def wrapper(*args, **kwargs):
        if "google_id" not in session:  # authorization required
            return abort(401)
        else:
            return function()

    return wrapper


@app.route("/login")  # the page where the user can login
def login():
    authorization_url, state = flow.authorization_url()  # asking the flow class for the authorization (login) url
    session["state"] = state
    return redirect(authorization_url)


@app.route("/login/callback")  # this is the page that will handle the callback process meaning process after the authorization
def callback():
    flow.fetch_token(authorization_response=request.url)

    if not session.get("state", False) == request.args["state"]:
        abort(500)  # state does not match!

    credentials = flow.credentials
    request_session = requests.session()
    cached_session = cachecontrol.CacheControl(request_session)
    token_request = google.auth.transport.requests.Request(session=cached_session)

    id_info = id_token.verify_oauth2_token(id_token=credentials._id_token, request=token_request, audience=GOOGLE_CLIENT_ID)

    # check if email contained in email field of users table
    with fn.conn_alchemy().connect() as con:
        if len(con.execute(text("SELECT * FROM users WHERE email = :email"), {"email": id_info.get("email")}).mappings().all()):
            session["google_id"] = id_info.get("sub")  # defing the results to show on the page
            session["firstname"] = id_info.get("given_name")
            session["lastname"] = id_info.get("family_name")
            session["email"] = id_info.get("email")
        else:
            session.clear()
            return redirect("/")

    flash(Markup(f"<h2>Welcome {session['firstname']} {session['lastname']}</h2>"))
    return redirect("/")  # the final page where the authorized users will end up


@app.route("/logout")  # the logout page and function
def logout():
    session.clear()
    flash(Markup("<h2>You are not allowed to access this resource</h2>"))
    return redirect("/")
