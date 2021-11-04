"""
WolfDB web service
(c) Olivier Friard
"""

from flask import Flask, render_template, redirect, request
import psycopg2
from config import config
from wtforms import (Form, BooleanField, StringField,
                     validators, SelectField, IntegerField)


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


connect()

app = Flask(__name__)

app.debug = True

@app.route("/")
def hello_world():
    return render_template("home.html")


class New_scat(Form):
    scat_id = StringField("Scat ID", [])
    # genetic_id = StringField('Genetic ID', [])
    # genetic_id = StringField('Genetic ID', [])
    date = StringField("Date", [])
    sampling_year = StringField("Sampling year", [])
    sampling_type = SelectField("Sampling type", choices=[('-', '-'),
                                                          ('Opportunistico', 'Opportunistico'),
                                                          ('Sistematico', 'Sistematico')],
                                default="-")
    transect_id = StringField("Transect ID", [])
    st_id = StringField("ST ID", [])
    localita = StringField("Località", [])
    comune = StringField("Comune", [])
    provincia = StringField("Provincia", [])
    deposition = SelectField("Deposition", choices=[('-', '-'),('fresca', 'fresca'), ('vecchia', 'vecchia')], default="-")
    matrix = SelectField("Matrix", choices=[('-', '-'),('Yes', 'Yes'), ('No', 'No')], default="-")
    collected_scat = SelectField("Collected scat", choices=[('-', '-'),('Yes', 'Yes'), ('No', 'No')], default="-")
    sample_genetic = SelectField("Sample genetic", choices=[('-', '-'),('Yes', 'Yes'), ('No', 'No')], default="-")
    coord_east = IntegerField("Coordinate East (UTM 32N WGS84)")
    coord_north  = IntegerField("Coordinate North (UTM 32N WGS84)")
    rilevatore_ente = StringField("Rilevatore / Ente", [])
    scalp_category = StringField("SCALP category", [])



@app.route("/new_scat")
def new_scat():
    
    if request.method == 'POST':
        form = New_scat(request.form)
        if form.validate():
            #user = User(form.username.data, form.email.data,
            #        form.password.data)
        
           
            return "OK"


    form = New_scat()
    return render_template('new_scat.html',
                           form=form,
                           default_values={})


if __name__ == "__main__":
    app.run(host="127.0.0.1")


