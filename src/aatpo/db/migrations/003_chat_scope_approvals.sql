ALTER TABLE work_orders ADD COLUMN kind TEXT NOT NULL DEFAULT 'general';
ALTER TABLE work_orders ADD COLUMN requires_scope_approval INTEGER NOT NULL DEFAULT 0;
ALTER TABLE work_orders ADD COLUMN parent_work_order_id TEXT REFERENCES work_orders(work_order_id);
ALTER TABLE work_orders ADD COLUMN brief TEXT;

CREATE TABLE customer_messages (
  message_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(project_id),
  work_order_id TEXT REFERENCES work_orders(work_order_id),
  role TEXT NOT NULL CHECK (role IN ('customer','assistant','system')),
  text TEXT NOT NULL,
  meta TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX idx_messages_project ON customer_messages(project_id, created_at);

CREATE TABLE scopes (
  scope_id TEXT PRIMARY KEY,
  work_order_id TEXT NOT NULL REFERENCES work_orders(work_order_id),
  version INTEGER NOT NULL,
  option_key TEXT NOT NULL CHECK (option_key IN ('lean','balanced','quick')),
  title_vi TEXT NOT NULL,
  effort TEXT NOT NULL CHECK (effort IN ('XS','S','M','L','XL')),
  cost_note TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'proposed' CHECK (status IN ('proposed','approved','rejected','superseded')),
  created_at TEXT NOT NULL,
  UNIQUE (work_order_id, version, option_key)
);
CREATE TABLE features (
  feature_id TEXT PRIMARY KEY,
  scope_id TEXT NOT NULL REFERENCES scopes(scope_id),
  name TEXT NOT NULL,
  priority TEXT NOT NULL CHECK (priority IN ('MUST','SHOULD','LATER','DROP')),
  note TEXT
);
CREATE TABLE approvals (
  approval_id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  project_id TEXT NOT NULL REFERENCES projects(project_id),
  work_order_id TEXT NOT NULL REFERENCES work_orders(work_order_id),
  scope_version INTEGER,
  action_text TEXT NOT NULL,
  consequences TEXT NOT NULL,
  options TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected','superseded')),
  chosen_option TEXT,
  created_at TEXT NOT NULL,
  decided_at TEXT,
  operator TEXT
);
