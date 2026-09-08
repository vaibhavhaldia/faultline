import copy
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from faultline.contracts import compare
from faultline.engine import agent_brief, analyze, path_seeds, validate

DEMO = json.loads(Path("examples/commerce/topology.json").read_text())


def ids(report):
    return {n["id"] for n in report["affected"]}


def test_api_change_reaches_consumers_and_events_not_provider():
    r = analyze(DEMO, ["payments-api"])
    assert ids(r) == {
        "payments-api",
        "checkout",
        "orders-topic",
        "analytics",
        "fulfillment",
        "notifications",
    }
    node = next(n for n in r["affected"] if n["id"] == "analytics")
    assert node["path"] == ["payments-api", "checkout", "orders-topic", "analytics"]
    assert node["confidence"] == "inferred"
    assert node["evidence"][-1]["kind"] == "consumes"


def test_consumer_does_not_poison_topic_or_siblings():
    assert ids(analyze(DEMO, ["fulfillment"])) == {"fulfillment"}


def test_provider_publishes_api_and_database_impact():
    assert ids(analyze(DEMO, ["payments"])) == {n["id"] for n in DEMO["nodes"]} - {
        "catalog"
    }


def test_filter_inferred_and_depth_limit():
    r = analyze(DEMO, ["payments-api"], include_inferred=False)
    assert "analytics" not in ids(r)
    limited = analyze(DEMO, ["payments-api"], max_depth=1)
    assert ids(limited) == {"payments-api", "checkout"}
    assert limited["truncated"]
    assert not analyze(DEMO, ["payments-api"])["truncated"]


def test_cycles_and_multiple_seeds_terminate():
    d = copy.deepcopy(DEMO)
    d["edges"].append(
        {
            "source": "payments",
            "target": "checkout",
            "kind": "calls",
            "evidence": "declared",
            "location": "test",
        }
    )
    r = analyze(d, ["payments", "payments-api", "payments"])
    assert len(r["affected"]) == len(ids(r))
    assert next(n for n in r["affected"] if n["id"] == "payments-api")["depth"] == 0


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d["nodes"].append(d["nodes"][0]),
        lambda d: d["edges"][0].update(target="missing"),
        lambda d: d["edges"][0].update(evidence="certain"),
        lambda d: d["edges"][0].update(location=""),
        lambda d: d["nodes"][0].update(paths=["../secret"]),
        lambda d: d["nodes"][0].update(tests="bad"),
        lambda d: d["edges"].append(d["edges"][0]),
    ],
)
def test_invalid_topology_rejected(change):
    d = copy.deepcopy(DEMO)
    change(d)
    with pytest.raises(ValueError):
        validate(d)


@pytest.mark.parametrize(
    "seeds,depth",
    [
        ([], 12),
        (["unknown"], 12),
        (["payments"], 51),
        (["payments"], -1),
        (["payments"], True),
    ],
)
def test_invalid_analysis_rejected(seeds, depth):
    with pytest.raises(ValueError):
        analyze(DEMO, seeds, max_depth=depth)


def test_path_mapping_boundaries_and_unknowns():
    mapped, unknown = path_seeds(
        DEMO,
        [
            "./services/payments/main.py",
            "services/payments-extra/x.py",
            "contracts/payments.json",
        ],
    )
    assert mapped == ["payments", "payments-api"]
    assert unknown == ["services/payments-extra/x.py"]


def test_markdown_carries_limits_evidence_and_checks():
    text = agent_brief(analyze(DEMO, ["payments-api"], max_depth=1))
    assert "faultline.json: checkout payment dependency" in text
    assert "Checkout → payment contract test" in text
    assert "depth limit" in text


def test_contract_change_flags_removal_and_required():
    before = {
        "properties": {"id": {"type": "string"}, "status": {"type": "string"}},
        "required": ["id"],
    }
    after = {"properties": {"id": {"type": "integer"}}, "required": ["id", "amount"]}
    r = compare(before, after)
    assert any(n["path"] == "/properties/status" for n in r)
    assert any(n["path"] == "/properties/id/type" for n in r)
    assert any("required" in n["reason"] for n in r)
    assert compare(before, before) == []
    assert compare({"description": "old"}, {"description": "new"}) == []


def test_cli_handles_invalid_and_export():
    cmd = [
        sys.executable,
        "-m",
        "faultline.cli",
        "impact",
        "examples/commerce/topology.json",
    ]
    r = subprocess.run(
        cmd + ["--changed", "payments-api"], capture_output=True, text=True, check=False
    )
    assert r.returncode == 0
    assert len(json.loads(r.stdout)["affected"]) == 6
    r = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert r.returncode == 2
    assert "Select at least one" in r.stderr


def test_symbolgraph_adapter_reads_index_without_mutation(tmp_path):
    db_path = tmp_path / "index.sqlite"
    with sqlite3.connect(db_path) as db:
        db.execute(
            "CREATE TABLE symbols (symbol_id TEXT, qualified_name TEXT, relative_path TEXT, start_line INTEGER)"
        )
        db.execute(
            "INSERT INTO symbols VALUES ('s1','pay','services/payments/main.py',4)"
        )
    before = db_path.read_bytes()
    r = subprocess.run(
        [
            sys.executable,
            "-m",
            "faultline.cli",
            "symbols",
            "examples/commerce/topology.json",
            "--index",
            str(db_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0
    assert json.loads(r.stdout)[0]["nodes"] == ["payments"]
    assert db_path.read_bytes() == before


def test_git_mapping_detects_committed_changes(tmp_path):
    for cmd in [
        ["git", "init", "-b", "main"],
        ["git", "config", "user.email", "test@example.com"],
        ["git", "config", "user.name", "Test"],
    ]:
        subprocess.run(cmd, cwd=tmp_path, check=True, capture_output=True)
    p = tmp_path / "services/payments/main.py"
    p.parent.mkdir(parents=True)
    p.write_text("original")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "base"], cwd=tmp_path, check=True, capture_output=True
    )
    p.write_text("updated")
    subprocess.run(
        ["git", "commit", "-am", "change"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    r = subprocess.run(
        [
            sys.executable,
            "-m",
            "faultline.cli",
            "impact",
            "examples/commerce/topology.json",
            "--repo",
            str(tmp_path),
            "--git-base",
            "HEAD~1",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0
    assert json.loads(r.stdout)["seeds"] == ["payments"]


def test_compose_import_preserves_dependencies_and_ownership():
    from faultline.compose import import_compose

    d = import_compose(
        {
            "name": "shop",
            "services": {
                "api": {
                    "depends_on": {"db": {}},
                    "build": {"context": "./services/api"},
                    "labels": {"faultline.owner": "Platform"},
                },
                "db": {"labels": {"faultline.kind": "database"}},
            },
        }
    )
    assert d["nodes"][0]["owner"] == "Platform"
    assert d["nodes"][0]["paths"] == ["services/api"]
    assert ids(analyze(d, ["db"])) == {"api", "db"}
    assert d["edges"][0]["location"] == "compose.json#/services/api/depends_on/db"
    with pytest.raises(ValueError):
        import_compose({"services": {"api": {"depends_on": ["missing"]}}})


def test_mcp_tools_share_engine_and_keep_upstream_tools():
    import asyncio

    from faultline.mcp_server import mcp, system_impact

    assert mcp.name == "faultline"
    r = asyncio.run(system_impact("examples/commerce/topology.json", ["payments-api"]))
    assert ids(r) == ids(analyze(DEMO, ["payments-api"]))


@pytest.mark.parametrize(
    "field,value", [("source", []), ("target", {}), ("kind", []), ("evidence", {})]
)
def test_malformed_edge_types_are_validation_errors(field, value):
    d = copy.deepcopy(DEMO)
    d["edges"][0][field] = value
    with pytest.raises(ValueError):
        validate(d)


@pytest.mark.parametrize(
    "extra",
    [
        ["validate", "examples/commerce/topology.json"],
        ["impact", "examples/commerce/topology.json", "--changed", "payments-api"],
        [
            "impact",
            "examples/commerce/topology.json",
            "--file",
            "services/payments/main.py",
            "--format",
            "markdown",
        ],
        [
            "contract-diff",
            "examples/commerce/topology.json",
            "examples/commerce/topology.json",
        ],
    ],
)
def test_cli_entrypoints_in_process(extra, monkeypatch, capsys):
    from faultline.cli import main

    monkeypatch.setattr(sys, "argv", ["faultline", *extra])
    main()
    assert capsys.readouterr().out


def test_cli_invalid_json_and_compose_import(tmp_path, monkeypatch, capsys):
    from faultline.cli import main

    p = tmp_path / "compose.json"
    p.write_text(json.dumps({"services": {"app": {}}}))
    monkeypatch.setattr(sys, "argv", ["faultline", "import-compose", str(p)])
    main()
    assert json.loads(capsys.readouterr().out)["nodes"][0]["id"] == "app"
    p.write_text("invalid")
    monkeypatch.setattr(sys, "argv", ["faultline", "validate", str(p)])
    with pytest.raises(SystemExit) as e:
        main()
    assert e.value.code == 2


def test_git_rename_maps_old_and_new_paths(tmp_path):
    for cmd in [
        ["git", "init", "-b", "main"],
        ["git", "config", "user.email", "test@example.com"],
        ["git", "config", "user.name", "Test"],
    ]:
        subprocess.run(cmd, cwd=tmp_path, check=True, capture_output=True)
    old = tmp_path / "services/payments/main.py"
    old.parent.mkdir(parents=True)
    old.write_text("content")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "base"], cwd=tmp_path, check=True, capture_output=True
    )
    new = tmp_path / "services/checkout/main.py"
    new.parent.mkdir(parents=True)
    old.rename(new)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "rename"], cwd=tmp_path, check=True, capture_output=True
    )
    r = subprocess.run(
        [
            sys.executable,
            "-m",
            "faultline.cli",
            "impact",
            "examples/commerce/topology.json",
            "--repo",
            str(tmp_path),
            "--git-base",
            "HEAD~1",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0
    assert json.loads(r.stdout)["seeds"] == ["checkout", "payments"]
