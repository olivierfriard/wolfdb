"""
WolfDB web service
(c) Olivier Friard

flask blueprint for scats management
"""



import flask
from flask import Flask, render_template, redirect, request, Markup, flash, session, current_app
import psycopg2
import psycopg2.extras
from config import config

from scat import Scat
import functions as fn
import utm
import json
import pathlib as pl
import pandas as pd
import numpy as np
import uuid

app = flask.Blueprint("scats", __name__, template_folder="templates")

app.debug = True


params = config()

ALLOWED_EXTENSIONS = [".TSV"]
UPLOAD_FOLDER = "/tmp"

@app.route("/scats")
def scats():
    return render_template("scats.html")




@app.route("/wa_form", methods=("POST",))
def wa_form():

    data = request.form

    return f"""
<form action="/add_wa" method="POST" style="padding-top:30px; padding-bottom:30px">

  <input type="hidden" id="scat_id" name="scat_id" value="{request.form['scat_id']}">

  <div class="form-group">
  <label for="usr">WA code</label>
  <input type="text" class="form-control" id="wa" name="wa">
</div>

<button type="submit" class="btn btn-primary">Add code</button>
</form>
"""


@app.route("/add_wa", methods=("POST",))
def add_wa():

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("UPDATE scats SET wa_code = %s WHERE scat_id = %s",
                   [request.form['wa'].upper(), request.form['scat_id']])

    connection.commit()
    return redirect(f"/view_scat/{request.form['scat_id']}")





@app.route("/view_scat/<scat_id>")
def view_scat(scat_id):
    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT *, ST_AsGeoJSON(geo) AS lonlat FROM scats WHERE scat_id = %s",
                   [scat_id])
    results = cursor.fetchone()

    lon, lat = json.loads(results["lonlat"])['coordinates']
    results["lonlat"] = f"{lon}, {lat}"

    print(f'{results["lonlat"]=}')

    return render_template("view_scat.html",
                           results=results)



@app.route("/scats_list")
def scats_list():
    # get all scats

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT * FROM scats ORDER BY scat_id")

    return render_template("scats_list.html",
                           results=cursor.fetchall())


@app.route("/new_scat", methods=("GET", "POST"))
def new_scat():

    def not_valid(msg):
        # default values
        default_values = {}
        for k in request.form:
            default_values[k] = request.form[k]

        flash(Markup(f"<b>{msg}</b>"))

        return render_template("new_scat.html",
                            title="New scat",
                            action=f"/new_scat",
                            form=form,
                            default_values=default_values)


    if request.method == "GET":
        form = Scat()
        # get id of all paths
        form.path_id.choices = [("", "")] + [(x, x) for x in fn.all_path_id()]
        # get id of all snow tracks
        form.snowtrack_id.choices = [("", "")] + [(x, x) for x in fn.all_snow_tracks_id()]

        return render_template("new_scat.html",
                               title="New scat",
                               action=f"/new_scat",
                               form=form,
                               default_values={"coord_zone": "32N"})

    if request.method == "POST":
        form = Scat(request.form)

        # get id of all transects
        form.path_id.choices = [("", "")] + [(x, x) for x in fn.all_path_id()]

        # get id of all snow tracks
        form.snowtrack_id.choices = [("", "")] + [(x, x) for x in fn.all_snow_tracks_id()]

        if form.validate():

            # date
            try:
                year = int(request.form['scat_id'][1:2+1]) + 2000
                month = int(request.form['scat_id'][3:4+1])
                day = int(request.form['scat_id'][5:6+1])
                date = f"{year}-{month}-{day}"
            except Exception:
                return not_valid("The scat_id value is not correct")

            # region
            scat_region = fn.get_region(request.form["province"])

            # UTM coord conversion
            coord_latlon = utm.to_latlon(int(request.form["coord_east"]), int(request.form["coord_north"]), int(request.form["coord_zone"].replace("N", "")), "N")

            connection = fn.get_connection()
            cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

            sql = ("INSERT INTO scats (scat_id, date, sampling_season, sampling_type, path_id, snowtrack_id, "
                   "location, municipality, province, region, "
                   "deposition, matrix, collected_scat, scalp_category, "
                   "coord_east, coord_north, coord_zone, "
                   "observer, institution,"
                   "geo) "
                   "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)")
            cursor.execute(sql,
                           [
                            request.form["scat_id"],
                            date,
                            fn.sampling_season(date),
                            request.form["sampling_type"],
                            request.form["path_id"],
                            request.form["snowtrack_id"],
                            request.form["location"], request.form["municipality"], request.form["province"].upper(), scat_region,
                            request.form["deposition"], request.form["matrix"], request.form["collected_scat"], request.form["scalp_category"],
                            request.form["coord_east"], request.form["coord_north"], request.form["coord_zone"],
                            request.form["observer"], request.form["institution"],
                            f"SRID=4326;POINT({coord_latlon[1]} {coord_latlon[0]})"
                           ]
                           )

            connection.commit()

            return redirect("/scats_list")
        else:
            return not_valid("Some values are not set or are wrong. Please check and submit again")



@app.route("/edit_scat/<scat_id>", methods=("GET", "POST"))
def edit_scat(scat_id):

    def not_valid(msg):
            # default values
            default_values = {}
            for k in request.form:
                default_values[k] = request.form[k]

            flash(Markup(f"<b>{msg}</b>"))

            return render_template("new_scat.html",
                                   title="Edit scat",
                                   action=f"/edit_scat/{scat_id}",
                                   form=form,
                                   default_values=default_values)


    if request.method == "GET":
        connection = fn.get_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("SELECT * FROM scats WHERE scat_id = %s",
                    [scat_id])
        default_values = cursor.fetchone()

        form = Scat(path_id=default_values["path_id"],
                    snowtrack_id=default_values["snowtrack_id"],
                    sampling_type=default_values["sampling_type"],
                    deposition=default_values["deposition"],
                    matrix=default_values["matrix"],
                    collected_scat=default_values["collected_scat"],
                    scalp_category=default_values["scalp_category"])

        # get id of all paths
        form.path_id.choices = [("", "")] + [(x, x) for x in fn.all_path_id()]
        # get id of all snow tracks
        form.snowtrack_id.choices = [("", "")] + [(x, x) for x in fn.all_snow_tracks_id()]

        return render_template("new_scat.html",
                            title="Edit scat",
                            action=f"/edit_scat/{scat_id}",
                            form=form,
                            default_values=default_values)


    if request.method == "POST":

        form = Scat(request.form)

        # get id of all paths
        form.path_id.choices = [("", "")] + [(x, x) for x in fn.all_path_id()]

        # get id of all snow tracks
        form.snowtrack_id.choices = [("", "")] + [(x, x) for x in fn.all_snow_tracks_id()]

        if form.validate():

            # date
            try:
                year = int(request.form['scat_id'][1:2+1]) + 2000
                month = int(request.form['scat_id'][3:4+1])
                day = int(request.form['scat_id'][5:6+1])
                date = f"{year}-{month:02}-{day:02}"
            except Exception:
                return not_valid("The scat_id value is not correct")

            # region
            scat_region = fn.get_region(request.form["province"])

            # UTM coord conversion
            coord_latlon = utm.to_latlon(int(request.form["coord_east"]), int(request.form["coord_north"]), int(request.form["coord_zone"].replace("N", "")), "N")

            connection = fn.get_connection()
            cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

            sql = ("UPDATE scats SET scat_id = %s, "
                   "                date = %s,"
                   "                sampling_season = %s,"
                   "                sampling_type = %s,"
                   "                path_id = %s, "
                   "                snowtrack_id = %s, "
                   "                location = %s, "
                   "                municipality = %s, "
                   "                province = %s, "
                   "                region = %s, "
                   "                deposition = %s, "
                   "                matrix = %s, "
                   "                collected_scat = %s, "
                   "                scalp_category = %s, "
                   "                coord_east = %s, "
                   "                coord_north = %s, "
                   "                coord_zone = %s, "
                   "                observer = %s, "
                   "                institution = %s, "
                   "                geo = %s "
                   "WHERE scat_id = %s")
            cursor.execute(sql,
                           [
                            request.form["scat_id"],
                            date,
                            fn.sampling_season(date),
                            request.form["sampling_type"],
                            request.form["path_id"],
                            request.form["snowtrack_id"],
                            request.form["location"], request.form["municipality"], request.form["province"], scat_region,
                            request.form["deposition"], request.form["matrix"], request.form["collected_scat"], request.form["scalp_category"],
                            request.form["coord_east"], request.form["coord_north"], request.form["coord_zone"],
                            request.form["observer"], request.form["institution"],
                            f"SRID=4326;POINT({coord_latlon[1]} {coord_latlon[0]})",
                            scat_id
                           ]
                           )

            connection.commit()

            return redirect(f"/view_scat/{scat_id}")
        else:
            return not_valid("Some values are not set or are wrong. Please check and submit again")


@app.route("/del_scat/<scat_id>")
def del_scat(scat_id):
    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("DELETE FROM scats WHERE scat_id = %(scat_id)s",
                   {"scat_id": scat_id})
    connection.commit()
    return redirect("/scats_list")



def extract_data_from_tsv(filename):
    """
    Extract and check data from a TSV file
    """

    df = pd.read_csv(pl.Path(UPLOAD_FOLDER) / pl.Path(filename), sep="\t")

    # check columns
    for column in ['scat_id', 'date', 'wa_code', 'genotype_id', 'sampling_type', 'transect_id', 'snowtrack_id',
                    'location', 'municipality', 'province', 
                    'deposition', 'matrix', 'collected_scat', 'scalp_category', 
                    'genetic_sample', 
                    'coord_east', 'coord_north', 'coord_zone', 
                    'operator', 'institution']:
        if column not in list(df.columns):
            return True, fn.alert_danger(f"Column {column} is missing"), {}

    all_data = {}
    for index, row in df.iterrows():
        data = {}
        for column in list(df.columns):
            data[column] = row[column]
            if isinstance(data[column], float) and str(data[column]) == "nan":
                data[column] = ""
            

        # date
        try:
            year = int(data['scat_id'][1:2+1]) + 2000
            month = int(data['scat_id'][3:4+1])
            day = int(data['scat_id'][5:6+1])
            date = f"{year}-{month}-{day}"
        except Exception:
            return True, fn.alert_danger(f"The scat ID is not valid at row {index + 1}: {data['scat_id']}"), {}

        # check date
        if date != data["date"].strip():
            return True, fn.alert_danger(f"Check the scat ID and the date at row {index + 1}: {data['scat_id']}  {data['date']}"), {}

        # path_id
        path_id = data['transect_id'] + "_" + date[2:].replace("-", "")
        data["path_id"] = path_id

        # region
        scat_region = fn.get_region(data["province"])
        data["region"] = scat_region        

        # UTM coord conversion
        try:
            coord_latlon = utm.to_latlon(int(data["coord_east"]), int(data["coord_north"]), int(data["coord_zone"].replace("N", "")), "N")
        except Exception:
            return True, fn.alert_danger(f'Check the UTM coordinates at row {index + 1}: {data["coord_east"]} {data["coord_north"]} {data["coord_zone"]}'), {}
        data["coord_latlon"] = f"SRID=4326;POINT({coord_latlon[1]} {coord_latlon[0]})"

        # sampling_type
        if data["sampling_type"].upper().strip() not in ["OPPORTUNISTIC", "SYSTEMATIC"]:
            return True, fn.alert_danger(f'Sampling type must be <b>Opportunistic</b> or <b>Systematic</b> at row {index + 1}'), {}

        # deposition
        if data["deposition"].upper().strip() not in ["FRESH", "OLD"]:
            return True, fn.alert_danger(f'The deposition must be <b>fresh</b> or <b>old</b> at row {index + 1}'), {}

        # collected_scat
        if data["collected_scat"].upper().strip() not in ["YES", "NO"]:
            return True, fn.alert_danger(f'The collected_scat must be <b>Yes</b> or <b>No</b> at row {index + 1}'), {}

        # matrix
        if data["matrix"].upper().strip() not in ["YES", "NO"]:
            return True, fn.alert_danger(f'The matrix must be <b>Yes</b> or <b>No</b> at row {index + 1}')

        all_data[index] = dict(data)

    return False, "", all_data


@app.route("/load_scats_tsv", methods=("GET", "POST",))
def load_scats_tsv():

    if request.method == "GET":
        return render_template("load_scats_tsv.html")

    if request.method == "POST":

        new_file = request.files["new_file"]

        # check file extension
        if pl.Path(new_file.filename).suffix.upper() not in ALLOWED_EXTENSIONS:
            flash("The uploaded file does not have an allowed extension")
            return redirect(f"/load_scats_tsv")

        try:
            filename = str(uuid.uuid4())
            new_file.save(pl.Path(UPLOAD_FOLDER) / pl.Path(filename))
        except Exception:
            flash(fn.alert_danger("Error with the uploaded file"))
            return redirect(f"/load_scats_tsv")

        r, msg, all_data = extract_data_from_tsv(filename)
        if r:
            flash(msg)
            return redirect(f"/load_scats_tsv")

        else:
            # check if scat_id already in DB
            connection = fn.get_connection()
            cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
            scats_list = "','".join([all_data[idx]['scat_id'] for idx in all_data])
            sql = f"select scat_id from scats where scat_id in ('{scats_list}')"   
            cursor.execute(sql) 
            scats_to_update = [row["scat_id"] for row in cursor.fetchall()]


            return render_template("confirm_load_scats_tsv.html",
                                   n_scats = len(all_data),
                                   n_scats_to_update=scats_to_update,
                                   all_data=all_data,
                                   filename=filename)


@app.route("/confirm_load/<filename>/<mode>")
def confirm_load(filename, mode):

    if mode not in ["new", "all"]:
        flash(fn.alert_danger("Error: mode not allowed"))
        return redirect(f"/load_scats_tsv")

    r, msg, all_data = extract_data_from_tsv(filename)
    if r:
        flash(msg)
        return redirect(f"/load_scats_tsv")

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # check if scat_id already in DB
    scats_list = "','".join([all_data[idx]['scat_id'] for idx in all_data])
    sql = f"select scat_id from scats where scat_id in ('{scats_list}')"   
    cursor.execute(sql) 
    scats_to_update = [row["scat_id"] for row in cursor.fetchall()]

    sql = ("UPDATE scats SET scat_id = %(scat_id)s, "
            "                date = %(date)s,"
            "                wa_code = %(wa_code)s,"
            "                genotype_id = %(genotype_id)s,"
            "                sampling_season = %(sampling_season)s,"
            "                sampling_type = %(sampling_type)s,"
            "                path_id = %(path_id)s, "
            "                snowtrack_id = %(snowtrack_id)s, "
            "                location = %(location)s, "
            "                municipality = %(municipality)s, "
            "                province = %(province)s, "
            "                region = %(region)s, "
            "                deposition = %(deposition)s, "
            "                matrix = %(matrix)s, "
            "                collected_scat = %(collected_scat)s, "
            "                scalp_category = %(scalp_category)s, "
            "                coord_east = %(coord_east)s, "
            "                coord_north = %(coord_north)s, "
            "                coord_zone = %(coord_zone)s, "
            "                observer = %(operator)s, "
            "                institution = %(institution)s, "
            "                geo = %(geo)s "
            "WHERE scat_id = %(scat_id)s;"
        
            "INSERT INTO scats (scat_id, date, wa_code, genotype_id, sampling_season, sampling_type, path_id, snowtrack_id, "
            "location, municipality, province, region, "
            "deposition, matrix, collected_scat, scalp_category, "
            "coord_east, coord_north, coord_zone, "
            "observer, institution,"
            "geo) "
            "SELECT %(scat_id)s, %(date)s, %(wa_code)s, %(genotype_id)s, "
            " %(sampling_season)s, %(sampling_type)s, %(path_id)s, %(snowtrack_id)s, "
            "%(location)s, %(municipality)s, %(province)s, %(region)s, %(deposition)s, %(matrix)s, %(collected_scat)s, %(scalp_category)s, "
            " %(coord_east)s, %(coord_north)s, %(coord_zone)s, %(operator)s, %(institution)s, %(geo)s "
            "WHERE NOT EXISTS (SELECT 1 FROM scats WHERE scat_id = %(scat_id)s)"
            )
    count_added = 0
    count_updated = 0
    for idx in all_data:
        data = dict(all_data[idx])

        if mode == "new" and (data["scat_id"] in scats_to_update):
            continue
        if data["scat_id"] in scats_to_update:
            count_updated += 1
        else:
            count_added += 1

        cursor.execute(sql,
                        {"scat_id": data["scat_id"].strip(),
                        "date": data["date"],
                        "wa_code": data["wa_code"].strip(),
                        "genotype_id": data["genotype_id"].strip(),
                        "sampling_season": fn.sampling_season(data["date"]),
                        "sampling_type": data["sampling_type"].strip(),
                        "path_id": data["path_id"],
                        "snowtrack_id": data["snowtrack_id"].strip(),
                        "location": data["location"].strip(), "municipality": data["municipality"].strip(),
                        "province": data["province"].strip().upper(), "region": data["region"],
                        "deposition": data["deposition"], "matrix": data["matrix"].strip(),
                        "collected_scat": data["collected_scat"].strip(), "scalp_category": data["scalp_category"].strip(),
                        "coord_east": data["coord_east"], "coord_north": data["coord_north"], "coord_zone": data["coord_zone"].strip(),
                        "operator": data["operator"].strip(),   "institution": data["institution"].strip(),
                        "geo": data["coord_latlon"],
                        }
                        )
    connection.commit()

    msg = f"TSV file successfully loaded. {count_added} scats added, {count_updated} scats updated."
    flash(fn.alert_success(msg))

    return redirect(f'/scats')





'''
https://stackoverflow.com/questions/1109061/insert-on-duplicate-update-in-postgresql

            INSERT INTO the_table (id, column_1, column_2) 
VALUES (1, 'A', 'X'), (2, 'B', 'Y'), (3, 'C', 'Z')
ON CONFLICT (id) DO UPDATE 
  SET column_1 = excluded.column_1, 
      column_2 = excluded.column_2;



      UPDATE table SET field='C', field2='Z' WHERE id=3;
INSERT INTO table (id, field, field2)
       SELECT 3, 'C', 'Z'
       WHERE NOT EXISTS (SELECT 1 FROM table WHERE id=3);
            
'''

