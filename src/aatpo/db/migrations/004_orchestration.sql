ALTER TABLE tasks ADD COLUMN plan_version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE tasks ADD COLUMN plan_key TEXT;
ALTER TABLE tasks ADD COLUMN role_id TEXT REFERENCES agent_roles(role_id);
ALTER TABLE tasks ADD COLUMN acceptance TEXT;
ALTER TABLE tasks ADD COLUMN writes INTEGER NOT NULL DEFAULT 0;
ALTER TABLE tasks ADD COLUMN rework_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE tasks ADD COLUMN blocked_reason TEXT;
ALTER TABLE work_orders ADD COLUMN plan_mode TEXT;
ALTER TABLE work_orders ADD COLUMN pause_requested INTEGER NOT NULL DEFAULT 0;

CREATE TABLE plans (
  plan_id TEXT PRIMARY KEY,
  work_order_id TEXT NOT NULL REFERENCES work_orders(work_order_id),
  version INTEGER NOT NULL,
  mode TEXT NOT NULL CHECK (mode IN ('fast_lane','standard','full')),
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','superseded')),
  created_at TEXT NOT NULL,
  UNIQUE (work_order_id, version)
);
CREATE TABLE artifacts (
  artifact_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(project_id),
  work_order_id TEXT NOT NULL REFERENCES work_orders(work_order_id),
  task_id TEXT NOT NULL REFERENCES tasks(task_id),
  run_id TEXT REFERENCES process_runs(run_id),
  path TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  kind TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE reviews (
  review_id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL REFERENCES tasks(task_id),
  reviewer_task_id TEXT NOT NULL REFERENCES tasks(task_id),
  verdict TEXT NOT NULL CHECK (verdict IN ('pass','fail')),
  findings TEXT NOT NULL,
  evidence_artifact_id TEXT REFERENCES artifacts(artifact_id),
  created_at TEXT NOT NULL
);
CREATE TABLE handoffs (
  handoff_id TEXT PRIMARY KEY,
  work_order_id TEXT NOT NULL REFERENCES work_orders(work_order_id),
  from_task_id TEXT REFERENCES tasks(task_id),
  to_task_id TEXT NOT NULL REFERENCES tasks(task_id),
  reason TEXT NOT NULL,
  summary TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE resource_locks (
  resource TEXT PRIMARY KEY,
  holder_task_id TEXT NOT NULL REFERENCES tasks(task_id),
  acquired_at TEXT NOT NULL
);
