"""Import Docker Compose's normalized JSON without executing the project."""

from faultline.engine import validate


def import_compose(data: dict, location: str = "compose.json") -> dict:
    if (
        not isinstance(data, dict)
        or not isinstance(data.get("services"), dict)
        or not data["services"]
    ):
        raise ValueError("Expected Docker Compose config JSON with a services object")
    services = data["services"]
    nodes, edges = [], []
    for name, service in sorted(services.items()):
        if not isinstance(service, dict):
            raise ValueError("Each Compose service must be an object")  # noqa: TRY004
        labels = service.get("labels", {})
        if not isinstance(labels, dict):
            raise ValueError("Use normalized Compose JSON with object labels")  # noqa: TRY004
        build = service.get("build", {})
        context = build.get("context", "") if isinstance(build, dict) else build
        paths = (
            [context.removeprefix("./")]
            if isinstance(context, str)
            and context
            and not context.startswith("/")
            and ".." not in context.split("/")
            else []
        )
        nodes.append(
            {
                "id": name,
                "label": name,
                "kind": labels.get("faultline.kind", "service"),
                "owner": labels.get("faultline.owner", "Unassigned"),
                "paths": paths,
            }
        )
        dependencies = service.get("depends_on", {})
        if not isinstance(dependencies, (dict, list)) or any(
            not isinstance(d, str) for d in dependencies
        ):
            raise ValueError("depends_on must be an object or list of service names")
        for dep in sorted(dependencies):
            edges.append(
                {
                    "source": name,
                    "target": dep,
                    "kind": "depends_on",
                    "evidence": "declared",
                    "location": f"{location}#/services/{name}/depends_on/{dep}",
                }
            )
    return validate(
        {
            "version": 1,
            "name": data.get("name", "Compose system"),
            "nodes": nodes,
            "edges": edges,
        }
    )
