-- Database schema for Memory Management System
-- Compatible with PostgreSQL and Supabase

-- ============================================
-- Chat History Table
-- ============================================
CREATE TABLE IF NOT EXISTS chat_history (
    id BIGSERIAL PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    agent_name VARCHAR(100),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb,
    
    -- Indexes for fast queries
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_history_session ON chat_history(session_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_chat_history_created ON chat_history(created_at);


-- ============================================
-- Workflow States Table
-- ============================================
CREATE TABLE IF NOT EXISTS workflow_states (
    id BIGSERIAL PRIMARY KEY,
    workflow_id VARCHAR(100) UNIQUE NOT NULL,
    status VARCHAR(50) NOT NULL CHECK (status IN ('running', 'completed', 'failed', 'paused', 'escalated')),
    current_step VARCHAR(200),
    context JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_workflow_states_id ON workflow_states(workflow_id);
CREATE INDEX IF NOT EXISTS idx_workflow_states_status ON workflow_states(status);
CREATE INDEX IF NOT EXISTS idx_workflow_states_created ON workflow_states(created_at);


-- ============================================
-- Agent Executions Table
-- ============================================
CREATE TABLE IF NOT EXISTS agent_executions (
    id BIGSERIAL PRIMARY KEY,
    workflow_id VARCHAR(100) NOT NULL,
    agent_name VARCHAR(100) NOT NULL,
    task TEXT NOT NULL,
    result JSONB,
    confidence DECIMAL(3,2),
    error TEXT,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'::jsonb,
    
    -- Foreign key to workflow_states
    FOREIGN KEY (workflow_id) REFERENCES workflow_states(workflow_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_agent_executions_workflow ON agent_executions(workflow_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_executions_agent ON agent_executions(agent_name);
CREATE INDEX IF NOT EXISTS idx_agent_executions_started ON agent_executions(started_at);


-- ============================================
-- Cached Results Table
-- ============================================
CREATE TABLE IF NOT EXISTS cached_results (
    id BIGSERIAL PRIMARY KEY,
    cache_key VARCHAR(64) UNIQUE NOT NULL,
    agent_name VARCHAR(100) NOT NULL,
    task_hash VARCHAR(64) NOT NULL,
    task TEXT NOT NULL,
    result JSONB NOT NULL,
    confidence DECIMAL(3,2) NOT NULL,
    params JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    hit_count INTEGER DEFAULT 0,
    last_hit_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_cached_results_key ON cached_results(cache_key);
CREATE INDEX IF NOT EXISTS idx_cached_results_agent ON cached_results(agent_name);
CREATE INDEX IF NOT EXISTS idx_cached_results_expires ON cached_results(expires_at);
CREATE INDEX IF NOT EXISTS idx_cached_results_task_hash ON cached_results(task_hash);

-- ============================================
-- Auto-update timestamp trigger
-- ============================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_workflow_states_updated_at ON workflow_states;
CREATE TRIGGER update_workflow_states_updated_at
    BEFORE UPDATE ON workflow_states
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- Cleanup Functions
-- ============================================

-- Clean up old chat history (older than retention period)
CREATE OR REPLACE FUNCTION cleanup_old_chat_history(retention_days INTEGER DEFAULT 30)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM chat_history 
    WHERE created_at < NOW() - (retention_days || ' days')::INTERVAL;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Clean up expired cache
CREATE OR REPLACE FUNCTION cleanup_expired_cache()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM cached_results 
    WHERE expires_at IS NOT NULL AND expires_at < NOW();
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Clean up old workflow states (older than retention period)
CREATE OR REPLACE FUNCTION cleanup_old_workflows(retention_days INTEGER DEFAULT 7)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM workflow_states 
    WHERE created_at < NOW() - (retention_days || ' days')::INTERVAL
    AND status IN ('completed', 'failed');
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- Analytics Views
-- ============================================

-- View: Agent Performance
CREATE OR REPLACE VIEW agent_performance AS
SELECT 
    agent_name,
    COUNT(*) as total_executions,
    COUNT(*) FILTER (WHERE error IS NULL) as successful_executions,
    COUNT(*) FILTER (WHERE error IS NOT NULL) as failed_executions,
    ROUND(AVG(confidence)::numeric, 2) as avg_confidence,
    ROUND(AVG(EXTRACT(EPOCH FROM (completed_at - started_at)))::numeric, 2) as avg_duration_seconds,
    MAX(started_at) as last_execution
FROM agent_executions
WHERE started_at > NOW() - INTERVAL '7 days'
GROUP BY agent_name;

-- View: Cache Statistics
CREATE OR REPLACE VIEW cache_statistics AS
SELECT 
    agent_name,
    COUNT(*) as total_cached,
    SUM(hit_count) as total_hits,
    ROUND(AVG(confidence)::numeric, 2) as avg_confidence,
    COUNT(*) FILTER (WHERE expires_at > NOW() OR expires_at IS NULL) as active_cache,
    COUNT(*) FILTER (WHERE expires_at <= NOW()) as expired_cache
FROM cached_results
GROUP BY agent_name;

-- View: Workflow Statistics
CREATE OR REPLACE VIEW workflow_statistics AS
SELECT 
    status,
    COUNT(*) as count,
    ROUND(AVG(EXTRACT(EPOCH FROM (updated_at - created_at)))::numeric, 2) as avg_duration_seconds
FROM workflow_states
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY status;

-- ============================================
-- Comments
-- ============================================
COMMENT ON TABLE chat_history IS 'Stores conversation history for each session';
COMMENT ON TABLE workflow_states IS 'Tracks state of each workflow execution';
COMMENT ON TABLE agent_executions IS 'Records each agent execution within workflows';
COMMENT ON TABLE cached_results IS 'Caches high-confidence results to avoid redundant processing';

COMMENT ON FUNCTION cleanup_old_chat_history IS 'Removes chat messages older than specified days';
COMMENT ON FUNCTION cleanup_expired_cache IS 'Removes expired cached results';
COMMENT ON FUNCTION cleanup_old_workflows IS 'Removes completed/failed workflows older than specified days';
