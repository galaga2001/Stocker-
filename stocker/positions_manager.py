"""Positions manager — save and load named positions to a local YAML file."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import yaml

DEFAULT_PATH = Path("positions.yaml")


def load_positions(path: Path = DEFAULT_PATH) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    return data.get("positions", [])


def save_positions(positions: List[Dict[str, Any]], path: Path = DEFAULT_PATH) -> None:
    with open(path, "w") as f:
        yaml.safe_dump({"positions": positions}, f, default_flow_style=False)


def add_or_update(
    positions: List[Dict[str, Any]],
    new_pos: Dict[str, Any],
) -> List[Dict[str, Any]]:
    name = new_pos["name"]
    for i, p in enumerate(positions):
        if p["name"] == name:
            positions[i] = new_pos
            return positions
    positions.append(new_pos)
    return positions


def delete(positions: List[Dict[str, Any]], name: str) -> List[Dict[str, Any]]:
    return [p for p in positions if p["name"] != name]
