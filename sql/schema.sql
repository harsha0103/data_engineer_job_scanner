-- ============================================================
-- embedd schema — data engineer job scanner
-- ============================================================

CREATE EXTENSION IF NOT EXISTS vector;   -- pgvector, for semantic job-fit matching
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE SCHEMA IF NOT EXISTS embedd;
SET search_path TO embedd, public;   -- keep public visible so the vector/uuid-ossp types resolve

-- ------------------------------------------------------------
-- sources: which job board / connector a listing came from
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS embedd.sources (
    id          SMALLSERIAL PRIMARY KEY,
    name        TEXT UNIQUE NOT NULL   -- 'indeed', 'dice', 'ziprecruiter'
);

INSERT INTO embedd.sources (name) VALUES
    ('indeed'), ('dice'), ('ziprecruiter')
ON CONFLICT (name) DO NOTHING;

-- ------------------------------------------------------------
-- jobs: raw scanned listings, deduped by (source_id, external_id)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS embedd.jobs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id       SMALLINT NOT NULL REFERENCES embedd.sources(id),
    external_id     TEXT NOT NULL,          -- the job board's own listing id
    title           TEXT NOT NULL,
    company         TEXT NOT NULL,
    location        TEXT,
    remote_type     TEXT,                   -- 'remote' | 'hybrid' | 'onsite'
    salary_min      NUMERIC,
    salary_max      NUMERIC,
    description     TEXT NOT NULL,
    url             TEXT NOT NULL,
    posted_at       TIMESTAMPTZ,
    scraped_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    description_embedding  vector(1536),    -- OpenAI text-embedding-3-small dims
    UNIQUE (source_id, external_id)
);

CREATE INDEX IF NOT EXISTS idx_jobs_company     ON embedd.jobs (company);
CREATE INDEX IF NOT EXISTS idx_jobs_scraped_at   ON embedd.jobs (scraped_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_embedding    ON embedd.jobs
    USING ivfflat (description_embedding vector_cosine_ops) WITH (lists = 100);

-- ------------------------------------------------------------
-- job_scores: fit evaluation per job (rubric-based, A-F style)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS embedd.job_scores (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id          UUID NOT NULL REFERENCES embedd.jobs(id) ON DELETE CASCADE,
    overall_score   NUMERIC(3,2) NOT NULL,   -- 1.00 - 5.00
    skills_match    NUMERIC(3,2),
    level_match     NUMERIC(3,2),
    location_match  NUMERIC(3,2),
    comp_match      NUMERIC(3,2),
    notes           TEXT,
    scored_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (job_id)                          -- one active score per job; re-score = update
);

-- ------------------------------------------------------------
-- resumes: tailored resume versions generated per job
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS embedd.resumes (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id          UUID NOT NULL REFERENCES embedd.jobs(id) ON DELETE CASCADE,
    file_path       TEXT NOT NULL,           -- path to generated PDF/docx
    summary_of_changes TEXT,                 -- what was tailored vs base resume
    generated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------
-- applications: tracks status through the pipeline
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS embedd.applications (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id          UUID NOT NULL REFERENCES embedd.jobs(id) ON DELETE CASCADE,
    resume_id       UUID REFERENCES embedd.resumes(id),
    status          TEXT NOT NULL DEFAULT 'not_applied',
        -- 'not_applied' | 'draft_ready' | 'applied' | 'interviewing' | 'rejected' | 'offer'
    applied_at      TIMESTAMPTZ,
    last_updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    notes           TEXT
);

CREATE INDEX IF NOT EXISTS idx_applications_status ON embedd.applications (status);

-- ------------------------------------------------------------
-- scan_runs: log of each scan, for observability
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS embedd.scan_runs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id       SMALLINT REFERENCES embedd.sources(id),
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ,
    jobs_found      INT DEFAULT 0,
    jobs_new        INT DEFAULT 0,
    status          TEXT DEFAULT 'running'   -- 'running' | 'success' | 'failed'
);

-- Ownership: give harsha full rights over the schema and everything in it
ALTER SCHEMA embedd OWNER TO harsha;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA embedd TO harsha;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA embedd TO harsha;
