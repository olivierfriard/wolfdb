"""
WolfDB web service
(c) Olivier Friard
"""

from flask import Flask, render_template, redirect, request, Markup, g, flash, session
import psycopg2
from psycopg2 import pool
import psycopg2.extras
from config import config



from scat import Scat
from transect import Transect
from path import Path
from track import Track



def get_db():
    print ('GETTING CONN')
    if 'db' not in g:
        g.db = app.config['postgreSQL_pool'].getconn()
    return g.db


app = Flask(__name__)

app.debug = True

app.secret_key = "dfhsdlfsdhflsdfhsnqq45"

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

@app.route("/scats")
def scats():
    return render_template("scats.html")

@app.route("/transects")
def transects():
    return render_template("transects.html")


@app.route("/paths")
def paths():
    return render_template("paths.html")


@app.route("/snow_tracks")
def snow_tracks():
    return render_template("snow_tracks.html")


@app.route("/new_scat", methods=("GET", "POST"))
def new_scat():
    
    if request.method == "POST":
        form = Scat(request.form)

        if form.validate():

            db = get_db()
            cursor = db.cursor()

            sql = ("INSERT INTO scat (scat_id, date, sampling_year, sampling_type, transect_id, snowtracking_id, "
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
                            request.form["snowtracking_id"],
                            request.form["localita"], request.form["comune"], request.form["provincia"],
                            request.form["deposition"], request.form["matrix"], request.form["collected_scat"],
                            request.form["coord_east"], request.form["coord_north"],
                            request.form["rilevatore_ente"], request.form["scalp_category"]
                           ]
                           )
            
            db.commit()

            return 'Scat inserted<br><a href="/">Home</a>'
        else:
            return "form NOT validated<br><a href="/">Home</a>"

    if request.method == "GET":
        form = Scat()

        # get id of all transects
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT transect_id FROM transect ORDER BY transect_id")
        transect_id_list = cursor.fetchall()
        form.transect_id.choices = [("-", "-")] + [(x[0].strip(), x[0].strip()) for x in transect_id_list]

        # get id of all snow tracks
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT snowtracking_id FROM snow_tracks ORDER BY snowtracking_id")
        track_id_list = cursor.fetchall()
        form.snowtracking_id.choices = [("-", "-")] + [(x[0].strip(), x[0].strip()) for x in track_id_list]


        return render_template("new_scat.html",
                            form=form,
                            default_values={})


@app.route("/transects_list")
def transects_list():
    # get all transects
    db = get_db()
    cursor = db.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT * FROM transect ORDER BY transect_id")

    results = cursor.fetchall()
    print(results)
    return render_template("transects_list.html",
                           results=results)



@app.route("/new_transect", methods=("GET", "POST"))
def new_transect():
    
    if request.method == "POST":
        form = Transect(request.form)

        if form.validate():

            db = get_db()
            cursor = db.cursor()

            sql = ("INSERT INTO transect (transect_id, sector, localita, provincia, regione) "
                   "VALUES (%s, %s, %s, %s, %s)")
            cursor.execute(sql,
                           [
                            request.form["transect_id"], request.form["sector"],
                            request.form["localita"], request.form["provincia"], request.form["regione"]
                           ]
                           )
            
            db.commit()

            return 'Transect inserted<br><a href="/">Home</a>'
        else:
            return "form NOT validated<br><a href="/">Home</a>"

    if request.method == "GET":
        form = Transect()
        return render_template('new_transect.html',
                            form=form,
                            default_values={})


@app.route("/paths_list")
def paths_list():
    # get  all path
    db = get_db()
    cursor = db.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT * FROM paths ORDER BY date DESC")

    results = cursor.fetchall()
    print(results)
    return render_template("paths_list.html",
                           results=results)


@app.route("/new_path", methods=("GET", "POST"))
def new_path():
    
    if request.method == "POST":
        form = Path(request.form)

        # get id of all transects
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT transect_id FROM transect ORDER BY transect_id")
        transect_id_list = cursor.fetchall()

        form.transect_id.choices = [("-", "-")] + [(x[0].strip(), x[0].strip()) for x in transect_id_list]

        if form.validate():

            db = get_db()
            cursor = db.cursor()
            sql = ("INSERT INTO paths (transect_id, date, sampling_year, completeness, numero_segni_trovati, numero_campioni, operatore, note) "
                   "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)")
            cursor.execute(sql,
                           [
                            request.form["transect_id"],
                            request.form["date"],
                            request.form["sampling_year"],
                            request.form["completeness"] if request.form["completeness"] else None,
                            request.form["numero_segni_trovati"] if request.form["numero_segni_trovati"] else None,
                            request.form["numero_campioni"] if request.form["numero_campioni"] else None,
                            request.form["operatore"], request.form["note"]
                           ]
                           )
            db.commit()

            return 'New path inserted<br><a href="/">Home</a>'
        else:
            # default values
            default_values = {}
            for k in request.form:
                default_values[k] = request.form[k]

            flash(Markup("<b>Some values are not set or are wrong. Please check and submit again</b>"))
            return render_template('new_path.html',
                                    form=form,
                                    default_values=default_values)



    if request.method == "GET":
        form = Path()

        # get id of all transects
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT transect_id FROM transect ORDER BY transect_id")
        transect_id_list = cursor.fetchall()

        form.transect_id.choices = [("-", "-")] + [(x[0].strip(), x[0].strip()) for x in transect_id_list]
        return render_template('new_path.html',
                            form=form,
                            default_values={})


@app.route("/snow_tracks_list")
def tracks_list():
    # get  all tracks
    db = get_db()
    cursor = db.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT * FROM snow_tracks ORDER BY date DESC")

    results = cursor.fetchall()

    return render_template("tracks_list.html",
                           results=results)



@app.route("/new_track", methods=("GET", "POST"))
def new_track():
    if request.method == "POST":
        form = Track(request.form)

        # get id of all transects
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT transect_id FROM transect ORDER BY transect_id")
        transect_id_list = cursor.fetchall()

        form.transect_id.choices = [("-", "-")] + [(x[0].strip(), x[0].strip()) for x in transect_id_list]

        if form.validate():

            db = get_db()
            cursor = db.cursor()
            sql = ("INSERT INTO snow_tracks (snowtracking_id, date, sampling_season, comune, "
                                             "provincia, regione, rilevatore, scalp_category, "
                                             "systematic_sampling, transect_id, giorni_dopo_nevicata, n_minimo_individui, track_format) "
                   "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)")
            cursor.execute(sql,
                           [
                            request.form["snowtracking_id"],
                            request.form["date"],
                            request.form["sampling_season"],
                            request.form["comune"],
                            request.form["provincia"],
                            request.form["regione"],                            
                            request.form["rilevatore"],

                            request.form["scalp_category"],
                            request.form["systematic_sampling"],
                            request.form["transect_id"],

                            request.form["giorni_dopo_nevicata"],
                            request.form["n_minimo_individui"],
                            request.form["track_format"],
                            ]   
                           )
            db.commit()

            return 'New track inserted<br><a href="/">Home</a>'
        else:
            # default values
            default_values = {}
            for k in request.form:
                default_values[k] = request.form[k]

            flash(Markup("<b>Some values are not set or are wrong. Please check and submit again</b>"))
            return render_template('new_track.html',
                                    form=form,
                                    default_values=default_values)



    if request.method == "GET":
        form = Track()

        # get id of all transects
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT transect_id FROM transect ORDER BY transect_id")
        transect_id_list = cursor.fetchall()

        form.transect_id.choices = [("-", "-")] + [(x[0].strip(), x[0].strip()) for x in transect_id_list]
        return render_template('new_track.html',
                            form=form,
                            default_values={})


if __name__ == "__main__":
    app.run(host="127.0.0.1")


