'''
auth
from:
https://www.digitalocean.com/community/tutorials/how-to-add-authentication-to-your-app-with-flask-login
'''


from flask import Blueprint, render_template, request, redirect, flash, session, Markup, current_app
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
import psycopg2.extras

from config import config
import functions as fn

#params = config()

auth = Blueprint('auth', __name__)

@auth.route('/login')
def login():
    return render_template('login.html')


@auth.route('/login_post', methods=['POST'])
def login_post():

    email = request.form.get('email')
    password = request.form.get('password')

    if not email or not password:
        flash(f"Input email and password")
        return redirect("/login")

    # password_sha256 = generate_password_hash(password, method='sha256')

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT * FROM users WHERE email = %s", [email])
    result = cursor.fetchone()

    if check_password_hash(result["password"], password):
        session['user_id'] = result["id"]
        session['firstname'] = result["firstname"]
        session['lastname'] = result["lastname"]
        session['email'] = result["email"]

        current_app.db_log.info(f"Login of {session['firstname']} {session['lastname']} ({session['email']})")

        flash(Markup(f"<h2>Welcome {session['firstname']} {session['lastname']}</h2>"))
        return redirect("/")
    else:
        flash(f"Please retry")
        return redirect("/login")


@auth.route('/logout')
@fn.check_login
def logout():

    current_app.db_log.info(f"Logout of {session['firstname']} {session['lastname']} ({session['email']})")

    session.pop('user_id', None)
    session.pop('firstname', None)
    session.pop('lastname', None)
    session.pop('email', None)

    return redirect("/")
