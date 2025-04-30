"""
WolfDB web service
(c) Olivier Friard

export results in XLSX format
"""

from openpyxl import Workbook
from tempfile import NamedTemporaryFile


def export_wa_genetic_samples(loci_list, wa_scats, loci_values, with_notes):
    wb = Workbook()

    ws1 = wb.active
    ws1.title = "WA genetic samples"

    header: list = [
        "WA code",
        "Sample ID",
        "Date",
        "Municipality",
        "Coordinate WGS84 UTM East",
        "Coordinate WGS84 UTM North",
        "UTM Zone",
        "mtDNA result",
        "Genotype ID",
        "Notes on genotype",
        "Temp ID",
        "Sex",
        "Status",
        "Pack",
        "Dead recovery",
    ]

    for locus in loci_list:
        for allele in ("a", "b")[: loci_list[locus]]:
            header.extend([f"{locus} {allele}", f"Notes for {locus} {allele}"])

    ws1.append(header)

    for row in wa_scats:
        out = []
        out.append(row["wa_code"])
        out.append(row["sample_id"] if row["sample_id"] is not None else "")
        out.append(row["date"] if row["date"] is not None else "")
        out.append(row["municipality"] if row["municipality"] is not None else "")

        out.append(row["coord_east"])
        out.append(row["coord_north"])
        out.append("32N")

        out.append(row["mtdna"] if row["mtdna"] is not None else "")
        out.append(row["genotype_id"] if row["genotype_id"] is not None else "")
        out.append(row["notes"] if row["notes"] is not None else "")
        out.append(row["tmp_id"] if row["tmp_id"] is not None else "")
        out.append(row["sex_id"] if row["sex_id"] is not None else "")
        out.append(row["status"] if row["status"] is not None else "")
        out.append(row["pack"] if row["pack"] is not None else "")
        out.append(row["dead_recovery"] if row["dead_recovery"] is not None else "")

        for locus in loci_list:
            for allele in ("a", "b")[: loci_list[locus]]:
                out.extend(
                    [
                        loci_values[row["wa_code"]][locus][allele]["value"],
                        loci_values[row["wa_code"]][locus][allele]["notes"],
                    ]
                )

        ws1.append(out)

    with NamedTemporaryFile() as tmp:
        wb.save(tmp.name)
        tmp.seek(0)
        stream = tmp.read()

        return stream


def export_wa_analysis(loci_list, wa_scats, loci_values, distance: int, cluster_id: int):
    """
    export cluster content in XLSX
    """

    wb = Workbook()

    ws1 = wb.active
    ws1.title = f"WA matches (DBSCAN distance {distance} cluster ID {cluster_id})"

    header: list = [
        "WA code",
        "Sample ID",
        "Date",
        "Municipality",
        "Coordinate WGS84 UTM East",
        "Coordinate WGS84 UTM North",
        "UTM Zone",
        "mtDNA result",
        "Genotype ID",
        "Notes on genotype",
        "Temporary ID",
        "Sex",
        "Status",
        "Pack",
        "Dead recovery",
    ]
    for locus in loci_list:
        header.extend([f"{locus} a", f"Notes for {locus} a"])
        if loci_list[locus] == 2:
            header.extend([f"{locus} b", f"Notes for {locus} b"])

    ws1.append(header)

    for row in wa_scats:
        out = []
        out.append(row["wa_code"])
        out.append(row["sample_id"] if row["sample_id"] is not None else "")
        out.append(row["date"] if row["date"] is not None else "")
        out.append(row["municipality"] if row["municipality"] is not None else "")

        out.append(row["coord_east"])
        out.append(row["coord_north"])
        out.append("32N")

        out.append(row["mtdna"] if row["mtdna"] is not None else "")
        out.append(row["genotype_id"] if row["genotype_id"] is not None else "")

        out.append(row["notes"] if row["notes"] is not None else "")

        out.append(row["tmp_id"] if row["tmp_id"] is not None else "")
        out.append(row["sex_id"] if row["sex_id"] is not None else "")

        out.append(row["status"] if row["status"] is not None else "")
        out.append(row["pack"] if row["pack"] is not None else "")
        out.append(row["dead_recovery"] if row["dead_recovery"] is not None else "")

        for locus in loci_list:
            out.extend(
                [
                    loci_values[row["wa_code"]][locus]["a"]["value"],
                    loci_values[row["wa_code"]][locus]["a"]["notes"],
                    loci_values[row["wa_code"]][locus]["b"]["value"],
                    loci_values[row["wa_code"]][locus]["b"]["notes"],
                ]
            )

        ws1.append(out)

    with NamedTemporaryFile() as tmp:
        wb.save(tmp.name)
        tmp.seek(0)
        stream = tmp.read()

        return stream


def export_wa_analysis_group(loci_list, data, loci_values):
    wb = Workbook()

    ws1 = wb.active
    ws1.title = "Genotype matches"

    header = [
        "Genotype ID",
        "Notes on genotype",
        "Temporary ID",
        "Sex",
        "Status",
        "Pack",
        "Hybrid",
        "Dispersal",
        "Number of recaptures",
        "Dead recovery",
    ]
    for locus in loci_list:
        header.extend([f"{locus} a", f"Notes for {locus} a"])
        if loci_list[locus] == 2:
            header.extend([f"{locus} b", f"Notes for {locus} b"])

    ws1.append(header)

    for genotype_id in data:
        out = []

        out.append(genotype_id)
        out.append(data[genotype_id]["working_notes"])
        out.append(data[genotype_id]["tmp_id"])
        out.append(data[genotype_id]["sex"])
        out.append(data[genotype_id]["status"])
        out.append(data[genotype_id]["pack"])
        out.append(data[genotype_id]["hybrid"])
        out.append(data[genotype_id]["dispersal"])
        out.append(data[genotype_id]["n_recap"])
        out.append(data[genotype_id]["dead_recovery"])

        for locus in loci_list:
            out.extend(
                [
                    loci_values[genotype_id][locus]["a"]["value"],
                    loci_values[genotype_id][locus]["a"]["notes"],
                    loci_values[genotype_id][locus]["b"]["value"] if "b" in loci_values[genotype_id][locus] else "",
                    loci_values[genotype_id][locus]["b"]["notes"] if "b" in loci_values[genotype_id][locus] else "",
                ]
            )

        ws1.append(out)

    with NamedTemporaryFile() as tmp:
        wb.save(tmp.name)
        tmp.seek(0)
        stream = tmp.read()

        return stream


def export_wa(loci_list, wa_list, loci_values):
    """
    export WA in XLSX
    """

    wb = Workbook()

    ws1 = wb.active
    ws1.title = "WA"

    header = [
        "WA code",
        "Sample ID",
        "Genotype ID",
        "Date",
        "Box number",
        "Municipality",
        "Province",
        "Coordinates East WGS84 UTM",
        "Coordinates North WGS84 UTM",
        "UTM Zone",
        "mtDNA result",
        "Temporary ID",
        "Sex",
        "Status",
        "Pack",
        "Dead recovery",
    ]
    for locus in loci_list:
        header.extend([f"{locus} a", f"Notes for {locus} a"])
        if loci_list[locus] == 2:
            header.extend([f"{locus} b", f"Notes for {locus} b"])

    ws1.append(header)

    for wa in wa_list:
        out = []

        out.append(wa["wa_code"])
        out.append(wa["sample_id"])
        out.append(wa["genotype_id"])
        out.append(wa["date"])
        out.append(wa["box_number"])
        out.append(wa["municipality"])
        out.append(wa["province"])
        out.append(wa["coord_east"])
        out.append(wa["coord_north"])
        out.append("32N")
        out.append(wa["mtdna"])
        out.append(wa["tmp_id"])
        out.append(wa["sex_id"])
        out.append(wa["status"])
        out.append(wa["pack"])
        out.append(wa["dead_recovery"])

        for locus in loci_list:
            if wa["wa_code"] in loci_values:
                out.extend(
                    [
                        loci_values[wa["wa_code"]][locus]["a"]["value"],
                        loci_values[wa["wa_code"]][locus]["a"]["notes"],
                        loci_values[wa["wa_code"]][locus]["b"]["value"] if "b" in loci_values[wa["wa_code"]][locus] else "",
                        loci_values[wa["wa_code"]][locus]["b"]["notes"] if "b" in loci_values[wa["wa_code"]][locus] else "",
                    ]
                )
            else:
                out.extend(["", "", "", ""])

        ws1.append(out)

    with NamedTemporaryFile() as tmp:
        wb.save(tmp.name)
        tmp.seek(0)
        stream = tmp.read()

        return stream


def export_genotypes_list(loci_list, results, loci_values):
    wb = Workbook()

    ws1 = wb.active
    ws1.title = "Genotype matches"

    fields = {
        "genotype_id": "Genotype ID",
        "tmp_id": "Other ID",
        "date": "Date",
        "pack": "Pack",
        "sex": "Sex",
        "hybrid": "Hybrid",
        "status": "Status",
        "age_first_capture": "Age at first capture",
        "status_first_capture": "status at first capture",
        "dispersal": "Dispersal",
        "n_recaptures": "Number of recaptures",
        "dead_recovery": "Dead recovery",
    }

    header: list = list(fields.values())
    for locus in loci_list:
        for allele in ("a", "b")[: loci_list[locus]]:
            header.extend([f"{locus} {allele}", f"Notes for {locus} {allele}"])

    ws1.append(header)

    for row in results:
        out: list = [row[field] if row[field] is not None else "" for field in fields]
        for locus in loci_list:
            for allele in ("a", "b")[: loci_list[locus]]:
                out.extend(
                    [
                        loci_values[row["genotype_id"]][locus][allele]["value"],
                        loci_values[row["genotype_id"]][locus][allele]["notes"],
                    ]
                )

        ws1.append(out)

    with NamedTemporaryFile() as tmp:
        wb.save(tmp.name)
        tmp.seek(0)
        stream = tmp.read()

        return stream
