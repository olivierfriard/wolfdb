





# alter table scats alter column geometry_utm TYPE geometry USING geometry_utm::geometry;
# alter table transects alter column multilines TYPE geometry(MultiLineString) USING multilines::geometry;
# alter table transects drop column points_utm;
# alter table snow_tracks drop column geometry_utm;
# alter table snow_tracks alter column multilines TYPE geometry(MultiLineString) USING multilines::geometry;

-- 1

DROP VIEW IF EXISTS wa_scat CASCADE;

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


-- 2


DROP VIEW IF EXISTS wa_dw CASCADE;

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



-- 3

DROP MATERIALIZED VIEW IF EXISTS wa_scat_dw_mat CASCADE;

CREATE MATERIALIZED VIEW wa_scat_dw_mat AS
 SELECT wa_code,
    sample_id,
    date,
    coord_east,
    coord_north,
    coord_zone,
    geometry_utm,
    location,
    municipality,
    province,
    region,
    quality_genotype,
    genotype_id,
    tmp_id,
    mtdna,
    sex_id,
    sample_type,
    box_number

   FROM wa_scat

UNION
 SELECT wa_code,
    sample_id,
    date,
    coord_east,
    coord_north,
    coord_zone,
    geometry_utm,
    location,
    municipality,
    province,
    region,
    quality_genotype,
    genotype_id,
    tmp_id,
    mtdna,
    sex_id,
    sample_type,
    box_number

   FROM wa_dw;


CREATE INDEX idx_wa_scat_dw_mat_date ON wa_scat_dw_mat USING btree (date);
CREATE INDEX idx_wa_scat_dw_mat_genotypeid ON wa_scat_dw_mat USING btree (genotype_id);
CREATE INDEX idx_wa_scat_dw_mat_mtdna ON wa_scat_dw_mat USING btree (mtdna);
CREATE INDEX idx_wa_scat_dw_mat_wa_code ON wa_scat_dw_mat USING btree (wa_code);



-- 4

DROP MATERIALIZED VIEW IF EXISTS scats_list_mat;

CREATE MATERIALIZED VIEW scats_list_mat AS
WITH wa_summary AS (
    SELECT DISTINCT ON (wa_code)
        wa_code,
        genotype_id,
        lower(mtdna) AS mtdna_lower
    FROM wa_scat_dw_mat
    ORDER BY wa_code, date DESC -- ou autre critère pertinent pour choisir "le bon"
)
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
    ws.genotype_id AS genotype_id2,
    CASE
        WHEN ws.mtdna_lower LIKE '%wolf%' THEN 'C1'
        ELSE s.scalp_category
    END AS scalp_category
FROM 
    scats s
LEFT JOIN 
    wa_summary ws ON ws.wa_code = s.wa_code
ORDER BY 
    s.scat_id;

CREATE INDEX idx_scats_list_mat_date ON scats_list_mat USING btree (date);
CREATE INDEX idx_scats_list_mat_wa ON scats_list_mat USING btree (wa_code);

-- 5


DROP MATERIALIZED VIEW IF EXISTS wa_genetic_samples_mat;

CREATE MATERIALIZED VIEW wa_genetic_samples_mat AS
SELECT 
    ws.wa_code,
    ws.sample_id,
    ws.date,
    ws.municipality,
    ws.province,
    ws.coord_east,
    ws.coord_north,
    ws.coord_zone,
    ws.geometry_utm,
    ws.genotype_id,
    ws.tmp_id,
    ws.mtdna,
    ws.sex_id,
    ws.sample_type,
    ws.box_number,
    g.working_notes AS notes,
    g.status,
    g.pack,
    g.hybrid,
    CASE 
        WHEN dw.tissue_id IS NOT NULL THEN 'Yes'
        ELSE NULL
    END AS dead_recovery
FROM 
    wa_scat_dw_mat ws
LEFT JOIN 
    genotypes g ON g.genotype_id = ws.genotype_id
LEFT JOIN 
    dead_wolves dw ON dw.tissue_id = ws.sample_id
WHERE 
    ws.mtdna <> 'Poor DNA'
ORDER BY 
    ws.wa_code;

CREATE INDEX idx_wa_genetic_samples_mat_date ON wa_genetic_samples_mat USING btree (date);


-- 6

DROP MATERIALIZED VIEW IF EXISTS genotypes_list_mat;


CREATE MATERIALIZED VIEW genotypes_list_mat AS
WITH recap AS (
    SELECT
        genotype_id,
        COUNT(sample_id) AS n_recaptures,
        MIN(date) AS date_first_capture,
        MAX(
            CASE 
                WHEN sample_id LIKE 'T%' OR sample_id LIKE 'M%' THEN 'Yes'
                ELSE NULL
            END
        ) AS dead_recovery
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
    r.n_recaptures,
    r.dead_recovery,
    r.date_first_capture
FROM 
    genotypes g
LEFT JOIN 
    recap r ON r.genotype_id = g.genotype_id
ORDER BY 
    g.genotype_id;


CREATE INDEX idx_genotypes_list_mat_genotype_id ON genotypes_list_mat USING btree (genotype_id);
CREATE INDEX idx_genotypes_list_mat_date ON genotypes_list_mat USING btree (date);



call refresh_materialized_views() ;
