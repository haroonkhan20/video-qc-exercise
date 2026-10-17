# Shared reason registry and decision settings

worker/config/reason-codes.json is the authoritative definition of reason identifiers, their roles, classification groups and score explanations. qc.reasons supplies those definitions to the worker and local grading adapters. Postgres reason-code constraints are generated from this registry; the migration has been applied to the deployed database.

POSSIBLE_OBSTRUCTION identifies a suspected blocked-camera view requiring review. CHECKS_PASSED explicitly explains a successful verdict. Success and informational codes are retained in downloadable evidence without being displayed as actionable faults.

worker/config/qc.json holds inventory, timing, content and verdict policy, movement limits, obstruction settings, score ceilings/precision, camera evaluation budgets, profile validation limits, numerical comparison allowances and the explicit capture profile. Existing saved grading standards retain their own versioned choices.

New workflow runs freeze their configuration. Movement and obstruction checks use those frozen settings. Recording declarations take priority over configured assumptions; missing rates and confirmed pose units use the narrowly scoped profile described in PHYSICAL-POLICY.md.

Numerical budgets such as rotation-boundary epsilon and floating-point comparison allowance are explicit. Operational transport timeouts, Temporal retry settings and mathematical identities are not data-quality thresholds.

New reports include actionable movement and obstruction findings in the verdict. Encoder stillness alone is informational. The first second of tracking is excluded from movement comparisons, while value validity and timing checks remain active.

Earlier reports retain their original configuration and source versions. A rerun creates new versioned evidence and updates the latest recording result only after finalization. Cached evidence is never relabelled as freshly processed data.

The current image is deployed on two workers and passes 210 tests in its pinned runtime. Complete representative workflows were checked before the 41-file batch. REPORT.md records whether the full acceptance export is still in progress or complete.
