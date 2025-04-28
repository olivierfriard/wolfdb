




drop view wa_scat CASCADE;


alter table scats alter column geometry_utm TYPE geometry USING geometry_utm::geometry;



alter table transects alter column multilines TYPE geometry(MultiLineString) USING multilines::geometry;
alter table transects drop column points_utm;

alter table snow_tracks drop column geometry_utm;
alter table snow_tracks alter column multilines TYPE geometry(MultiLineString) USING multilines::geometry;










CREATE VIEW public.wa_dw AS
 SELECT wa_results.wa_code,
    dead_wolves.tissue_id AS sample_id,
    dead_wolves.discovery_date AS date,
    dead_wolves.utm_east AS coord_east,
    dead_wolves.utm_north AS coord_north,
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
   FROM public.dead_wolves,
    public.wa_results
  WHERE ((wa_results.wa_code)::text = (dead_wolves.wa_code)::text);


ALTER VIEW public.wa_dw OWNER TO postgres;

--
-- Name: wa_scat; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.wa_scat AS
 SELECT wa_results.wa_code,
    scats.scat_id AS sample_id,
    scats.date,
    scats.coord_east,
    scats.coord_north,
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
   FROM public.scats,
    public.wa_results
  WHERE ((scats.wa_code)::text = (wa_results.wa_code)::text);


ALTER VIEW public.wa_scat OWNER TO postgres;

--
-- Name: wa_scat_dw_mat; Type: MATERIALIZED VIEW; Schema: public; Owner: postgres
--

CREATE MATERIALIZED VIEW public.wa_scat_dw_mat AS
 SELECT wa_scat.wa_code,
    wa_scat.sample_id,
    wa_scat.date,
    wa_scat.coord_east,
    wa_scat.coord_north,
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
   FROM public.wa_scat
UNION
 SELECT wa_dw.wa_code,
    wa_dw.sample_id,
    wa_dw.date,
    wa_dw.coord_east,
    wa_dw.coord_north,
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
   FROM public.wa_dw
  WITH NO DATA;


ALTER MATERIALIZED VIEW public.wa_scat_dw_mat OWNER TO postgres;

--
-- Name: genotypes_list_mat; Type: MATERIALIZED VIEW; Schema: public; Owner: postgres
--

CREATE MATERIALIZED VIEW public.genotypes_list_mat AS
 SELECT genotype_id,
    date,
    pack,
    sex,
    age_first_capture,
    status_first_capture,
    dispersal,
    record_status,
    tmp_id,
    notes,
    status,
    working_notes,
    changed_status,
    mother,
    father,
    hybrid,
    mtdna,
    ( SELECT count(wa_scat_dw_mat.sample_id) AS count
           FROM public.wa_scat_dw_mat
          WHERE ((wa_scat_dw_mat.genotype_id)::text = (genotypes.genotype_id)::text)) AS n_recaptures,
    ( SELECT 'Yes'::text AS text
           FROM public.wa_scat_dw_mat
          WHERE ((((wa_scat_dw_mat.sample_id)::text ~~ 'T%'::text) OR ((wa_scat_dw_mat.sample_id)::text ~~ 'M%'::text)) AND ((wa_scat_dw_mat.genotype_id)::text = (genotypes.genotype_id)::text))
         LIMIT 1) AS dead_recovery,
    ( SELECT min(wa_scat_dw_mat.date) AS min
           FROM public.wa_scat_dw_mat
          WHERE ((wa_scat_dw_mat.genotype_id)::text = (genotypes.genotype_id)::text)) AS date_first_capture
   FROM public.genotypes
  ORDER BY genotype_id
  WITH NO DATA;


ALTER MATERIALIZED VIEW public.genotypes_list_mat OWNER TO postgres;

--
-- Name: geo_info; Type: TABLE; Schema: public; Owner: postgres
--


CREATE MATERIALIZED VIEW public.scats_list_mat AS
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


ALTER MATERIALIZED VIEW public.scats_list_mat OWNER TO postgres;


CREATE MATERIALIZED VIEW public.wa_genetic_samples_mat AS
 SELECT wa_code,
    sample_id,
    date,
    municipality,
    province,
    coord_east,
    coord_north,
    geometry_utm,
    genotype_id,
    tmp_id,
    mtdna,
    sex_id,
    sample_type,
    box_number,
    ( SELECT genotypes.working_notes
           FROM public.genotypes
          WHERE ((genotypes.genotype_id)::text = (wa_scat_dw_mat.genotype_id)::text)) AS notes,
    ( SELECT genotypes.status
           FROM public.genotypes
          WHERE ((genotypes.genotype_id)::text = (wa_scat_dw_mat.genotype_id)::text)) AS status,
    ( SELECT genotypes.pack
           FROM public.genotypes
          WHERE ((genotypes.genotype_id)::text = (wa_scat_dw_mat.genotype_id)::text)) AS pack,
    ( SELECT 'Yes'::text AS text
           FROM public.dead_wolves
          WHERE (dead_wolves.tissue_id = (wa_scat_dw_mat.sample_id)::text)
         LIMIT 1) AS dead_recovery
   FROM public.wa_scat_dw_mat
  WHERE ((mtdna)::text <> 'Poor DNA'::text)
  ORDER BY wa_code
  WITH NO DATA;


ALTER MATERIALIZED VIEW public.wa_genetic_samples_mat OWNER TO postgres;


CREATE INDEX idx_scats_list_mat_date ON public.wa_scat_dw_mat USING btree (date);


--
-- Name: idx_wa_scat_dw_mat_date; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_wa_scat_dw_mat_date ON public.wa_scat_dw_mat USING btree (date);


--
-- Name: idx_wa_scat_dw_mat_genotypeid; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_wa_scat_dw_mat_genotypeid ON public.wa_scat_dw_mat USING btree (genotype_id);


--
-- Name: idx_wa_scat_dw_mat_mtdna; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_wa_scat_dw_mat_mtdna ON public.wa_scat_dw_mat USING btree (mtdna);


--
-- Name: idx_wa_scat_dw_mat_wa_code; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_wa_scat_dw_mat_wa_code ON public.wa_scat_dw_mat USING btree (wa_code);



