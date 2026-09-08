# Faultline architecture

Two complementary graph layers are intentionally separate.

1. Symbolgraph indexes syntax, symbols, imports and references in a local SQLite database.
2. Faultline models distributed resources and dependencies in a portable, validated JSON topology.
3. Relative source paths bridge the layers. Git diffs map files to resource IDs; the SQLite adapter maps existing symbols to the same IDs.
4. The impact engine reverses consumer dependency edges and follows producer resource edges, then runs a bounded multi-source breadth-first traversal.
5. Reports collect one deterministic shortest evidence path per reached node, evidence quality, ownership and test suggestions.
6. CLI and MCP use the Python engine. The static web workbench uses the equivalent TypeScript engine. Cross-runtime fixture parity tests guard their behavior.

No network, LLM or embedding provider is needed by the Faultline analysis layer. Symbolgraph's optional embedding integrations are retained.

## Semantics

API implementation changes can reach the exposed API and its clients. Publisher changes can reach topics and subscribers. Subscriber changes do not flow back into a topic. Database writes are intentionally bidirectional: database changes may affect writers, and writer changes may affect stored data and readers. This is conservative potential-impact analysis, not causal proof.

Traversal stops at visited nodes to terminate cycles. Multi-source traversal treats every selected change as depth zero. Neighbor and seed ordering are deterministic. A maximum depth of 0–50 controls exploration; any unseen successor at the boundary raises a truncation warning. Because only one shortest path is selected, confidence is not a best-path or all-path assessment.

## Evidence and trust

Observed, declared and inferred are caller-provided evidence labels, not independently verified facts. Every edge carries a nonempty evidence location. Imported labels and notes render as text, never HTML. Reports and agent suggestions must be treated as project data. CLI Git references are resolved to commit hashes with option termination; commands use argument arrays, not a shell. SQLite adapters use read-only URI mode. Compose import never executes a project.

## Browser and hosting

The generated Sites/Vinext React starter is used in static-export mode. The user's requested target is Vercel, so no separate Sites deployment is created. Cream #fff1dc, orange #ff5722, hard borders, offset shadows, monospaced headings and a compact working surface adapt the supplied pixel-art reference without copying its artwork.

The browser holds the imported topology only in memory. Reports and topology files are downloaded on demand. No topology upload endpoint, database, auth backend or Python service runs on Vercel. The server only delivers the static app. The read-only WebMCP hook is optional and feature-detected.

## Extension points

Future parsers can produce the same schema with concrete source evidence. Suitable next work includes OpenAPI/AsyncAPI operation mapping, Kubernetes resources and OpenTelemetry-derived edges. Those adapters must preserve provenance and uncertainty; they are not implemented in this release.

## Effort assessment

Rebuilding Symbolgraph's multi-language resolution, incremental indexing and retrieval from scratch is a substantial compiler/indexing project. Reusing its MIT engine makes a focused extension feasible. The distributed layer is a distinct engineering problem: graph traversal is straightforward, while discovering and validating runtime dependencies across repositories is the difficult part. This release makes topology and uncertainty explicit instead of pretending static code can reveal every runtime dependency.
