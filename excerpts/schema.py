# Excerpt from Salud (not the complete source).
"""SQLite data model (one local database file) and idempotent migrations.

Principles:
- Raw data is never overwritten: every download is kept verbatim in `raw_import`,
  and every save of the daily journal leaves a copy in `journal_log`.
- The `ring_*` tables are the "latest known version" view used day to day; models
  can rebuild "what was known at a given hour" from the raw rows.
- Migrations only add: they never drop columns or rows.
- Empty means "unknown", never 0.
"""
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);

-- Append-only history of the daily journal: one full-row copy per save
CREATE TABLE IF NOT EXISTS journal_log (
  id INTEGER PRIMARY KEY,
  day TEXT NOT NULL,
  data_json TEXT NOT NULL,
  saved_at TEXT NOT NULL,
  origin TEXT NOT NULL DEFAULT 'web'          -- web | migration
);
CREATE INDEX IF NOT EXISTS ix_journal_log ON journal_log(day, saved_at);

-- Measuring devices. A new device, finger or size = a new row = a new baseline.
CREATE TABLE IF NOT EXISTS device (
  id INTEGER PRIMARY KEY,
  kind TEXT NOT NULL, model TEXT, size TEXT, finger TEXT,
  since TEXT NOT NULL, until TEXT,
  config_json TEXT,                           -- which source field feeds each signal
  notes TEXT
);

-- Every download exactly as it arrived. Never modified.
CREATE TABLE IF NOT EXISTS raw_import (
  id INTEGER PRIMARY KEY,
  source TEXT NOT NULL,                       -- ring_api | phone_app | weather_api | ...
  endpoint TEXT, params TEXT,
  device_id INTEGER,
  imported_at TEXT NOT NULL,
  day_from TEXT, day_to TEXT,
  sha256 TEXT, bytes INTEGER,
  content TEXT NOT NULL,                      -- full response or file
  status TEXT NOT NULL DEFAULT 'ok',          -- ok | error
  notes TEXT
);
CREATE INDEX IF NOT EXISTS ix_raw_import ON raw_import(source, imported_at);

-- One row per sleep session (main night or nap), latest known version
CREATE TABLE IF NOT EXISTS ring_sleep (
  device_id INTEGER NOT NULL,
  start TEXT NOT NULL,                        -- local time 'YYYY-MM-DD HH:MM:SS'
  end TEXT NOT NULL,
  day TEXT NOT NULL,                          -- day D of waking up
  kind TEXT,                                  -- main | nap
  in_bed_min INTEGER, asleep_min INTEGER, latency_min INTEGER, awake_min INTEGER,
  light_min INTEGER, deep_min INTEGER, rem_min INTEGER, efficiency REAL,
  hr_mean REAL, hr_min REAL,                  -- bpm while asleep
  hrv REAL,                                   -- mean RMSSD during sleep, ms
  resp REAL,                                  -- breaths per minute
  temp_dev REAL,                              -- degC relative to the device's own baseline
  spo2 REAL,
  import_id INTEGER NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (device_id, start)
);
CREATE INDEX IF NOT EXISTS ix_ring_sleep_day ON ring_sleep(day);

-- Intraday samples (heart rate every few minutes, temperature...)
CREATE TABLE IF NOT EXISTS ring_sample (
  device_id INTEGER NOT NULL,
  metric TEXT NOT NULL,                       -- hr | hrv | temp | spo2 | motion
  ts TEXT NOT NULL,                           -- local time
  value REAL NOT NULL,
  context TEXT,                               -- sleep | rest | awake | workout
  import_id INTEGER NOT NULL,
  PRIMARY KEY (device_id, metric, ts)
);

-- Phone usage: every screen-on, screen-off and unlock, uploaded once a day
CREATE TABLE IF NOT EXISTS phone_event (
  ts TEXT NOT NULL,
  event TEXT NOT NULL,                        -- screen_on | screen_off | unlock
  import_id INTEGER NOT NULL,
  PRIMARY KEY (ts, event)
);

-- What the system said each morning. Frozen at a fixed hour and never regenerated,
-- so past warnings can be audited honestly against what happened.
CREATE TABLE IF NOT EXISTS warning (
  day TEXT NOT NULL,
  version TEXT NOT NULL,
  scored_at TEXT NOT NULL,
  level TEXT NOT NULL,                        -- no_data | calibrating | green | yellow | red
  reason TEXT,
  features_json TEXT,
  user_answer TEXT,                           -- optional feedback the next day
  PRIMARY KEY (day, version)
);
"""


def connect(path):
    c = sqlite3.connect(path, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    return c


def columns(c, table):
    return {r[1] for r in c.execute(f"PRAGMA table_info({table})")}


def init_db(path, journal_fields):
    """Create/upgrade the database. Safe to run on every start.

    The journal table is built from a list of field names, so adding a field to the
    list is enough: the column is added automatically on the next start.
    """
    with connect(path) as c:
        c.execute("PRAGMA journal_mode = WAL")
        cols = ", ".join(f"{k} TEXT" for k in journal_fields)
        c.execute(f"CREATE TABLE IF NOT EXISTS journal (day TEXT PRIMARY KEY, {cols}, created_at TEXT, updated_at TEXT)")
        c.executescript(SCHEMA)
        for k in [*journal_fields, "created_at"]:
            if k not in columns(c, "journal"):
                c.execute(f"ALTER TABLE journal ADD COLUMN {k} TEXT")
        c.execute("INSERT OR IGNORE INTO schema_version VALUES (1, datetime('now','localtime'))")
