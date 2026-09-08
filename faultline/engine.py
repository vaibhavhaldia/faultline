"""Portable topology and deterministic impact analysis; no network or LLM required.

Edges point from consumer to dependency. Produces/implements edges additionally
propagate changes from a provider to the resource it owns. Confidence is evidence
quality, never a probability of failure.
"""

from __future__ import annotations

from collections import defaultdict, deque
from fnmatch import fnmatchcase
from pathlib import PurePosixPath

KINDS = {"service", "api", "topic", "database", "external"}
RELATIONS = {
    "calls",
    "consumes",
    "publishes",
    "reads",
    "writes",
    "implements",
    "depends_on",
}
FORWARD = {"publishes", "writes", "implements"}
REVERSE = {"calls", "consumes", "reads", "writes", "depends_on"}


def validate(data: dict) -> dict:
    if (
        not isinstance(data, dict)
        or type(data.get("version")) is not int
        or data.get("version") != 1
    ):
        raise ValueError("Expected a version: 1 topology object")
    if "name" in data and not isinstance(data["name"], str):
        raise ValueError("System name must be text")
    nodes, edges = data.get("nodes"), data.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise ValueError("nodes and edges must be arrays")  # noqa: TRY004
    if not 1 <= len(nodes) <= 500 or len(edges) > 5000:
        raise ValueError("Topology must contain 1–500 nodes and at most 5,000 edges")
    ids = set()
    for n in nodes:
        if (
            not isinstance(n, dict)
            or not isinstance(n.get("id"), str)
            or not n["id"].strip()
        ):
            raise ValueError("Each node needs a nonempty string id")
        if (
            n["id"] in ids
            or not isinstance(n.get("kind"), str)
            or n.get("kind") not in KINDS
        ):
            raise ValueError(f"Duplicate id or unsupported node kind: {n['id']}")
        ids.add(n["id"])
        for key in ("label", "owner"):
            if key in n and not isinstance(n[key], str):
                raise ValueError(f"{key} must be text")
        for key in ("paths", "tests"):
            if key in n and (
                not isinstance(n[key], list)
                or any(not isinstance(p, str) for p in n[key])
            ):
                raise ValueError(f"{key} must be an array of strings")
        if any(
            p.startswith("/") or ".." in PurePosixPath(p).parts
            for p in n.get("paths", [])
        ):
            raise ValueError("Node paths must be repository-relative")
    keys = set()
    for e in edges:
        if (
            not isinstance(e, dict)
            or not isinstance(e.get("source"), str)
            or not isinstance(e.get("target"), str)
            or e.get("source") not in ids
            or e.get("target") not in ids
        ):
            raise ValueError("Every edge endpoint must reference a node")
        if (
            not isinstance(e.get("kind"), str)
            or not isinstance(e.get("evidence"), str)
            or e.get("kind") not in RELATIONS
            or e.get("evidence")
            not in {
                "declared",
                "observed",
                "inferred",
            }
        ):
            raise ValueError("Every edge needs a supported kind and evidence quality")
        if not isinstance(e.get("location"), str) or not e["location"].strip():
            raise ValueError("Every edge needs an evidence location")
        key = (e["source"], e["target"], e["kind"])
        if key in keys:
            raise ValueError("Duplicate dependency edge")
        keys.add(key)
    return data


def path_seeds(data: dict, paths: list[str]) -> tuple[list[str], list[str]]:
    seeds, unmatched = set(), []
    for raw in paths:
        path = raw.replace("\\", "/")
        path = path.removeprefix("./")
        matched = False
        for n in data["nodes"]:
            if any(
                fnmatchcase(path, pattern) or path.startswith(pattern.rstrip("/") + "/")
                for pattern in n.get("paths", [])
            ):
                seeds.add(n["id"])
                matched = True
        if not matched:
            unmatched.append(raw)
    return sorted(seeds), unmatched


def analyze(
    data: dict, seeds: list[str], *, max_depth: int = 12, include_inferred: bool = True
) -> dict:
    validate(data)
    if type(max_depth) is not int or not 0 <= max_depth <= 50:
        raise ValueError("max_depth must be an integer from 0 to 50")
    nodes = {n["id"]: n for n in data["nodes"]}
    if not seeds or any(s not in nodes for s in seeds):
        raise ValueError("Select at least one known changed node")
    adjacency = defaultdict(list)
    for i, e in enumerate(data["edges"]):
        if not include_inferred and e["evidence"] == "inferred":
            continue
        if e["kind"] in REVERSE:
            adjacency[e["target"]].append((e["source"], i))
        if e["kind"] in FORWARD:
            adjacency[e["source"]].append((e["target"], i))
    seen = {
        s: {"id": s, "depth": 0, "path": [s], "edge_indices": []}
        for s in sorted(set(seeds))
    }
    queue = deque(seen)
    truncated = False
    while queue:
        current = queue.popleft()
        row = seen[current]
        for target, i in sorted(adjacency[current]):
            if target in seen:
                continue
            if row["depth"] >= max_depth:
                truncated = True
                continue
            seen[target] = {
                "id": target,
                "depth": row["depth"] + 1,
                "path": row["path"] + [target],
                "edge_indices": row["edge_indices"] + [i],
            }
            queue.append(target)
    affected = []
    for row in sorted(seen.values(), key=lambda r: (r["depth"], r["id"])):
        n = nodes[row["id"]]
        evidence = [data["edges"][i] for i in row["edge_indices"]]
        quality = (
            "inferred"
            if any(e["evidence"] == "inferred" for e in evidence)
            else (
                "declared"
                if any(e["evidence"] == "declared" for e in evidence)
                else "observed"
            )
        )
        affected.append(
            {
                **row,
                "kind": n["kind"],
                "label": n.get("label", n["id"]),
                "owner": n.get("owner", "Unassigned"),
                "evidence": evidence,
                "confidence": "changed" if row["depth"] == 0 else quality,
            }
        )
    affected_ids = set(seen)
    return {
        "version": 1,
        "name": data.get("name", "System"),
        "seeds": sorted(set(seeds)),
        "affected": affected,
        "truncated": truncated,
        "unaffected": sorted(set(nodes) - affected_ids),
        "owners": sorted(
            {
                n.get("owner", "Unassigned")
                for n in data["nodes"]
                if n["id"] in affected_ids
            }
        ),
        "tests": sorted(
            {
                t
                for n in data["nodes"]
                if n["id"] in affected_ids
                for t in n.get("tests", [])
            }
        ),
        "limitations": [
            "Potential impact based on supplied topology, not a prediction of production failure.",
            "One shortest evidence path per node; missing dependencies are not discoverable here.",
        ],
    }


def agent_brief(report: dict) -> str:
    lines = [
        f"# Faultline impact brief — {report['name']}",
        "",
        "Changed: " + ", ".join(report["seeds"]),
        "",
        "## Potential impact",
    ]
    for n in report["affected"]:
        lines.append(
            f"- {n['label']} ({n['kind']}; {n['owner']}; {n['confidence']}): "
            + " → ".join(n["path"])
        )
        for e in n["evidence"]:
            lines.append(f"  - {e['kind']}: {e['location']} [{e['evidence']}]")
    lines += [
        "",
        "## Suggested checks",
        *[f"- {t}" for t in report["tests"]],
        "",
        "## Limits",
        *[f"- {s}" for s in report["limitations"]],
    ]
    if report["truncated"]:
        lines.append(
            "- Traversal reached the depth limit; increase it before making a release decision."
        )
    if report.get("unmatched_paths"):
        lines.append(
            "- Unmapped changed files: " + ", ".join(report["unmatched_paths"])
        )
    return "\n".join(lines) + "\n"
