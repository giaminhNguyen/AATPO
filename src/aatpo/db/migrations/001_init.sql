CREATE TABLE projects (
  project_id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  root_path TEXT NOT NULL,
  root_key TEXT NOT NULL UNIQUE,
  project_type TEXT NOT NULL CHECK (project_type IN ('existing_code','new_product','research','other')),
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','archived')),
  selected_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  notes TEXT,
  repo_detected INTEGER NOT NULL DEFAULT 0,
  git_auto_history INTEGER NOT NULL DEFAULT 0,
  git_default_branch TEXT
);
CREATE TABLE app_state (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE provider_registry (
  provider_id TEXT PRIMARY KEY, executable TEXT, version TEXT,
  status TEXT NOT NULL DEFAULT 'unknown', checked_at TEXT
);
CREATE TABLE agent_roles (
  role_id TEXT PRIMARY KEY, profile_version INTEGER NOT NULL DEFAULT 1, title_vi TEXT NOT NULL DEFAULT ''
);
CREATE TABLE work_orders (
  work_order_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(project_id),
  title TEXT NOT NULL, state TEXT NOT NULL,
  version INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE tasks (
  task_id TEXT PRIMARY KEY,
  work_order_id TEXT NOT NULL REFERENCES work_orders(work_order_id),
  title TEXT NOT NULL, state TEXT NOT NULL,
  version INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE task_dependencies (
  task_id TEXT NOT NULL REFERENCES tasks(task_id),
  depends_on TEXT NOT NULL REFERENCES tasks(task_id),
  PRIMARY KEY (task_id, depends_on), CHECK (task_id <> depends_on)
);
CREATE TABLE assignments (
  assignment_id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL REFERENCES tasks(task_id),
  role_id TEXT NOT NULL REFERENCES agent_roles(role_id),
  provider_id TEXT NOT NULL REFERENCES provider_registry(provider_id),
  created_at TEXT NOT NULL,
  UNIQUE (task_id, role_id, provider_id)
);
CREATE TABLE agent_sessions (
  session_id TEXT PRIMARY KEY,
  assignment_id TEXT NOT NULL UNIQUE REFERENCES assignments(assignment_id),
  project_id TEXT NOT NULL REFERENCES projects(project_id),
  work_order_id TEXT NOT NULL REFERENCES work_orders(work_order_id),
  task_id TEXT NOT NULL REFERENCES tasks(task_id),
  role_id TEXT NOT NULL, provider_id TEXT NOT NULL,
  provider_session_id TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE process_runs (
  run_id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES agent_sessions(session_id),
  state TEXT NOT NULL,
  idempotency_key TEXT NOT NULL UNIQUE,
  exit_code INTEGER, started_at TEXT, finished_at TEXT, created_at TEXT NOT NULL
);
CREATE TABLE events (
  event_id INTEGER PRIMARY KEY AUTOINCREMENT,
  at TEXT NOT NULL, kind TEXT NOT NULL,
  entity_type TEXT, entity_id TEXT, project_id TEXT, detail TEXT
);
CREATE TRIGGER events_no_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT, 'events are append-only'); END;
CREATE TRIGGER events_no_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT, 'events are append-only'); END;
CREATE TABLE git_repositories (
  repo_id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(project_id),
  repo_root TEXT NOT NULL, created_by_aatpo INTEGER NOT NULL DEFAULT 0, recorded_at TEXT NOT NULL
);
CREATE TABLE git_branches (
  branch_id TEXT PRIMARY KEY, repo_id TEXT NOT NULL REFERENCES git_repositories(repo_id),
  name TEXT NOT NULL, work_order_id TEXT, task_id TEXT, base_sha TEXT, created_at TEXT NOT NULL
);
CREATE TABLE git_commit_events (
  commit_event_id TEXT PRIMARY KEY, repo_id TEXT NOT NULL REFERENCES git_repositories(repo_id),
  branch TEXT, sha TEXT NOT NULL, parent_sha TEXT, task_id TEXT, evidence_ref TEXT,
  author_source TEXT, status TEXT NOT NULL, at TEXT NOT NULL
);
CREATE TABLE git_operations (
  op_id TEXT PRIMARY KEY, repo_root TEXT NOT NULL, project_id TEXT,
  argv TEXT NOT NULL, exit_code INTEGER, stdout_tail TEXT, stderr_tail TEXT,
  head_before TEXT, head_after TEXT, at TEXT NOT NULL
);
