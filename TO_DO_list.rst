TO DO list
===================================


* fix:

wolf=# SELECT wa_code, count(*) FROM wa_scat group by wa_code having count(*) > 1;
 wa_code  | count 
----------+-------
 WA3112   |     2
 FEM65319 |     2
(2 rows)

wolf=# SELECT wa_code, count(*) FROM wa_dw group by wa_code having count(*) > 1;
 wa_code | count 
---------+-------
 WA990   |     2
 WA2216  |     2
(2 rows)

wolf=# SELECT wa_code, count(*) FROM wa_scat_dw_mat group by wa_code having count(*) > 1;
 wa_code  | count 
----------+-------
 FEM65319 |     2
 WA2216   |     2
 WA3112   |     2
 WA6230   |     2
 WA6243   |     2
 WA990    |     2
(6 rows)




* add check for sampling type when scats are uploaded





* region in dead_wolves [DONE]

* insert snow_track coordinates [DONE]

* insert auto location in  transects [DONE]

* add modify genotype in WA [DONE]

* add notes in edit scat [DONE]

* modify WA coordinates in export [DONE]

* add delete genotypes [DONE]

* insert auto location in scats [DONE]