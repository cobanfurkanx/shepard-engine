CREATE SCHEMA IF NOT EXISTS engine;

CREATE TABLE IF NOT EXISTS engine.candles (
  symbol text NOT NULL CHECK (symbol ~ '^[A-Z0-9]{2,16}USDT$'),
  open_ms bigint NOT NULL CHECK (open_ms >= 0 AND open_ms % 900000 = 0),
  close double precision NOT NULL CHECK (close > 0 AND close < 'Infinity'::float8),
  quote_volume double precision NOT NULL CHECK (quote_volume >= 0 AND quote_volume < 'Infinity'::float8),
  rsi double precision CHECK (rsi BETWEEN 0 AND 100),
  previous_rsi double precision CHECK (previous_rsi BETWEEN 0 AND 100),
  PRIMARY KEY (symbol, open_ms)
);
CREATE INDEX IF NOT EXISTS candles_report_window ON engine.candles (open_ms, symbol)
  INCLUDE (quote_volume, rsi, previous_rsi);

CREATE TABLE IF NOT EXISTS engine.indicator_state (
  symbol text PRIMARY KEY,
  open_ms bigint NOT NULL,
  close double precision NOT NULL,
  gain double precision NOT NULL,
  loss double precision NOT NULL,
  samples integer NOT NULL,
  rsi double precision
);

CREATE TABLE IF NOT EXISTS engine.users (
  id uuid PRIMARY KEY,
  email text UNIQUE NOT NULL,
  password_hash text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS engine.sessions (
  id uuid PRIMARY KEY,
  user_id uuid NOT NULL REFERENCES engine.users(id) ON DELETE CASCADE,
  revoked boolean NOT NULL DEFAULT false,
  expires_at timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_expiry ON engine.sessions(expires_at);
CREATE TABLE IF NOT EXISTS engine.refresh_tokens (
  token_hash text PRIMARY KEY,
  session_id uuid NOT NULL REFERENCES engine.sessions(id) ON DELETE CASCADE,
  consumed boolean NOT NULL DEFAULT false
);
CREATE INDEX IF NOT EXISTS refresh_session ON engine.refresh_tokens(session_id);
