"""
WolfDB web service
(c) Olivier Friard
"""

from flask import Flask, render_template, redirect, request, Markup, g, flash, session
import psycopg2
import psycopg2.extras
from config import config


from scat import Scat
from transect import Transect
from path import Path
from track import Track

__version__ = "1"

app = Flask(__name__)

app.debug = True

app.secret_key = "dfhsdlfsdhflsdfhsnqq45"

params = config()

def get_connection():
    return psycopg2.connect(user=params["user"],
                                  password=params["password"],
                                  host=params["host"],
                                  #port="5432",
                                  database=params["database"])


def all_transect_id():
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT transect_id FROM transect ORDER BY transect_id")
    return [x[0].strip() for x in cursor.fetchall()]

def all_path_id():
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT CONCAT(transect_id, ' ',  date) FROM paths ORDER BY date DESC")
    return [x[0].strip() for x in cursor.fetchall()]


def all_snow_tracks_id():
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT snowtrack_id FROM snow_tracks ORDER BY snowtrack_id")
    return [x[0].strip() for x in cursor.fetchall()]


@app.route("/")
def home():
    return render_template("home.html")

@app.route("/version")
def version():
    return __version__



@app.route("/test")
def test():
    return render_template("test.html")


@app.route("/test_action", methods=("POST",))
def test_action():
    print(request.form)
    return f"""
<input id="date" type="text" value="{request.form["path_id"].split(" ")[-1]}">
"""






@app.route("/wa_form", methods=("POST",))
def wa_form():

    data = request.form

    return f"""
<form action="/add_wa" method="POST" style="padding-top:30px; padding-bottom:30px">

  <input type="hidden" id="scat_id" name="scat_id" value="{request.form['scat_id']}">

  <div class="form-group">
  <label for="usr">WA code/genetic ID</label>
  <input type="text" class="form-control" id="wa" name="wa">
</div>

<button type="submit" class="btn btn-primary">Add code</button>
</form>
"""


@app.route("/add_wa", methods=("POST",))
def add_wa():

    print(request.form)
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("UPDATE scat SET genetic_id = %s WHERE scat_id = %s",
                   [request.form['wa'], request.form['scat_id']])

    connection.commit()
    return redirect(f"/view_scat/{request.form['scat_id']}")



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



# scats


@app.route("/view_scat/<scat_id>")
def view_scat(scat_id):
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT * FROM scat WHERE scat_id = %s",
                   [scat_id])

    return render_template("view_scat.html",
                           results=cursor.fetchone())




@app.route("/scats_list")
def scats_list():
    # get all scats

    connection = get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT * FROM scat ORDER BY scat_id")

    return render_template("scats_list.html",
                           results=cursor.fetchall())


@app.route("/new_scat", methods=("GET", "POST"))
def new_scat():

    if request.method == "GET":
        form = Scat()
        # get id of all paths
        form.path_id.choices = [("-", "-")] + [(x, x) for x in all_path_id()]
        # get id of all snow tracks
        form.snowtrack_id.choices = [("-", "-")] + [(x, x) for x in all_snow_tracks_id()]

        return render_template("new_scat.html",
                               title="New scat",
                               action=f"/new_scat",
                               form=form,
                               default_values={})

    if request.method == "POST":
        form = Scat(request.form)

        # get id of all transects
        form.path_id.choices = [("-", "-")] + [(x, x) for x in all_path_id()]

        # get id of all snow tracks
        form.snowtrack_id.choices = [("-", "-")] + [(x, x) for x in all_snow_tracks_id()]

        if form.validate():

            connection = get_connection()
            cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

            sql = ("INSERT INTO scat (scat_id, date, sampling_season, sampling_type, path_id, snowtrack_id, "
                   "localita, comune, provincia, "
                   "deposition, matrix,collected_scat, "
                   "coord_east, coord_north, rilevatore_ente, scalp_category) "
                   "VALUES (%s, %s, %s, %s,%s, %s, %s, %s,%s, %s, %s, %s,%s, %s, %s, %s)")
            cursor.execute(sql,
                           [
                            request.form["scat_id"],
                            request.form["date"],
                            sampling_season(request.form["date"]),
                            request.form["sampling_type"],
                            request.form["path_id"],
                            request.form["snowtrack_id"],
                            request.form["localita"], request.form["comune"], request.form["provincia"],
                            request.form["deposition"], request.form["matrix"], request.form["collected_scat"],
                            request.form["coord_east"], request.form["coord_north"],
                            request.form["rilevatore_ente"], request.form["scalp_category"]
                           ]
                           )

            connection.commit()

            return redirect("/scats_list")
        else:
            # default values
            default_values = {}
            for k in request.form:
                default_values[k] = request.form[k]

            flash(Markup("<b>Some values are not set or are wrong. Please check and submit again</b>"))

            return render_template("new_scat.html",
                                   title="New scat",
                                   action=f"/new_scat",
                                   form=form,
                                   default_values=default_values)



@app.route("/edit_scat/<scat_id>", methods=("GET", "POST"))
def edit_scat(scat_id):

    if request.method == "GET":
        connection = get_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("SELECT * FROM scat WHERE scat_id = %s",
                    [scat_id])
        default_values = cursor.fetchone()

        form = Scat(transect_id=default_values["transect_id"],
                    snowtrack_id=default_values["snowtrack_id"],
                    sampling_type=default_values["sampling_type"],
                    deposition=default_values["deposition"],
                    matrix=default_values["matrix"],
                    collected_scat=default_values["collected_scat"])
        # get id of all transects
        form.transect_id.choices = [("-", "-")] + [(x, x) for x in all_transect_id()]
        # get id of all snow tracks
        form.snowtrack_id.choices = [("-", "-")] + [(x, x) for x in all_snow_tracks_id()]

        return render_template("new_scat.html",
                            title="Edit scat",
                            action=f"/edit_scat/{scat_id}",
                            form=form,
                            default_values=default_values)


    if request.method == "POST":

        form = Scat(request.form)

        # get id of all transects
        form.transect_id.choices = [("-", "-")] + [(x, x) for x in all_transect_id()]

        # get id of all snow tracks
        form.snowtrack_id.choices = [("-", "-")] + [(x, x) for x in all_snow_tracks_id()]

        if form.validate():

            connection = get_connection()
            cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

            sql = ("UPDATE scat SET scat_id = %s, "
                   "                date = %s,"
                   "                sampling_season = %s,"
                   "                sampling_type = %s,"
                   "                transect_id = %s, "
                   "                snowtrack_id = %s, "
                   "                localita = %s, "
                   "                comune = %s, "
                   "                provincia = %s, "
                   "                deposition = %s, "
                   "                matrix = %s, "
                   "                collected_scat = %s, "
                   "                coord_east = %s, "
                   "                coord_north = %s, "
                   "                rilevatore_ente = %s, "
                   "                scalp_category = %s "
                   "WHERE scat_id = %s")
            cursor.execute(sql,
                           [
                            request.form["scat_id"],
                            request.form["date"],
                            request.form["sampling_season"],
                            request.form["sampling_type"],
                            request.form["transect_id"],
                            request.form["snowtrack_id"],
                            request.form["localita"], request.form["comune"], request.form["provincia"],
                            request.form["deposition"], request.form["matrix"], request.form["collected_scat"],
                            request.form["coord_east"], request.form["coord_north"],
                            request.form["rilevatore_ente"], request.form["scalp_category"],
                            scat_id
                           ]
                           )

            connection.commit()

            return redirect(f"/view_scat/{scat_id}")
        else:
            # default values
            default_values = {}
            for k in request.form:
                default_values[k] = request.form[k]

            flash(Markup("<b>Some values are not set or are wrong. Please check and submit again</b>"))

            return render_template("new_scat.html",
                                   title="Edit scat",
                                   action=f"/edit_scat/{scat_id}",
                                   form=form,
                                   default_values=default_values)



# transects

@app.route("/view_transect/<transect_id>")
def view_transect(transect_id):
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT * FROM transect WHERE transect_id = %s",
                   [transect_id])
    transect = cursor.fetchone()

    # path
    cursor.execute("SELECT * FROM paths WHERE transect_id = %s ORDER BY date DESC",
                   [transect_id])
    results_paths = cursor.fetchall()

    # snow tracks
    cursor.execute("SELECT * FROM snow_tracks WHERE transect_id = %s ORDER BY date DESC",
                   [transect_id])
    results_snowtracks = cursor.fetchall()

    return render_template("view_transect.html",
                           transect=transect,
                           paths=results_paths,
                           snowtracks=results_snowtracks)


@app.route("/transects_list")
def transects_list():
    # get all transects
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT * FROM transect ORDER BY transect_id")

    results = cursor.fetchall()

    return render_template("transects_list.html",
                           results=results)


@app.route("/new_transect", methods=("GET", "POST"))
def new_transect():

    if request.method == "GET":
        form = Transect()
        return render_template('new_transect.html',
                               title="New transect",
                               action=f"/new_transect",
                            form=form,
                            default_values={})


    if request.method == "POST":
        form = Transect(request.form)

        if form.validate():

            connection = get_connection()
            cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

            sql = ("INSERT INTO transect (transect_id, sector, localita, provincia, regione) "
                   "VALUES (%s, %s, %s, %s, %s)")
            cursor.execute(sql,
                           [
                            request.form["transect_id"], request.form["sector"],
                            request.form["localita"], request.form["provincia"], request.form["regione"]
                           ]
                           )

            connection.commit()

            return 'Transect inserted<br><a href="/">Home</a>'
        else:
            return "Transect form NOT validated<br><a href="/">Home</a>"



@app.route("/edit_transect/<transect_id>", methods=("GET", "POST"))
def edit_transect(transect_id):

    if request.method == "GET":
        connection = get_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("SELECT * FROM transect WHERE transect_id = %s",
                    [transect_id])
        default_values = cursor.fetchone()

        form = Transect()

        return render_template("new_transect.html",
                            title="Edit transect",
                            action=f"/edit_transect/{transect_id}",
                            form=form,
                            default_values=default_values)

    if request.method == "POST":

        form = Transect(request.form)
        if form.validate():

            connection = get_connection()
            cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

            sql = ("UPDATE transect SET transect_id = %s, sector =%s, localita = %s, provincia = %s, regione = %s "
                   "WHERE transect_id = %s")
            cursor.execute(sql,
                           [
                            request.form["transect_id"], request.form["sector"],
                            request.form["localita"], request.form["provincia"], request.form["regione"],
                            transect_id
                           ]
                           )

            connection.commit()

            return redirect(f"/view_transect/{transect_id}")
        else:
            return "Transect form NOT validated<br><a href="/">Home</a>"



def sampling_season(date):
    month = int(request.form['date'][5:6+1])
    year = int(request.form['date'][0:3+1])
    if 5 <= month <= 12:
        return f"{year}-{year + 1}"
    if 1 <= month <= 4:
        return f"{year - 1}-{year}"



# path

@app.route("/view_path/<id>")
def view_path(id):
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT * FROM paths WHERE concat(transect_id, ' ', date) = %s",
                   [id])

    results = cursor.fetchone()

    # n samples
    path_id = f'{results["transect_id"]} {results["date"]}'
    cursor.execute("SELECT COUNT(*) AS n_samples FROM scat WHERE path_id = %s ", [path_id])
    n_samples = cursor.fetchone()["n_samples"]

    # n tracks
    path_id = f'{results["transect_id"]} {results["date"]}'
    cursor.execute("SELECT COUNT(*) AS n_tracks FROM snow_tracks WHERE transect_id = %s AND date = %s",
    [results["transect_id"], results["date"]])
    n_tracks = cursor.fetchone()["n_tracks"]


    return render_template("view_path.html",
                           results=results,
                           n_samples=n_samples,
                           n_tracks=n_tracks)


@app.route("/paths_list")
def paths_list():
    # get  all path
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute(("SELECT *, "
                    "(SELECT COUNT(*) FROM scat WHERE path_id = CONCAT(paths.transect_id, ' ', paths.date)) AS n_samples, "
                    "(SELECT COUNT(*) FROM snow_tracks WHERE transect_id = paths.transect_id AND date = paths.date) AS n_tracks "
                   "FROM paths ORDER BY date DESC"
                   ))

    results = cursor.fetchall()
    return render_template("paths_list.html",
                           results=results,
                            )




@app.route("/new_path", methods=("GET", "POST"))
def new_path():

    if request.method == "GET":
        form = Path()

        # get id of all transects
        form.transect_id.choices = [("-", "-")] + [(x, x) for x in all_transect_id()]

        return render_template("new_path.html",
                               title="New path",
                               action=f"/new_path",
                               form=form,
                               default_values={})

    if request.method == "POST":
        form = Path(request.form)

        # get id of all transects
        form.transect_id.choices = [("-", "-")] + [(x, x) for x in all_transect_id()]

        if form.validate():

            connection = get_connection()
            cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
            sql = ("INSERT INTO paths (transect_id, date, sampling_season, completeness, "
                   #"numero_segni_trovati, numero_campioni, "
                   "operatore, note) "
                   "VALUES (%s, %s, %s, %s, %s, %s)")
            cursor.execute(sql,
                           [
                            request.form["transect_id"],
                            request.form["date"],
                            sampling_season(request.form["date"]),
                            request.form["completeness"] if request.form["completeness"] else None,
                            #request.form["numero_segni_trovati"] if request.form["numero_segni_trovati"] else None,
                            #request.form["numero_campioni"] if request.form["numero_campioni"] else None,
                            request.form["operatore"], request.form["note"]
                           ]
                           )
            connection.commit()

            return redirect("/paths_list")
        else:
            # default values
            default_values = {}
            for k in request.form:
                default_values[k] = request.form[k]

            flash(Markup("<b>Some values are not set or are wrong. Please check and submit again</b>"))
            return render_template('new_path.html',
                                    title="New path",
                                    action=f"/new_path",
                                    form=form,
                                    default_values=default_values)





@app.route("/edit_path/<id>", methods=("GET", "POST"))
def edit_path(id):

    if request.method == "GET":
        connection = get_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("SELECT * FROM paths WHERE id = %s",
                    [id])
        default_values = cursor.fetchone()

        form = Path(transect_id=default_values["transect_id"],)
        # get id of all transects
        form.transect_id.choices = [("-", "-")] + [(x, x) for x in all_transect_id()]


        return render_template("new_path.html",
                            title="Edit path",
                            action=f"/edit_path/{id}",
                            form=form,
                            default_values=default_values)


    if request.method == "POST":
        form = Path(request.form)

        # get id of all transects
        form.transect_id.choices = [("-", "-")] + [(x, x) for x in all_transect_id()]

        if form.validate():

            connection = get_connection()
            cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
            sql = ("UPDATE paths SET "
                   "transect_id=%s, "
                   "date=%s, "
                   "sampling_season=%s, "
                   "completeness=%s, "
                   #"numero_segni_trovati=%s, "
                   #"numero_campioni=%s, "
                   "operatore=%s, "
                   "note=%s "
                   "WHERE id = %s")

            cursor.execute(sql,
                           [
                            request.form["transect_id"],
                            request.form["date"],
                            sampling_season(request.form["date"]),
                            request.form["completeness"] if request.form["completeness"] else None,
                            #request.form["numero_segni_trovati"] if request.form["numero_segni_trovati"] else None,
                            #request.form["numero_campioni"] if request.form["numero_campioni"] else None,
                            request.form["operatore"], request.form["note"],
                            id
                           ]
                           )
            connection.commit()

            return redirect(f"/view_path/{id}")
        else:
            # default values
            default_values = {}
            for k in request.form:
                default_values[k] = request.form[k]

            flash(Markup("<b>Some values are not set or are wrong. Please check and submit again</b>"))
            return render_template("new_path.html",
                                    title="Edit path",
                                    action=f"/edit_path/{id}",
                                    form=form,
                                    default_values=default_values)


# snow track

@app.route("/view_snowtrack/<snowtrack_id>")
def view_snowtrack(snowtrack_id):
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT * FROM snow_tracks WHERE snowtrack_id = %s",
                   [snowtrack_id])

    return render_template("view_snowtrack.html",
                           results=cursor.fetchone())



@app.route("/snowtracks_list")
def snowtracks_list():
    # get  all tracks
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT * FROM snow_tracks ORDER BY date DESC")

    results = cursor.fetchall()

    return render_template("snowtracks_list.html",
                           results=results)



@app.route("/new_snowtrack", methods=("GET", "POST"))
def new_snowtrack():


    if request.method == "GET":
        form = Track()

        # get id of all transects
        form.transect_id.choices = [("-", "-")] + [(x, x) for x in all_transect_id()]
        return render_template('new_snowtrack.html',
                                title="New snow track",
                                action="/new_snowtrack",
                                form=form,
                                default_values={})


    if request.method == "POST":
        form = Track(request.form)

        # get id of all transects
        form.transect_id.choices = [("-", "-")] + [(x, x) for x in all_transect_id()]

        if form.validate():

            connection = get_connection()
            cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
            sql = ("INSERT INTO snow_tracks (snowtrack_id, date, sampling_season, comune, "
                                             "provincia, regione, rilevatore, scalp_category, "
                                             "systematic_sampling, transect_id, giorni_dopo_nevicata, n_minimo_individui, track_format) "
                   "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)")
            cursor.execute(sql,
                           [
                            request.form["snowtrack_id"],
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
            connection.commit()

            return 'New track inserted<br><a href="/">Home</a>'
        else:
            # default values
            default_values = {}
            for k in request.form:
                default_values[k] = request.form[k]

            flash(Markup("<b>Some values are not set or are wrong. Please check and submit again</b>"))
            return render_template('new_snowtrack.html',
                                   title="New snow track",
                                   action="/new_snowtrack",

                                    form=form,
                                    default_values=default_values)



@app.route("/edit_snowtrack/<snowtrack_id>", methods=("GET", "POST"))
def edit_snowtrack(snowtrack_id):

    if request.method == "GET":
        connection = get_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("SELECT * FROM snow_tracks WHERE snowtrack_id = %s",
                    [snowtrack_id])
        default_values = cursor.fetchone()

        form = Track(transect_id=default_values["transect_id"],)
        # get id of all transects
        form.transect_id.choices = [("-", "-")] + [(x, x) for x in all_transect_id()]


        return render_template("new_track.html",
                            title="Edit track",
                            action=f"/edit_snowtrack/{snowtrack_id}",
                            form=form,
                            default_values=default_values)


    if request.method == "POST":
        form = Track(request.form)

        # get id of all transects
        form.transect_id.choices = [("-", "-")] + [(x, x) for x in all_transect_id()]

        if form.validate():

            connection = get_connection()
            cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
            sql = ("UPDATE snow_tracks SET "
                        "snowtrack_id = %s,"
                        "date = %s,"
                        "sampling_season = %s,"
                        "comune = %s,"
                        "provincia = %s,"
                        "regione = %s,"
                        "rilevatore = %s,"
                        "scalp_category = %s,"
                        "systematic_sampling = %s,"
                        "transect_id = %s,"
                        "giorni_dopo_nevicata = %s,"
                        "n_minimo_individui = %s,"
                        "track_format = %s"
                   "WHERE snowtrack_id = %s")

            cursor.execute(sql,
                           [
                            request.form["snowtrack_id"],
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
                            snowtrack_id
                           ]
                           )
            connection.commit()

            return redirect(f"/view_snowtrack/{snowtrack_id}")
        else:
            # default values
            default_values = {}
            for k in request.form:
                default_values[k] = request.form[k]

            flash(Markup("<b>Some values are not set or are wrong. Please check and submit again</b>"))
            return render_template('new_track.html',
                                    title="Edit track",
                                    action=f"/edit_snowtrack/{snowtrack_id}",
                                    form=form,
                                    default_values=default_values)



if __name__ == "__main__":
    app.run(host="127.0.0.1")


