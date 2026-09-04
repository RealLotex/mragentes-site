CREATE TABLE IF NOT EXISTS metric_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event TEXT NOT NULL CHECK (event IN ('share_native', 'share_copy', 'share_whatsapp', 'social_referral')),
  dimension TEXT NOT NULL,
  occurred_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_metric_events_time ON metric_events (occurred_at);
CREATE INDEX IF NOT EXISTS idx_metric_events_event_dimension ON metric_events (event, dimension);
