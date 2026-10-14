ALTER TABLE projects ADD COLUMN test_command TEXT;
ALTER TABLE work_orders ADD COLUMN integration_status TEXT NOT NULL DEFAULT 'none';
ALTER TABLE work_orders ADD COLUMN integration_note TEXT;

CREATE TABLE test_runs (
  test_run_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(project_id),
  work_order_id TEXT NOT NULL REFERENCES work_orders(work_order_id),
  task_id TEXT REFERENCES tasks(task_id),
  argv TEXT NOT NULL,
  exit_code INTEGER,
  status TEXT NOT NULL CHECK (status IN ('passed','failed','error','timeout')),
  duration_ms INTEGER NOT NULL,
  output_artifact_id TEXT REFERENCES artifacts(artifact_id),
  created_at TEXT NOT NULL
);
