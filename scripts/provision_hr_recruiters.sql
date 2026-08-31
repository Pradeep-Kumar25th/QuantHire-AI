-- Pre-provision Malomatia HR recruiters with RECRUITER role (same as xx1@malomatia.com).
-- Run on Azure Non-Prod Postgres when Entra SSO is ready but users have not logged in yet.
--
--   kubectl exec deploy/quanthire-nonprod-api -n quanthire-nonprod -- \\
--     psql "$DATABASE_URL" -f /tmp/provision_hr_recruiters.sql

INSERT INTO users (
    id, email, name, role, org_id, hashed_password,
    is_active, is_verified, metadata, created_at, updated_at, last_login_at
)
VALUES
    (gen_random_uuid(), 'vbhushan@malomatia.com', 'Vaibhav Bharat Bhushan', 'RECRUITER'::userrole, NULL, NULL, true, true, '{}'::jsonb, NOW(), NOW(), NULL),
    (gen_random_uuid(), 'rcambell@malomatia.com', 'Rohan Cambell', 'RECRUITER'::userrole, NULL, NULL, true, true, '{}'::jsonb, NOW(), NOW(), NULL),
    (gen_random_uuid(), 'kpole@malomatia.com', 'Ketaki Pole', 'RECRUITER'::userrole, NULL, NULL, true, true, '{}'::jsonb, NOW(), NOW(), NULL),
    (gen_random_uuid(), 'rxavier@malomatia.com', 'Romin Xavier', 'RECRUITER'::userrole, NULL, NULL, true, true, '{}'::jsonb, NOW(), NOW(), NULL),
    (gen_random_uuid(), 'nsahare@malomatia.com', 'Nisha Sahare', 'RECRUITER'::userrole, NULL, NULL, true, true, '{}'::jsonb, NOW(), NOW(), NULL),
    (gen_random_uuid(), 'mvismonte@malomatia.com', 'Melanie Carlos Vismonte', 'RECRUITER'::userrole, NULL, NULL, true, true, '{}'::jsonb, NOW(), NOW(), NULL),
    (gen_random_uuid(), 'pdudhnale@malomatia.com', 'Pradeep Dudhnale', 'RECRUITER'::userrole, NULL, NULL, true, true, '{}'::jsonb, NOW(), NOW(), NULL),
    (gen_random_uuid(), 'rgirle@malomatia.com', 'Richard Duncan Girle', 'RECRUITER'::userrole, NULL, NULL, true, true, '{}'::jsonb, NOW(), NOW(), NULL)
ON CONFLICT (email) DO UPDATE SET
    name = EXCLUDED.name,
    role = EXCLUDED.role,
    is_active = true,
    is_verified = true,
    updated_at = NOW();

SELECT email, role::text AS role, is_active FROM users
WHERE lower(email) IN (
    'vbhushan@malomatia.com',
    'rcambell@malomatia.com',
    'kpole@malomatia.com',
    'rxavier@malomatia.com',
    'nsahare@malomatia.com',
    'mvismonte@malomatia.com',
    'pdudhnale@malomatia.com',
    'rgirle@malomatia.com'
)
ORDER BY email;
