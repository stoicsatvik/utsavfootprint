"""Read-only audit of historical SQLite observation timestamp representations.

Exit 0: all stored timestamp fields are explicit, parseable, and consistent.
Exit 2: at least one row requires operator review.
Exit 1: database unavailable or schema unreadable.

This tool never infers a timezone, changes records, or quarantines evidence.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path


def parse_instant(value: object, row_id: str, field: str, issues: list[dict]):
    if not isinstance(value, str):
        issues.append({"id": row_id, "field": field, "code": "invalid_timestamp"})
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        issues.append({"id": row_id, "field": field, "code": "invalid_timestamp"})
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        issues.append({"id": row_id, "field": field, "code": "naive_timestamp"})
        return None
    return parsed.astimezone(UTC)


def audit_database(path: Path) -> tuple[dict, int]:
    if not path.is_file():
        return {"error": "database_unavailable"}, 1

    issues: list[dict] = []
    total_rows = 0
    try:
        # SQLite mode=ro prevents accidental creation and database writes.
        with closing(sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)) as db:
            for row_id, observed, ingested, payload_text in db.execute(
                "SELECT id, observed_at, ingested_at, payload "
                "FROM observations ORDER BY id"
            ):
                total_rows += 1
                column_times = {
                    "observed_at": parse_instant(observed, row_id, "observed_at", issues),
                    "ingested_at": parse_instant(ingested, row_id, "ingested_at", issues),
                }
                try:
                    payload = json.loads(payload_text)
                except (TypeError, ValueError):
                    issues.append({"id": row_id, "field": "payload", "code": "invalid_json"})
                    continue
                if not isinstance(payload, dict):
                    issues.append({"id": row_id, "field": "payload", "code": "invalid_object"})
                    continue
                for field, column_instant in column_times.items():
                    payload_instant = parse_instant(
                        payload.get(field), row_id, f"payload.{field}", issues
                    )
                    if (
                        column_instant is not None
                        and payload_instant is not None
                        and column_instant != payload_instant
                    ):
                        issues.append(
                            {"id": row_id, "field": field, "code": "instant_mismatch"}
                        )
    except (OSError, sqlite3.Error):
        return {"error": "database_unavailable"}, 1

    affected = len({issue["id"] for issue in issues})
    return {
        "total_rows": total_rows,
        "affected_rows": affected,
        "issues": issues,
    }, 2 if affected else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path, help="Path to an existing SQLite database")
    args = parser.parse_args()
    report, exit_code = audit_database(args.database)
    print(json.dumps(report, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
