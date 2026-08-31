-- Initialize QuantHireAI Database
-- Enable pgvector extension for vector similarity search

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgvector";

-- Create default schema
CREATE SCHEMA IF NOT EXISTS public;

-- Grant permissions
GRANT ALL PRIVILEGES ON SCHEMA public TO quanthire;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO quanthire;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO quanthire;

-- Create custom types
DO $$ BEGIN
    CREATE TYPE user_role AS ENUM ('admin', 'recruiter', 'hiring_manager', 'interviewer', 'candidate');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE job_status AS ENUM ('draft', 'open', 'paused', 'closed', 'filled');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE application_status AS ENUM ('applied', 'screening', 'assessment', 'interviewing', 'offer', 'accepted', 'rejected', 'withdrawn');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE interview_type AS ENUM ('phone_screen', 'technical', 'behavioral', 'panel', 'async_video');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE offer_status AS ENUM ('draft', 'sent', 'negotiating', 'accepted', 'declined');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Set default timezone
SET timezone = 'UTC';

-- Optimize for performance
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '16MB';
ALTER SYSTEM SET default_statistics_target = 100;
ALTER SYSTEM SET random_page_cost = 1.1;
ALTER SYSTEM SET effective_io_concurrency = 200;
ALTER SYSTEM SET work_mem = '4MB';
ALTER SYSTEM SET min_wal_size = '1GB';
ALTER SYSTEM SET max_wal_size = '4GB';

COMMIT;

