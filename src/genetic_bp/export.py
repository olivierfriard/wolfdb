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


def export_wa_analysis(loci_list, wa_scats, loci_values, distance, cluster_id):
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


def export_genotypes_list(loci_list, results, loci_values):
    wb = Workbook()

    ws1 = wb.active
    ws1.title = "Genotype matches"

    header: list = [
        "Genotype ID",
        "Other ID",
        "Date",
        "Pack",
        "Sex",
        "Hybrid",
        "Status",
        "Age at first capture",
        "status at first capture",
        "Dispersal",
        "Number of recaptures",
        "Dead recovery",
    ]
    for locus in loci_list:
        for allele in ("a", "b")[: loci_list[locus]]:
            header.extend([f"{locus} {allele}", f"Notes for {locus} {allele}"])

    ws1.append(header)

    for row in results:
        out = []
        out.append(row["genotype_id"])
        out.append(row["tmp_id"] if row["tmp_id"] is not None else "")
        out.append(row["date"] if row["date"] is not None else "")
        out.append(row["pack"] if row["pack"] is not None else "")
        out.append(row["sex"] if row["sex"] is not None else "")
        out.append(row["hybrid"] if row["hybrid"] is not None else "")
        out.append(row["status"] if row["status"] is not None else "")
        out.append(row["age_first_capture"] if row["age_first_capture"] is not None else "")
        out.append(row["status_first_capture"] if row["status_first_capture"] is not None else "")

        out.append(row["dispersal"] if row["dispersal"] is not None else "")
        out.append(row["n_recaptures"] if row["n_recaptures"] is not None else "")
        out.append(row["dead_recovery"] if row["dead_recovery"] is not None else "")

        for locus in loci_list:
            """
            print()
            print(locus)
            print(loci_list[locus])
            print(f"{loci_values[row["genotype_id"]][locus]}=")
            """
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
