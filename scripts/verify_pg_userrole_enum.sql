-- List exact PostgreSQL labels for type ``userrole`` (run on Azure Non-Prod).
-- Jump VM example:
--   kubectl exec -it deploy/quanthire-nonprod-api -n quanthire-nonprod -- \
--     psql "$DATABASE_URL" -f /tmp/verify_pg_userrole_enum.sql
--
-- Or paste into psql after copying the file into the API pod.

SELECT e.enumsortorder AS ord, e.enumlabel AS label
FROM pg_type t
JOIN pg_enum e ON e.enumtypid = t.oid
WHERE t.typname = 'userrole'
ORDER BY e.enumsortorder;

-- Expected on Azure Non-Prod (Aug 2026):
--   ADMIN
--   RECRUITER
--   HIRING_MANAGER
--   INTERVIEWER
--   CANDIDATE
--   viewer          ← lowercase (added via ALTER TYPE)

-- Quick cast test (should not error):
-- SELECT unnest(ARRAY['ADMIN','RECRUITER','HIRING_MANAGER','INTERVIEWER','viewer']::userrole[]);
