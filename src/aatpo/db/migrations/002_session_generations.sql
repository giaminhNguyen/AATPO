-- A fallback (unsupported/broken resume) starts a NEW session for the same assignment,
-- linked to the one it replaces. Rebuild agent_sessions: UNIQUE(assignment_id) -> UNIQUE(assignment_id, generation).
CREATE TABLE agent_sessions_new (
  session_id TEXT PRIMARY KEY,
  assignment_id TEXT NOT NULL REFERENCES assignments(assignment_id),
  project_id TEXT NOT NULL REFERENCES projects(project_id),
  work_order_id TEXT NOT NULL REFERENCES work_orders(work_order_id),
  task_id TEXT NOT NULL REFERENCES tasks(task_id),
  role_id TEXT NOT NULL, provider_id TEXT NOT NULL,
  provider_session_id TEXT,
  created_at TEXT NOT NULL,
  generation INTEGER NOT NULL DEFAULT 1,
  supersedes_session_id TEXT REFERENCES agent_sessions_new(session_id),
  fallback_reason TEXT,
  handoff_brief TEXT,
  UNIQUE (assignment_id, generation)
);
INSERT INTO agent_sessions_new(session_id,assignment_id,project_id,work_order_id,task_id,role_id,provider_id,
                               provider_session_id,created_at)
  SELECT session_id,assignment_id,project_id,work_order_id,task_id,role_id,provider_id,provider_session_id,created_at
  FROM agent_sessions;
DROP TABLE agent_sessions;
ALTER TABLE agent_sessions_new RENAME TO agent_sessions;
