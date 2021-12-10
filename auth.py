'''
auth
from:
https://www.digitalocean.com/community/tutorials/how-to-add-authentication-to-your-app-with-flask-login
'''


from flask import Blueprint, render_template, request, redirect, flash, session
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

        return f"Welcome {session['firstname']} {session['lastname']}"
    else:
        flash(f"Error {email} ")
        return redirect("/login")


@auth.route('/logout')
def logout():
    return 'Logout'
