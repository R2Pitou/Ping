# Ping Vision

Ping is an evidence platform for labour market observation. It collects public
job advertisements from configured sources, preserves what it observed, and
makes the resulting historical record inspectable and searchable.

The core promise is simple: collect evidence, not pages. A fetched page is an
observation. A normalized job is a durable record. A meaningful change becomes
an immutable revision. Downstream analysis must be able to point back to the
specific observation that supports it.

## Goals

- Preserve an auditable history of public labour-market advertisements.
- Make ordinary archive inspection possible without SQLite tools or SQL.
- Support local-first keyword and semantic discovery over stored evidence.
- Keep sources isolated so a new source can be added without core changes.
- Expose one internal read model to the CLI, API, and desktop interface.
- Make crawler decisions, skipped work, failures, and timing observable.

## Philosophy

Ping is deliberately boring. It is not an AI agent and does not reason,
classify, or infer. Ping observes, normalizes, fingerprints, and preserves.
Future intelligence features are consumers of the record, not crawler
behaviour hidden behind an intelligent-sounding name.

Information is immutable. History is never discarded. SQLite is the source of
truth. Derived indexes, embeddings, dashboards, and search results can always
be rebuilt from Sanya's stored evidence.

## Observability

Silence is a bug. Every important decision should be observable. If Ping does
not fetch, enqueue, parse, index, or return something, it should state why.
Normal logs explain the operator-facing story; verbose logs explain developer
decisions; trace logs expose queue mutations, SQL, retries, and timings. The
same state must be inspectable after the fact through the CLI and API.

## Non-goals

- Circumventing robots directives, rate limits, access controls, or paywalls.
- Treating an extractor guess as a fact without preserving source evidence.
- Deleting historical revisions to make the current view convenient.
- Requiring a cloud model, vector service, or SaaS control plane.
- Building a general-purpose workflow engine before multiple real plugins need
  one.
- Making job recommendations, rankings, employer judgments, or predictions in
  Phase 2.
