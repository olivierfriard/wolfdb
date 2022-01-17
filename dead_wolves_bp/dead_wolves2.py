"""
WolfDB web service
(c) Olivier Friard

flask blueprint for scats management
"""



import flask
from flask import Flask, render_template, redirect, request, Markup, flash, session
import psycopg2
import psycopg2.extras
import json
import utm
from config import config

from .dw_form import Dead_wolf

#from dead_wolf import Dead_wolf
import functions as fn
from italian_regions import regions

app = flask.Blueprint("dead_wolves", __name__, template_folder="templates")

app.debug = True


params = config()

@app.route("/dead_wolves")
@fn.check_login
def dead_wolves():
    return render_template("dead_wolves.html")


@app.route("/view_dead_wolf/<id>")
@fn.check_login
def view_dead_wolf(id):
    """
    visualize dead wolf data (by id)
    """
    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # fields list
    cursor.execute("select * from dead_wolves_fields_definition order by position")
    fields_list = cursor.fetchall()

    cursor.execute("select id,name,val from dead_wolves_values, dead_wolves_fields_definition where dead_wolves_values.field_id=dead_wolves_fields_definition.field_id AND id = %s",
                   [id])

    rows = cursor.fetchall()

    dead_wolf = {}
    for row in rows:
        dead_wolf[row["name"]] = row["val"]
    
    try:
        dead_wolf["UTM Coordinates X"] = int(float(dead_wolf["UTM Coordinates X"]))
        dead_wolf["UTM Coordinates Y"] = int(float(dead_wolf["UTM Coordinates Y"]))

        lat_lon = utm.to_latlon(dead_wolf["UTM Coordinates X"],
                                dead_wolf["UTM Coordinates Y"],
                                int(dead_wolf["UTM zone"].replace("N", "")),
                                dead_wolf["UTM zone"][-1])
    except Exception:
        lat_lon = []
    
    if lat_lon:

        dw_feature = {"geometry": {'type': 'Point', 'coordinates': [lat_lon[1], lat_lon[0]]},
                     "type": "Feature",
                     "properties": {"style": {"color": "purple", "fillColor": "purple", "fillOpacity": 1},
                                   "popupContent": f"Dead wolf ID: {id}"
                                  },
                    "id": id
                   }

        dw_features = [dw_feature]
        center = f"{lat_lon[0]}, {lat_lon[1]}"
    else:
        dw_features = []
        center = ""

    return render_template("view_dead_wolf.html",
                           header_title=f"Dead wolf #{dead_wolf['ID']}", 
                           fields_list=fields_list,
                           dead_wolf=dead_wolf,
                           map=Markup(fn.leaflet_geojson(center, dw_features, []))
                          )



@app.route("/view_tissue/<tissue_id>")
@fn.check_login
def view_tissue(tissue_id):

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cursor.execute(("SELECT *, "
                    "ST_AsGeoJSON(st_transform(geometry_utm, 4326)) AS dw_lonlat, "
                    "ROUND(st_x(st_transform(geometry_utm, 4326))::numeric, 6) as longitude, "
                    "ROUND(st_y(st_transform(geometry_utm, 4326))::numeric, 6) as latitude "
                    "FROM dead_wolves WHERE tissue_id = %s"),
                   [tissue_id])
    dead_wolf = cursor.fetchone()

    dw_geojson = json.loads(dead_wolf["dw_lonlat"])

    print(dict(dw_geojson))

    dw_feature = {"geometry": dict(dw_geojson),
                    "type": "Feature",
                    "properties": {"style": {"color": "purple", "fillColor": "purple", "fillOpacity": 1},
                                   "popupContent": f"Tissue ID: {tissue_id}"
                                  },
                    "id": tissue_id
                   }

    dw_features = [dw_feature]

    center = f"{dead_wolf['latitude']}, {dead_wolf['longitude']}"


    return render_template("view_tissue.html",
                           dead_wolf=dead_wolf,
                           map=Markup(fn.leaflet_geojson(center, dw_features, []))
                          )


@app.route("/dead_wolves_list")
@fn.check_login
def dead_wolves_list():
    """
    get list all dead_wolves
    """
    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute(("SELECT * FROM dw_short ORDER BY id"))

    results = cursor.fetchall()

    return render_template("dead_wolves_list.html",
                           header_title="List of dead wolves",
                           length=len(results),
                           results=results
                           )


@app.route("/plot_dead_wolves")
@fn.check_login
def plot_dead_wolves():
    """
    plot dead wolves
    """
    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT * FROM dw_short2")

    scat_features = []
    for row in cursor.fetchall():

        try:
            lat_lon = utm.to_latlon(int(float(row["utm_east"])),
                                    int(float(row["utm_north"])),
                                    32, "N")

            scat_geojson =  {'type': 'Point', 'coordinates': [lat_lon[1], lat_lon[0]]}

            scat_feature = {"geometry": dict(scat_geojson),
                            "type": "Feature",
                            "properties": {"style": {"color": "purple", "fillColor": "purple", "fillOpacity": 1},
                                        "popupContent": f"""Tissue ID: <a href="/view_tissue/{row['tissue_id']}" target="_blank">{row['tissue_id']}</a>"""
                                        },
                            "id": row["tissue_id"]
                    }
            scat_features.append(dict(scat_feature))

        except Exception:
            pass

    center = f"45 , 9"

    transect_features = []

    return render_template("plot_dead_wolves.html",
                           header_title="Plot of dead wolves",
                           map=Markup(fn.leaflet_geojson(center, scat_features, transect_features, zoom=7))
                           )




@app.route("/new_dead_wolf", methods=("GET", "POST"))
def new_dead_wolf():

    def not_valid(msg):
        # default values
        default_values = {}
        for k in request.form:
            default_values[k] = request.form[k]

        flash(Markup(f"<b>{msg}</b>"))

        return render_template("new_transect.html",
                            title="New transect",
                            action=f"/new_transect",
                            form=form,
                            default_values=default_values)


    if request.method == "GET":
        form = Dead_wolf()
        return render_template('new_dead_wolf.html',
                               title="New dead wolf",
                               action=f"/new_dead_wolf",
                            form=form,
                            default_values={})


    if request.method == "POST":
        form = Dead_wolf(request.form)

        if form.validate():

            connection = fn.get_connection()
            cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

            cursor.execute("SELECT MAX(id) AS max_id FROM dead_wolves_values")
            row = cursor.fetchone()
            new_id = row["max_id"] + 1

            # fields list
            cursor.execute("select * from dead_wolves_fields_definition order by position")
            fields_list = cursor.fetchall()

            cursor.execute("INSERT INTO dead_wolves_values (id, field_id, val) VALUE (%s, %s, %s)",
                                    [new_id, 1, new_id])
            connection.commit()
            for field in fields_list:
                if f"field{field['field_id']}" in request.form:
                    print(request.form[f"field{field['field_id']}"])

                    cursor.execute("INSERT INTO dead_wolves_values (id, field_id, val) VALUES (%s, %s, %s)",
                                    [new_id, field['field_id'], request.form[f"field{field['field_id']}"]])

            connection.commit()

            return redirect("/dead_wolves_list")
        else:
            return not_valid("Dead wolf form NOT validated")






@app.route("/edit_dead_wolf/<id>", methods=("GET", "POST"))
def edit_dead_wolf(id):

    def not_valid(msg):
        # default values
        default_values = {}
        for k in request.form:
            default_values[k] = request.form[k]

        flash(Markup(f"<b>{msg}</b>"))

        return render_template("new_transect.html",
                            title="Edit transect",
                            action=f"/edit_transect/{transect_id}",
                            form=form,
                            default_values=default_values)


    if request.method == "GET":
        connection = fn.get_connection()
        cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("SELECT * FROM transects WHERE transect_id = %s",
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

            transect_regions = fn.get_regions(request.form["province"])
            if request.form["province"] and transect_regions == "":
                return not_valid("Check the province field!")


            connection = fn.get_connection()
            cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

            sql = ("UPDATE transects SET transect_id = %s, sector =%s, location = %s, municipality = %s, province = %s, region = %s "
                   "WHERE transect_id = %s")
            cursor.execute(sql,
                           [
                            request.form["transect_id"].strip(), request.form["sector"],
                            request.form["location"].strip(), request.form["municipality"].strip(),
                            request.form["province"].strip().upper(), transect_regions,
                            transect_id
                           ]
                           )

            connection.commit()

            return redirect(f"/view_dead_wolf/{transect_id}")
        else:
            return not_valid("Dead wolf form NOT validated")

'''
@app.route("/del_transect/<transect_id>")
def del_scat(transect_id):

    connection = fn.get_connection()
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # check if path based on transect exist
    cursor.execute("SELECT COUNT(*) AS n_paths FROM paths WHERE transect_id = %s", [transect_id])
    result = cursor.fetchone()
    if result["n_paths"] > 0:
        return "Some paths are based on this transect. Please remove them before"

    cursor.execute("DELETE FROM transects WHERE transect_id = %s",
                   [transect_id])
    connection.commit()
    return redirect("/transects_list")


'''