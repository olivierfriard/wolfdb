--
-- PostgreSQL database dump
--

\restrict hfh8FTvluJ8VxBC8xo2p9b8cgnvN1XoHGYuvlyYmKGRUb8t1hy66Pcw82zSsYf9

-- Dumped from database version 18.3 (Debian 18.3-1.pgdg13+1)
-- Dumped by pg_dump version 18.3 (Debian 18.3-1.pgdg13+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: public; Type: SCHEMA; Schema: -; Owner: postgres
--

-- *not* creating schema, since initdb creates it


ALTER SCHEMA public OWNER TO postgres;

--
-- Name: postgis; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS postgis WITH SCHEMA public;


--
-- Name: EXTENSION postgis; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION postgis IS 'PostGIS geometry and geography spatial types and functions';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: comuni; Type: TABLE; Schema: public; Owner: wolf_user
--

CREATE TABLE public.comuni (
    ogc_fid integer NOT NULL,
    wkb_geometry public.geometry(MultiPolygon,32632),
    cod_rip numeric(10,0),
    cod_reg numeric(10,0),
    cod_prov numeric(10,0),
    cod_cm numeric(10,0),
    cod_uts numeric(10,0),
    pro_com numeric(10,0),
    pro_com_t character varying(6),
    comune character varying(100),
    comune_a character varying(100),
    cc_uts numeric(10,0),
    shape_leng numeric(31,11),
    shape_area numeric(31,11)
);


ALTER TABLE public.comuni OWNER TO wolf_user;

--
-- Name: comuni_ogc_fid_seq; Type: SEQUENCE; Schema: public; Owner: wolf_user
--

CREATE SEQUENCE public.comuni_ogc_fid_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.comuni_ogc_fid_seq OWNER TO wolf_user;

--
-- Name: comuni_ogc_fid_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: wolf_user
--

ALTER SEQUENCE public.comuni_ogc_fid_seq OWNED BY public.comuni.ogc_fid;


--
-- Name: dead_wolves; Type: TABLE; Schema: public; Owner: wolf_user
--

CREATE TABLE public.dead_wolves (
    id integer NOT NULL,
    genotype_id text,
    tissue_id text,
    discovery_date date,
    location text,
    municipality text,
    province text,
    region text,
    wa_code character varying(50),
    deleted timestamp without time zone,
    utm_east integer,
    utm_north integer,
    geometry_utm public.geometry,
    utm_zone character varying(3),
    box_number character varying(50),
    scalp_category character varying(2),
    notes text,
    sampling_season character varying(9),
    operator character varying(255),
    institution character varying(255)
);


ALTER TABLE public.dead_wolves OWNER TO wolf_user;

--
-- Name: dead_wolves_fields_definition; Type: TABLE; Schema: public; Owner: wolf_user
--

CREATE TABLE public.dead_wolves_fields_definition (
    field_id integer NOT NULL,
    name character varying(100),
    type character varying(50),
    allowed_values text,
    default_value text,
    "position" integer,
    visible character varying(50),
    description text
);


ALTER TABLE public.dead_wolves_fields_definition OWNER TO wolf_user;

--
-- Name: dead_wolves_fields_definition_field_id_seq; Type: SEQUENCE; Schema: public; Owner: wolf_user
--

CREATE SEQUENCE public.dead_wolves_fields_definition_field_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.dead_wolves_fields_definition_field_id_seq OWNER TO wolf_user;

--
-- Name: dead_wolves_fields_definition_field_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: wolf_user
--

ALTER SEQUENCE public.dead_wolves_fields_definition_field_id_seq OWNED BY public.dead_wolves_fields_definition.field_id;


--
-- Name: dead_wolves_id_seq; Type: SEQUENCE; Schema: public; Owner: wolf_user
--

ALTER TABLE public.dead_wolves ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.dead_wolves_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: dead_wolves_values; Type: TABLE; Schema: public; Owner: wolf_user
--

CREATE TABLE public.dead_wolves_values (
    id integer,
    field_id integer,
    val text
);


ALTER TABLE public.dead_wolves_values OWNER TO wolf_user;

--
-- Name: genotype_locus; Type: TABLE; Schema: public; Owner: wolf_user
--

CREATE TABLE public.genotype_locus (
    id integer NOT NULL,
    genotype_id character varying(100),
    locus character varying(20),
    allele character varying(1),
    val integer,
    "timestamp" timestamp without time zone,
    notes text,
    user_id character varying(100),
    validated boolean
);


ALTER TABLE public.genotype_locus OWNER TO wolf_user;

--
-- Name: genotype_locus_id_seq; Type: SEQUENCE; Schema: public; Owner: wolf_user
--

CREATE SEQUENCE public.genotype_locus_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.genotype_locus_id_seq OWNER TO wolf_user;

--
-- Name: genotype_locus_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: wolf_user
--

ALTER SEQUENCE public.genotype_locus_id_seq OWNED BY public.genotype_locus.id;


--
-- Name: genotypes; Type: TABLE; Schema: public; Owner: wolf_user
--

CREATE TABLE public.genotypes (
    genotype_id character varying(100) NOT NULL,
    date date,
    pack character varying(255),
    sex character varying(2),
    age_first_capture character varying(50),
    status_first_capture character varying(50),
    dispersal character varying(255),
    n_recaptures character varying(255),
    dead_recovery character varying(255),
    record_status character varying(255) NOT NULL,
    tmp_id character varying(50),
    notes text,
    status character varying(100),
    working_notes text,
    changed_status character varying(255),
    hybrid character varying(255),
    mtdna character varying(255),
    mother character varying(100),
    father character varying(100),
    CONSTRAINT record_status_constraint CHECK (((record_status)::text = ANY (ARRAY[('OK'::character varying)::text, ('deleted'::character varying)::text, ('temp'::character varying)::text])))
);


ALTER TABLE public.genotypes OWNER TO wolf_user;

--
-- Name: scats; Type: TABLE; Schema: public; Owner: wolf_user
--

CREATE TABLE public.scats (
    scat_id character varying(100) NOT NULL,
    date date,
    wa_code character varying(100),
    sampling_season character varying(9),
    sampling_type character varying(20),
    path_id character varying(50),
    snowtrack_id character varying(100),
    location character varying(100),
    municipality character varying(50),
    province character varying(50),
    region character varying(50),
    deposition character varying(100),
    matrix character varying(3),
    collected_scat character varying(3),
    scalp_category character varying(2),
    genetic_sample character varying(3),
    coord_east integer,
    coord_north integer,
    coord_zone character varying(3),
    observer character varying(255),
    institution character varying(255),
    notes text,
    geometry_utm public.geometry,
    region_auto character varying(50),
    province_auto character varying(50),
    municipality_auto character varying(50),
    location_auto character varying(100),
    sample_type character varying(50),
    box_number character varying(50),
    ispra_id character varying(100),
    CONSTRAINT sample_type_constraint CHECK (((sample_type)::text = ANY (ARRAY[('scat'::character varying)::text, ('blood'::character varying)::text, ('tissue'::character varying)::text, ('urine'::character varying)::text, ('saliva'::character varying)::text, ('hair'::character varying)::text, ('unknown'::character varying)::text]))),
    CONSTRAINT sampling_type_constraint CHECK (((sampling_type)::text = ANY (ARRAY[('Opportunistic'::character varying)::text, ('Systematic'::character varying)::text, ('Unknown'::character varying)::text])))
);


ALTER TABLE public.scats OWNER TO wolf_user;

--
-- Name: wa_results; Type: TABLE; Schema: public; Owner: wolf_user
--

CREATE TABLE public.wa_results (
    wa_code character varying(100) NOT NULL,
    package_sent character varying(255),
    pack character varying(255),
    notes text,
    extraction_lab_apam_id character varying(255),
    genotype_id character varying(100),
    mtdna character varying(255),
    sex_id character varying(100),
    recapture_old_individual character varying(255),
    individual_id character varying(255),
    matching character varying(255),
    quality_genotype character varying(50),
    box_number character varying(50),
    CONSTRAINT quality_genotype CHECK (((quality_genotype)::text = ANY (ARRAY[('Yes'::character varying)::text, ('No'::character varying)::text, ('Poor DNA'::character varying)::text])))
);


ALTER TABLE public.wa_results OWNER TO wolf_user;

--
-- Name: wa_dw; Type: VIEW; Schema: public; Owner: wolf_user
--

CREATE VIEW public.wa_dw AS
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
   FROM public.dead_wolves,
    public.wa_results
  WHERE ((wa_results.wa_code)::text = (dead_wolves.wa_code)::text);


ALTER VIEW public.wa_dw OWNER TO wolf_user;

--
-- Name: wa_scat; Type: VIEW; Schema: public; Owner: wolf_user
--

CREATE VIEW public.wa_scat AS
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
   FROM public.scats,
    public.wa_results
  WHERE ((scats.wa_code)::text = (wa_results.wa_code)::text);


ALTER VIEW public.wa_scat OWNER TO wolf_user;

--
-- Name: wa_scat_dw_all; Type: VIEW; Schema: public; Owner: wolf_user
--

CREATE VIEW public.wa_scat_dw_all AS
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
   FROM public.wa_scat
UNION ALL
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
   FROM public.wa_dw;


ALTER VIEW public.wa_scat_dw_all OWNER TO wolf_user;

--
-- Name: genotypes_list_all; Type: VIEW; Schema: public; Owner: wolf_user
--

CREATE VIEW public.genotypes_list_all AS
 SELECT g.genotype_id,
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
    COALESCE(w.n_recaptures, (0)::bigint) AS n_recaptures,
        CASE
            WHEN w.dead_recovery THEN 'Yes'::text
            ELSE NULL::text
        END AS dead_recovery,
    w.date_first_capture
   FROM (public.genotypes g
     LEFT JOIN ( SELECT wa_scat_dw_all.genotype_id,
            count(*) AS n_recaptures,
            bool_or((((wa_scat_dw_all.sample_id)::text ~~ 'T%'::text) OR ((wa_scat_dw_all.sample_id)::text ~~ 'M%'::text))) AS dead_recovery,
            min(wa_scat_dw_all.date) AS date_first_capture
           FROM public.wa_scat_dw_all
          GROUP BY wa_scat_dw_all.genotype_id) w ON (((w.genotype_id)::text = (g.genotype_id)::text)))
  ORDER BY g.genotype_id;


ALTER VIEW public.genotypes_list_all OWNER TO wolf_user;

--
-- Name: geo_info; Type: TABLE; Schema: public; Owner: wolf_user
--

CREATE TABLE public.geo_info (
    province_code character varying(10) NOT NULL,
    province_name character varying(30),
    region character varying(30),
    country character varying(30),
    province_code_num integer,
    region_code_num integer
);


ALTER TABLE public.geo_info OWNER TO wolf_user;

--
-- Name: istat_province; Type: TABLE; Schema: public; Owner: wolf_user
--

CREATE TABLE public.istat_province (
    cod_prov integer NOT NULL,
    nome_provincia character varying(150) NOT NULL,
    sigla character varying(5),
    cod_reg integer NOT NULL
);


ALTER TABLE public.istat_province OWNER TO wolf_user;

--
-- Name: istat_regioni; Type: TABLE; Schema: public; Owner: wolf_user
--

CREATE TABLE public.istat_regioni (
    cod_reg integer NOT NULL,
    nome_regione character varying(100) NOT NULL
);


ALTER TABLE public.istat_regioni OWNER TO wolf_user;

--
-- Name: loci; Type: TABLE; Schema: public; Owner: wolf_user
--

CREATE TABLE public.loci (
    name character varying(20) NOT NULL,
    n_alleles integer,
    "position" integer,
    use_with_colony boolean
);


ALTER TABLE public.loci OWNER TO wolf_user;

--
-- Name: paths; Type: TABLE; Schema: public; Owner: wolf_user
--

CREATE TABLE public.paths (
    path_id character varying(50) NOT NULL,
    transect_id character varying(20),
    date date,
    sampling_season character varying(9),
    completeness integer,
    observer character varying(255),
    institution character varying(255),
    notes text,
    created timestamp without time zone,
    category character varying(100),
    experience_index integer
);


ALTER TABLE public.paths OWNER TO wolf_user;

--
-- Name: paths_path_id_seq; Type: SEQUENCE; Schema: public; Owner: wolf_user
--

CREATE SEQUENCE public.paths_path_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.paths_path_id_seq OWNER TO wolf_user;

--
-- Name: scats_list_all; Type: VIEW; Schema: public; Owner: wolf_user
--

CREATE VIEW public.scats_list_all AS
 SELECT s.scat_id,
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
    w.genotype_id AS genotype_id2,
        CASE
            WHEN (lower((w.mtdna)::text) ~~ '%wolf%'::text) THEN 'C1'::character varying
            ELSE s.scalp_category
        END AS scalp_category
   FROM (public.scats s
     LEFT JOIN LATERAL ( SELECT wsdm.genotype_id,
            wsdm.mtdna
           FROM public.wa_scat_dw_all wsdm
          WHERE ((wsdm.wa_code)::text = (s.wa_code)::text)
          ORDER BY wsdm.date DESC NULLS LAST
         LIMIT 1) w ON (true))
  ORDER BY s.scat_id;


ALTER VIEW public.scats_list_all OWNER TO wolf_user;

--
-- Name: snow_tracks; Type: TABLE; Schema: public; Owner: wolf_user
--

CREATE TABLE public.snow_tracks (
    snowtrack_id character varying(50) NOT NULL,
    transect_id character varying(50),
    date date,
    sampling_season character varying(9),
    track_type character varying(10),
    location character varying(255),
    municipality character varying(50),
    province character varying(50),
    region character varying(50),
    observer character varying(255),
    institution character varying(255),
    scalp_category character varying(2),
    sampling_type character varying(20),
    days_after_snowfall character varying(100),
    minimum_number_of_wolves character varying(100),
    track_format character varying(255),
    notes text,
    multilines public.geometry(MultiLineString),
    coord_east integer,
    coord_north integer,
    coord_zone character varying(3)
);


ALTER TABLE public.snow_tracks OWNER TO wolf_user;

--
-- Name: test; Type: TABLE; Schema: public; Owner: wolf_user
--

CREATE TABLE public.test (
    t timestamp without time zone
);


ALTER TABLE public.test OWNER TO wolf_user;

--
-- Name: transects; Type: TABLE; Schema: public; Owner: wolf_user
--

CREATE TABLE public.transects (
    transect_id character varying(50) NOT NULL,
    sector character varying(10),
    location character varying(255),
    municipality character varying(255),
    province character varying(50),
    region character varying(50),
    multilines public.geometry(MultiLineString),
    province_code character varying(10)
);


ALTER TABLE public.transects OWNER TO wolf_user;

--
-- Name: users; Type: TABLE; Schema: public; Owner: wolf_user
--

CREATE TABLE public.users (
    id integer NOT NULL,
    email character varying(50) NOT NULL,
    firstname character varying(100),
    lastname character varying(100),
    institution character varying(100),
    deleted timestamp without time zone,
    allele_modifier boolean,
    role character varying(20)
);


ALTER TABLE public.users OWNER TO wolf_user;

--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: wolf_user
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.users_id_seq OWNER TO wolf_user;

--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: wolf_user
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: wa_genetic_samples_all; Type: VIEW; Schema: public; Owner: wolf_user
--

CREATE VIEW public.wa_genetic_samples_all AS
 SELECT w.wa_code,
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
            WHEN (EXISTS ( SELECT 1
               FROM public.dead_wolves dw
              WHERE (dw.tissue_id = (w.sample_id)::text))) THEN 'Yes'::text
            ELSE NULL::text
        END AS dead_recovery
   FROM (public.wa_scat_dw_all w
     LEFT JOIN public.genotypes g ON (((g.genotype_id)::text = (w.genotype_id)::text)))
  ORDER BY w.wa_code;


ALTER VIEW public.wa_genetic_samples_all OWNER TO wolf_user;

--
-- Name: wa_loci_values; Type: TABLE; Schema: public; Owner: wolf_user
--

CREATE TABLE public.wa_loci_values (
    wa_code character varying(100) NOT NULL,
    loci_values jsonb NOT NULL
);


ALTER TABLE public.wa_loci_values OWNER TO wolf_user;

--
-- Name: wa_locus; Type: TABLE; Schema: public; Owner: wolf_user
--

CREATE TABLE public.wa_locus (
    id integer NOT NULL,
    wa_code character varying(20),
    locus character varying(20),
    allele character varying(1),
    val integer,
    "timestamp" timestamp without time zone,
    notes text,
    user_id character varying(100),
    definitive boolean
);


ALTER TABLE public.wa_locus OWNER TO wolf_user;

--
-- Name: wa_locus2_id_seq; Type: SEQUENCE; Schema: public; Owner: wolf_user
--

CREATE SEQUENCE public.wa_locus2_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.wa_locus2_id_seq OWNER TO wolf_user;

--
-- Name: wa_locus2_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: wolf_user
--

ALTER SEQUENCE public.wa_locus2_id_seq OWNED BY public.wa_locus.id;


--
-- Name: comuni ogc_fid; Type: DEFAULT; Schema: public; Owner: wolf_user
--

ALTER TABLE ONLY public.comuni ALTER COLUMN ogc_fid SET DEFAULT nextval('public.comuni_ogc_fid_seq'::regclass);


--
-- Name: dead_wolves_fields_definition field_id; Type: DEFAULT; Schema: public; Owner: wolf_user
--

ALTER TABLE ONLY public.dead_wolves_fields_definition ALTER COLUMN field_id SET DEFAULT nextval('public.dead_wolves_fields_definition_field_id_seq'::regclass);


--
-- Name: genotype_locus id; Type: DEFAULT; Schema: public; Owner: wolf_user
--

ALTER TABLE ONLY public.genotype_locus ALTER COLUMN id SET DEFAULT nextval('public.genotype_locus_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: wolf_user
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Name: wa_locus id; Type: DEFAULT; Schema: public; Owner: wolf_user
--

ALTER TABLE ONLY public.wa_locus ALTER COLUMN id SET DEFAULT nextval('public.wa_locus2_id_seq'::regclass);


--
-- Name: comuni comuni_pk; Type: CONSTRAINT; Schema: public; Owner: wolf_user
--

ALTER TABLE ONLY public.comuni
    ADD CONSTRAINT comuni_pk PRIMARY KEY (ogc_fid);


--
-- Name: dead_wolves_fields_definition dead_wolves_fields_definition_pkey; Type: CONSTRAINT; Schema: public; Owner: wolf_user
--

ALTER TABLE ONLY public.dead_wolves_fields_definition
    ADD CONSTRAINT dead_wolves_fields_definition_pkey PRIMARY KEY (field_id);


--
-- Name: genotype_locus genotype_locus_pkey; Type: CONSTRAINT; Schema: public; Owner: wolf_user
--

ALTER TABLE ONLY public.genotype_locus
    ADD CONSTRAINT genotype_locus_pkey PRIMARY KEY (id);


--
-- Name: genotypes genotypes_pkey; Type: CONSTRAINT; Schema: public; Owner: wolf_user
--

ALTER TABLE ONLY public.genotypes
    ADD CONSTRAINT genotypes_pkey PRIMARY KEY (genotype_id);


--
-- Name: geo_info geo_info_pkey; Type: CONSTRAINT; Schema: public; Owner: wolf_user
--

ALTER TABLE ONLY public.geo_info
    ADD CONSTRAINT geo_info_pkey PRIMARY KEY (province_code);


--
-- Name: istat_province istat_province_pkey; Type: CONSTRAINT; Schema: public; Owner: wolf_user
--

ALTER TABLE ONLY public.istat_province
    ADD CONSTRAINT istat_province_pkey PRIMARY KEY (cod_prov);


--
-- Name: istat_regioni istat_regioni_pkey; Type: CONSTRAINT; Schema: public; Owner: wolf_user
--

ALTER TABLE ONLY public.istat_regioni
    ADD CONSTRAINT istat_regioni_pkey PRIMARY KEY (cod_reg);


--
-- Name: loci loci_pkey; Type: CONSTRAINT; Schema: public; Owner: wolf_user
--

ALTER TABLE ONLY public.loci
    ADD CONSTRAINT loci_pkey PRIMARY KEY (name);


--
-- Name: paths paths_pkey; Type: CONSTRAINT; Schema: public; Owner: wolf_user
--

ALTER TABLE ONLY public.paths
    ADD CONSTRAINT paths_pkey PRIMARY KEY (path_id);


--
-- Name: scats scats_pkey; Type: CONSTRAINT; Schema: public; Owner: wolf_user
--

ALTER TABLE ONLY public.scats
    ADD CONSTRAINT scats_pkey PRIMARY KEY (scat_id);


--
-- Name: snow_tracks snow_tracks_pkey; Type: CONSTRAINT; Schema: public; Owner: wolf_user
--

ALTER TABLE ONLY public.snow_tracks
    ADD CONSTRAINT snow_tracks_pkey PRIMARY KEY (snowtrack_id);


--
-- Name: dead_wolves tissue_id_constraint; Type: CONSTRAINT; Schema: public; Owner: wolf_user
--

ALTER TABLE ONLY public.dead_wolves
    ADD CONSTRAINT tissue_id_constraint UNIQUE (tissue_id);


--
-- Name: transects transects_pkey; Type: CONSTRAINT; Schema: public; Owner: wolf_user
--

ALTER TABLE ONLY public.transects
    ADD CONSTRAINT transects_pkey PRIMARY KEY (transect_id);


--
-- Name: dead_wolves unique_id_constraint; Type: CONSTRAINT; Schema: public; Owner: wolf_user
--

ALTER TABLE ONLY public.dead_wolves
    ADD CONSTRAINT unique_id_constraint UNIQUE (id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: wolf_user
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (email);


--
-- Name: wa_loci_values wa_loci_values_pkey; Type: CONSTRAINT; Schema: public; Owner: wolf_user
--

ALTER TABLE ONLY public.wa_loci_values
    ADD CONSTRAINT wa_loci_values_pkey PRIMARY KEY (wa_code);


--
-- Name: wa_locus wa_locus2_pkey; Type: CONSTRAINT; Schema: public; Owner: wolf_user
--

ALTER TABLE ONLY public.wa_locus
    ADD CONSTRAINT wa_locus2_pkey PRIMARY KEY (id);


--
-- Name: wa_results wa_results_pkey; Type: CONSTRAINT; Schema: public; Owner: wolf_user
--

ALTER TABLE ONLY public.wa_results
    ADD CONSTRAINT wa_results_pkey PRIMARY KEY (wa_code);


--
-- Name: comuni_wkb_geometry_geom_idx; Type: INDEX; Schema: public; Owner: wolf_user
--

CREATE INDEX comuni_wkb_geometry_geom_idx ON public.comuni USING gist (wkb_geometry);


--
-- Name: dead_wolves_fields_definition_name_idx; Type: INDEX; Schema: public; Owner: wolf_user
--

CREATE INDEX dead_wolves_fields_definition_name_idx ON public.dead_wolves_fields_definition USING btree (name);


--
-- Name: dead_wolves_geom_idx; Type: INDEX; Schema: public; Owner: wolf_user
--

CREATE INDEX dead_wolves_geom_idx ON public.dead_wolves USING gist (geometry_utm);


--
-- Name: dead_wolves_values_field_id_idx; Type: INDEX; Schema: public; Owner: wolf_user
--

CREATE INDEX dead_wolves_values_field_id_idx ON public.dead_wolves_values USING btree (field_id);


--
-- Name: dead_wolves_values_id_idx; Type: INDEX; Schema: public; Owner: wolf_user
--

CREATE INDEX dead_wolves_values_id_idx ON public.dead_wolves_values USING btree (id);


--
-- Name: genotype_locus_allele_idx; Type: INDEX; Schema: public; Owner: wolf_user
--

CREATE INDEX genotype_locus_allele_idx ON public.genotype_locus USING btree (allele);


--
-- Name: genotype_locus_genotype_id_idx; Type: INDEX; Schema: public; Owner: wolf_user
--

CREATE INDEX genotype_locus_genotype_id_idx ON public.genotype_locus USING btree (genotype_id);


--
-- Name: genotype_locus_locus_idx; Type: INDEX; Schema: public; Owner: wolf_user
--

CREATE INDEX genotype_locus_locus_idx ON public.genotype_locus USING btree (locus);


--
-- Name: geo_info_codes_idx; Type: INDEX; Schema: public; Owner: wolf_user
--

CREATE INDEX geo_info_codes_idx ON public.geo_info USING btree (province_code_num, region_code_num);


--
-- Name: geo_info_province_name_idx; Type: INDEX; Schema: public; Owner: wolf_user
--

CREATE INDEX geo_info_province_name_idx ON public.geo_info USING btree (province_name);


--
-- Name: geo_info_region_idx; Type: INDEX; Schema: public; Owner: wolf_user
--

CREATE INDEX geo_info_region_idx ON public.geo_info USING btree (region);


--
-- Name: id_fieldid; Type: INDEX; Schema: public; Owner: wolf_user
--

CREATE UNIQUE INDEX id_fieldid ON public.dead_wolves_values USING btree (id, field_id);


--
-- Name: notes_idx; Type: INDEX; Schema: public; Owner: wolf_user
--

CREATE INDEX notes_idx ON public.wa_locus USING btree (notes);


--
-- Name: paths_date_idx; Type: INDEX; Schema: public; Owner: wolf_user
--

CREATE INDEX paths_date_idx ON public.paths USING btree (date);


--
-- Name: paths_transect_id_idx; Type: INDEX; Schema: public; Owner: wolf_user
--

CREATE INDEX paths_transect_id_idx ON public.paths USING btree (transect_id);


--
-- Name: scats_path_id_idx; Type: INDEX; Schema: public; Owner: wolf_user
--

CREATE INDEX scats_path_id_idx ON public.scats USING btree (path_id);


--
-- Name: scats_wa_code_idx; Type: INDEX; Schema: public; Owner: wolf_user
--

CREATE INDEX scats_wa_code_idx ON public.scats USING btree (wa_code);


--
-- Name: scats_wa_code_idx1; Type: INDEX; Schema: public; Owner: wolf_user
--

CREATE INDEX scats_wa_code_idx1 ON public.scats USING btree (wa_code);


--
-- Name: snow_tracks_date_idx; Type: INDEX; Schema: public; Owner: wolf_user
--

CREATE INDEX snow_tracks_date_idx ON public.snow_tracks USING btree (date);


--
-- Name: snow_tracks_transect_id_idx; Type: INDEX; Schema: public; Owner: wolf_user
--

CREATE INDEX snow_tracks_transect_id_idx ON public.snow_tracks USING btree (transect_id);


--
-- Name: wa_locus2_allele_idx; Type: INDEX; Schema: public; Owner: wolf_user
--

CREATE INDEX wa_locus2_allele_idx ON public.wa_locus USING btree (allele);


--
-- Name: wa_locus2_locus_idx; Type: INDEX; Schema: public; Owner: wolf_user
--

CREATE INDEX wa_locus2_locus_idx ON public.wa_locus USING btree (locus);


--
-- Name: wa_locus2_wa_code_idx; Type: INDEX; Schema: public; Owner: wolf_user
--

CREATE INDEX wa_locus2_wa_code_idx ON public.wa_locus USING btree (wa_code);


--
-- Name: wa_results_genotype_id_idx; Type: INDEX; Schema: public; Owner: wolf_user
--

CREATE INDEX wa_results_genotype_id_idx ON public.wa_results USING btree (genotype_id);


--
-- Name: wa_results_mtdna_idx; Type: INDEX; Schema: public; Owner: wolf_user
--

CREATE INDEX wa_results_mtdna_idx ON public.wa_results USING btree (mtdna);


--
-- Name: SCHEMA public; Type: ACL; Schema: -; Owner: postgres
--

REVOKE USAGE ON SCHEMA public FROM PUBLIC;
GRANT ALL ON SCHEMA public TO PUBLIC;


--
-- PostgreSQL database dump complete
--

\unrestrict hfh8FTvluJ8VxBC8xo2p9b8cgnvN1XoHGYuvlyYmKGRUb8t1hy66Pcw82zSsYf9

