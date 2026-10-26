CREATE OR REPLACE VIEW public.wa_dw AS
SELECT
    wa_results.wa_code,
    dead_wolves.tissue_id AS sample_id,
    dead_wolves.discovery_date AS date,
    dead_wolves.utm_east AS coord_east,
    dead_wolves.utm_north AS coord_north,
    dead_wolves.utm_zone AS coord_zone,
    dead_wolves.geometry_utm,
    dead_wolves.location,
    dead_wolves.municipality,
    dead_wolves.province,
    dead_wolves.region,
    wa_results.quality_genotype,
    wa_results.genotype_id,
    wa_results.individual_id AS tmp_id,
    wa_results.mtdna,
    wa_results.sex_id,
    'Dead wolf'::text AS sample_type,
    wa_results.box_number,
    wa_results.laboratory_acronym
FROM public.dead_wolves, public.wa_results
WHERE wa_results.wa_code::text = dead_wolves.wa_code::text;


CREATE OR REPLACE VIEW public.wa_scat AS
SELECT
    wa_results.wa_code,
    scats.scat_id AS sample_id,
    scats.date,
    scats.coord_east,
    scats.coord_north,
    scats.coord_zone,
    scats.geometry_utm,
    scats.location,
    scats.municipality,
    scats.province,
    scats.region,
    wa_results.quality_genotype,
    wa_results.genotype_id,
    wa_results.individual_id AS tmp_id,
    wa_results.mtdna,
    wa_results.sex_id,
    scats.sample_type,
    wa_results.box_number,
    wa_results.laboratory_acronym
FROM public.scats, public.wa_results
WHERE scats.wa_code::text = wa_results.wa_code::text;


CREATE OR REPLACE VIEW public.wa_scat_dw_all AS
SELECT
    wa_scat.wa_code,
    wa_scat.sample_id,
    wa_scat.date,
    wa_scat.coord_east,
    wa_scat.coord_north,
    wa_scat.coord_zone,
    wa_scat.geometry_utm,
    wa_scat.location,
    wa_scat.municipality,
    wa_scat.province,
    wa_scat.region,
    wa_scat.quality_genotype,
    wa_scat.genotype_id,
    wa_scat.tmp_id,
    wa_scat.mtdna,
    wa_scat.sex_id,
    wa_scat.sample_type,
    wa_scat.box_number,
    wa_scat.laboratory_acronym
FROM public.wa_scat
UNION ALL
SELECT
    wa_dw.wa_code,
    wa_dw.sample_id,
    wa_dw.date,
    wa_dw.coord_east,
    wa_dw.coord_north,
    wa_dw.coord_zone,
    wa_dw.geometry_utm,
    wa_dw.location,
    wa_dw.municipality,
    wa_dw.province,
    wa_dw.region,
    wa_dw.quality_genotype,
    wa_dw.genotype_id,
    wa_dw.tmp_id,
    wa_dw.mtdna,
    wa_dw.sex_id,
    wa_dw.sample_type,
    wa_dw.box_number,
    wa_dw.laboratory_acronym
FROM public.wa_dw;


CREATE OR REPLACE VIEW public.wa_genetic_samples_all AS
SELECT
    w.wa_code,
    w.sample_id,
    w.date,
    w.municipality,
    w.province,
    w.coord_east,
    w.coord_north,
    w.coord_zone,
    w.geometry_utm,
    w.genotype_id,
    w.tmp_id,
    w.mtdna,
    w.sex_id,
    w.sample_type,
    w.box_number,
    g.working_notes AS notes,
    g.status,
    g.hybrid,
    g.pack,
    CASE
        WHEN EXISTS (
            SELECT 1
            FROM public.dead_wolves AS dw
            WHERE dw.tissue_id = w.sample_id::text
        ) THEN 'Yes'::text
        ELSE NULL::text
    END AS dead_recovery,
    w.laboratory_acronym
FROM public.wa_scat_dw_all AS w
LEFT JOIN public.genotypes AS g ON g.genotype_id::text = w.genotype_id::text
ORDER BY w.wa_code;


CREATE OR REPLACE VIEW public.genotypes_list_all AS
SELECT
    g.genotype_id,
    g.date,
    g.pack,
    g.sex,
    g.age_first_capture,
    g.status_first_capture,
    g.dispersal,
    g.record_status,
    g.tmp_id,
    g.notes,
    g.status,
    g.working_notes,
    g.changed_status,
    g.mother,
    g.father,
    g.hybrid,
    g.mtdna,
    COALESCE(w.n_recaptures, 0::bigint) AS n_recaptures,
    CASE
        WHEN w.dead_recovery THEN 'Yes'::text
        ELSE NULL::text
    END AS dead_recovery,
    w.date_first_capture
FROM public.genotypes AS g
LEFT JOIN (
    SELECT
        wa_scat_dw_all.genotype_id,
        count(DISTINCT (sample_type, sample_id)) AS n_recaptures,
        bool_or(
            wa_scat_dw_all.sample_id::text ~~ 'T%'::text
            OR wa_scat_dw_all.sample_id::text ~~ 'M%'::text
        ) AS dead_recovery,
        min(wa_scat_dw_all.date) AS date_first_capture
    FROM public.wa_scat_dw_all
    GROUP BY wa_scat_dw_all.genotype_id
) AS w ON w.genotype_id::text = g.genotype_id::text
ORDER BY g.genotype_id;


CREATE OR REPLACE VIEW public.scats_list_all AS
SELECT
    s.scat_id,
    s.date,
    s.wa_code,
    s.sampling_season,
    s.sampling_type,
    s.sample_type,
    s.box_number,
    s.path_id,
    s.snowtrack_id,
    s.location,
    s.municipality,
    s.province,
    s.region,
    s.deposition,
    s.matrix,
    s.collected_scat,
    s.genetic_sample,
    s.coord_east,
    s.coord_north,
    s.coord_zone,
    s.observer,
    s.institution,
    s.notes,
    s.geometry_utm,
    s.region_auto,
    s.province_auto,
    s.municipality_auto,
    s.location_auto,
    s.ispra_id,
    w.genotype_id AS genotype_id2,
    CASE
        WHEN lower(w.mtdna::text) ~~ '%wolf%'::text THEN 'C1'::character varying
        ELSE s.scalp_category
    END AS scalp_category
FROM public.scats AS s
LEFT JOIN LATERAL (
    SELECT wsdm.genotype_id, wsdm.mtdna
    FROM public.wa_scat_dw_all AS wsdm
    WHERE wsdm.wa_code::text = s.wa_code::text
    ORDER BY (wsdm.laboratory_acronym = 'NGC') DESC,
             wsdm.laboratory_acronym, wsdm.date DESC NULLS LAST
    LIMIT 1
) AS w ON true
ORDER BY s.scat_id;
