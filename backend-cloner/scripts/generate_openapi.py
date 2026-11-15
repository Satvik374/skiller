#!/usr/bin/env python3
"""Convert distilled traffic (endpoints.json) into an OpenAPI 3.0 YAML specification.

The generator is deliberately conservative: it describes what was observed and invents
nothing. Every operation carries `x-provenance: OBSERVED` and `x-evidence` with the HAR
entry indices behind it. Bodies become `$ref` components deduplicated by content hash.
Routes that exist only in client bundles are emitted separately under `x-inferred-routes`
so they can never be mistaken for implemented contract.

    python3 generate_openapi.py \
        --endpoints recon/distilled/endpoints.json \
        --schemas recon/distilled/schemas.json \
        --routes recon/distilled/js_routes.json \
        --title "Example API (reconstructed)" \
        --out recon/openapi.yaml

Deterministic: same inputs produce byte-identical YAML. No timestamps, no random ids,
sorted paths/parameters/components. Dependency-free YAML emission (stdlib only); if PyYAML
is installed, --validate additionally parses and structurally checks the result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterator

TOOL = "generate_openapi"
TOOL_VERSION = "1.0.0"

HTTP_METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")
API_PREFIX_SEGMENTS = {
    "api", "graphql", "gql", "rest", "rpc", "internal", "functions", "wp-json",
}
MASK_SENTINELS = {"<redacted>", "<masked:token>", "<masked:pii>"}

YAML_KEYWORDS = {"true", "false", "null", "yes", "no", "on", "off", "y", "n", "~"}
NUMERIC_RE = re.compile(r"[-+]?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?")
YAML_INDICATORS = "-?:,[]{}#&*!|>'\"%@`"


# --------------------------------------------------------------------------------------
# YAML emission (stdlib only)
# --------------------------------------------------------------------------------------


def plain_ok(text: str) -> bool:
    if not text or text != text.strip():
        return False
    if text.lower() in YAML_KEYWORDS:
        return False
    if NUMERIC_RE.fullmatch(text) or re.fullmatch(r"0[xXoObB][0-9A-Fa-f_]+", text):
        return False
    if text[0] in YAML_INDICATORS:
        return False
    if any(char in text for char in "{}[],"):
        return False
    if ": " in text or " #" in text or text.endswith(":"):
        return False
    if any(ord(char) < 0x20 for char in text):
        return False
    return True


def emit_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)):
        return repr(value)
    text = str(value)
    if plain_ok(text):
        return text
    return json.dumps(text, ensure_ascii=False)


def emit_key(key: Any) -> str:
    text = str(key)
    if plain_ok(text):
        return text
    return json.dumps(text, ensure_ascii=False)


def emit_inline(value: Any) -> str:
    if isinstance(value, dict):
        return "{}"
    if isinstance(value, list):
        return "[]"
    return emit_scalar(value)


def emit_map(mapping: dict[Any, Any], indent: str, lines: list[str], step: int) -> None:
    for key in mapping:
        value = mapping[key]
        key_text = emit_key(key)
        if isinstance(value, dict) and value:
            lines.append(f"{indent}{key_text}:")
            emit_map(value, indent + " " * step, lines, step)
        elif isinstance(value, list) and value:
            lines.append(f"{indent}{key_text}:")
            emit_list(value, indent + " " * step, lines, step)
        elif isinstance(value, str) and "\n" in value:
            lines.append(f"{indent}{key_text}: |-")
            block_indent = indent + " " * step
            for block_line in value.split("\n"):
                lines.append(f"{block_indent}{block_line}" if block_line else "")
        else:
            lines.append(f"{indent}{key_text}: {emit_inline(value)}")


def emit_list(items: list[Any], indent: str, lines: list[str], step: int) -> None:
    for item in items:
        if isinstance(item, dict) and item:
            sub: list[str] = []
            emit_map(item, indent + " " * step, sub, step)
            sub[0] = indent + "- " + sub[0][len(indent) + step:]
            lines.extend(sub)
        elif isinstance(item, list) and item:
            sub = []
            emit_list(item, indent + " " * step, sub, step)
            sub[0] = indent + "- " + sub[0][len(indent) + step:]
            lines.extend(sub)
        elif isinstance(item, str) and "\n" in item:
            lines.append(f"{indent}- |-")
            block_indent = indent + " " * step
            for block_line in item.split("\n"):
                lines.append(f"{block_indent}{block_line}" if block_line else "")
        else:
            lines.append(f"{indent}- {emit_inline(item)}")


def dump_yaml(document: dict[str, Any], step: int = 2) -> str:
    lines: list[str] = [
        "# Reconstructed API contract. Generated deterministically by backend-cloner.",
        "# x-provenance=OBSERVED means captured on the wire; see x-evidence for HAR entries.",
        "# x-inferred-routes lists bundle-only hypotheses that were never observed.",
    ]
    emit_map(document, "", lines, step)
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------------------
# Naming helpers
# --------------------------------------------------------------------------------------


def pascal(value: str) -> str:
    parts = re.split(r"[^A-Za-z0-9]+", value)
    joined = "".join(part[:1].upper() + part[1:] for part in parts if part)
    if not joined:
        return "X"
    if joined[0].isdigit():
        return "X" + joined
    return joined


def operation_id(method: str, template: str) -> str:
    chunks = [method.lower()]
    for segment in template.strip("/").split("/"):
        if not segment:
            continue
        if segment.startswith("{") and segment.endswith("}"):
            chunks.append("By" + pascal(segment[1:-1]))
        else:
            chunks.append(pascal(segment))
    return "".join(chunks)


def tag_for(template: str) -> str:
    for segment in template.strip("/").split("/"):
        if not segment or (segment.startswith("{") and segment.endswith("}")):
            continue
        lowered = segment.lower()
        if lowered in API_PREFIX_SEGMENTS or re.fullmatch(r"v\d+(\.\d+)?", lowered):
            continue
        return lowered
    return "default"


def content_hash(value: Any) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


class ComponentRegistry:
    """Deduplicate schemas by content so identical shapes share one component."""

    def __init__(self) -> None:
        self.by_hash: dict[str, str] = {}
        self.schemas: dict[str, Any] = {}
        self.used: set[str] = set()

    def add(self, candidate: str, schema: Any) -> str | None:
        if not schema:
            return None
        digest = content_hash(schema)
        if digest in self.by_hash:
            return self.by_hash[digest]
        name = self._unique(candidate)
        self.by_hash[digest] = name
        self.used.add(name)
        self.schemas[name] = schema
        return name

    def _unique(self, candidate: str) -> str:
        base = re.sub(r"[^A-Za-z0-9_.\-]", "", candidate) or "Schema"
        if not re.match(r"^[A-Za-z_]", base):
            base = "Schema" + base
        name = base
        counter = 2
        while name in self.used:
            name = f"{base}_{counter}"
            counter += 1
        return name


def ref_to(name: str) -> dict[str, str]:
    return {"$ref": f"#/components/schemas/{name}"}


def status_sort_key(status: str) -> tuple[int, int]:
    if status == "default":
        return (1, 0)
    try:
        return (0, int(status))
    except (TypeError, ValueError):
        return (0, 999)


def scheme_name_for(scheme: str, header_names: list[str], cookie_names: list[str]) -> str:
    if scheme in {"http_bearer", "http_token"}:
        return "bearerAuth"
    if scheme == "http_basic":
        return "basicAuth"
    if scheme == "http_authorization":
        return "authorizationHeader"
    if scheme == "api_key_header":
        header = header_names[0] if header_names else "X-API-Key"
        return "apiKey" + pascal(header)
    if scheme == "cookie":
        _ = cookie_names
        return "cookieAuth"
    return "observedAuth"


def security_scheme_object(scheme: str, header_names: list[str], cookie_names: list[str]) -> dict[str, Any]:
    if scheme in {"http_bearer", "http_token"}:
        return {"type": "http", "scheme": "bearer"}
    if scheme == "http_basic":
        return {"type": "http", "scheme": "basic"}
    if scheme == "http_authorization":
        return {"type": "apiKey", "in": "header", "name": "Authorization"}
    if scheme == "api_key_header":
        return {
            "type": "apiKey",
            "in": "header",
            "name": header_names[0] if header_names else "X-API-Key",
        }
    if scheme == "cookie":
        return {
            "type": "apiKey",
            "in": "cookie",
            "name": cookie_names[0] if cookie_names else "session",
        }
    return {"type": "apiKey", "in": "header", "name": "Authorization"}


# --------------------------------------------------------------------------------------
# Document construction
# --------------------------------------------------------------------------------------


def coerce_example(value: Any, type_name: str) -> Any:
    """Query strings arrive as text; emit an example that matches the declared type."""
    if type_name == "integer":
        try:
            return int(str(value))
        except ValueError:
            return value
    if type_name == "number":
        try:
            return float(str(value))
        except ValueError:
            return value
    if type_name == "boolean":
        return str(value).lower() == "true"
    return value


def parameters_for(endpoint: dict[str, Any]) -> list[dict[str, Any]]:
    parameters: list[dict[str, Any]] = []
    for param in endpoint.get("path_params") or []:
        schema: dict[str, Any] = {"type": param.get("type") or "string"}
        if param.get("format"):
            schema["format"] = param["format"]
        parameters.append(
            {"name": param["name"], "in": "path", "required": True, "schema": schema}
        )
    for query in sorted(endpoint.get("query_params") or [], key=lambda item: item["name"]):
        item: dict[str, Any] = {
            "name": query["name"],
            "in": "query",
            "required": bool(query.get("required")),
            "schema": {"type": query.get("type") or "string"},
        }
        examples = [
            value
            for value in (query.get("examples") or [])
            if value not in MASK_SENTINELS and value != ""
        ]
        if examples:
            item["example"] = coerce_example(examples[0], item["schema"]["type"])
        if query.get("masked"):
            item["x-value-masked"] = True
        parameters.append(item)
    return parameters


def pick_mime(candidates: list[str], fallback: str = "application/json") -> str:
    for candidate in candidates or []:
        if candidate and candidate not in {"text/html", "application/octet-stream"}:
            return candidate
    return fallback


def build_operation(
    endpoint: dict[str, Any],
    registry: ComponentRegistry,
    op_ids: set[str],
    security_schemes: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    method = str(endpoint["method"]).upper()
    template = endpoint["path_template"]
    base = operation_id(method, template)
    ident = base
    counter = 2
    while ident in op_ids:
        ident = f"{base}_{counter}"
        counter += 1
    op_ids.add(ident)

    auth = endpoint.get("auth") or {}
    schemes: list[str] = []
    for scheme in auth.get("schemes") or []:
        name = scheme_name_for(
            scheme, auth.get("header_names") or [], auth.get("cookie_names") or []
        )
        security_schemes.setdefault(
            name,
            security_scheme_object(
                scheme, auth.get("header_names") or [], auth.get("cookie_names") or []
            ),
        )
        if name not in schemes:
            schemes.append(name)

    operation: dict[str, Any] = {
        "operationId": ident,
        "summary": f"Observed {method} {template}",
        "tags": [tag_for(template)],
    }
    parameters = parameters_for(endpoint)
    if parameters:
        operation["parameters"] = parameters

    request_schema = (endpoint.get("request") or {}).get("schema")
    if request_schema:
        request_name = registry.add(f"{pascal(base)}Request", request_schema)
        if request_name:
            mime = pick_mime(endpoint.get("request_content_types") or [])
            operation["requestBody"] = {
                "required": True,
                "content": {mime: {"schema": ref_to(request_name)}},
            }

    responses: dict[str, Any] = {}
    observed = endpoint.get("responses") or {}
    for status in sorted(observed, key=status_sort_key):
        bucket = observed[status] or {}
        key = status if status == "default" or status.isdigit() else "default"
        samples = int(bucket.get("samples") or 0)
        response: dict[str, Any] = {
            "description": (
                f"Observed response ({samples} sample{'s' if samples != 1 else ''})"
                if samples
                else "Observed status with no captured body"
            )
        }
        schema = bucket.get("schema")
        if schema:
            suffix = "" if key == "200" else f"Status{key}"
            name = registry.add(f"{pascal(base)}Response{suffix}", schema)
            if name:
                mime = pick_mime(bucket.get("content_types") or [])
                response["content"] = {mime: {"schema": ref_to(name)}}
        response["x-samples"] = samples
        responses[key] = response
    if not responses:
        responses["default"] = {"description": "No response captured", "x-samples": 0}
    operation["responses"] = responses

    operation["security"] = [{name: []} for name in schemes]
    operation["x-provenance"] = "OBSERVED"
    operation["x-observed-count"] = int(endpoint.get("count") or 0)
    operation["x-evidence"] = {
        "har_entries": list(endpoint.get("har_indices") or [])[:20],
        "har_entries_total": len(endpoint.get("har_indices") or []),
    }
    if auth.get("schemes"):
        operation["x-auth-observed"] = {
            "schemes": list(auth.get("schemes") or []),
            "header_names": list(auth.get("header_names") or []),
        }
    if endpoint.get("timing"):
        operation["x-timing"] = dict(endpoint["timing"])
    if endpoint.get("graphql"):
        operation["x-graphql"] = dict(endpoint["graphql"])

    return method.lower(), operation


def build_document(
    endpoints_doc: dict[str, Any],
    schemas_doc: dict[str, Any] | None,
    routes_doc: dict[str, Any] | None,
    title: str,
    api_version: str,
    description: str | None,
    servers: list[str],
) -> dict[str, Any]:
    endpoints = list(endpoints_doc.get("endpoints") or [])
    capture = endpoints_doc.get("capture") or {}
    registry = ComponentRegistry()
    security_schemes: dict[str, Any] = {}
    op_ids: set[str] = set()
    paths: dict[str, dict[str, Any]] = {}

    for endpoint in sorted(endpoints, key=lambda item: (item["path_template"], item["method"])):
        method, operation = build_operation(endpoint, registry, op_ids, security_schemes)
        paths.setdefault(str(endpoint["path_template"]), {})[method] = operation

    observed_paths = {str(endpoint["path_template"]) for endpoint in endpoints}
    inferred: list[dict[str, Any]] = []
    skipped_inferred = 0
    for route in (routes_doc or {}).get("routes") or []:
        template = route.get("path_template")
        if not template:
            continue
        if template in observed_paths:
            skipped_inferred += 1
            continue
        raw_method = route.get("method") or "ANY"
        inferred.append(
            {
                "path": template,
                "method": "UNKNOWN" if raw_method == "ANY" else raw_method,
                "sources": list(route.get("sources") or []),
                "bundle_urls": list(route.get("bundle_urls") or [])[:5],
                "provenance": "INFERRED",
                "note": "Found in client code only; never observed on the wire.",
            }
        )

    tags = sorted({tag_for(path) for path in paths})
    info_description = (
        "Reconstructed from observed client-server traffic only. Every operation is "
        "x-provenance=OBSERVED and carries x-evidence with the HAR entry indices behind it. "
        "Schemas are DERIVED by unioning captured samples: a field absent from some samples "
        "is optional, and no field is invented. Routes under x-inferred-routes came from "
        "client bundles and were never called, so they are hypotheses rather than contract. "
        "Server-side logic, database layout and unobserved behaviour are UNKNOWN and belong "
        "in the architecture dossier, not in this document."
    )
    if description:
        info_description = f"{description}\n\n{info_description}"

    document: dict[str, Any] = {
        "openapi": "3.0.3",
        "info": {
            "title": title,
            "version": api_version,
            "description": info_description,
            "x-source": "Observed HTTP/WS traffic (HAR capture)",
        },
    }

    server_list = [{"url": server} for server in servers]
    if server_list:
        document["servers"] = server_list
    if tags:
        document["tags"] = [
            {"name": tag, "description": f"Operations observed for the '{tag}' resource"}
            for tag in tags
        ]
    document["paths"] = paths
    document["components"] = {
        "schemas": dict(sorted(registry.schemas.items())),
        "securitySchemes": dict(sorted(security_schemes.items())),
    }
    document["x-capture-metadata"] = {
        "endpoints": len(paths),
        "operations": sum(len(item) for item in paths.values()),
        "origins": list(capture.get("origins") or []),
        "har_sha256": capture.get("har_sha256"),
        "har_entries": capture.get("entries"),
        "distilled_by": f"{endpoints_doc.get('tool')} {endpoints_doc.get('tool_version')}",
        "schema_registry_entries": len((schemas_doc or {}).get("schemas") or {}),
        "inferred_routes": len(inferred),
        "inferred_routes_already_observed": skipped_inferred,
    }
    document["x-inferred-routes"] = inferred
    document["x-provenance-legend"] = {
        "OBSERVED": "Directly captured request/response/status/frame.",
        "DERIVED": "Computed mechanically from captures (paths, schemas, dedupe).",
        "INFERRED": "Agent reasoning about unobserved behaviour; see architecture dossier.",
        "UNKNOWN": "Not determinable from client traffic; never filled in here.",
    }
    return document


# --------------------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------------------


def iter_refs(node: Any) -> Iterator[str]:
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "$ref" and isinstance(value, str):
                yield value
            else:
                yield from iter_refs(value)
    elif isinstance(node, list):
        for item in node:
            yield from iter_refs(item)


def validate_text(text: str) -> tuple[list[str], bool]:
    """Return (problems, parsed). Structural checks; YAML parsing only if PyYAML exists."""
    problems: list[str] = []
    try:
        import yaml  # type: ignore
    except ImportError:
        return problems, False

    try:
        document = yaml.safe_load(text)
    except Exception as exc:  # noqa: BLE001 - any parser error is a hard failure
        return [f"YAML does not parse: {exc}"], False

    if not isinstance(document, dict):
        return ["document root is not a mapping"], True
    if not str(document.get("openapi", "")).startswith("3.0"):
        problems.append("openapi version must start with 3.0")
    info = document.get("info") or {}
    if not info.get("title"):
        problems.append("info.title is missing")
    if not info.get("version"):
        problems.append("info.version is missing")

    schemas = ((document.get("components") or {}).get("schemas") or {})
    paths = document.get("paths") or {}
    if not isinstance(paths, dict):
        problems.append("paths is not a mapping")
        paths = {}
    for path, item in paths.items():
        if not isinstance(path, str) or not path.startswith("/"):
            problems.append(f"path key {path!r} is not an absolute path")
        if not isinstance(item, dict):
            problems.append(f"path {path!r} is not a mapping")
            continue
        for method, operation in item.items():
            if method not in HTTP_METHODS:
                problems.append(f"{path}: unexpected method key {method!r}")
                continue
            if not isinstance(operation, dict):
                problems.append(f"{method.upper()} {path}: operation is not a mapping")
                continue
            responses = operation.get("responses") or {}
            if not responses:
                problems.append(f"{method.upper()} {path}: no responses")
            for status, response in responses.items():
                if not isinstance(status, str):
                    problems.append(
                        f"{method.upper()} {path}: response key {status!r} must be a string"
                    )
                if not isinstance(response, dict) or "description" not in response:
                    problems.append(f"{method.upper()} {path}: response {status} lacks a description")
            for ref in iter_refs(operation):
                name = ref.rsplit("/", 1)[-1]
                if name not in schemas:
                    problems.append(f"{method.upper()} {path}: unresolved $ref {ref}")
            if "operationId" not in operation:
                problems.append(f"{method.upper()} {path}: missing operationId")
    return problems, True


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="generate_openapi.py",
        description=(
            "Turn distilled traffic into an OpenAPI 3.0 YAML specification, tagged with "
            "provenance and evidence so observed contract stays separate from inference."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Output: OpenAPI 3.0.3 YAML with x-provenance, x-evidence, x-observed-count, "
            "x-inferred-routes and x-capture-metadata extensions.\n"
            "Exit codes: 0 ok, 1 invalid/inconsistent spec, 2 bad input, 4 no endpoints.\n"
        ),
    )
    parser.add_argument("--endpoints", required=True, help="distilled endpoints.json")
    parser.add_argument("--schemas", help="distilled schemas.json (optional reference registry)")
    parser.add_argument("--routes", help="distilled js_routes.json (bundle-only hypotheses)")
    parser.add_argument("--out", required=True, help="output OpenAPI YAML path")
    parser.add_argument("--title", default="Reconstructed API", help="info.title")
    parser.add_argument("--api-version", default="0.1.0", help="info.version (default: 0.1.0)")
    parser.add_argument("--description", help="extra info.description preamble")
    parser.add_argument(
        "--server",
        action="append",
        default=[],
        metavar="URL",
        help="server URL for the servers list (repeatable); defaults to captured origins",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="parse and structurally validate the YAML before writing (needs PyYAML)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="fail (exit 4) when the endpoint list is empty",
    )
    parser.add_argument("--version", action="version", version=f"{TOOL} {TOOL_VERSION}")
    return parser


def load_json(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    candidate = Path(path).expanduser()
    if not candidate.exists():
        print(f"[generate_openapi] error: file not found: {candidate}", file=sys.stderr)
        raise SystemExit(2)
    try:
        payload = json.loads(candidate.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        print(f"[generate_openapi] error: invalid JSON in {candidate}: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    if not isinstance(payload, dict):
        print(f"[generate_openapi] error: {candidate} must contain a JSON object", file=sys.stderr)
        raise SystemExit(2)
    return payload


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    endpoints_doc = load_json(args.endpoints) or {}
    schemas_doc = load_json(args.schemas)
    routes_doc = load_json(args.routes)

    endpoints = endpoints_doc.get("endpoints") or []
    if not endpoints and args.strict:
        print(
            "[generate_openapi] error: no endpoints to convert (--strict). "
            "Re-run parse_har.py against a capture that contains API traffic.",
            file=sys.stderr,
        )
        return 4
    if not endpoints:
        print(
            "[generate_openapi] warning: no endpoints found; emitting a spec shell.",
            file=sys.stderr,
        )

    capture = endpoints_doc.get("capture") or {}
    servers = [server for server in args.server if server]
    if not servers:
        servers = [
            origin for origin in (capture.get("origins") or []) if isinstance(origin, str)
        ]

    document = build_document(
        endpoints_doc,
        schemas_doc,
        routes_doc,
        args.title,
        args.api_version,
        args.description,
        servers,
    )
    text = dump_yaml(document)

    problems, parsed = validate_text(text) if True else ([], False)
    if problems:
        print("[generate_openapi] validation failed:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    if not parsed:
        print(
            "[generate_openapi] note: PyYAML not installed, YAML structure not re-parsed. "
            "`pip install pyyaml` enables full --validate checks.",
            file=sys.stderr,
        )

    out_path = Path(args.out).expanduser()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")

    operations = sum(len(item) for item in document["paths"].values())
    summary = {
        "status": "ok",
        "out": str(out_path),
        "bytes": len(text.encode("utf-8")),
        "operations": operations,
        "paths": len(document["paths"]),
        "components": len(document["components"]["schemas"]),
        "security_schemes": sorted(document["components"]["securitySchemes"]),
        "inferred_routes": len(document["x-inferred-routes"]),
        "validated": bool(parsed),
        "next_step": (
            "Fill references/architecture_template.md as recon/architecture.md, then build "
            "the service from the spec and verify parity."
        ),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
