CREATE TABLE IF NOT EXISTS ai_requests(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, requested_at BIGINT NOT NULL);
CREATE INDEX IF NOT EXISTS ai_requests_time ON ai_requests(requested_at);
CREATE INDEX IF NOT EXISTS ai_requests_user_time ON ai_requests(user_id,requested_at);
