-- Dedicated additive schema. Does not modify the original application tables.
CREATE TABLE IF NOT EXISTS cf_radar_meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
INSERT OR IGNORE INTO cf_radar_meta VALUES ('app_id','reese-max/ai-flight-radar:cloudflare-v1');
INSERT OR IGNORE INTO cf_radar_meta VALUES ('schema_version','1');
INSERT OR IGNORE INTO cf_radar_meta VALUES ('snapshot_count','0');
INSERT OR IGNORE INTO cf_radar_meta VALUES ('task_count','0');
INSERT OR IGNORE INTO cf_radar_meta VALUES ('receipt_count','0');

CREATE TABLE IF NOT EXISTS cf_radar_tasks (
  id TEXT PRIMARY KEY,
  query_key TEXT NOT NULL UNIQUE,
  origin TEXT NOT NULL,
  destination TEXT NOT NULL,
  depart_date TEXT NOT NULL,
  return_date TEXT NOT NULL,
  next_run INTEGER NOT NULL DEFAULT 0,
  lease_until INTEGER NOT NULL DEFAULT 0,
  lease_owner TEXT,
  last_outcome TEXT,
  enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0,1))
);
CREATE INDEX IF NOT EXISTS cf_tasks_due ON cf_radar_tasks(enabled,next_run,lease_until);
CREATE TRIGGER IF NOT EXISTS cf_tasks_limit BEFORE INSERT ON cf_radar_tasks
WHEN NOT EXISTS (SELECT 1 FROM cf_radar_tasks WHERE query_key=NEW.query_key)
 AND CAST((SELECT value FROM cf_radar_meta WHERE key='task_count') AS INTEGER)>=128
BEGIN SELECT RAISE(ABORT,'task capacity reached'); END;
CREATE TRIGGER IF NOT EXISTS cf_task_added AFTER INSERT ON cf_radar_tasks BEGIN
  UPDATE cf_radar_meta SET value=CAST(CAST(value AS INTEGER)+1 AS TEXT) WHERE key='task_count';
END;

CREATE TABLE IF NOT EXISTS cf_radar_receipts (
  token TEXT PRIMARY KEY,
  payload_hash TEXT NOT NULL,
  task_id TEXT NOT NULL REFERENCES cf_radar_tasks(id),
  outcome TEXT NOT NULL CHECK(outcome IN ('ok','empty','error')),
  completed_at TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS cf_receipts_limit BEFORE INSERT ON cf_radar_receipts
WHEN NOT EXISTS (SELECT 1 FROM cf_radar_receipts WHERE token=NEW.token)
 AND CAST((SELECT value FROM cf_radar_meta WHERE key='receipt_count') AS INTEGER)>=100000
BEGIN SELECT RAISE(ABORT,'receipt capacity reached'); END;
CREATE TRIGGER IF NOT EXISTS cf_receipt_added AFTER INSERT ON cf_radar_receipts BEGIN
  UPDATE cf_radar_meta SET value=CAST(CAST(value AS INTEGER)+1 AS TEXT) WHERE key='receipt_count';
END;

CREATE TABLE IF NOT EXISTS cf_radar_snapshots (
  id TEXT PRIMARY KEY,
  query_key TEXT NOT NULL,
  origin TEXT NOT NULL,
  destination TEXT NOT NULL,
  depart_date TEXT NOT NULL,
  return_date TEXT NOT NULL,
  trip_days INTEGER NOT NULL CHECK(trip_days BETWEEN 2 AND 31),
  price_twd INTEGER NOT NULL CHECK(price_twd BETWEEN 1 AND 1000000),
  searched_at TEXT NOT NULL,
  payload TEXT NOT NULL CHECK(json_valid(payload))
);
CREATE INDEX IF NOT EXISTS cf_snap_history ON cf_radar_snapshots(query_key,searched_at);
CREATE TRIGGER IF NOT EXISTS cf_snap_limit BEFORE INSERT ON cf_radar_snapshots
WHEN NOT EXISTS (SELECT 1 FROM cf_radar_snapshots WHERE id=NEW.id)
 AND CAST((SELECT value FROM cf_radar_meta WHERE key='snapshot_count') AS INTEGER)>=20000
BEGIN SELECT RAISE(ABORT,'snapshot capacity reached'); END;

CREATE TABLE IF NOT EXISTS cf_radar_latest (
  query_key TEXT PRIMARY KEY,
  snapshot_id TEXT NOT NULL REFERENCES cf_radar_snapshots(id),
  origin TEXT NOT NULL,
  destination TEXT NOT NULL,
  depart_date TEXT NOT NULL,
  return_date TEXT NOT NULL,
  trip_days INTEGER NOT NULL,
  price_twd INTEGER NOT NULL,
  searched_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS cf_latest_route ON cf_radar_latest(origin,destination,depart_date,return_date);
CREATE INDEX IF NOT EXISTS cf_latest_fresh ON cf_radar_latest(searched_at,price_twd);
CREATE TRIGGER IF NOT EXISTS cf_snapshot_added AFTER INSERT ON cf_radar_snapshots BEGIN
  INSERT INTO cf_radar_latest VALUES
    (NEW.query_key,NEW.id,NEW.origin,NEW.destination,NEW.depart_date,NEW.return_date,NEW.trip_days,NEW.price_twd,NEW.searched_at)
  ON CONFLICT(query_key) DO UPDATE SET
    snapshot_id=excluded.snapshot_id, origin=excluded.origin, destination=excluded.destination,
    depart_date=excluded.depart_date, return_date=excluded.return_date, trip_days=excluded.trip_days,
    price_twd=excluded.price_twd, searched_at=excluded.searched_at
  WHERE excluded.searched_at>cf_radar_latest.searched_at
    OR (excluded.searched_at=cf_radar_latest.searched_at AND excluded.snapshot_id>cf_radar_latest.snapshot_id);
  UPDATE cf_radar_meta SET value=CAST(CAST(value AS INTEGER)+1 AS TEXT) WHERE key='snapshot_count';
  INSERT INTO cf_radar_meta VALUES ('last_quote_at',NEW.searched_at)
    ON CONFLICT(key) DO UPDATE SET value=excluded.value WHERE excluded.value>cf_radar_meta.value;
END;

-- Fixed names rather than a new counter row for every request/hour.
CREATE TABLE IF NOT EXISTS cf_radar_budgets (
  name TEXT PRIMARY KEY,
  window_start INTEGER NOT NULL,
  used INTEGER NOT NULL
);

CREATE TRIGGER IF NOT EXISTS cf_task_removed AFTER DELETE ON cf_radar_tasks BEGIN
  UPDATE cf_radar_meta SET value=CAST(CAST(value AS INTEGER)-1 AS TEXT) WHERE key='task_count';
END;
CREATE TRIGGER IF NOT EXISTS cf_receipt_removed AFTER DELETE ON cf_radar_receipts BEGIN
  UPDATE cf_radar_meta SET value=CAST(CAST(value AS INTEGER)-1 AS TEXT) WHERE key='receipt_count';
END;
CREATE TRIGGER IF NOT EXISTS cf_snapshot_removed AFTER DELETE ON cf_radar_snapshots BEGIN
  UPDATE cf_radar_meta SET value=CAST(CAST(value AS INTEGER)-1 AS TEXT) WHERE key='snapshot_count';
END;
