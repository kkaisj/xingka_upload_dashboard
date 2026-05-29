import json
from pathlib import Path
from typing import Any

from .global_config_service import load_global_config, save_global_config


def get_brand_profiles_path(root_dir: Path) -> Path:
    return root_dir / "backend" / "brand_profiles.json"


def _clean_regions(raw: Any) -> list[str]:
    seen: set[str] = set()
    regions: list[str] = []
    for item in raw or []:
        region = str(item or "").strip()
        if not region or region in seen:
            continue
        seen.add(region)
        regions.append(region)
    return regions


def _clean_profiles(values: dict[str, Any]) -> dict[str, dict[str, list[str]]]:
    profiles: dict[str, dict[str, list[str]]] = {}
    for raw_brand, raw_profile in values.items():
        brand = str(raw_brand or "").strip()
        if not brand or not isinstance(raw_profile, dict):
            continue
        regions = _clean_regions(raw_profile.get("regions"))
        if regions:
            profiles[brand] = {"regions": regions}
    return profiles


def load_brand_profiles(root_dir: Path) -> dict[str, dict[str, list[str]]]:
    path = get_brand_profiles_path(root_dir)
    if not path.exists():
        cfg = load_global_config(root_dir)
        brand = str(cfg.get("BRAND") or "").strip()
        regions = _clean_regions(str(cfg.get("REGION_CATALOG") or cfg.get("PARALLEL_REGIONS") or "").split(","))
        return {brand: {"regions": regions}} if brand and regions else {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return _clean_profiles(data)


def save_brand_profiles(root_dir: Path, values: dict[str, Any]) -> dict[str, dict[str, list[str]]]:
    profiles = _clean_profiles(values)
    path = get_brand_profiles_path(root_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profiles, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return profiles


def _reset_brand_progress(state_path: Path, brand: str, regions: list[str]) -> dict[str, Any]:
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except Exception:
            state = {}
    else:
        state = {}

    def keep_other_brand_work_id(work_id: Any) -> bool:
        return not str(work_id or "").startswith(f"{brand}|")

    def keep_other_brand_inflight(item: Any) -> bool:
        if not isinstance(item, dict):
            return False
        return str(item.get("brand") or "") != brand and not str(item.get("work_id") or "").startswith(f"{brand}|")

    state["brand"] = brand
    state["stage_index"] = 0
    state["stage_name"] = "upload_oss"
    state["parallel_regions"] = regions
    state["done"] = [str(w) for w in state.get("done", []) if keep_other_brand_work_id(w)]
    state["failed"] = [str(w) for w in state.get("failed", []) if keep_other_brand_work_id(w)]
    state["inflight"] = [i for i in state.get("inflight", []) if keep_other_brand_inflight(i)]
    state.setdefault("attempts", {})
    state.setdefault("accounts", [])

    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return state


def apply_brand_profile(
    root_dir: Path,
    brand: str,
    *,
    reset_progress: bool = False,
    state_path: Path | None = None,
) -> dict[str, Any]:
    clean_brand = str(brand or "").strip()
    profiles = load_brand_profiles(root_dir)
    if clean_brand not in profiles:
        raise KeyError(f"unknown brand profile: {clean_brand}")

    regions = profiles[clean_brand]["regions"]
    config = save_global_config(
        root_dir,
        {
            "BRAND": clean_brand,
            "PARALLEL_REGIONS": ",".join(regions),
            "REGION_CATALOG": ",".join(regions),
        },
    )
    state = None
    if reset_progress:
        state = _reset_brand_progress(state_path or (root_dir / ".task_state.json"), clean_brand, regions)

    return {"brand": clean_brand, "regions": regions, "config": config, "state": state}
