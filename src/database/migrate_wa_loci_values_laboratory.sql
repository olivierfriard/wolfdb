-- Run before deploying the laboratory-aware cache writers.
-- Existing cache data is retained; both identifiers become mandatory.
BEGIN;
SET LOCAL lock_timeout = '5s';

ALTER TABLE public.wa_loci_values
    ALTER COLUMN laboratory_acronym SET NOT NULL;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'public.wa_loci_values'::regclass
          AND conname = 'wa_loci_values_pkey'
          AND pg_get_constraintdef(oid) = 'PRIMARY KEY (wa_code)'
    ) THEN
        ALTER TABLE public.wa_loci_values DROP CONSTRAINT wa_loci_values_pkey;
        ALTER TABLE public.wa_loci_values
            ADD CONSTRAINT wa_loci_values_pkey
            PRIMARY KEY (wa_code, laboratory_acronym);
    END IF;
END $$;

COMMIT;
