"""
WolfDB web service
(c) Olivier Friard
"""

from flask import Flask, render_template, redirect, request, Markup, g
import psycopg2
from psycopg2 import pool
from config import config
import datetime
from wtforms import (Form, BooleanField, StringField,
                     validators, SelectField, IntegerField)

from wtforms.validators import Optional, Required, ValidationError

from new_scat import New_scat


def get_db():
    print ('GETTING CONN')
    if 'db' not in g:
        g.db = app.config['postgreSQL_pool'].getconn()
    return g.db


def connect():
    """ Connect to the PostgreSQL database server """
    conn = None
    try:
        # read connection parameters
        params = config()

        # connect to the PostgreSQL server
        print('Connecting to the PostgreSQL database...')
        conn = psycopg2.connect(**params)

        # create a cursor
        cur = conn.cursor()

	# execute a statement
        print('PostgreSQL database version:')
        cur.execute('SELECT version()')

        # display the PostgreSQL database server version
        db_version = cur.fetchone()
        print(db_version)

	# close the communication with the PostgreSQL
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if conn is not None:
            conn.close()
            print('Database connection closed.')


# connect()

app = Flask(__name__)

app.debug = True

params = config()
app.config['postgreSQL_pool'] = psycopg2.pool.SimpleConnectionPool(1, 20,
                                                  user = params["user"],
                                                  password = params["password"],
                                                  host = params["host"],
                                                  
                                                  database = params["database"])


@app.teardown_appcontext
def close_conn(e):
    print('CLOSING CONN')
    db = g.pop('db', None)
    if db is not None:
        app.config['postgreSQL_pool'].putconn(db)



@app.route("/")
def home():

    return render_template("home.html")





@app.route("/new_scat", methods=("GET", "POST"))
def new_scat():
    
    if request.method == "POST":
        form = New_scat(request.form)
        print(request.form["scat_id"])
        if form.validate():
            #user = User(form.username.data, form.email.data,
            #        form.password.data)


            db = get_db()
            cursor = db.cursor()

            sql = ("INSERT INTO scat (scat_id, date, sampling_year, sampling_type, transect_id, st_id, "
                   "localita, comune, provincia, "
                   "deposition, matrix,collected_scat, "
                   "coord_east, coord_north, rilevatore_ente, scalp_category) "
                   "VALUES (%s, %s, %s, %s,%s, %s, %s, %s,%s, %s, %s, %s,%s, %s, %s, %s)")
            cursor.execute(sql,
                           [
                            request.form["scat_id"],
                            request.form["date"],
                            request.form["sampling_year"],
                            request.form["sampling_type"],
                            request.form["transect_id"],
                            request.form["st_id"],
                            request.form["localita"], request.form["comune"], request.form["provincia"],
                            request.form["deposition"], request.form["matrix"], request.form["collected_scat"],
                            request.form["coord_east"], request.form["coord_north"],
                            request.form["rilevatore_ente"], request.form["scalp_category"]
                           ]
                           )
            
            db.commit()


            return 'Scat inserted<br><a href="/">Home</a>'
        else:
            return "form not validated"

    if request.method == "GET":
        form = New_scat()
        return render_template('new_scat.html',
                            form=form,
                            default_values={})


if __name__ == "__main__":
    app.run(host="127.0.0.1")


