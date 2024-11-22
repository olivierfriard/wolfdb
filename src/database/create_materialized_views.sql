 Schema |          Name          |       Type        |  Owner   
--------+------------------------+-------------------+----------
 public | genotypes_list_mat     | materialized view | postgres
 public | scats_list_mat         | materialized view | postgres
 public | wa_genetic_samples_mat | materialized view | postgres
 public | wa_scat_dw_mat         | materialized view | postgres



drop materialized view wa_genetic_samples_mat;
create materialized view wa_genetic_samples_mat AS 
 SELECT wa_scat_dw_mat.wa_code,
    wa_scat_dw_mat.sample_id,
    wa_scat_dw_mat.date,
    wa_scat_dw_mat.municipality,
    wa_scat_dw_mat.province,
    wa_scat_dw_mat.coord_east,
    wa_scat_dw_mat.coord_north,
    wa_scat_dw_mat.genotype_id,
    wa_scat_dw_mat.tmp_id,
    wa_scat_dw_mat.mtdna,
    wa_scat_dw_mat.sex_id,
    wa_scat_dw_mat.sample_type,
    wa_scat_dw_mat.box_number,
    ( SELECT genotypes.working_notes
           FROM genotypes
          WHERE genotypes.genotype_id::text = wa_scat_dw_mat.genotype_id::text) AS notes,
    ( SELECT genotypes.status
           FROM genotypes
          WHERE genotypes.genotype_id::text = wa_scat_dw_mat.genotype_id::text) AS status,
    ( SELECT genotypes.pack
           FROM genotypes
          WHERE genotypes.genotype_id::text = wa_scat_dw_mat.genotype_id::text) AS pack,
    ( SELECT 'Yes'::text AS text
           FROM dead_wolves
          WHERE dead_wolves.tissue_id = wa_scat_dw_mat.sample_id::text
         LIMIT 1) AS dead_recovery
   FROM wa_scat_dw_mat
  WHERE wa_scat_dw_mat.mtdna::text <> 'Poor DNA'::text
  ORDER BY wa_scat_dw_mat.wa_code;


