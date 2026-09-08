"""Conservative structural contract diff, not a full OpenAPI compatibility proof."""


def compare(before: dict, after: dict) -> list[dict]:
    findings = []

    def add(path, reason):
        findings.append({"path": path or "/", "severity": "review", "reason": reason})

    def walk(old, new, path):
        if isinstance(old, dict) and isinstance(new, dict):
            for key in sorted(old.keys() - new.keys()):
                add(f"{path}/{key}", "Removed contract member")
            for key in sorted(old.keys() & new.keys()):
                if key == "description" or key == "example":
                    continue
                walk(old[key], new[key], f"{path}/{key}")
            if set(new.get("required", [])) - set(old.get("required", [])):
                add(
                    f"{path}/required",
                    "Added required fields; check request and response direction",
                )
        elif old != new:
            add(path, "Contract value changed; verify compatibility with consumers")

    walk(before, after, "")
    return findings
