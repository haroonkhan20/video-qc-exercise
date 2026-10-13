CREATE TABLE IF NOT EXISTS qc_metrics (
 digest String, config_version String, code_version String,
 stream String, check_name LowCardinality(String), metric LowCardinality(String),
 delivery_id String DEFAULT '', row_id String DEFAULT '',
 time_ns Int64, value Float64
) ENGINE = MergeTree
ORDER BY (digest, config_version, code_version, stream, check_name, metric, time_ns)
SETTINGS non_replicated_deduplication_window = 100000
;
ALTER TABLE qc_metrics ADD COLUMN IF NOT EXISTS delivery_id String DEFAULT '';
ALTER TABLE qc_metrics ADD COLUMN IF NOT EXISTS row_id String DEFAULT '';
