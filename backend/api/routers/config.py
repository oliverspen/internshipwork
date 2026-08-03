"""Config endpoint — exposes and persists the input_config.json over HTTP."""

import json

from fastapi import APIRouter

from ..schemas import ConfigUpdateRequest
from backend.user_inputs import INPUT_CONFIG_PATH, get_input_config, reload_input_config

router = APIRouter()


@router.get("/")
def get_config():
    """Return the full input configuration (plants, merge options, pressure)."""
    config = get_input_config()
    return {
        "p_bara": config.get("p_bara"),
        "plant_inputs": config.get("plant_inputs", []),
        "merge_pipe_inputs": config.get("merge_pipe_inputs", {}),
        "storage_name": config.get("storage_name", "Storage"),
    }


@router.put("/")
def update_config(body: ConfigUpdateRequest):
    """Persist updated plant inputs, merge options, and pressure to input_config.json."""
    new_config = {
        "p_bara": body.p_bara,
        "plant_inputs": [p.model_dump() for p in body.plant_inputs],
        "merge_pipe_inputs": {k: v.model_dump() for k, v in body.merge_pipe_inputs.items()},
        "storage_name": (body.storage_name or "Storage").strip() or "Storage",
    }
    INPUT_CONFIG_PATH.write_text(json.dumps(new_config, indent=2), encoding="utf-8")
    reload_input_config()
    return {"status": "saved"}
