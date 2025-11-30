-- TIMEPOINT Flash Database Initialization
-- This script runs when PostgreSQL container starts for the first time

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create timepoints table
CREATE TABLE IF NOT EXISTS timepoints (
    id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    query TEXT NOT NULL,
    slug VARCHAR(150) UNIQUE NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    year INTEGER,
    month INTEGER,
    day INTEGER,
    season VARCHAR(20),
    time_of_day VARCHAR(50),
    era VARCHAR(50),
    location TEXT,
    metadata_json JSONB,
    character_data_json JSONB,
    scene_data_json JSONB,
    dialog_json JSONB,
    image_prompt TEXT,
    image_url TEXT,
    image_base64 TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    parent_id VARCHAR(36) REFERENCES timepoints(id),
    error_message TEXT
);

-- Create generation_logs table
CREATE TABLE IF NOT EXISTS generation_logs (
    id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    timepoint_id VARCHAR(36) NOT NULL REFERENCES timepoints(id) ON DELETE CASCADE,
    step VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    input_data JSONB,
    output_data JSONB,
    model_used VARCHAR(100),
    provider VARCHAR(20),
    latency_ms INTEGER,
    token_usage JSONB,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_timepoints_status ON timepoints(status);
CREATE INDEX IF NOT EXISTS idx_timepoints_year ON timepoints(year);
CREATE INDEX IF NOT EXISTS idx_timepoints_created_at ON timepoints(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_timepoints_query ON timepoints USING gin(to_tsvector('english', query));
CREATE INDEX IF NOT EXISTS idx_generation_logs_timepoint ON generation_logs(timepoint_id);
CREATE INDEX IF NOT EXISTS idx_generation_logs_step ON generation_logs(step);

-- Grant permissions (if needed for specific users)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO timepoint;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO timepoint;

-- Add comment for documentation
COMMENT ON TABLE timepoints IS 'Core timepoint data for temporal simulations';
COMMENT ON TABLE generation_logs IS 'Pipeline step logs for debugging and monitoring';
