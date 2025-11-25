"""
https://www.mattbutton.com/2019/01/05/google-authentication-with-python-and-flask/
"""

import functools

import flask
from markupsafe import Markup
from authlib.integrations.requests_client import OAuth2Session
import google.oauth2.credentials
import googleapiclient.discovery
from sqlalchemy import text

from config import config
import functions as fn

params = config()

AUTH_REDIRECT_URI = params["redirect_uri"]
BASE_URI = params["base_uri"]
CLIENT_ID = params["google_client_id"]
CLIENT_SECRET = params["client_secret"]

ACCESS_TOKEN_URI = params["token_uri"]
AUTHORIZATION_URL = params["auth_uri"]
AUTHORIZATION_SCOPE = "openid email profile"


AUTH_TOKEN_KEY = "auth_token"
AUTH_STATE_KEY = "auth_state"

app = flask.Blueprint("google_auth", __name__)


def is_logged_in():
    return True if AUTH_TOKEN_KEY in flask.session else False


def build_credentials():
    if not is_logged_in():
        raise Exception("User must be logged in")

    oauth2_tokens = flask.session[AUTH_TOKEN_KEY]

    return google.oauth2.credentials.Credentials(
        oauth2_tokens["access_token"],
        refresh_token=oauth2_tokens["refresh_token"],
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        token_uri=ACCESS_TOKEN_URI,
    )


def get_user_info():
    """
    get user info from Google
    """
    credentials = build_credentials()

    oauth2_client = googleapiclient.discovery.build(
        "oauth2", "v2", credentials=credentials
    )

    return oauth2_client.userinfo().get().execute()


def no_cache(view):
    @functools.wraps(view)
    def no_cache_impl(*args, **kwargs):
        response = flask.make_response(view(*args, **kwargs))
        response.headers["Cache-Control"] = (
            "no-store, no-cache, must-revalidate, max-age=0"
        )
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "-1"
        return response

    return functools.update_wrapper(no_cache_impl, view)


@app.route("/google/login")
@no_cache
def login():
    session = OAuth2Session(
        CLIENT_ID,
        CLIENT_SECRET,
        scope=AUTHORIZATION_SCOPE,
        redirect_uri=AUTH_REDIRECT_URI,
    )

    uri, state = session.create_authorization_url(AUTHORIZATION_URL)

    flask.session[AUTH_STATE_KEY] = state

    flask.session.permanent = True

    return flask.redirect(uri, code=302)


@app.route("/google/auth")
@no_cache
def google_auth_redirect():
    req_state = flask.request.args.get("state", default=None, type=None)

    if req_state != flask.session[AUTH_STATE_KEY]:
        response = flask.make_response("Invalid state parameter", 401)
        return response

    session = OAuth2Session(
        CLIENT_ID,
        CLIENT_SECRET,
        scope=AUTHORIZATION_SCOPE,
        state=flask.session[AUTH_STATE_KEY],
        redirect_uri=AUTH_REDIRECT_URI,
    )

    oauth2_tokens = session.fetch_access_token(
        ACCESS_TOKEN_URI, authorization_response=flask.request.url
    )

    flask.session[AUTH_TOKEN_KEY] = oauth2_tokens

    # check if user authorized
    user_info = get_user_info()

    # check if email contained in email field of users table
    with fn.conn_alchemy().connect() as con:
        row = (
            con.execute(
                text("SELECT * FROM users WHERE email = :email"),
                {"email": user_info["email"]},
            )
            .mappings()
            .fetchone()
        )
        if row is None:
            flask.session.clear()
            flask.flash(
                fn.alert_danger("<h2>You are not allowed to access this resource</h2>")
            )
            return flask.redirect("/")

        flask.session["role"] = row["role"]
        flask.session["google_id"] = user_info["id"]
        flask.session["firstname"] = user_info["given_name"]
        flask.session["lastname"] = user_info["family_name"]
        flask.session["email"] = user_info["email"]
        flask.session["user_name"] = user_info["name"]

        print(f"{flask.session["role"]=}")

    flask.flash(Markup(f"<h2>Welcome {flask.session['user_name']}</h2>"))
    return flask.redirect(BASE_URI, code=302)


@app.route("/google/logout")
@no_cache
def logout():
    """
    flask.session.pop(AUTH_TOKEN_KEY, None)
    flask.session.pop(AUTH_STATE_KEY, None)
    flask.session.pop("email", None)
    """
    flask.session.clear()

    return flask.redirect("/", code=302)
