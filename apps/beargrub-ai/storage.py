from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from config import MENU_DATA_PATH, S3_BUCKET

logger = logging.getLogger(__name__)


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


class S3MenuStorage:
    """S3-backed menu snapshot store for deployed environments.

    S3 layout:
      {prefix}/snapshots/{date}/{hall}/classified_items.json
      {prefix}/snapshots/{date}/{hall}/raw_items.json
      {prefix}/snapshots/{date}/{hall}/summary.json
      {prefix}/classification_cache.json
      {prefix}/latest.json
    """

    def __init__(self, bucket: str, prefix: str = "beargrub") -> None:
        import boto3  # optional dependency — only required in deployed envs
        self.bucket = bucket
        self.prefix = prefix.rstrip("/")
        self._s3 = boto3.client("s3")

    def _key(self, *parts: str) -> str:
        return "/".join([self.prefix, *parts])

    def save_snapshot(
        self,
        menu_date: str,
        requested_hall: str,
        raw_items: list[dict[str, Any]],
        classified_items: list[dict[str, Any]],
        summary: dict[str, Any],
    ) -> SnapshotRecord:
        hall_slug = safe_component(requested_hall)
        base = f"snapshots/{menu_date}/{hall_slug}"
        self._put_json(self._key(base, "raw_items.json"), raw_items)
        self._put_json(self._key(base, "classified_items.json"), classified_items)
        self._put_json(self._key(base, "summary.json"), summary)
        record = SnapshotRecord(
            menu_date=menu_date,
            requested_hall=requested_hall,
            raw_item_count=len(raw_items),
            classified_item_count=len(classified_items),
            snapshot_dir=f"s3://{self.bucket}/{self._key(base)}",
        )
        self._put_json(self._key("latest.json"), asdict(record))
        logger.info("Saved snapshot to S3: %s", record.snapshot_dir)
        return record

    def load_classified_items(
        self,
        menu_date: str | None = None,
        requested_hall: str | None = None,
    ) -> list[dict[str, Any]]:
        if menu_date and requested_hall:
            hall_slug = safe_component(requested_hall)
            key = self._key(f"snapshots/{menu_date}/{hall_slug}", "classified_items.json")
        else:
            latest = self.load_latest_record()
            if latest is None:
                return []
            # derive key from snapshot_dir stored as s3://bucket/prefix/...
            path_in_bucket = latest.snapshot_dir.removeprefix(f"s3://{self.bucket}/")
            key = f"{path_in_bucket}/classified_items.json"
        data = self._get_json(key, default=[])
        return data if isinstance(data, list) else []

    def load_latest_record(self) -> SnapshotRecord | None:
        data = self._get_json(self._key("latest.json"), default=None)
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

    def sync_cache_to_s3(self, local_cache_path: str) -> bool:
        """Upload classification_cache.json to S3. Returns True on success."""
        try:
            self._s3.upload_file(local_cache_path, self.bucket, self._key("classification_cache.json"))
            logger.info("Synced classification cache to S3")
            return True
        except Exception:
            logger.exception("Failed to sync classification cache to S3")
            return False

    def sync_cache_from_s3(self, local_cache_path: str) -> bool:
        """Download classification_cache.json from S3. Returns True on success."""
        try:
            self._s3.download_file(self.bucket, self._key("classification_cache.json"), local_cache_path)
            logger.info("Pulled classification cache from S3")
            return True
        except Exception:
            logger.debug("No classification cache in S3 (first deploy or missing)")
            return False

    def _put_json(self, key: str, payload: Any) -> None:
        body = json.dumps(payload, indent=2, sort_keys=True).encode()
        self._s3.put_object(Bucket=self.bucket, Key=key, Body=body, ContentType="application/json")

    def _get_json(self, key: str, default: Any) -> Any:
        try:
            resp = self._s3.get_object(Bucket=self.bucket, Key=key)
            return json.loads(resp["Body"].read())
        except Exception:
            return default


def storage_from_env() -> S3MenuStorage | LocalMenuStorage:
    """Return S3MenuStorage if S3_BUCKET is configured, else LocalMenuStorage."""
    if S3_BUCKET:
        return S3MenuStorage(bucket=S3_BUCKET)
    return LocalMenuStorage()
