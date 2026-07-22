# Ping

Ping is a small, respectful web spider for labour market observatories. It
traverses configured sources, fetches pages politely, extracts structured job
advertisements, hashes normalized content, and archives immutable revisions in
SQLite.

The labour market is the first domain, not the limit of the engine. With clean
extractors, the same core can archive theatre listings, government tenders, real
estate notices, procurement notices, or any other source that can be represented
as structured observations.

## Principles

Ping is deliberately boring.

It is not an AI agent.

It does not reason.

It does not classify.

It does not infer.

Its job is to observe the world faithfully, preserve what it finds, and build a
historical record that other systems can reason about later.

Information is immutable.

History is never discarded.

The database is the source of truth.

## Logging

Ping is a developer tool.

Silence is considered a bug.

Every meaningful operation should be logged to the console. The operator should
always know what Ping is doing, why it is doing it, what happened, why something
was skipped, why something failed, and what Ping intends to do next.

The terminal is the primary debugging interface. Developers should not need to
attach a debugger or read source code to understand runtime behaviour.

Every decision made by Ping should be observable. If Ping decides not to do
something, it should explain why.

Each log message identifies the subsystem:

```text
Spider     Starting crawl: bongthom
Spider     Visiting https://...
Fetcher    GET https://...
Fetcher    HTTP 200 (183 KB)
Spider     42 links discovered
Extractor  Parsing job advertisement
Extractor  Title: IT Administrator
Hasher     SHA256 5a183f...
Archivist  Existing job found
Archivist  Content unchanged
Spider     Sleeping 2.3 seconds
```

Default logging is informative but concise. Verbose logging is designed for
debugging without source changes and includes discovered URLs, queued URLs,
HTTP retries, backoff timing, parsed fields, generated hashes, SQL transactions,
queue sizes, skipped URLs, rejected pages, and elapsed time for pipeline stages.

## MVP

This repository implements the MVP from the technical specification:

- Python CLI
- SQLite storage
- resumable crawl queue
- polite fetcher with retries, backoff, timeout, rate limiting, and jitter
- source-specific extractor interface
- initial `bongthom` source/extractor

## Usage

Run from the repository root:

```powershell
python -m ping sources
python -m ping crawl bongthom --max-pages 25
python -m ping resume bongthom --max-pages 25
python -m ping stats
```

Use `--verbose` before the command to expose every runtime decision:

```powershell
python -m ping --verbose crawl bongthom --max-pages 25
```

By default Ping stores data in `ping.sqlite3`. Use `--db` to choose another path:

```powershell
python -m ping --db data/ping.sqlite3 crawl bongthom
```

The BongThom seed URL can be overridden without changing code:

```powershell
$env:PING_BONGTHOM_SEED_URL = "https://example.com/jobs"
python -m ping crawl bongthom
```

## CLI

```text
ping crawl [source]
ping resume [source]
ping stats
ping sources
```

The installed console command is available after editable installation:

```powershell
python -m pip install -e .
ping sources
```

## Design

The components deliberately have narrow responsibilities:

- `ping.spider` traverses sources and discovers pages.
- `ping.fetcher` performs HTTP requests and returns raw HTML.
- `ping.extractors` convert source-specific HTML into normalized `JobRecord` objects.
- `ping.hasher` creates deterministic SHA-256 content identities.
- `ping.archivist` owns SQLite persistence, revision history, and crawl state.
- `ping.app` coordinates the command-line crawl workflow.

The database is append-only for job revisions. Existing jobs get `last_seen` updates;
meaningful content edits create new immutable revisions.
