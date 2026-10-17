"""Explicit deployment assumptions, separate from declarations inside recordings."""
from copy import deepcopy

def resolve(contract, config):
    result = deepcopy(contract)
    profile = config.get("capture_profile", {})
    delivery = result.get("delivery") or {}
    if (result.get("status") != "parsed_with_unknowns"
        or delivery.get("data_version") not in profile.get("data_versions", [])
        or delivery.get("head_basis") != profile.get("head_basis")):
        return result
    applied = []
    for name, stream in result.get("streams", {}).items():
        if not stream.get("topic"):
            continue
        if name.endswith("_pose") and not stream.get("position_unit"):
            stream["position_unit"] = {"unit": profile["position_unit"],
                "source": profile["position_unit_source"], "authority": "user_confirmation"}
            applied.append({"stream": name, "setting": "position_unit", **stream["position_unit"]})
        if not stream.get("expected_rate") and name in profile.get("expected_rate_hz", {}):
            stream["expected_rate"] = {"hz": profile["expected_rate_hz"][name],
                "source": profile["rate_source"], "authority": "configured_dataset_baseline"}
            applied.append({"stream": name, "setting": "expected_rate", **stream["expected_rate"]})
    result["configured_profile"] = {"id": profile["id"], "applied": applied,
        "note": "Explicit configured assumptions; original metadata unknowns are retained."}
    return result
