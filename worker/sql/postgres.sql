CREATE TABLE IF NOT EXISTS qc_episodes (
 digest text PRIMARY KEY CHECK(digest ~ '^[0-9a-f]{64}$'),
 byte_size bigint NOT NULL CHECK(byte_size >= 0),
 raw_key text UNIQUE NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS qc_aliases (
 digest text NOT NULL REFERENCES qc_episodes(digest),
 filename text NOT NULL, PRIMARY KEY(digest, filename)
);
CREATE TABLE IF NOT EXISTS qc_runs (
 digest text NOT NULL REFERENCES qc_episodes(digest),
 config_version text NOT NULL, code_version text NOT NULL,
 config jsonb NOT NULL,
 verdict text CHECK(verdict IN ('pass','fail','needs_review')),
 reason_codes text[], report jsonb,
 finalized_at timestamptz,
 PRIMARY KEY(digest,config_version,code_version)
);
CREATE TABLE IF NOT EXISTS qc_verdicts (
 digest text PRIMARY KEY REFERENCES qc_episodes(digest),
 verdict text NOT NULL CHECK(verdict IN ('pass','fail','needs_review')),
 reason_codes text[] NOT NULL,
 config_version text NOT NULL, code_version text NOT NULL,
 report jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS qc_deliveries (
 delivery_id text PRIMARY KEY, digest text NOT NULL REFERENCES qc_episodes(digest),
 artifact text NOT NULL, delivered_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS qc_verdicts_verdict_idx ON qc_verdicts(verdict);
CREATE INDEX IF NOT EXISTS qc_deliveries_digest_idx ON qc_deliveries(digest);

DO $$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='qc_verdict_reason_codes') THEN
  ALTER TABLE qc_verdicts ADD CONSTRAINT qc_verdict_reason_codes CHECK(reason_codes <@ ARRAY['BLACK_RUN','BLUR_RUN','BRIGHT_RUN','CAMERA_SYNC','CHECK_UNAVAILABLE','CONTAINER_INCOMPLETE','CONTAINER_TRUNCATED_RECOVERABLE','CONTAINER_UNREADABLE','CONTRACT_UNCONFIRMED','COVERAGE_MISMATCH','FROZEN_RUN','GAP_RUN','MISSING_STREAM','PAYLOAD_TIMESTAMP_MISMATCH','RATE_OUT_OF_RANGE','RESOLUTION_CHANGE','SENSOR_FLATLINE','SENSOR_NONFINITE','TIMESTAMP_DUPLICATE','TIMESTAMP_REVERSED','UNEXPECTED_STREAM','VIDEO_NOT_KEYFRAME_START','VIDEO_UNDECODABLE','WRONG_ENCODING','WRONG_SCHEMA']::text[]);
 END IF;
 IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='qc_run_reason_codes') THEN
  ALTER TABLE qc_runs ADD CONSTRAINT qc_run_reason_codes CHECK(reason_codes <@ ARRAY['BLACK_RUN','BLUR_RUN','BRIGHT_RUN','CAMERA_SYNC','CHECK_UNAVAILABLE','CONTAINER_INCOMPLETE','CONTAINER_TRUNCATED_RECOVERABLE','CONTAINER_UNREADABLE','CONTRACT_UNCONFIRMED','COVERAGE_MISMATCH','FROZEN_RUN','GAP_RUN','MISSING_STREAM','PAYLOAD_TIMESTAMP_MISMATCH','RATE_OUT_OF_RANGE','RESOLUTION_CHANGE','SENSOR_FLATLINE','SENSOR_NONFINITE','TIMESTAMP_DUPLICATE','TIMESTAMP_REVERSED','UNEXPECTED_STREAM','VIDEO_NOT_KEYFRAME_START','VIDEO_UNDECODABLE','WRONG_ENCODING','WRONG_SCHEMA']::text[]);
 END IF;
END $$;
