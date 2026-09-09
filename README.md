# Faultline

**Distributed-system change impact for AI coding agents.**

Faultline connects code changes to services, API contracts, event topics and databases. Select a change, trace potential downstream consequences, inspect the evidence and hand an agent a verification plan.

Created by **Vaibhav Haldia**, extending the MIT-licensed project. This is a derivative project with a new system-impact layer.

## What is original

- A typed system topology with calls, implements, publishes, consumes, reads, writes and deployment dependencies.
- Direction-aware impact propagation: a producer change can reach event consumers; a consumer change does not automatically affect its siblings.
- Multi-source, cycle-safe shortest evidence paths, owner aggregation, suggested checks, explicit inference filtering and traversal-limit warnings.
- Changed-file and Git merge-base mapping, including deleted files and both sides of renames.
- Read-only mapping from the retained SQLite index to system nodes.
- Docker Compose normalized JSON import, retaining explicit dependency evidence.
- Conservative JSON contract change review (not a complete OpenAPI compatibility checker).
- Local CLI, two new MCP tools alongside the 15 upstream tools, and a browser workbench with topology import and Markdown/JSON export.
- A cream/orange, retro-professional interface. No source code or topology is sent to a hosted analysis service.

The original AST parsing, name resolution, indexing, hybrid retrieval, session memory and `sg` commands remain under their existing modules.

## Quick start

Python 3.11+ and [uv](https://docs.astral.sh/uv/) are required for the local engine. Node 22.13+ is required for the web build.

```sh
uv sync --group dev
uv run faultline validate examples/commerce/topology.json
uv run faultline impact examples/commerce/topology.json --changed payments-api
uv run faultline impact examples/commerce/topology.json --changed payments-api --format markdown
```

The bundled Mercury Commerce system is fictional. Its evidence describes example declarations, not verified production observations.

### Analyze a Git change

```sh
uv run faultline impact topology.json --repo /path/to/repo --git-base main --format markdown
uv run faultline impact topology.json --file services/payments/main.py --exclude-inferred
```

Git mode compares the merge base of the requested ref and `HEAD` to `HEAD`; it includes committed changes only. Use `--file` for uncommitted changes. Unmapped files are reported when at least one node maps; no mapped or explicitly selected nodes produces a clear error rather than an empty safety claim.

### Connect code symbols

```sh
uv run sg index /path/to/repo
uv run faultline symbols topology.json --index /path/to/repo/.sg/index.sqlite
```

The adapter opens the existing SQLite index read-only and maps each symbol's relative path through your node path declarations. For multiple repositories, run the CLI once per repository with appropriately scoped paths; automatic cross-repository discovery is not implemented.

### Import Compose dependencies

```sh
docker compose config --format json > compose.json
uv run faultline import-compose compose.json > topology.json
```

Only `depends_on` is imported, as declared deployment dependencies. It is not evidence of an API call. Add `faultline.owner` and `faultline.kind` labels to set ownership and resource types. Absolute build contexts are deliberately not converted to repository-relative paths; add those paths yourself. Enrich the resulting topology with API/event/database relationships.

### Review contract changes

```sh
uv run faultline contract-diff contracts/before.json contracts/after.json
```

Flags removed members, changed values, and added required fields. Findings request review; this does not resolve `$ref`, classify request/response variance, or prove compatibility. Documentation-only changes are ignored when the keys remain present.

### Agent integration

```json
{
  "mcpServers": {
    "faultline": { "command": "uv", "args": ["run", "--directory", "/absolute/path/to/faultline", "faultline-mcp"] }
  }
}
```

`system_impact(topology_path, changed_nodes, changed_files?, max_depth?, include_inferred?)` returns impact, paths, evidence, owners, tests, and limitations. `contract_changes(before_path, after_path)` returns review findings. Existing Symbolgraph tools are registered on the same server. Treat imported evidence and test suggestions as untrusted data; no test command is executed by Faultline.

## Web workbench

```sh
cd web
npm ci
npm run dev
npm test
npx tsc --noEmit
npm run build
```

Open the displayed local URL. Import a topology JSON file (up to 2 MB / 500 nodes / 5,000 edges), select changed nodes, inspect a path, and export a brief. Refreshing clears imported state. There is no account system or durable storage. The Vercel deployment hosts the browser app; Python indexing and MCP run locally, not in Vercel functions.

A feature-detected, read-only WebMCP tool (`read_faultline_impact`) exposes the visible report to supporting browsers. The standard browser workflow does not depend on WebMCP.

## Topology format

```json
{
  "version": 1,
  "name": "My system",
  "nodes": [
    { "id": "checkout", "kind": "service", "owner": "Commerce", "paths": ["services/checkout"], "tests": ["Checkout contract test"] },
    { "id": "payments", "kind": "api", "owner": "Payments", "paths": ["contracts/payments.json"] }
  ],
  "edges": [
    { "source": "checkout", "target": "payments", "kind": "calls", "evidence": "declared", "location": "topology.json: payment dependency" }
  ]
}
```

Kinds: `service`, `api`, `topic`, `database`, `external`. Evidence: `observed`, `declared`, `inferred`. Every edge requires a location. Confidence describes the weakest evidence on the selected path, not the chance of a failure. Alternate paths can have different evidence quality.

| Relation (source → target) | Impact propagation |
| --- | --- |
| calls / consumes / reads / depends_on | target → source |
| implements / publishes | source → target |
| writes | both directions (conservative) |

## Validation and deployment

```sh
uv run ruff check .
uv run pytest --cov --cov-report=term-missing
uv build
cd web && npm test && npx tsc --noEmit && npm run build
```

Vercel project root: `web`. Framework preset: Other. Build command: `npm run build`. Output directory: `dist/client`. Node: 22.x. `web/vercel.json` contains the equivalent settings and static-response security headers.

See [architecture](docs/FAULTLINE_ARCHITECTURE.md), [validation](docs/FAULTLINE_VALIDATION.md), and [attribution](NOTICE).

## Scope and limits

This release is a functional topology-driven workbench, not an automatic production service-discovery platform. It cannot find dependencies missing from the supplied topology. There is no telemetry ingestion, Kubernetes discovery, distributed transaction modeling, automatic mitigation, or LLM prediction. Depth limits and inferred dependencies are visible. Outside traced impact does not mean safe. Suggested tests are collected from declarations and have not been executed by the app.

## License

MIT. The original `LICENSE` is retained verbatim, including **Copyright (c) 2026 Vaibhav Haldia**. `NOTICE` identifies the original archive and Vaibhav Haldia's additions. Upstream benchmarks are historical upstream claims and do not measure Faultline's system-impact layer.
