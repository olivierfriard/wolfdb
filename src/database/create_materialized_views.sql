
drop view wa_scat CASCADE;


-- alter table scats alter column geometry_utm TYPE geometry USING geometry_utm::geometry;
-- alter table transects alter column multilines TYPE geometry(MultiLineString) USING multilines::geometry;
-- alter table transects drop column points_utm;
-- alter table snow_tracks drop column geometry_utm;
-- alter table snow_tracks alter column multilines TYPE geometry(MultiLineString) USING multilines::geometry;




DROP view  IF EXISTS wa_dw;

CREATE VIEW wa_dw AS
 SELECT wa_results.wa_code,
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
    wa_results.box_number

   FROM dead_wolves, wa_results

  WHERE ((wa_results.wa_code)::text = (dead_wolves.wa_code)::text);



drop view  IF EXISTS wa_scat;

CREATE VIEW wa_scat AS
 SELECT wa_results.wa_code,
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
    wa_results.box_number

   FROM scats, wa_results

  WHERE ((scats.wa_code)::text = (wa_results.wa_code)::text);


-- wa_scat_dw_mat

drop MATERIALIZED view IF EXISTS wa_scat_dw_mat;

CREATE MATERIALIZED VIEW wa_scat_dw_mat AS
 SELECT wa_scat.wa_code,
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
    wa_scat.box_number

   FROM wa_scat

UNION
 SELECT wa_dw.wa_code,
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
    wa_dw.box_number

   FROM wa_dw

  WITH NO DATA;


CREATE INDEX idx_wa_scat_dw_mat_date ON wa_scat_dw_mat(date);
CREATE INDEX idx_wa_scat_dw_mat_genotypeid ON wa_scat_dw_mat(genotype_id);
CREATE INDEX idx_wa_scat_dw_mat_mtdna ON wa_scat_dw_mat(mtdna);
CREATE INDEX idx_wa_scat_dw_mat_good_mtdna ON wa_scat_dw_mat (genotype_id, sample_id) WHERE mtdna <> 'Poor DNA';
CREATE INDEX idx_wa_scat_dw_mat_wa_code ON wa_scat_dw_mat(wa_code);






-- genotypes_list_mat


drop MATERIALIZED view  IF EXISTS  genotypes_list_mat;

CREATE MATERIALIZED VIEW genotypes_list_mat AS
WITH scat_summary AS (
    SELECT
        genotype_id,
        COUNT(sample_id) AS n_recaptures,
        MIN(date) AS date_first_capture,
        MAX(CASE WHEN sample_id LIKE 'T%' OR sample_id LIKE 'M%' THEN 'Yes' ELSE NULL END) AS dead_recovery
    FROM
        wa_scat_dw_mat
    GROUP BY
        genotype_id
)
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
    COALESCE(s.n_recaptures, 0) AS n_recaptures,
    s.dead_recovery,
    s.date_first_capture
FROM
    genotypes g
LEFT JOIN
    scat_summary s ON s.genotype_id = g.genotype_id
ORDER BY
    g.genotype_id
WITH NO DATA;

CREATE INDEX idx_genotypes_list_mat_date ON genotypes_list_mat(date);
CREATE INDEX idx_genotypes_list_mat_genotype_id ON genotypes_list_mat(genotype_id);
CREATE INDEX idx_genotypes_list_mat_pack ON genotypes_list_mat(pack);
CREATE INDEX idx_genotypes_list_mat_date_first_capture ON genotypes_list_mat(date_first_capture);



-- CREATE MATERIALIZED VIEW genotypes_list_mat AS
--  SELECT genotype_id,
--     date,
--     pack,
--     sex,
--     age_first_capture,
--     status_first_capture,
--     dispersal,
--     record_status,
--     tmp_id,
--     notes,
--     status,
--     working_notes,
--     changed_status,
--     mother,
--     father,
--     hybrid,
--     mtdna,
--     ( SELECT count(wa_scat_dw_mat.sample_id) AS count
--            FROM public.wa_scat_dw_mat
--           WHERE ((wa_scat_dw_mat.genotype_id)::text = (genotypes.genotype_id)::text)) AS n_recaptures,
--     ( SELECT 'Yes'::text AS text
--            FROM public.wa_scat_dw_mat
--           WHERE ((((wa_scat_dw_mat.sample_id)::text ~~ 'T%'::text) OR ((wa_scat_dw_mat.sample_id)::text ~~ 'M%'::text)) AND ((wa_scat_dw_mat.genotype_id)::text = (genotypes.genotype_id)::text))
--          LIMIT 1) AS dead_recovery,
--     ( SELECT min(wa_scat_dw_mat.date) AS min
--            FROM public.wa_scat_dw_mat
--           WHERE ((wa_scat_dw_mat.genotype_id)::text = (genotypes.genotype_id)::text)) AS date_first_capture
--    FROM genotypes
--   ORDER BY genotype_id
--   WITH NO DATA;






-- scats_list_mat

drop MATERIALIZED view  IF EXISTS scats_list_mat;


CREATE MATERIALIZED VIEW scats_list_mat AS
 SELECT scat_id,
    date,
    wa_code,
    sampling_season,
    sampling_type,
    sample_type,
    box_number,
    path_id,
    snowtrack_id,
    location,
    municipality,
    province,
    region,
    deposition,
    matrix,
    collected_scat,
    genetic_sample,
    coord_east,
    coord_north,
    coord_zone,
    observer,
    institution,
    notes,
    geometry_utm,
    region_auto,
    province_auto,
    municipality_auto,
    location_auto,
    ( SELECT wa_scat_dw_mat.genotype_id
           FROM public.wa_scat_dw_mat
          WHERE ((wa_scat_dw_mat.wa_code)::text = (scats.wa_code)::text)
         LIMIT 1) AS genotype_id2,
        CASE
            WHEN (( SELECT lower((wa_scat_dw_mat.mtdna)::text) AS lower
               FROM public.wa_scat_dw_mat
              WHERE ((wa_scat_dw_mat.wa_code)::text = (scats.wa_code)::text)
             LIMIT 1) ~~ '%wolf%'::text) THEN 'C1'::character varying
            ELSE scalp_category
        END AS scalp_category
   FROM public.scats
  ORDER BY scat_id
  WITH NO DATA;


CREATE INDEX idx_scats_list_mat_date ON scats_list_mat(date);




-- wa_genetic_samples_mat

drop MATERIALIZED view IF EXISTS wa_genetic_samples_mat;


CREATE MATERIALIZED VIEW wa_genetic_samples_mat AS
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
    CASE WHEN d.tissue_id IS NOT NULL THEN 'Yes' ELSE NULL END AS dead_recovery
FROM
    wa_scat_dw_mat w
LEFT JOIN
    genotypes g ON g.genotype_id = w.genotype_id
LEFT JOIN
    dead_wolves d ON d.tissue_id = w.sample_id
WHERE
    w.mtdna <> 'Poor DNA'
ORDER BY
    w.wa_code
WITH NO DATA;

CREATE INDEX idx_wa_genetic_samples_mat_date ON wa_genetic_samples_mat(date);
CREATE INDEX idx_wa_genetic_samples_mat_wa_code ON wa_genetic_samples_mat(wa_code);

-- CREATE MATERIALIZED VIEW wa_genetic_samples_mat AS
--  SELECT wa_code,
--     sample_id,
--     date,
--     municipality,
--     province,
--     coord_east,
--     coord_north,
--     coord_zone,
--     geometry_utm,
--     genotype_id,
--     tmp_id,
--     mtdna,
--     sex_id,
--     sample_type,
--     box_number,
--     ( SELECT genotypes.working_notes
--            FROM public.genotypes
--           WHERE ((genotypes.genotype_id)::text = (wa_scat_dw_mat.genotype_id)::text)) AS notes,
--     ( SELECT genotypes.status
--            FROM public.genotypes
--           WHERE ((genotypes.genotype_id)::text = (wa_scat_dw_mat.genotype_id)::text)) AS status,
--     ( SELECT genotypes.hybrid
--            FROM public.genotypes
--           WHERE ((genotypes.genotype_id)::text = (wa_scat_dw_mat.genotype_id)::text)) AS hybrid,
--     ( SELECT genotypes.pack
--            FROM public.genotypes
--           WHERE ((genotypes.genotype_id)::text = (wa_scat_dw_mat.genotype_id)::text)) AS pack,
--     ( SELECT 'Yes'::text AS text
--            FROM public.dead_wolves
--           WHERE (dead_wolves.tissue_id = (wa_scat_dw_mat.sample_id)::text)
--          LIMIT 1) AS dead_recovery
--    FROM wa_scat_dw_mat
--   WHERE ((mtdna)::text <> 'Poor DNA'::text)
--   ORDER BY wa_code
--   WITH NO DATA;








call refresh_materialized_views() ;


-- update box_number in scats table
-- update scats s SET box_number = (select box_number FROM wa_results WHERE wa_code=s.wa_code) WHERE box_number IS NULL;

-- update box_number in dead_wolves table
-- update dead_wolves d SET box_number = (select box_number FROM wa_results WHERE wa_code=d.wa_code) WHERE box_number IS NULL;