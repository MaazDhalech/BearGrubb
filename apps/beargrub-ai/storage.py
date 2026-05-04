from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from config import MENU_DATA_PATH


@dataclass(frozen=True)
class SnapshotRecord:
    menu_date: str
    requested_hall: str
    raw_item_count: int
    classified_item_count: int
    snapshot_dir: str


class LocalMenuStorage:
    """Filesystem-backed menu snapshot store for local dev and single-node deploys."""

    def __init__(self, base_path: str | Path = MENU_DATA_PATH) -> None:
        self.base_path = Path(base_path)

    def save_snapshot(
        self,
        menu_date: str,
        requested_hall: str,
        raw_items: list[dict[str, Any]],
        classified_items: list[dict[str, Any]],
        summary: dict[str, Any],
    ) -> SnapshotRecord:
        snapshot_dir = self.snapshot_dir(menu_date, requested_hall)
        snapshot_dir.mkdir(parents=True, exist_ok=True)

        write_json_atomic(snapshot_dir / "raw_items.json", raw_items)
        write_json_atomic(snapshot_dir / "classified_items.json", classified_items)
        write_json_atomic(snapshot_dir / "summary.json", summary)

        record = SnapshotRecord(
            menu_date=menu_date,
            requested_hall=requested_hall,
            raw_item_count=len(raw_items),
            classified_item_count=len(classified_items),
            snapshot_dir=str(snapshot_dir),
        )
        write_json_atomic(self.base_path / "latest.json", asdict(record))
        return record

    def load_classified_items(
        self,
        menu_date: str | None = None,
        requested_hall: str | None = None,
    ) -> list[dict[str, Any]]:
        if menu_date and requested_hall:
            path = self.snapshot_dir(menu_date, requested_hall) / "classified_items.json"
        else:
            latest = self.load_latest_record()
            if latest is None:
                return []
            path = Path(latest.snapshot_dir) / "classified_items.json"
        data = read_json(path, default=[])
        return data if isinstance(data, list) else []

    def load_latest_record(self) -> SnapshotRecord | None:
        data = read_json(self.base_path / "latest.json", default=None)
        if not isinstance(data, dict):
            return None
        try:
            return SnapshotRecord(
                menu_date=str(data["menu_date"]),
                requested_hall=str(data["requested_hall"]),
                raw_item_count=int(data["raw_item_count"]),
                classified_item_count=int(data["classified_item_count"]),
                snapshot_dir=str(data["snapshot_dir"]),
            )
        except (KeyError, TypeError, ValueError):
            return None

    def snapshot_dir(self, menu_date: str, requested_hall: str) -> Path:
        return self.base_path / "snapshots" / menu_date / safe_component(requested_hall)


def write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def read_json(path: Path, default: Any) -> Any:
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def safe_component(value: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "-" for char in value.strip())
    return "-".join(part for part in cleaned.split("-") if part) or "all"
