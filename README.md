# Ping
> ពីងពាង [ping-peang] = spider in Khmer

Ping is a small, polite web spider for the public web. It
traverses configured sources, fetches pages respectfully, 
extracts structured data based on configured rules, 
hashes normalized content, and archives immutable revisions in
SQLite.

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

## Versioning

Ping follows semantic versioning: `major.minor.patch`.

- Patch releases (`x.x.+1`) are automatic for non-breaking implementation
  changes, including fixes, refactors, documentation, logging, tests, typo
  corrections, and small features.
- Minor releases (`x.+1.0`) are automatic when a meaningful engineering
  milestone introduces a usable capability, such as a new subsystem, CLI
  command, scraper, database table, or feature.
- Major releases (`+1.0.0`) are human-only. They mark a public release,
  breaking compatibility, an API redesign, an architecture rewrite, or a
  philosophical shift in what Ping is.

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

Ping has three log levels.

Normal is the default. It shows what a human wants to see: crawl start and
finish, visited pages, HTTP outcomes with timings, jobs parsed, archive
outcomes, sleep intervals, errors, and the final summary.

Verbose shows what a developer needs: queue sizes, HTTP requests and selected
response headers, parser strategy, parsed fields, generated hashes, revision
actions, `last_seen` updates, and component timings.

Trace shows absolutely everything Ping can observe: every SQL statement, every
discovered URL, every queue mutation, every retry/backoff detail, timing, and
raw parser output.

Every log line includes a timestamp and subsystem:

```text
09:12:18 Spider     Starting crawl: bongthom
09:12:18 Spider     Visiting page 1: https://...
09:12:19 Fetcher    HTTP 200 (183 KB, 412 ms)
09:12:19 Extractor  17 job(s) parsed in 14 ms
09:12:19 Archivist  11 inserted, 2 updated, 4 unchanged in 8 ms
09:12:19 Spider     Sleeping 2.1 s
09:12:21 Spider     Crawl complete
```

## MVP

This repository implements the MVP from the technical specification:

- Python CLI
- SQLite storage
- resumable crawl queue
- polite fetcher with  retries, backoff, timeout, rate limiting, and jitter
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

Use `--verbose` before the command for developer-level detail:

```powershell
python -m ping --verbose crawl bongthom --max-pages 25
```

Use `--trace` when you want the terminal equivalent of a packet capture:

```powershell
python -m ping --trace crawl bongthom --max-pages 25
```

Every subsystem is executable independently:

```powershell
python -m ping fetch https://example.com/jobs
python -m ping extract page.html --source bongthom --url https://www.bongthom.com/job_detail/various_positions_39416.html
python -m ping hash job.json
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
python -m ping crawl [source]
python -m ping resume [source]
python -m ping stats
python -m ping sources
python -m ping fetch URL
python -m ping extract file.html
python -m ping hash file.json
```

On Windows, `ping` is reserved by the built-in network diagnostic command. The
installed console command is therefore `ping-spider`:

```powershell
python -m pip install -e .
ping-spider crawl bongthom --max-pages 25
```

## Design

The components deliberately have narrow responsibilities:

| Public name | Technical responsibility | Descriptive implementation |
| --- | --- | --- |
| `Ping` | Spider and traversal | `ping.spider.Spider` |
| `Yok` | Fetch pages | `ping.fetcher.Fetcher` |
| `Dok` | Extract structured records | `ping.extractors.Extractor` |
| `Tra` | Stamp content identity | `ping.hasher` |
| `Sanya` | Commit and preserve history | `ping.archivist.Archivist` |
| `Rok` | Find records in the archive | `ping.rok.Rok` |

The Khmer names are concise public vocabulary, not a replacement for technical
meaning. The implementation retains descriptive module and class names so that
the code remains easy to read and navigate.

```python
from ping import Dok, Ping, Rok, Sanya, Tra, Yok

ping.crawl()
yok.fetch(url)
dok.get(html, page_url)
tra.hash(job)
sanya.commit(crawl_id, source_id, job)
rok.find(query)
```

`ping.app` coordinates the command-line crawl workflow; it is intentionally
separate from traversal.

The database is append-only for job revisions. Existing jobs get `last_seen` updates;
meaningful content edits create new immutable revisions.
