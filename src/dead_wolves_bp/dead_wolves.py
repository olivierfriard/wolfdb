"""
WolfDB web service
(c) Olivier Friard

flask blueprint for dead wolves management
"""

import flask
from flask import render_template, redirect, request, flash, session
from markupsafe import Markup
from sqlalchemy import text, exc
import utm
from config import config

from .dw_form import Dead_wolf

import functions as fn

app = flask.Blueprint("dead_wolves", __name__, template_folder="templates")

params = config()

app.debug = params["debug"]


@app.route("/view_tissue/<path:tissue_id>")
def view_tissue(tissue_id: str):
    """
    show dead wolf corresponding to tissue ID
    """

    with fn.conn_alchemy().connect() as con:
        row = (
            con.execute(
                text("SELECT id FROM dead_wolves WHERE tissue_id = :tissue_id"),
                {"tissue_id": tissue_id},
            )
            .mappings()
            .fetchone()
        )
        if row is not None:
            return redirect(f"/view_dead_wolf_id/{row['id']}")
        else:
            flash(fn.alert_danger(f"Tissue ID <b>{tissue_id}</b> not found."))
            return redirect("/dead_wolves_list")


@app.route("/view_dead_wolf_id/<int:id>")
@fn.check_login
def view_dead_wolf_id(id: int):
    """
    visualize dead wolf data (by id)
    """
    with fn.conn_alchemy().connect() as con:
        dead_wolf = (
            con.execute(
                text(
                    "SELECT * FROM dead_wolves WHERE deleted IS NULL AND id = :dead_wolf_id"
                ),
                {"dead_wolf_id": id},
            )
            .mappings()
            .fetchone()
        )

        if dead_wolf is None:
            flash(fn.alert_danger(f"Dead wolf <b>#{id}</b> not found"))
            return redirect("/dead_wolves_list")

        # fields list
        fields_list = (
            con.execute(
                text(
                    "SELECT * FROM dead_wolves_fields_definition WHERE visible = 'Y' ORDER BY position"
                )
            )
            .mappings()
            .all()
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

    dead_wolf_values: dict = {}
    for row in rows:
        dead_wolf_values[row["name"]] = row["val"]

    # coordinates
    lat_lon: list = []
    if dead_wolf["utm_east"] and dead_wolf["utm_north"] and dead_wolf["utm_zone"]:
        lat_lon = utm.to_latlon(
            dead_wolf["utm_east"],
            dead_wolf["utm_north"],
            int(dead_wolf["utm_zone"].replace("N", "")),
            dead_wolf["utm_zone"][-1],
        )

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
        header_title=f"Dead wolf #{dead_wolf['id']}",
        fields_list=fields_list,
        dead_wolf=dead_wolf,
        dead_wolf_values=dead_wolf_values,
        map=Markup(
            fn.leaflet_geojson(
                {
                    "dead_wolves": dw_features,
                    "dead_wolves_color": params["dead_wolf_color"],
                    "center": center,
                }
            )
        )
        if dead_wolf["geometry_utm"]
        else "",
    )


@app.route("/plot_dead_wolves")
@fn.check_login
def plot_dead_wolves():
    """
    plot dead wolves
    """
    with fn.conn_alchemy().connect() as con:
        tot_min_lat, tot_min_lon = 90, 90
        tot_max_lat, tot_max_lon = -90, -90

        dw_features: list = []
        dw_count: int = 0
        for row in (
            con.execute(
                text(
                    "SELECT id, genotype_id, tissue_id, discovery_date,"
                    "ST_X(st_transform(geometry_utm, 4326)) as longitude, "
                    "ST_Y(st_transform(geometry_utm, 4326)) as latitude "
                    "FROM dead_wolves "
                    "WHERE deleted is NULL "
                    "AND utm_east BETWEEN 166021 AND 833978 AND utm_north BETWEEN 1 AND 9329005 "
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
            # lat, lon = utm.to_latlon(int(float(row["utm_east"])), int(float(row["utm_north"])), 32, "N")

            print(f"{row["genotype_id"]=}  {row["latitude"]=}   {row["longitude"]=}")

            tot_min_lat = min([tot_min_lat, row["latitude"]])
            tot_max_lat = max([tot_max_lat, row["latitude"]])
            tot_min_lon = min([tot_min_lon, row["longitude"]])
            tot_max_lon = max([tot_max_lon, row["longitude"]])
            print()
            print(f"{tot_min_lat=}   {tot_max_lat=}")
            print(f"{tot_min_lon=}   {tot_max_lon=}")

            popup_content: list = [
                f"""ID: <a href="/view_dead_wolf_id/{row["id"]}" target="_blank">{row["id"]}</a><br>"""
            ]
            if row["genotype_id"]:
                popup_content.append(
                    f"""Genotype ID: <a href="/view_genotype/{row["genotype_id"]}" target="_blank">{row["genotype_id"]}</a><br>"""
                )
            else:
                popup_content.append(
                    f"""Tissue ID: <a href="/view_tissue/{row["tissue_id"]}" target="_blank">{row["tissue_id"]}</a><br>"""
                )

            if row["discovery_date"]:
                popup_content.append(f"""Discovery date: {row["discovery_date"]}<br>""")

            dw_feature = {
                "geometry": dict(
                    {
                        "type": "Point",
                        "coordinates": [row["longitude"], row["latitude"]],
                    }
                ),
                "type": "Feature",
                "properties": {
                    "popupContent": "".join(popup_content),
                },
                "id": row["id"],
            }
            dw_features.append(dict(dw_feature))

            dw_count += 1

    print()
    print(f"{dw_features=}")

    return render_template(
        "plot_dead_wolves.html",
        header_title="Locations of dead wolves",
        map=Markup(
            fn.leaflet_geojson(
                {
                    "dead_wolves": dw_features,
                    "dead_wolves_color": params["dead_wolf_color"],
                    "fit": [[tot_min_lat, tot_min_lon], [tot_max_lat, tot_max_lon]],
                }
            )
        ),
        dead_wolf_color=params["dead_wolf_color"],
        dw_count=dw_count,
    )


@app.route("/new_dead_wolf", methods=("GET", "POST"))
@fn.check_login
def new_dead_wolf():
    """
    insert a new dead wolf
    """

    def not_valid(form, msg):
        # default values
        default_values: dict = {}
        for k in request.form:
            default_values[k] = request.form[k]

        flash(fn.alert_danger(f"<b>{msg}</b>"))

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
            default_values={"utm_zone": "32N"},
        )

    if request.method == "POST":
        form = Dead_wolf(request.form)

        if not form.validate():
            return not_valid(form, "Dead wolf form NOT validated. See details below.")

        with fn.conn_alchemy().connect() as con:
            # check tissue id
            if request.form["tissue_id"]:
                tissue_id = (
                    con.execute(
                        text(
                            "SELECT tissue_id FROM dead_wolves WHERE tissue_id = :tissue_id"
                        ),
                        {"tissue_id": request.form["tissue_id"]},
                    )
                    .mappings()
                    .fetchone()
                )
                if tissue_id is not None:
                    return not_valid(
                        form,
                        f"The tissue id <b>{request.form['tissue_id']}</b> is already present in dead wolves table",
                    )

            # check tissue id
            if request.form["genotype_id"]:
                genotype_id = (
                    con.execute(
                        text(
                            "SELECT genotype_id FROM dead_wolves WHERE genotype_id = :genotype_id"
                        ),
                        {"genotype_id": request.form["genotype_id"]},
                    )
                    .mappings()
                    .fetchone()
                )
                if genotype_id is not None:
                    return not_valid(
                        form,
                        f"The genotype id <b>{request.form['genotype_id']}</b> is already present in dead wolves table",
                    )

            location = request.form["location"]
            municipality = request.form["municipality"]
            province_code = request.form["province"]

            # add location, municipality, province, region if not indicated
            if (
                request.form["utm_zone"]
                and request.form["utm_east"]
                and request.form["utm_north"]
            ):
                try:
                    lat_lon = utm.to_latlon(
                        int(request.form["utm_east"]),
                        int(request.form["utm_north"]),
                        int(request.form["utm_zone"].upper().replace("N", "")),
                        request.form["utm_zone"].upper()[-1],
                    )
                except Exception as error:
                    return not_valid(
                        form, f"Check the UTM coordinates ({error.args[0]})"
                    )
                r = fn.reverse_geocoding(lat_lon[::-1])
                if not location:
                    location = r["location"]
                if not municipality:
                    municipality = r["municipality"]
                if not province_code:
                    province_code = r["province_code"]

            # add region
            region: str = ""
            if province_code:
                region = (
                    con.execute(
                        text(
                            "SELECT region FROM geo_info WHERE province_code = :province_code"
                        ),
                        {"province_code": province_code},
                    )
                    .mappings()
                    .fetchone()["region"]
                )

            try:
                con.execute(
                    text(
                        (
                            "INSERT INTO dead_wolves "
                            "(genotype_id, tissue_id, discovery_date, location, municipality, province, region, wa_code, utm_east, utm_north, utm_zone, geometry_utm) "
                            "VALUES "
                            "(:genotype_id, :tissue_id, :discovery_date, :location, :municipality, :province, :region, :wa_code, "
                            ":utm_east, :utm_north, :utm_zone, st_geomfromtext(:utm_geometry, 32632))"
                        )
                    ),
                    {
                        # "new_id": new_id,
                        "genotype_id": request.form["genotype_id"]
                        if request.form["genotype_id"]
                        else None,
                        "tissue_id": request.form["tissue_id"]
                        if request.form["tissue_id"]
                        else None,
                        "discovery_date": request.form["discovery_date"]
                        if request.form["discovery_date"]
                        else None,
                        "location": location if location else None,
                        "municipality": municipality if municipality else None,
                        "province": province_code if province_code else None,
                        "wa_code": request.form["wa_code"]
                        if request.form["wa_code"]
                        else None,
                        "utm_east": request.form["utm_east"]
                        if request.form["utm_east"]
                        else None,
                        "utm_north": request.form["utm_north"]
                        if request.form["utm_north"]
                        else None,
                        "utm_zone": request.form["utm_zone"]
                        if request.form["utm_zone"]
                        and request.form["utm_east"]
                        and request.form["utm_north"]
                        else None,
                        "utm_geometry": f"POINT({request.form['utm_east']} {request.form['utm_north']})"
                        if request.form["utm_east"] and request.form["utm_north"]
                        else None,
                        "region": region if region else None,
                    },
                )
            except exc.IntegrityError as error:
                return not_valid(form, f"field not unique: {error.args[0]}")
            except exc.InternalError as error:
                if "invalid geometry" in error.args[0]:
                    return not_valid(
                        form, f"Check the UTM coordinates ({error.args[0]})"
                    )
                else:
                    return not_valid(form, f"Error {error.args[0]}")

            # get last id
            row = (
                con.execute(text("SELECT MAX(id) AS max_id FROM dead_wolves"))
                .mappings()
                .fetchone()
            )
            new_id = row["max_id"]

            # fields list
            fields_list = (
                con.execute(
                    text(
                        "SELECT * FROM dead_wolves_fields_definition ORDER BY position"
                    )
                )
                .mappings()
                .all()
            )

            for field in fields_list:
                if f"field{field['field_id']}" in request.form:
                    # date
                    if (
                        field["field_id"] in (8, 9, 11)
                        and request.form[f"field{field['field_id']}"] == ""
                    ):
                        con.execute(
                            text(
                                "INSERT INTO dead_wolves_values (id, field_id, val) VALUES (:new_id, :field_id, NULL)"
                            ),
                            {"new_id": new_id, "field_id": field["field_id"]},
                        )

                    else:
                        con.execute(
                            text(
                                "INSERT INTO dead_wolves_values (id, field_id, val) VALUES (:new_id, :field_id, :value)"
                            ),
                            {
                                "new_id": new_id,
                                "field_id": field["field_id"],
                                "value": request.form[f"field{field['field_id']}"],
                            },
                        )

        return redirect(f"/view_dead_wolf_id/{new_id}")


@app.route("/edit_dead_wolf/<int:id>", methods=("GET", "POST"))
@fn.check_login
def edit_dead_wolf(id: int):
    """
    Edit an existing dead wolf
    """

    def not_valid(form, msg):
        # default values
        default_values = {}
        for k in request.form:
            default_values[k] = request.form[k]

        flash(fn.alert_danger(f"<b>{msg}</b>"))

        return render_template(
            "new_dead_wolf.html",
            header_title=f"Edit dead wolf #{id}",
            title="Edit dead wolf",
            action=f"/edit_dead_wolf/{id}",
            form=form,
            default_values=default_values,
        )

    if request.method == "GET":
        with fn.conn_alchemy().connect() as con:
            dead_wolf = (
                con.execute(
                    text(
                        "SELECT * FROM dead_wolves WHERE deleted IS NULL AND id = :dead_wolf_id"
                    ),
                    {"dead_wolf_id": id},
                )
                .mappings()
                .fetchone()
            )

            if dead_wolf is None:
                flash(fn.alert_danger(f"Dead wolf <b>#{id}</b> not found"))
                return redirect("/dead_wolves_list")

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

        default_values = {
            "genotype_id": dead_wolf["genotype_id"]
            if dead_wolf["genotype_id"] is not None
            else "",
            "tissue_id": dead_wolf["tissue_id"]
            if dead_wolf["tissue_id"] is not None
            else "",
            "discovery_date": dead_wolf["discovery_date"]
            if dead_wolf["discovery_date"] is not None
            else "",
            "location": dead_wolf["location"]
            if dead_wolf["location"] is not None
            else "",
            "municipality": dead_wolf["municipality"]
            if dead_wolf["municipality"] is not None
            else "",
            "wa_code": dead_wolf["wa_code"] if dead_wolf["wa_code"] is not None else "",
            "utm_east": dead_wolf["utm_east"]
            if dead_wolf["utm_east"] is not None
            else "",
            "utm_north": dead_wolf["utm_north"]
            if dead_wolf["utm_north"] is not None
            else "",
            "utm_zone": dead_wolf["utm_zone"]
            if dead_wolf["utm_zone"] is not None
            else "",
        }

        for row in rows:
            if row["val"] is None:
                default_values[f"field{row['field_id']}"] = ""
            else:
                if row["field_id"] in (8, 9, 11) and " " in row["val"]:
                    default_values[f"field{row['field_id']}"] = row["val"].split(" ")[0]
                else:
                    default_values[f"field{row['field_id']}"] = row["val"]

        form = Dead_wolf(
            # for selectfield elements
            field2=default_values["field2"] if "field2" in default_values else "",
            field3=default_values["field3"] if "field3" in default_values else "",
            field12=default_values["field12"] if "field12" in default_values else "",
            field13=default_values["field13"] if "field13" in default_values else "",
            province=dead_wolf["province"],
            field26=default_values["field26"] if "field26" in default_values else "",
            field35=default_values["field34"] if "field34" in default_values else "",
            field43=default_values["field43"] if "field43" in default_values else "",
            field82=default_values["field82"] if "field82" in default_values else "",
            field83=default_values["field83"] if "field83" in default_values else "",
        )

        title = f"Edit dead wolf <b>#{id}</b>"
        if dead_wolf["tissue_id"]:
            title += f" - tissue ID <b>{dead_wolf['tissue_id']}</b>"
        if dead_wolf["genotype_id"]:
            title += f" - Genotype <b>{dead_wolf['genotype_id']}</b>"

        return render_template(
            "new_dead_wolf.html",
            header_title=f"Edit dead wolf #{id}",
            title=Markup(title),
            action=f"/edit_dead_wolf/{id}",
            form=form,
            default_values=default_values,
        )

    if request.method == "POST":
        form = Dead_wolf(request.form)

        if not form.validate():
            return not_valid(form, "Dead wolf form NOT validated. See details below.")

        with fn.conn_alchemy().connect() as con:
            # add region
            region: str = ""
            if request.form["province"]:
                region = (
                    con.execute(
                        text(
                            "SELECT region FROM geo_info WHERE province_code = :province_code"
                        ),
                        {"province_code": request.form["province"]},
                    )
                    .mappings()
                    .fetchone()["region"]
                )

            con.execute(
                text(
                    (
                        "UPDATE dead_wolves "
                        "SET genotype_id = :genotype_id,"
                        "tissue_id = :tissue_id,"
                        "discovery_date = :discovery_date,"
                        "location = :location,"
                        "municipality = :municipality,"
                        "province = :province,"
                        "region = :region,"
                        "wa_code = :wa_code,"
                        "utm_east = :utm_east,"
                        "utm_north = :utm_north,"
                        "utm_zone = :utm_zone,"
                        "geometry_utm = st_geomfromtext(:utm_geometry, 32632) "
                        "WHERE id = :dead_wolf_id "
                    )
                ),
                {
                    "dead_wolf_id": id,
                    "genotype_id": request.form["genotype_id"]
                    if request.form["genotype_id"]
                    else None,
                    "tissue_id": request.form["tissue_id"]
                    if request.form["tissue_id"]
                    else None,
                    "discovery_date": request.form["discovery_date"]
                    if request.form["discovery_date"]
                    else None,
                    "location": request.form["location"]
                    if request.form["location"]
                    else None,
                    "municipality": request.form["municipality"]
                    if request.form["municipality"]
                    else None,
                    "province": request.form["province"]
                    if request.form["province"]
                    else None,
                    "wa_code": request.form["wa_code"]
                    if request.form["wa_code"]
                    else None,
                    "utm_east": request.form["utm_east"]
                    if request.form["utm_east"]
                    else None,
                    "utm_north": request.form["utm_north"]
                    if request.form["utm_north"]
                    else None,
                    "utm_zone": request.form["utm_zone"]
                    if request.form["utm_zone"]
                    and request.form["utm_east"]
                    and request.form["utm_north"]
                    else None,
                    "utm_geometry": f"POINT({request.form['utm_east']} {request.form['utm_north']})"
                    if request.form["utm_east"] and request.form["utm_north"]
                    else None,
                    "region": region if region else None,
                },
            )

            fields_list = (
                con.execute(
                    text(
                        "SELECT * FROM dead_wolves_fields_definition ORDER BY position"
                    )
                )
                .mappings()
                .all()
            )

            for row in fields_list:
                if f"field{row['field_id']}" in request.form:
                    # date
                    if (
                        row["field_id"] in (8, 9, 11)
                        and request.form[f"field{row['field_id']}"] == ""
                    ):
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
                                "SET val = :value"
                            ),
                            {
                                "id": id,
                                "field_id": row["field_id"],
                                "value": request.form[f"field{row['field_id']}"],
                            },
                        )

        return redirect(f"/view_dead_wolf_id/{id}")


@app.route("/del_dead_wolf/<id>")
@fn.check_login
def del_dead_wolf(id):
    """
    set dead wolf as deleted
    """
    with fn.conn_alchemy().connect() as con:
        con.execute(
            text("UPDATE dead_wolves SET deleted = NOW() WHERE id = :dead_wolf_id"),
            {"dead_wolf_id": id},
        )

    flash(fn.alert_success(f"Dead wolf <b>#{id}</b> deleted"))

    return redirect("/dead_wolves_list")


@app.route("/dead_wolves_list")
@fn.check_login
def dead_wolves_list():
    """
    show list of dead wolves that were not deleted
    """

    with fn.conn_alchemy().connect() as con:
        results = (
            con.execute(
                text(
                    "SELECT * "
                    ",(SELECT genotype_id FROM genotypes WHERE genotype_id=dead_wolves.genotype_id) AS genotype_id_verif "
                    "FROM dead_wolves "
                    "WHERE "
                    "deleted is NULL "
                    "AND (discovery_date BETWEEN :start_date AND :end_date OR discovery_date IS NULL) "
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
        results=results,
        n_dead_wolves=len(results),
    )
