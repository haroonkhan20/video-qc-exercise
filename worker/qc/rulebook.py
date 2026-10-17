"""Versioned decision settings; safe to import without storage or credentials."""
import copy,json,math
from pathlib import Path
PATH=Path(__file__).resolve().parents[1]/"config/qc.json"
DEFAULTS=json.loads(PATH.read_text())
REQUIRED_FIELDS={'movement': ['baseline_max_mad_relative', 'baseline_min_pairs', 'baseline_seconds', 'gap_period_multiple', 'group_tolerance_seconds', 'maximum_pair_seconds', 'nominal_hz', 'norm_boundary_epsilon', 'numeric_noise_ulps', 'position_jump_multiple', 'rotation_boundary_epsilon_degrees', 'rotation_norm_tolerance', 'rotation_step_degrees'], 'obstruction': ['area_max', 'area_min', 'completion_minimum_samples', 'completion_minimum_seconds', 'dark_fraction', 'dark_pixel', 'grid', 'image_size', 'maximum_gap_seconds', 'minimum_samples', 'minimum_seconds', 'remaining_mean_min', 'remaining_std_min', 'stream_window_tolerance_seconds', 'tile_std_max'], 'score_limits': ['container_incomplete', 'container_recoverable', 'container_unreadable', 'decimal_places', 'essential_failure', 'maximum', 'nonperfect_ceiling', 'other_failure', 'review', 'weighted_decimal_places'], 'evaluation': ['camera_drift_segment_divisor', 'camera_skew_percentile', 'expected_camera_count'], 'profile_validation': ['maximum_band_count', 'maximum_limit_value', 'maximum_name_characters', 'minimum_band_count', 'weights_sum_absolute_tolerance']}
def validate(config):
 for name in ("movement","obstruction","score_limits","evaluation","profile_validation"):
  block=config.get(name)
  if not isinstance(block,dict) or set(block)!=set(REQUIRED_FIELDS[name]):
   raise ValueError("Missing or unknown "+name+" settings")
  for key,v in block.items():
   if not isinstance(v,(int,float)) or isinstance(v,bool) or not math.isfinite(v) or v<0 or (v==0 and key!="container_unreadable"):
    raise ValueError("Invalid "+name+"."+key)
 for key in ("grid","image_size","minimum_samples","completion_minimum_samples"):
  if not isinstance(config["obstruction"][key],int):raise ValueError("Obstruction sizes/counts must be integers")
 if config["obstruction"]["image_size"]%config["obstruction"]["grid"]:
  raise ValueError("Image size must divide into grid")
 limits=config["score_limits"]
 if not 0<=limits["essential_failure"]<=limits["other_failure"]<=limits["review"]<=limits["maximum"]:
  raise ValueError("Score limits must be ordered")
 if not 0<limits["nonperfect_ceiling"]<limits["maximum"]:raise ValueError("Invalid rounding ceiling")
 for key in ("decimal_places","weighted_decimal_places"):
  if not isinstance(limits[key],int):raise ValueError("Score precision must be an integer")
 for code in config["policy"]["failure_codes"]+config["policy"]["review_codes"]:
  from qc.reasons import PIPELINE_CODES
  if code not in PIPELINE_CODES:raise ValueError("Unknown policy reason")
 if not 0<config["obstruction"]["area_min"]<=config["obstruction"]["area_max"]<=1:
  raise ValueError("Invalid obstruction area fractions")
 if not 0<config["obstruction"]["dark_fraction"]<=1:raise ValueError("Invalid dark fraction")
 if not 0<config["evaluation"]["camera_skew_percentile"]<=100:raise ValueError("Invalid percentile")
 for name,key in (("evaluation","expected_camera_count"),("evaluation","camera_drift_segment_divisor"),("movement","baseline_min_pairs"),("movement","numeric_noise_ulps"),("profile_validation","minimum_band_count"),("profile_validation","maximum_band_count"),("profile_validation","maximum_name_characters")):
  if not isinstance(config[name][key],int):raise ValueError("Count settings must be integers")
 return config
def validate_physical(config):
 p=config.get("physical_movement")
 required={"mode","startup_seconds","head_position_speed_mps","hand_position_speed_mps","head_turn_rate_degrees_per_second","hand_turn_rate_degrees_per_second","clock_uncertainty_endpoint_factor","require_confirmed_position_unit"}
 if not isinstance(p,dict) or set(p)!=required or p["mode"] not in {"physical","legacy_relative"}:
  raise ValueError("Invalid physical movement configuration")
 if p["require_confirmed_position_unit"] is not True:raise ValueError("Position unit gate cannot be disabled")
 for key in required-{"mode","require_confirmed_position_unit"}:
  value=p[key]
  if not isinstance(value,(int,float)) or isinstance(value,bool) or not math.isfinite(value) or value<=0:
   raise ValueError("Invalid physical threshold: "+key)
 numeric=config.get("metadata_comparison")
 if not isinstance(numeric,dict) or set(numeric)!={"timestamp_quantum_ns","floating_point_ulps"}:
  raise ValueError("Missing metadata comparison precision")
 for value in numeric.values():
  if not isinstance(value,int) or isinstance(value,bool) or value<=0:raise ValueError("Invalid metadata comparison precision")
 informational=config["policy"].get("informational_codes",[])
 from qc.reasons import PIPELINE_CODES,REGISTRY
 if not isinstance(informational,list) or any(code not in PIPELINE_CODES for code in informational):
  raise ValueError("Invalid informational reason list")
 if set(informational)&set(config["policy"]["failure_codes"]+config["policy"]["review_codes"]):
  raise ValueError("Informational and actionable policy codes must be disjoint")
 success=config["policy"].get("success_reason_code")
 if success not in REGISTRY or REGISTRY[success]["kind"]!="success":raise ValueError("Missing valid success reason")
 return config
validate(DEFAULTS)
validate_physical(DEFAULTS)
def section(name,config=None):
 # Historical reports without refactored blocks retain the unchanged defaults.
 return copy.deepcopy((config or {}).get(name,DEFAULTS[name]))
