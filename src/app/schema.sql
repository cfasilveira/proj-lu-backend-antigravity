-- RH Connect: Supabase Schema

-- Enable pgcrypto for CPF encryption
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 1. Recruiters Table
CREATE TABLE IF NOT EXISTS recruiters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Jobs Table
CREATE TABLE IF NOT EXISTS jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recruiter_id UUID REFERENCES recruiters(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    salary NUMERIC,
    city TEXT NOT NULL,
    uf TEXT NOT NULL,
    type TEXT CHECK (type IN ('Presencial', 'Híbrido', 'Remoto')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Candidates Table
CREATE TABLE IF NOT EXISTS candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES jobs(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    gender TEXT CHECK (gender IN ('M', 'F', 'Outro')),
    uf TEXT NOT NULL,
    
    -- Encrypted CPF
    cpf_encrypted BYTEA NOT NULL,
    
    -- Resume & AI
    resume_text TEXT NOT NULL,
    ai_score INTEGER CHECK (ai_score >= 0 AND ai_score <= 100),
    ai_justification TEXT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexing for performance
CREATE INDEX idx_candidates_job_id ON candidates(job_id);
CREATE INDEX idx_jobs_recruiter_id ON jobs(recruiter_id);
