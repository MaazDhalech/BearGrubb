from __future__ import annotations

import argparse
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any, Callable

from classifier import classify_all
from config import DINING_HALLS
from rag import embed_menu
from scraper import fetch_all

logger = logging.getLogger(__name__)

FetchFn = Callable[[str, str], list[dict[str, Any]]]
ClassifyFn = Callable[..., list[dict[str, Any]]]
EmbedFn = Callable[[list[dict[str, Any]]], Any]


@dataclass
class RefreshSummary:
    menu_date: str
    requested_hall: str
    fetched_halls: list[str] = field(default_factory=list)
    failed_halls: list[str] = field(default_factory=list)
    raw_item_count: int = 0
    classified_item_count: int = 0
    classification_counts: dict[str, int] = field(default_factory=dict)
    embedded: bool = False
    kept_existing_store: bool = False
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.raw_item_count > 0 and self.classified_item_count > 0 and self.embedded

    @property
    def total_failure(self) -> bool:
        return self.raw_item_count == 0 or self.classified_item_count == 0

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["success"] = self.success
        payload["total_failure"] = self.total_failure
        return payload


@dataclass
class RefreshResult:
    store: Any
    summary: RefreshSummary


def refresh_menu_store(
    menu_date: str | None = None,
    hall: str = "ALL",
    existing_db: Any = None,
    cache: dict[str, dict[str, Any]] | None = None,
    fetcher: FetchFn = fetch_all,
    classifier: ClassifyFn = classify_all,
    embedder: EmbedFn = embed_menu,
    build_empty_store_on_total_failure: bool = True,
) -> RefreshResult:
    menu_date = menu_date or str(date.today())
    halls = selected_halls(hall)
    summary = RefreshSummary(menu_date=menu_date, requested_hall=hall)
    raw_items: list[dict[str, Any]] = []

    for dining_hall in halls:
        try:
            hall_items = fetcher(menu_date, dining_hall)
        except Exception as exc:
            summary.failed_halls.append(dining_hall)
            summary.errors.append(f"{dining_hall}: fetch failed: {exc}")
            logger.exception("Menu refresh fetch failed for %s on %s", dining_hall, menu_date)
            continue

        if not hall_items:
            summary.failed_halls.append(dining_hall)
            summary.errors.append(f"{dining_hall}: fetched 0 items")
            logger.warning("Menu refresh fetched 0 items for %s on %s", dining_hall, menu_date)
            continue

        summary.fetched_halls.append(dining_hall)
        raw_items.extend(hall_items)

    summary.raw_item_count = len(raw_items)
    if not raw_items:
        summary.kept_existing_store = existing_db is not None
        if existing_db is not None:
            return RefreshResult(store=existing_db, summary=summary)
        if build_empty_store_on_total_failure:
            return RefreshResult(store=embedder([]), summary=summary)
        return RefreshResult(store=None, summary=summary)

    try:
        classified_items = classifier(raw_items, cache=cache)
    except Exception as exc:
        summary.errors.append(f"classification failed: {exc}")
        summary.kept_existing_store = existing_db is not None
        logger.exception("Menu refresh classification failed for %s", menu_date)
        return RefreshResult(store=existing_db, summary=summary)

    summary.classified_item_count = len(classified_items)
    summary.classification_counts = count_classifications(classified_items)
    if not classified_items:
        summary.errors.append("classification returned 0 items")
        summary.kept_existing_store = existing_db is not None
        return RefreshResult(store=existing_db, summary=summary)

    try:
        store = embedder(classified_items)
    except Exception as exc:
        summary.errors.append(f"embedding failed: {exc}")
        summary.kept_existing_store = existing_db is not None
        logger.exception("Menu refresh embedding failed for %s", menu_date)
        return RefreshResult(store=existing_db, summary=summary)

    summary.embedded = True
    return RefreshResult(store=store, summary=summary)


def selected_halls(hall: str) -> list[str]:
    allowed = set(DINING_HALLS) | {"ALL"}
    if hall not in allowed:
        raise ValueError(f"Unsupported dining hall: {hall}")
    if hall == "ALL":
        return list(DINING_HALLS)
    return [hall]


def count_classifications(items: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"HALAL": 0, "NOT_HALAL": 0, "UNCERTAIN": 0}
    for item in items:
        status = str(item.get("halal_status") or "UNCERTAIN").upper()
        counts[status if status in counts else "UNCERTAIN"] += 1
    return counts


def format_summary(summary: RefreshSummary) -> str:
    status = "succeeded" if summary.success else "failed"
    lines = [
        f"Menu refresh {status} for {summary.menu_date}",
        f"Requested hall: {summary.requested_hall}",
        f"Fetched halls: {', '.join(summary.fetched_halls) or 'None'}",
        f"Failed halls: {', '.join(summary.failed_halls) or 'None'}",
        f"Raw items: {summary.raw_item_count}",
        f"Classified items: {summary.classified_item_count}",
        f"Classification counts: {summary.classification_counts}",
        f"Embedded new store: {summary.embedded}",
        f"Kept existing store: {summary.kept_existing_store}",
    ]
    if summary.errors:
        lines.append("Errors:")
        lines.extend(f"- {error}" for error in summary.errors)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Refresh BearGrub AI menu data")
    parser.add_argument("--date", default=str(date.today()), help="Menu date in YYYY-MM-DD format")
    parser.add_argument("--hall", default="ALL", choices=[*DINING_HALLS.keys(), "ALL"])
    parser.add_argument("--json", action="store_true", help="Print machine-readable refresh summary")
    args = parser.parse_args(argv)

    result = refresh_menu_store(
        menu_date=args.date,
        hall=args.hall,
        build_empty_store_on_total_failure=False,
    )
    if args.json:
        print(json.dumps(result.summary.to_dict(), indent=2, sort_keys=True))
    else:
        print(format_summary(result.summary))
    return 0 if result.summary.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
