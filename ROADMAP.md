# Roadmap

This roadmap is ordered to protect the archive first. A milestone is complete
only when it has a documented interface, focused tests, observable outcomes,
and no hidden operational dependency.

## Phase 1: Evidence archive

Complete: spider traversal, polite fetcher, source extractor, deterministic
hashing, SQLite persistence, immutable revisions, resumable queue, structured
logging, and base inspection CLI.

## Phase 2: Platform foundation

In progress: shared inspection service and inspection-command aliases.

1. Complete the inspection CLI: `jobs`, `show`, `pages`, `companies`,
   `crawl-history`, `revisions`, `search`, `doctor`, and `dump`.
2. Add FTS5 migration and a rebuildable revision text projection.
3. Add local embedding model adapter, embedding metadata, queue/run records,
   and deterministic backfill/retry commands.
4. Add hybrid search service and explainable scores.
5. Implement a versioned FastAPI adapter with generated OpenAPI output.
6. Implement a desktop-first GUI against that API, beginning with read-only
   inspection and job/revision history.

## Phase 3: Operations at scale

1. Move each source into an independently loadable plugin package.
2. Add validated configuration and plugin discovery.
3. Add scheduling, incremental crawl policies, crawl monitor, and retained
   structured logs.
4. Add notifications for crawl failure, source drift, and saved-search matches.
5. Add multiple sources with extractor fixture suites.

## Phase 4: Assisted labour-market intelligence

1. Build evidence-linked trend detection over revisions.
2. Add reviewed skill extraction with source spans and confidence.
3. Add employer profiles derived from observed evidence.
4. Add optional local AI assistance behind explicit, inspectable jobs.

No Phase 4 feature may rewrite source evidence or hide its supporting revisions.
