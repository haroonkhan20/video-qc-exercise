CREATE TABLE IF NOT EXISTS qc_metrics (
 digest String, config_version String, code_version String,
 stream String, check_name LowCardinality(String), metric LowCardinality(String),
 time_ns Int64, value Float64
) ENGINE = MergeTree
ORDER BY (digest, config_version, code_version, stream, check_name, metric, time_ns)
SETTINGS non_replicated_deduplication_window = 100000
