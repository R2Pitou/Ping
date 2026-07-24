# REST API Design

The REST API is a versioned adapter over application services. Route handlers
validate input, call shared read/write services, and serialize results. They do
not query SQLite directly. The CLI and GUI must use the same service contracts
so that one client cannot see a different interpretation of the archive.

The implementation target is FastAPI, installed as an optional `api` extra.
The core package remains standard-library-first and starts with no web server.

## Versioning and behavior

All routes begin with `/api/v1`. Additive fields and endpoints are compatible;
removing or changing field meaning requires `/api/v2`. List endpoints use
`limit` (default 50, maximum 200) and a stable cursor before data grows beyond
simple limits. All mutation responses include an operation ID. All errors use:

```json
{"error": {"code": "not_found", "message": "Job 42 was not found."}}
```

## Resources

| Resource | Endpoints | Notes |
| --- | --- | --- |
| Jobs | `GET /jobs`, `GET /jobs/{id}`, `GET /jobs/{id}/revisions` | Current view plus immutable evidence history. |
| Companies | `GET /companies`, `GET /companies/{name}/jobs` | Derived from latest revisions; no separate canonical company table yet. |
| Pages | `GET /pages`, `GET /pages/{id}` | Fetch evidence, status, hashes, crawl reference. |
| Sources | `GET /sources`, `GET /sources/{id}` | Source configuration and observed state. |
| Crawl | `GET /crawls`, `GET /crawls/{id}`, `POST /crawls` | Start is a controlled command, never a raw URL execution endpoint. |
| Search | `GET /search` | `mode=keyword|semantic|hybrid`, explicit filters and score explanation. |
| Stats | `GET /stats` | Archive counters and source summaries. |
| Health | `GET /health` | Database integrity and index freshness. |

The machine-readable starting contract is [openapi.yaml](openapi.yaml). It is
intentionally small: it anchors naming and response shape before FastAPI is
introduced. FastAPI-generated OpenAPI must replace this hand-maintained file
once the adapter exists, with contract tests ensuring the same paths and models.
