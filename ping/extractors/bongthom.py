from __future__ import annotations

import re
from html import unescape
from html.parser import HTMLParser
from urllib.parse import parse_qs, urljoin, urlparse

from ping.logging import NULL_LOGGER, PingLogger
from ping.models import JobRecord

from .base import Extractor


JOB_ID_RE = re.compile(r"(?:job[_-]?detail|jobs?)[^\d]*(\d+)", re.IGNORECASE)
SPACE_RE = re.compile(r"\s+")
KNOWN_LABELS = ("Company", "Location", "Salary", "Type", "Closing Date")


class _HTMLTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self.title_parts: list[str] = []
        self.h1_parts: list[str] = []
        self.meta: dict[str, str] = {}
        self._tag_stack: list[str] = []
        self._current_meta_name: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key.lower(): value for key, value in attrs if value is not None}
        if tag == "a" and "href" in attrs_dict:
            self.links.append(attrs_dict["href"])
        if tag in {"title", "h1"}:
            self._tag_stack.append(tag)
        if tag == "meta":
            name = attrs_dict.get("name") or attrs_dict.get("property")
            content = attrs_dict.get("content")
            if name and content:
                self.meta[name.lower()] = content

    def handle_endtag(self, tag: str) -> None:
        if self._tag_stack and self._tag_stack[-1] == tag:
            self._tag_stack.pop()

    def handle_data(self, data: str) -> None:
        if not self._tag_stack:
            return
        tag = self._tag_stack[-1]
        if tag == "title":
            self.title_parts.append(data)
        elif tag == "h1":
            self.h1_parts.append(data)

    @property
    def title(self) -> str | None:
        return _clean(" ".join(self.title_parts))

    @property
    def h1(self) -> str | None:
        return _clean(" ".join(self.h1_parts))


class BongThomExtractor(Extractor):
    """Best-effort extractor for BongThom-style job pages.

    The parser intentionally avoids networking and keeps assumptions local to this source.
    It extracts links from anchors and creates a job record only for URLs that expose a
    stable numeric job identifier.
    """

    def __init__(self, logger: PingLogger = NULL_LOGGER) -> None:
        self.logger = logger

    def links(self, html: str, page_url: str) -> set[str]:
        parser = _parse(html)
        base_host = urlparse(page_url).netloc
        discovered: set[str] = set()
        for href in parser.links:
            absolute = urljoin(page_url, href)
            parsed = urlparse(absolute)
            if parsed.scheme not in {"http", "https"}:
                self.logger.verbose("Extractor", f"Rejected link: unsupported scheme {href}")
                continue
            if parsed.netloc != base_host:
                self.logger.verbose("Extractor", f"Rejected link: different host {absolute}")
                continue
            discovered.add(parsed._replace(fragment="").geturl())
        return discovered

    def jobs(self, html: str, page_url: str) -> list[JobRecord]:
        self.logger.verbose("Extractor", "Parsing job advertisement")
        source_identifier = self._source_identifier(page_url)
        if source_identifier is None:
            self.logger.info("Extractor", "Rejected page: no job schema detected")
            return []

        parser = _parse(html)
        self.logger.verbose("Extractor", 'CSS selector ".job-title": not configured; using title and h1 fallback')
        self.logger.trace("Extractor", f"Raw title: {parser.title}")
        self.logger.trace("Extractor", f"Raw h1: {parser.h1}")
        self.logger.trace("Extractor", f"Raw meta: {parser.meta}")
        title = parser.h1 or _strip_site_suffix(parser.title)
        description = _first_present(
            parser.meta.get("description"),
            parser.meta.get("og:description"),
            _body_text(html),
        )
        job = JobRecord(
            source_identifier=source_identifier,
            title=title,
            company=_field_from_text(description, "Company"),
            location=_field_from_text(description, "Location"),
            salary=_field_from_text(description, "Salary"),
            employment_type=_field_from_text(description, "Type"),
            description=description,
            application_url=page_url,
            closing_date=_field_from_text(description, "Closing Date"),
        )
        self._log_job(job)
        return [job]

    def _source_identifier(self, page_url: str) -> str | None:
        parsed = urlparse(page_url)
        match = JOB_ID_RE.search(parsed.path)
        if match:
            return f"bongthom:{match.group(1)}"

        query = parse_qs(parsed.query)
        for key in ("id", "job_id", "jobid"):
            if key in query and query[key]:
                value = query[key][0]
                if value.isdigit():
                    return f"bongthom:{value}"
        return None

    def _log_job(self, job: JobRecord) -> None:
        self.logger.verbose("Extractor", f"Source ID: {job.source_identifier}")
        for label, value in (
            ("Title", job.title),
            ("Company", job.company),
            ("Location", job.location),
            ("Salary", job.salary),
            ("Employment type", job.employment_type),
            ("Application URL", job.application_url),
            ("Closing date", job.closing_date),
        ):
            if value:
                self.logger.verbose("Extractor", f"{label}: {value}")
            else:
                self.logger.trace("Extractor", f"{label}: not found")


def _parse(html: str) -> _HTMLTextParser:
    parser = _HTMLTextParser()
    parser.feed(html)
    return parser


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = SPACE_RE.sub(" ", unescape(value)).strip()
    return cleaned or None


def _strip_site_suffix(value: str | None) -> str | None:
    cleaned = _clean(value)
    if cleaned is None:
        return None
    return re.split(r"\s+[-|]\s+BongThom", cleaned, maxsplit=1, flags=re.IGNORECASE)[0]


def _first_present(*values: str | None) -> str | None:
    for value in values:
        cleaned = _clean(value)
        if cleaned:
            return cleaned
    return None


def _body_text(html: str) -> str | None:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return _clean(text)


def _field_from_text(text: str | None, label: str) -> str | None:
    if not text:
        return None
    label_pattern = re.compile(
        r"(?P<label>" + "|".join(re.escape(item) for item in KNOWN_LABELS) + r")\s*:",
        re.IGNORECASE,
    )
    matches = list(label_pattern.finditer(text))
    target_index = next(
        (index for index, match in enumerate(matches) if match.group("label").lower() == label.lower()),
        None,
    )
    if target_index is None:
        return None

    start = matches[target_index].end()
    end = matches[target_index + 1].start() if target_index + 1 < len(matches) else len(text)
    return _clean(text[start:end])
