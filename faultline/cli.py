"""Local CLI. Reports are portable JSON accepted directly by the web workbench."""

import argparse
import json
import sqlite3
import subprocess
from contextlib import closing
from pathlib import Path

from faultline.compose import import_compose
from faultline.contracts import compare
from faultline.engine import agent_brief, analyze, path_seeds, validate


def load(path):
    p = Path(path)
    if p.stat().st_size > 2_000_000:
        raise ValueError("Input exceeds the 2 MB limit")
    return json.loads(p.read_text())


def main():
    parser = argparse.ArgumentParser(
        prog="faultline", description="Trace distributed-system change impact"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    impact = sub.add_parser(
        "impact", help="Analyze declared topology and optional Git changes"
    )
    impact.add_argument("topology")
    impact.add_argument("--changed", action="append", default=[])
    impact.add_argument("--file", action="append", default=[])
    impact.add_argument(
        "--git-base", help="Include committed changes from this merge base to HEAD"
    )
    impact.add_argument("--repo", default=".")
    impact.add_argument("--max-depth", type=int, default=12)
    impact.add_argument("--exclude-inferred", action="store_true")
    impact.add_argument("--format", choices=["json", "markdown"], default="json")
    check = sub.add_parser("validate")
    check.add_argument("topology")
    diff = sub.add_parser(
        "contract-diff", help="Flag structural contract changes for review"
    )
    diff.add_argument("before")
    diff.add_argument("after")
    symbols = sub.add_parser(
        "symbols", help="Map existing Symbolgraph symbols to topology nodes"
    )
    symbols.add_argument("topology")
    symbols.add_argument("--index", required=True)
    compose = sub.add_parser(
        "import-compose", help="Convert normalized Docker Compose JSON into a topology"
    )
    compose.add_argument("compose_json")
    args = parser.parse_args()
    try:
        if args.command == "import-compose":
            print(
                json.dumps(
                    import_compose(load(args.compose_json), args.compose_json), indent=2
                )
            )
            return
        if args.command == "contract-diff":
            print(json.dumps(compare(load(args.before), load(args.after)), indent=2))
            return
        data = validate(load(args.topology))
        if args.command == "validate":
            print(
                f"Valid topology: {len(data['nodes'])} nodes, {len(data['edges'])} edges"
            )
            return
        if args.command == "symbols":
            with closing(
                sqlite3.connect(
                    Path(args.index).resolve().as_uri() + "?mode=ro", uri=True
                )
            ) as db:
                rows = db.execute(
                    "SELECT symbol_id, qualified_name, relative_path, start_line FROM symbols ORDER BY relative_path, start_line"
                ).fetchall()
            print(
                json.dumps(
                    [
                        {
                            "symbol_id": sid,
                            "name": name,
                            "file": path,
                            "line": line,
                            "nodes": path_seeds(data, [path])[0],
                        }
                        for sid, name, path, line in rows
                    ],
                    indent=2,
                )
            )
            return
        paths = args.file
        if args.git_base:
            base = subprocess.run(
                [
                    "git",
                    "-C",
                    args.repo,
                    "rev-parse",
                    "--verify",
                    "--end-of-options",
                    args.git_base + "^{commit}",
                ],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            raw = subprocess.run(
                [
                    "git",
                    "-C",
                    args.repo,
                    "diff",
                    "--name-only",
                    "--no-renames",
                    "-z",
                    base + "...HEAD",
                    "--",
                ],
                check=True,
                capture_output=True,
            ).stdout
            paths += [
                p.decode("utf-8", errors="replace") for p in raw.split(b"\0") if p
            ]
        mapped, unmatched = path_seeds(data, paths)
        report = analyze(
            data,
            args.changed + mapped,
            max_depth=args.max_depth,
            include_inferred=not args.exclude_inferred,
        )
        report["unmatched_paths"] = unmatched
        print(
            agent_brief(report)
            if args.format == "markdown"
            else json.dumps(report, indent=2)
        )
    except (ValueError, OSError, sqlite3.Error, subprocess.CalledProcessError) as exc:
        parser.exit(2, f"faultline: {exc}\n")


if __name__ == "__main__":
    main()
