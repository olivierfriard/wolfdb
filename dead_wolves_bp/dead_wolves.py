"""
WolfDB web service
(c) Olivier Friard

flask blueprint for dead wolves management
"""


import flask
from flask import render_template, redirect, request, flash, session
from markupsafe import Markup
from sqlalchemy import text
import utm
from config import config

from .dw_form import Dead_wolf

import functions as fn
from italian_regions import regions

app = flask.Blueprint("dead_wolves", __name__, template_folder="templates")

params = config()

app.debug = params["debug"]


@app.route("/dead_wolves")
@fn.check_login
def dead_wolves():
    return render_template("dead_wolves.html", header_title="Dead wolves")


@app.route("/view_tissue/<path:tissue_id>")
def view_tissue(tissue_id):
    """
    show dead wolf corresponding to tissue ID
    """

    with fn.conn_alchemy().connect() as con:
        row = (
            con.execute(text("SELECT id FROM dead_wolves_mat WHERE tissue_id = :tissue_id"), {"tissue_id": tissue_id}).mappings().fetchone()
        )
        if row is not None:
            return redirect(f"/view_dead_wolf_id/{row['id']}")
        else:
            "Tissue ID not found"


@app.route("/view_dead_wolf_id/<id>")
@fn.check_login
def view_dead_wolf_id(id):
    """
    visualize dead wolf data (by id)
    """
    with fn.conn_alchemy().connect() as con:
        # fields list
        fields_list = (
            con.execute(text("SELECT * FROM dead_wolves_fields_definition WHERE visible = 'Y' ORDER BY position")).mappings().all()
        )

        rows = (
            con.execute(
                text(
                    "SELECT id, name, val "
                    "FROM dead_wolves_values, dead_wolves_fields_definition "
                    "WHERE dead_wolves_values.field_id=dead_wolves_fields_definition.field_id "
                    "AND id = :id"
                ),
                {"id": id},
            )
            .mappings()
            .all()
        )

    dead_wolf: dict = {}
    for row in rows:
        dead_wolf[row["name"]] = row["val"]

    try:
        dead_wolf["UTM Coordinates X"] = int(float(dead_wolf["UTM Coordinates X"]))
        dead_wolf["UTM Coordinates Y"] = int(float(dead_wolf["UTM Coordinates Y"]))

        lat_lon = utm.to_latlon(
            dead_wolf["UTM Coordinates X"],
            dead_wolf["UTM Coordinates Y"],
            int(dead_wolf["UTM zone"].replace("N", "")),
            dead_wolf["UTM zone"][-1],
        )

        dead_wolf[
            "Coordinates (WGS 84 / UTM zone 32N EPSG:32632)"
        ] = f"East: {dead_wolf['UTM Coordinates X']} North: {dead_wolf['UTM Coordinates Y']}"
        fields_list.append({"name": "Coordinates (WGS 84 / UTM zone 32N EPSG:32632)"})

    except Exception:
        lat_lon = []

    if lat_lon:
        dw_feature = {
            "geometry": {"type": "Point", "coordinates": [lat_lon[1], lat_lon[0]]},
            "type": "Feature",
            "properties": {"popupContent": f"Dead wolf ID: {id}"},
            "id": id,
        }

        dw_features = [dw_feature]
        center = f"{lat_lon[0]}, {lat_lon[1]}"
    else:
        dw_features = []
        center = ""

    return render_template(
        "view_dead_wolf.html",
        header_title=f"Dead wolf #{dead_wolf['ID']}",
        fields_list=fields_list,
        dead_wolf=dead_wolf,
        map=Markup(
            fn.leaflet_geojson2(
                {
                    "dead_wolves": dw_features,
                    "dead_wolves_color": params["dead_wolf_color"],
                    "center": center,
                }
            )
        ),
    )


@app.route("/plot_dead_wolves")
@fn.check_login
def plot_dead_wolves():
    """
    plot dead wolves
    """
    con = fn.conn_alchemy().connect()

    tot_min_lat, tot_min_lon = 90, 90
    tot_max_lat, tot_max_lon = -90, -90

    dw_features = []
    for row in (
        con.execute(
            text(
                "SELECT * FROM dead_wolves_mat "
                "WHERE deleted is NULL "
                "AND utm_east != '0' AND utm_north != '0' "
                "AND discovery_date BETWEEN :start_date AND :end_date"
            ),
            {
                "start_date": session["start_date"],
                "end_date": session["end_date"],
            },
        )
        .mappings()
        .all()
    ):
        try:
            lat, lon = utm.to_latlon(int(float(row["utm_east"])), int(float(row["utm_north"])), 32, "N")

            tot_min_lat = min([tot_min_lat, lat])
            tot_max_lat = max([tot_max_lat, lat])
            tot_min_lon = min([tot_min_lon, lon])
            tot_max_lon = max([tot_max_lon, lon])

            dw_geojson = {"type": "Point", "coordinates": [lon, lat]}

            dw_feature = {
                "geometry": dict(dw_geojson),
                "type": "Feature",
                "properties": {
                    "popupContent": (f"""ID: <a href="/view_dead_wolf_id/{row['id']}" target="_blank">{row['id']}</a><br>""")
                    + (
                        f"""Genotype ID: <a href="/view_genotype/{row['genotype_id']}" target="_blank">{row['genotype_id']}</a><br>"""
                        if row["genotype_id"]
                        else "" f"""Tissue ID: <a href="/view_tissue/{row['tissue_id']}" target="_blank">{row['tissue_id']}</a><br>"""
                    ),
                },
                "id": row["id"],
            }
            dw_features.append(dict(dw_feature))

        except Exception:
            pass

    return render_template(
        "plot_dead_wolves.html",
        header_title="Plot of dead wolves",
        map=Markup(
            fn.leaflet_geojson2(
                {
                    "dead_wolves": dw_features,
                    "dead_wolves_color": params["dead_wolf_color"],
                    "fit": [[tot_min_lat, tot_min_lon], [tot_max_lat, tot_max_lon]],
                }
            )
        ),
        scat_color=params["scat_color"],
        dead_wolf_color=params["dead_wolf_color"],
        transect_color=params["transect_color"],
        track_color=params["track_color"],
    )


@app.route("/new_dead_wolf", methods=("GET", "POST"))
@fn.check_login
def new_dead_wolf():
    """
    insert a new dead wolf
    """

    def not_valid(form, msg):
        # default values
        default_values = {}
        for k in request.form:
            default_values[k] = request.form[k]

        flash(Markup(f'<div class="alert alert-danger" role="alert"><b>{msg}</b></div>'))

        return render_template(
            "new_dead_wolf.html",
            title="New dead wolf",
            action="/new_dead_wolf",
            form=form,
            default_values=default_values,
        )

    if request.method == "GET":
        form = Dead_wolf()
        return render_template(
            "new_dead_wolf.html",
            header_title="New dead wolf",
            title="New dead wolf",
            action="/new_dead_wolf",
            form=form,
            default_values={},
        )

    if request.method == "POST":
        form = Dead_wolf(request.form)

        if not form.validate():
            return not_valid(form, "Dead wolf form NOT validated. See details below.")

        con = fn.conn_alchemy().connect()

        row = con.execute(text("SELECT MAX(id) AS max_id FROM dead_wolves_values")).mappings().fetchone()
        new_id = row["max_id"] + 1

        # add region
        if request.form["field20"]:
            region = (
                con.execute(text("SELECT region from geo_info WHERE province_code = %s", [request.form["field20"]]))
                .mappings()
                .fetchone()["region"]
            )
        else:
            region = ""

        # fields list
        fields_list = con.execute(text("SELECT * FROM dead_wolves_fields_definition order by position")).mappings().all()

        # insert ID
        con.execute(text("INSERT INTO dead_wolves_values (id, field_id, val) VALUES (:new_id, 1, :new_id)"), {"new_id": new_id})

        for field in fields_list:
            # region
            if field["field_id"] == 200:
                con.execute(
                    text("INSERT INTO dead_wolves_values (id, field_id, val) VALUES (:new_id, :field_id, :region)"),
                    {"new_id": new_id, "field_id": field["field_id"], "region": region},
                )

            if f"field{field['field_id']}" in request.form:
                # check UTM coordinates
                if field["field_id"] in (23, 24) and request.form[f"field{field['field_id']}"] == "":
                    con.execute(
                        text("INSERT INTO dead_wolves_values (id, field_id, val) VALUES (:new_id, :field_id, :value)"),
                        {"new_id": new_id, "field_id": field["field_id"], "value": "0"},
                    )
                # date
                elif field["field_id"] in (8, 9, 11) and request.form[f"field{field['field_id']}"] == "":
                    con.execute(
                        text("INSERT INTO dead_wolves_values (id, field_id, val) VALUES (:new_id, :field_id, NULL)"),
                        {"new_id": new_id, "field_id": field["field_id"]},
                    )

                else:
                    con.execute(
                        "INSERT INTO dead_wolves_values (id, field_id, val) VALUES (:new_id, :field_id, :value)",
                        {"new_id": new_id, "field_id": field["field_id"], "value": request.form[f"field{field['field_id']}"]},
                    )

        return redirect(f"/view_dead_wolf_id/{new_id}")


@app.route("/edit_dead_wolf/<id>", methods=("GET", "POST"))
@fn.check_login
def edit_dead_wolf(id):
    """
    Edit an existing dead wolf
    """

    def not_valid(form, msg):
        # default values
        default_values = {}
        for k in request.form:
            default_values[k] = request.form[k]

        flash(Markup(f'<div class="alert alert-danger" role="alert"><b>{msg}</b></div>'))

        return render_template(
            "new_dead_wolf.html",
            header_title=f"Edit dead wolf #{id}",
            title="Edit dead wolf",
            action=f"/edit_dead_wolf/{id}",
            form=form,
            default_values=default_values,
        )

    con = fn.conn_alchemy().connect()

    if request.method == "GET":
        rows = (
            con.execute(
                text(
                    "SELECT id, dead_wolves_values.field_id AS field_id, name, val "
                    "FROM dead_wolves_values, dead_wolves_fields_definition "
                    "WHERE dead_wolves_values.field_id=dead_wolves_fields_definition.field_id AND id = :id"
                ),
                {"id": id},
            )
            .mappings()
            .all()
        )

        default_values: dict = {}
        for row in rows:
            if row["val"] is None:
                default_values[f"field{row['field_id']}"] = ""
            else:
                if row["field_id"] in (8, 9, 11) and " " in row["val"]:
                    default_values[f"field{row['field_id']}"] = row["val"].split(" ")[0]
                else:
                    default_values[f"field{row['field_id']}"] = row["val"]

        form = Dead_wolf(
            field2=default_values["field2"],  # for selectfield elements
            field3=default_values["field3"],
            field12=default_values["field12"],
            field13=default_values["field13"],
            field20=default_values["field20"],
            field26=default_values["field26"],
            field35=default_values["field34"],
            field43=default_values["field43"],
            field82=default_values["field82"],
            field83=default_values["field83"],
        )

        return render_template(
            "new_dead_wolf.html",
            header_title=f"Edit dead wolf #{id}",
            title=f"Edit dead wolf #{id}",
            action=f"/edit_dead_wolf/{id}",
            form=form,
            default_values=default_values,
        )

    if request.method == "POST":
        form = Dead_wolf(request.form)

        if form.validate():
            fields_list = con.execute(text("SELECT * FROM dead_wolves_fields_definition ORDER BY position")).mappings().all()

            for row in fields_list:
                if f"field{row['field_id']}" in request.form:
                    # date
                    if row["field_id"] in (8, 9, 11) and request.form[f"field{row['field_id']}"] == "":
                        con.execute(
                            text(
                                "INSERT INTO dead_wolves_values (id, field_id, val) VALUES (:id, :field_id, NULL)"
                                "ON CONFLICT (id, field_id) DO UPDATE SET val = NULL"
                            ),
                            {"id": id, "field_id": row["field_id"]},
                        )
                    else:
                        con.execute(
                            text(
                                "INSERT INTO dead_wolves_values VALUES (:id, :field_id, :value) "
                                "ON CONFLICT (id, field_id) DO UPDATE "
                                "SET val = EXCLUDED.val"
                            ),
                            {"id": id, "field_id": row["field_id"], "value": request.form[f"field{row['field_id']}"]},
                        )

            return redirect(f"/view_dead_wolf_id/{id}")
        else:
            return not_valid(form, "Dead wolf form NOT validated. See details below.")


@app.route("/del_dead_wolf/<id>")
@fn.check_login
def del_dead_wolf(id):
    with fn.conn_alchemy().connect() as con:
        con.execute(
            text("INSERT INTO dead_wolves_values VALUES (:id, 107, NOW()) ON CONFLICT (id, field_id) DO UPDATE SET val = NOW()"),
            {"id": id},
        )

    return redirect("/dead_wolves_list")


@app.route("/dead_wolves_list")
@fn.check_login
def dead_wolves_list():
    """
    get list of all dead_wolves
    """

    with fn.conn_alchemy().connect() as con:
        results = (
            con.execute(
                text(
                    "SELECT *,"
                    "(SELECT genotype_id FROM genotypes WHERE genotype_id=dead_wolves_mat.genotype_id) AS genotype_id_verif "
                    "FROM dead_wolves_mat "
                    "WHERE "
                    "deleted is NULL "
                    "AND discovery_date BETWEEN :start_date AND :end_date "
                    "ORDER BY id"
                ),
                {
                    "start_date": session["start_date"],
                    "end_date": session["end_date"],
                },
            )
            .mappings()
            .all()
        )

    return render_template(
        "dead_wolves_list.html",
        header_title="List of dead wolves",
        length=len(results),
        results=results,
        n_dead_wolves=len(results),
    )
