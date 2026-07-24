"""Human-readable terminal rendering for Sanya's persisted records."""

from __future__ import annotations

import textwrap
from collections.abc import Iterable
from sqlite3 import Row


TABLE_NAMES = {
    "sources": "Sources",
    "crawls": "Crawls",
    "pages": "Pages",
    "jobs": "Jobs",
    "revisions": "Job revisions",
    "queue": "Crawl queue",
}

LIST_COLUMNS = {
    "sources": ("id", "name", "enabled", "crawl_delay_ms", "base_url", "created_at"),
    "crawls": ("id", "source_id", "status", "started_at", "finished_at", "pages_visited", "jobs_discovered"),
    "pages": ("id", "crawl_id", "http_status", "fetched_at", "url"),
    "jobs": ("id", "source_id", "source_identifier", "active", "first_seen", "last_seen"),
    "revisions": ("id", "job_id", "created_at", "title", "company", "location", "content_hash"),
    "queue": ("id", "crawl_id", "status", "attempts", "updated_at", "url"),
}
BOOLEAN_FIELDS = {"active", "enabled"}


def render_records(table: str, rows: Iterable[Row], detailed: bool = False) -> str:
    records = list(rows)
    name = TABLE_NAMES[table]
    if not records:
        return f"No {name.lower()} found."
    if detailed:
        return "\n\n".join(_render_detail(name.removesuffix("s"), row) for row in records)
    return _render_table(LIST_COLUMNS[table], records)


def render_job_detail(job: Row, revisions: Iterable[Row]) -> str:
    """Render a job identity together with its immutable content history."""
    history = list(revisions)
    output = [_render_detail("Job", job)]
    if not history:
        output.append("Current revision\n  No immutable content revision has been stored.")
        return "\n\n".join(output)

    output.append("Current revision\n" + _render_detail("Revision", history[0]))
    if len(history) > 1:
        output.append("Revision history\n" + _render_table(LIST_COLUMNS["revisions"], history))
    else:
        output.append("Revision history\n  1 immutable revision stored.")
    return "\n\n".join(output)


def render_rows(columns: tuple[str, ...], rows: Iterable[Row]) -> str:
    """Render an arbitrary read-only query for terminal inspection."""
    records = list(rows)
    if not records:
        return "No records found."
    return _render_table(columns, records)


def _render_detail(name: str, row: Row) -> str:
    lines = [f"{name} #{row['id']}"]
    for key, value in dict(row).items():
        label = key.replace("_", " ").capitalize()
        rendered = _value(value, boolean=key in BOOLEAN_FIELDS)
        if "\n" in rendered or len(rendered) > 88:
            lines.append(f"  {label}:")
            lines.extend(f"    {line}" for line in textwrap.wrap(rendered, width=88) or ["(empty)"])
        else:
            lines.append(f"  {label}: {rendered}")
    return "\n".join(lines)


def _render_table(columns: tuple[str, ...], rows: list[Row]) -> str:
    headers = [column.replace("_", " ").upper() for column in columns]
    values = [[_shorten(_value(row[column], boolean=column in BOOLEAN_FIELDS)) for column in columns] for row in rows]
    widths = [max(len(header), *(len(row[index]) for row in values)) for index, header in enumerate(headers)]
    header = "  ".join(value.ljust(widths[index]) for index, value in enumerate(headers))
    divider = "  ".join("-" * width for width in widths)
    body = ["  ".join(value.ljust(widths[index]) for index, value in enumerate(row)) for row in values]
    return "\n".join([header, divider, *body])


def _value(value: object, *, boolean: bool = False) -> str:
    if value is None:
        return "-"
    if boolean:
        return "yes" if bool(value) else "no"
    return str(value)


def _shorten(value: str, width: int = 52) -> str:
    return value if len(value) <= width else f"{value[:width - 3]}..."
