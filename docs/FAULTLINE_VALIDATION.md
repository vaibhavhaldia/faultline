# Release validation

Validated locally on macOS with Python 3.14.5 and Node 22.23.2.

- Full Python suite: **732 passed**, plus 8 subtests. Combined branch-aware coverage: **80.57%**.
- Faultline-specific suite: **35 passed**, **89.34%** branch-aware coverage.
- TypeScript impact suite: **8 passed**, including Python/TypeScript parity across 54 change/depth/inference combinations.
- TypeScript type check: passed.
- Python lint: passed across the repository.
- Python wheel and source distribution: built successfully.
- Web production static export: built successfully, including `/` and the 404 page.
- Local route: HTTP 200; preview handed to Codex.
- MIT license: original notice retained verbatim; new-work attribution recorded in NOTICE.

The initial restricted-environment run could not bind dashboard sockets or download the tokenizer; rerunning with the necessary environment access passed. No upstream assertion was weakened to obtain the result. Two non-failing warnings relate to Hypothesis discovery and SQLite resource cleanup in tests/upstream code.

The optional WebMCP integration is feature-detected. No supported live WebMCP validation context was available, so its browser registration/execute lifecycle is not claimed as verified. Interactive browser automation and screenshot QA were not performed; static build, type, engine and HTTP checks are the recorded verification.

## Product limits tested or documented

Cycles terminate. Multiple changes retain depth zero. Inferred links can be excluded. Depth truncation is explicit. Event consumers do not propagate changes back into their topics. Graph imports reject invalid endpoints, duplicate IDs/edges and unsupported evidence. Git rename mapping includes old and new paths. The SQLite adapter reads without mutating the source index.

Contract comparison is a structural review aid, not a complete compatibility verdict. There is no runtime telemetry discovery or hosted Python backend. Imported topology stays in browser memory; refreshing resets it. The sample system and its dependency declarations are fictional.

Dependency audit after patched framework/tooling updates and the Sharp 0.35.4 override: **0 vulnerabilities** reported by npm. The Vercel artifact contains only static client assets; no image-processing or server runtime is deployed.
