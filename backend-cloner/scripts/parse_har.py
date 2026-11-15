#!/usr/bin/env python3
"""Distil a HAR capture (plus WebSocket/SSE logs) into deterministic API contracts.

What it does, in order:

1. Drops static resources (images, CSS, fonts, media) and page navigations.
2. Normalizes dynamic path segments: /users/123 -> /users/{user_id}, UUIDs, hashes, tokens.
3. Masks credentials and PII (headers, query values, JSON bodies) before anything is written.
4. Deduplicates observations into one record per (method, path template).
5. Infers JSON Schema for request/response bodies by unioning every captured sample.
6. Scans captured JS bundles and source maps for API routes the browser never called.
7. Groups WebSocket/SSE messages into channels with inferred payload schemas.

    python3 parse_har.py --har recon/capture/network.har --out recon/distilled

Deterministic: same inputs produce byte-identical outputs (no timestamps, no randomness,
sorted collections, input hashes instead of dates).
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qsl, urlsplit

TOOL = "parse_har"
TOOL_VERSION = "1.0.0"
SCHEMA_VERSION = "1"

# --------------------------------------------------------------------------------------
# Static-resource and classification tables
# --------------------------------------------------------------------------------------

STATIC_EXTENSIONS = {
    "png", "jpg", "jpeg", "gif", "webp", "avif", "ico", "bmp", "svg", "tif", "tiff",
    "css", "woff", "woff2", "ttf", "otf", "eot",
    "mp4", "webm", "mov", "m4v", "mp3", "wav", "ogg", "oga", "m4a", "flac", "aac",
    "pdf", "zip", "gz", "br", "wasm", "webmanifest", "vtt", "csv", "xls", "xlsx",
}
STATIC_RESOURCE_TYPES = {
    "image", "stylesheet", "font", "media", "texttrack", "manifest",
    "ping", "csp_report", "preflight", "signed-exchange",
}
BUNDLE_EXTENSIONS = {"js", "mjs", "cjs", "jsx"}
API_PREFIX_SEGMENTS = {
    "api", "graphql", "gql", "rest", "rpc", "internal", "functions", "wp-json",
}

SECRET_HEADERS = {
    "authorization", "proxy-authorization", "cookie", "set-cookie", "x-api-key",
    "api-key", "apikey", "x-auth-token", "x-access-token", "x-session-id",
    "x-csrf-token", "x-xsrf-token", "x-amz-security-token", "x-goog-api-key",
    "x-client-secret", "cf-access-jwt-assertion",
}

_SECRET_WORDS = (
    r"(?:password|passwd|pwd|secret|token|api[_\-]?key|apikey|auth|authorization|"
    r"credential|session|csrf|xsrf|signature|otp|pin|private[_\-]?key|"
    r"client[_\-]?secret|oauth|jwt|bearer|cookie)"
)
SECRET_KEY_RE = re.compile(rf"(?:^|_){_SECRET_WORDS}(?:s)?(?:$|_)", re.I)

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
JWT_RE = re.compile(r"eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}")
AUTH_PREFIX_RE = re.compile(r"^(?:Bearer|Basic|Token)\s+\S{8,}$", re.I)
CARD_RE = re.compile(r"^(?:\d[ -]?){13,19}$")
PHONE_RE = re.compile(r"^\+?\d[\d\s().\-]{7,}\d$")

MASK_REDACTED = "<redacted>"
MASK_TOKEN = "<masked:token>"
MASK_PII = "<masked:pii>"
MASK_SENTINELS = {MASK_REDACTED, MASK_TOKEN, MASK_PII}

UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
HEX_LONG_RE = re.compile(r"^[0-9a-fA-F]{16,}$")
INT_RE = re.compile(r"^\d{1,18}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TOKENISH_RE = re.compile(r"^[A-Za-z0-9]{20,}$")

CALL_PATH_RE = re.compile(
    r"""(?:fetch|axios(?:\.\w+)?|got|ky|superagent|request|apiClient|httpClient|"""
    r"""useSWR|useQuery|\.open|\.request)\s*\(\s*(?P<q>["'`])(?P<path>[^"'`\s]{2,300})(?P=q)"""
)
AXIOS_METHOD_RE = re.compile(
    r"""axios\.(?P<method>get|post|put|patch|delete|head|options)\s*\(\s*"""
    r"""(?P<q>["'`])(?P<path>[^"'`\s]{2,300})(?P=q)""",
    re.I,
)
PREFIX_PATH_RE = re.compile(
    r"""(?P<q>["'`])(?P<path>/(?:api|v\d+(?:\.\d+)?|graphql|gql|rest|rpc|internal|"""
    r"""functions|_next/data|wp-json)/[^"'`\s\\]{0,200})(?P=q)"""
)
TEMPLATE_EXPR_RE = re.compile(r"\$\{[^}]{0,80}\}")
EXPRESS_PARAM_RE = re.compile(r":([A-Za-z_]\w*)")
GRAPHQL_OP_RE = re.compile(r"(?:query|mutation|subscription)\s+([A-Za-z_]\w*)")
CHANNEL_KEYS = ("type", "event", "op", "action", "channel", "method", "cmd", "kind", "name")


# --------------------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------------------


def utc_from_iso(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def sanitize_ident(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_")
    return cleaned or "root"


def singularize(word: str) -> str:
    text = word.lower()
    if len(text) > 3 and text.endswith("ies"):
        return text[:-3] + "y"
    if len(text) > 4 and text.endswith(("sses", "shes", "ches", "xes", "zes")):
        return text[:-2]
    if len(text) > 2 and text.endswith("s") and not text.endswith("ss"):
        return text[:-1]
    return text


def normalize_key(key: str) -> str:
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", str(key))
    spaced = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", "_", spaced)
    return re.sub(r"[^a-z0-9]+", "_", spaced.lower()).strip("_")


def is_secret_key(key: str) -> bool:
    return bool(SECRET_KEY_RE.search(normalize_key(key)))


def mask_string(value: str, mask_pii: bool) -> tuple[str, str | None]:
    text = value.strip()
    if JWT_RE.search(text):
        return MASK_TOKEN, "token"
    if AUTH_PREFIX_RE.match(text):
        return MASK_TOKEN, "token"
    if not mask_pii:
        return value, None
    if EMAIL_RE.fullmatch(text):
        return MASK_PII, "pii"
    if CARD_RE.fullmatch(text) and sum(ch.isdigit() for ch in text) >= 13:
        return MASK_PII, "pii"
    if PHONE_RE.match(text) and sum(ch.isdigit() for ch in text) >= 9:
        return MASK_PII, "pii"
    return value, None


def mask_json(value: Any, stats: dict[str, int], mask_pii: bool) -> Any:
    if isinstance(value, dict):
        masked: dict[str, Any] = {}
        for key, item in value.items():
            if is_secret_key(str(key)):
                if item not in (None, "", [], {}):
                    stats["secret_values"] += 1
                masked[key] = MASK_REDACTED
            else:
                masked[key] = mask_json(item, stats, mask_pii)
        return masked
    if isinstance(value, list):
        return [mask_json(item, stats, mask_pii) for item in value]
    if isinstance(value, str):
        masked_value, kind = mask_string(value, mask_pii)
        if kind:
            stats[f"{kind}_values"] += 1
        return masked_value
    return value


def dynamic_kind(segment: str) -> str | None:
    if UUID_RE.match(segment):
        return "uuid"
    if DATE_RE.match(segment):
        return "date"
    if INT_RE.match(segment):
        return "integer"
    if HEX_LONG_RE.match(segment):
        return "hash"
    if TOKENISH_RE.match(segment):
        has_upper = any(ch.isupper() for ch in segment)
        has_lower = any(ch.islower() for ch in segment)
        has_digit = any(ch.isdigit() for ch in segment)
        if (has_upper and has_lower) or (has_digit and (has_upper or has_lower)):
            return "token"
    return None


def template_path(path: str, named: bool = True) -> tuple[str, list[dict[str, str]]]:
    """Turn /users/123/posts/abc into /users/{user_id}/posts/{post_id}."""
    if not path.startswith("/"):
        path = "/" + path
    segments = path.split("/")
    out: list[str] = []
    params: list[dict[str, str]] = []
    used: dict[str, int] = {}
    last_literal = ""

    for segment in segments:
        kind = dynamic_kind(segment) if segment else None
        if kind is None:
            out.append(segment)
            if segment:
                last_literal = segment
            continue

        if named and last_literal:
            base = sanitize_ident(singularize(last_literal)).lower()
            name = f"{base}_id" if base else "id"
        else:
            name = "id"
        if not re.match(r"^[A-Za-z_]", name):
            name = "id"
        count = used.get(name, 0) + 1
        used[name] = count
        if count > 1:
            name = f"{name}{count}"

        placeholder = "{" + name + "}"
        out.append(placeholder)
        param: dict[str, str] = {"name": name, "type": "string"}
        if kind == "integer":
            param["type"] = "integer"
        elif kind == "uuid":
            param["format"] = "uuid"
        elif kind == "date":
            param["format"] = "date"
        elif kind == "hash":
            param["max_length"] = "128"
        params.append(param)

    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for param in params:
        if param["name"] in seen:
            continue
        seen.add(param["name"])
        unique.append(param)
    return "/".join(out) or "/", unique


# --------------------------------------------------------------------------------------
# HAR reading and classification
# --------------------------------------------------------------------------------------


def har_entries(har: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        entries = har["log"]["entries"]
    except (KeyError, TypeError):
        return []
    return [entry for entry in entries if isinstance(entry, dict)]


def content_text(response: dict[str, Any]) -> str | None:
    content = response.get("content") or {}
    text = content.get("text")
    if text is None:
        return None
    if content.get("encoding") == "base64":
        try:
            return base64.b64decode(text).decode("utf-8", errors="replace")
        except Exception:
            return None
    return str(text)


def mime_of(response: dict[str, Any]) -> str:
    mime = (response.get("content") or {}).get("mimeType") or ""
    return str(mime).split(";")[0].strip().lower()


def extension_of(path: str) -> str:
    tail = path.rsplit("/", 1)[-1]
    if "." not in tail:
        return ""
    return tail.rsplit(".", 1)[-1].lower()


def classify(entry: dict[str, Any]) -> str:
    request = entry.get("request") or {}
    response = entry.get("response") or {}
    url = str(request.get("url") or "")
    method = str(request.get("method") or "GET").upper()
    path = urlsplit(url).path or "/"
    mime = mime_of(response)
    resource = str(entry.get("_resourceType") or "").lower()
    extension = extension_of(path)

    if extension in STATIC_EXTENSIONS or resource in STATIC_RESOURCE_TYPES:
        return "static"
    if extension in BUNDLE_EXTENSIONS or resource == "script":
        return "bundle"
    if extension == "map" or resource == "sourcemap":
        return "sourcemap"
    if resource == "document" and method == "GET":
        return "page"
    if "json" in mime or mime.endswith("+json") or mime in {"application/graphql", "application/x-ndjson"}:
        return "api"
    if resource in {"xhr", "fetch", "eventsource"}:
        return "api"
    if method != "GET":
        return "api"
    if mime.startswith("text/") or mime in {"application/xml", "application/graphql-response+json"}:
        return "api"
    return "other"


def header_list(entry: dict[str, Any], side: str) -> list[dict[str, str]]:
    container = entry.get(side) or {}
    headers = container.get("headers") or []
    return [h for h in headers if isinstance(h, dict)]


def detect_auth(
    request_headers: list[dict[str, str]], cookie_names: Iterable[str]
) -> dict[str, Any]:
    schemes: set[str] = set()
    names: set[str] = set()
    for header in request_headers:
        name = str(header.get("name", "")).lower()
        value = str(header.get("value", ""))
        if name == "authorization":
            lowered = value.strip().lower()
            if lowered.startswith("bearer "):
                schemes.add("http_bearer")
            elif lowered.startswith("basic "):
                schemes.add("http_basic")
            elif lowered.startswith("token "):
                schemes.add("http_token")
            else:
                schemes.add("http_authorization")
            names.add("authorization")
        elif name in {"x-api-key", "api-key", "apikey", "x-auth-token", "x-access-token"}:
            schemes.add("api_key_header")
            names.add(name)
    cookies = sorted({str(name) for name in cookie_names if name})
    if cookies:
        schemes.add("cookie")
    return {
        "schemes": sorted(schemes),
        "header_names": sorted(names),
        "cookie_observed": bool(cookies),
        "cookie_names": cookies,
    }


def parse_form(text: str) -> dict[str, Any] | None:
    pairs = parse_qsl(text, keep_blank_values=True)
    if not pairs:
        return None
    grouped: dict[str, list[str]] = {}
    for key, value in pairs:
        grouped.setdefault(key, []).append(value)
    return {key: values[0] if len(values) == 1 else values for key, values in grouped.items()}


def parse_body(
    text: str | None,
    mime: str,
    stats: dict[str, int],
    max_bytes: int,
    mask_pii: bool,
) -> Any | None:
    if text is None:
        return None
    if len(text) > max_bytes:
        stats["bodies_skipped_oversize"] += 1
        return None
    stripped = text.strip()
    if not stripped:
        return None
    mime = (mime or "").split(";")[0].strip().lower()
    parsed: Any | None = None
    if "json" in mime or stripped[:1] in "{[":
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            parsed = None
    if parsed is None and "x-www-form-urlencoded" in mime:
        parsed = parse_form(stripped)
    if parsed is None:
        stats["non_json_bodies"] += 1
        return None
    return mask_json(parsed, stats, mask_pii)


# --------------------------------------------------------------------------------------
# Schema inference
# --------------------------------------------------------------------------------------


def json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    return "string"


def detect_format(strings: list[str]) -> str | None:
    if not strings:
        return None
    if all(UUID_RE.match(value) for value in strings):
        return "uuid"
    if all(re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})", value) for value in strings):
        return "date-time"
    if all(DATE_RE.match(value) for value in strings):
        return "date"
    if all(EMAIL_RE.fullmatch(value) for value in strings):
        return "email"
    if all(value.startswith(("http://", "https://")) for value in strings):
        return "uri"
    if all(re.fullmatch(r"(\d{1,3}\.){3}\d{1,3}", value) for value in strings):
        return "ipv4"
    return None


def infer_schema(samples: list[Any], enum_max: int, item_cap: int = 50) -> dict[str, Any]:
    """Infer a JSON-Schema-ish node by unioning every sample of one field."""
    if not samples:
        return {}
    present = [sample for sample in samples if sample is not None]
    if not present:
        return {"nullable": True, "x-only-null-observed": True}

    types = sorted({json_type(sample) for sample in present})
    if types == ["integer", "number"]:
        types = ["number"]

    node: dict[str, Any]
    if len(types) == 1:
        node = {"type": types[0]}
        if types[0] == "object":
            objects = [sample for sample in present if isinstance(sample, dict)]
            keys = sorted({key for obj in objects for key in obj})
            properties = {
                key: infer_schema([obj[key] for obj in objects if key in obj], enum_max, item_cap)
                for key in keys
            }
            if properties:
                node["properties"] = properties
                required = [key for key in keys if all(key in obj for obj in objects)]
                if required:
                    node["required"] = required
        elif types[0] == "array":
            items: list[Any] = []
            for sample in present:
                if isinstance(sample, list):
                    items.extend(sample[:item_cap])
            node["items"] = infer_schema(items, enum_max, item_cap) if items else {}
        elif types[0] == "string":
            strings = [sample for sample in present if isinstance(sample, str)]
            fmt = detect_format(strings)
            if fmt:
                node["format"] = fmt
            distinct = sorted({value for value in strings if value not in MASK_SENTINELS})
            unmasked = all(value not in MASK_SENTINELS for value in strings)
            # Never enumerate identifiers or formatted values (ids, timestamps, emails,
            # URIs): those are data, not a closed set, and an enum there would be a lie.
            if (
                fmt is None
                and unmasked
                and 2 <= len(distinct) <= enum_max
                and all(len(value) <= 48 for value in distinct)
            ):
                node["enum"] = distinct
    else:
        node = {
            "oneOf": [
                infer_schema([sample for sample in present if json_type(sample) == name], enum_max, item_cap)
                for name in types
            ],
            "x-mixed-types": types,
        }

    if len(present) != len(samples):
        node["nullable"] = True
    return node


# --------------------------------------------------------------------------------------
# Endpoint aggregation
# --------------------------------------------------------------------------------------


def new_endpoint(method: str, template: str, path_params: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "key": f"{method} {template}",
        "method": method,
        "path_template": template,
        "path_params": path_params,
        "count": 0,
        "har_indices": [],
        "_statuses": set(),
        "_content_types": set(),
        "_request_content_types": set(),
        "_auth_schemes": set(),
        "_auth_headers": set(),
        "_cookie_names": set(),
        "_auth_seen": 0,
        "_noauth_seen": 0,
        "_query": {},
        "_request_samples": [],
        "_responses": {},
        "_timestamps": [],
        "_graphql_ops": set(),
    }


def record_query(endpoint: dict[str, Any], query: str, stats: dict[str, int], mask_pii: bool) -> None:
    pairs = parse_qsl(query, keep_blank_values=True)
    for name, raw_value in pairs:
        slot = endpoint["_query"].setdefault(
            name, {"name": name, "raw": [], "examples": [], "secret": is_secret_key(name), "count": 0}
        )
        slot["count"] += 1
        if len(slot["raw"]) < 5:
            slot["raw"].append(raw_value)
        if slot["secret"]:
            stats["secret_values"] += 1
            continue
        masked, kind = mask_string(raw_value, mask_pii)
        if kind:
            stats[f"{kind}_values"] += 1
        if masked not in MASK_SENTINELS and len(masked) <= 64:
            if masked not in slot["examples"] and len(slot["examples"]) < 3:
                slot["examples"].append(masked)


def scalar_type(values: list[str]) -> str:
    if values and all(re.fullmatch(r"-?\d{1,18}", value) for value in values):
        return "integer"
    if values and all(value.lower() in {"true", "false"} for value in values):
        return "boolean"
    return "string"


def finalize_endpoint(endpoint: dict[str, Any], registry: dict[str, Any], enum_max: int) -> dict[str, Any]:
    observations = max(endpoint["count"], 1)
    query_params = []
    for name in sorted(endpoint["_query"]):
        slot = endpoint["_query"][name]
        param: dict[str, Any] = {
            "name": name,
            "required": slot["count"] >= observations,
            "type": scalar_type(slot["raw"]),
        }
        if slot["examples"]:
            param["examples"] = list(slot["examples"])
        if slot["secret"]:
            param["masked"] = True
        query_params.append(param)

    auth = {
        "schemes": sorted(endpoint["_auth_schemes"]),
        "header_names": sorted(endpoint["_auth_headers"]),
        "cookie_observed": bool(endpoint["_cookie_names"]),
        "cookie_names": sorted(endpoint["_cookie_names"]),
        "observed_with_auth": endpoint["_auth_seen"],
        "observed_without_auth": endpoint["_noauth_seen"],
    }

    request_schema = (
        infer_schema(endpoint["_request_samples"], enum_max) if endpoint["_request_samples"] else None
    )
    request_ref = None
    if request_schema:
        request_ref = f"{sanitize_ident(endpoint['method'] + '_' + endpoint['path_template'])}_request"
        registry[request_ref] = request_schema

    responses: dict[str, Any] = {}
    for status in sorted(endpoint["_responses"], key=lambda value: int(value)):
        bucket = endpoint["_responses"][status]
        schema = infer_schema(bucket["samples"], enum_max) if bucket["samples"] else None
        entry: dict[str, Any] = {
            "samples": len(bucket["samples"]),
            "content_types": sorted(bucket["content_types"]),
            "schema": schema,
        }
        if schema:
            ref = f"{sanitize_ident(endpoint['method'] + '_' + endpoint['path_template'])}_response_{status}"
            registry[ref] = schema
            entry["schema_ref"] = ref
        responses[str(status)] = entry

    timing: dict[str, Any] = {}
    stamps = sorted(stamp for stamp in endpoint["_timestamps"] if stamp is not None)
    if len(stamps) >= 2:
        deltas = [
            round((later - earlier).total_seconds(), 2)
            for earlier, later in zip(stamps, stamps[1:])
            if (later - earlier).total_seconds() > 0
        ]
        if deltas:
            timing["min_interval_seconds"] = min(deltas)
            timing["max_interval_seconds"] = max(deltas)

    finalized: dict[str, Any] = {
        "key": endpoint["key"],
        "method": endpoint["method"],
        "path_template": endpoint["path_template"],
        "path_params": endpoint["path_params"],
        "query_params": query_params,
        "statuses": sorted(endpoint["_statuses"]),
        "content_types": sorted(endpoint["_content_types"]),
        "request_content_types": sorted(endpoint["_request_content_types"]),
        "auth": auth,
        "provenance": "OBSERVED",
        "count": endpoint["count"],
        "har_indices": endpoint["har_indices"],
        "request": {
            "samples": len(endpoint["_request_samples"]),
            "schema": request_schema,
            "schema_ref": request_ref,
        },
        "responses": responses,
    }
    if endpoint["_graphql_ops"]:
        finalized["graphql"] = {"operations": sorted(endpoint["_graphql_ops"])}
    if timing:
        finalized["timing"] = timing
    return finalized


# --------------------------------------------------------------------------------------
# Client bundle route extraction
# --------------------------------------------------------------------------------------


def normalize_route(raw: str, allowed_hosts: set[str]) -> str | None:
    candidate = raw.strip()
    if not candidate or candidate.startswith(("data:", "blob:", "javascript:")):
        return None
    if candidate.startswith(("http://", "https://", "//", "ws://", "wss://")):
        parts = urlsplit(candidate if "//" not in candidate[:2] else "https:" + candidate)
        host = (parts.hostname or "").lower()
        if allowed_hosts and host not in allowed_hosts:
            return None
        candidate = parts.path or "/"
    candidate = candidate.split("?")[0].split("#")[0]
    if not candidate.startswith("/"):
        return None
    candidate = TEMPLATE_EXPR_RE.sub("1", candidate)
    candidate = EXPRESS_PARAM_RE.sub("1", candidate)
    candidate = candidate.rstrip("/") or "/"
    if any(ch in candidate for ch in ' <>"\\'):
        return None
    if extension_of(candidate) in STATIC_EXTENSIONS:
        return None
    segments = [segment for segment in candidate.split("/") if segment]
    if not segments:
        return None
    first = segments[0].lower()
    is_api_prefix = first in API_PREFIX_SEGMENTS or re.fullmatch(r"v\d+(\.\d+)?", first) is not None
    if not is_api_prefix and len(segments) < 2:
        return None
    if any(segment in {"..", "."} for segment in segments):
        return None
    template, _ = template_path(candidate, named=True)
    return template


def extract_routes(
    text: str,
    source: str,
    source_url: str | None,
    allowed_hosts: set[str],
    routes: dict[tuple[str, str], dict[str, Any]],
    limit: int,
) -> int:
    found = 0
    for regex, method_default in ((AXIOS_METHOD_RE, None), (CALL_PATH_RE, None), (PREFIX_PATH_RE, "ANY")):
        for match in regex.finditer(text):
            if sum(len(value["line_hints"]) for value in routes.values()) > limit:
                return found
            raw = match.group("path")
            method = (match.groupdict().get("method") or method_default or "ANY").upper()
            template = normalize_route(raw, allowed_hosts)
            if not template:
                continue
            key = (template, method)
            record = routes.setdefault(
                key,
                {
                    "path_template": template,
                    "method": method,
                    "sources": set(),
                    "bundle_urls": set(),
                    "line_hints": set(),
                    "provenance": "INFERRED",
                },
            )
            record["sources"].add(source)
            if source_url:
                record["bundle_urls"].add(source_url)
            record["line_hints"].add(text.count("\n", 0, match.start()) + 1)
            found += 1
    return found


def prune_routes(
    routes: dict[tuple[str, str], dict[str, Any]]
) -> dict[tuple[str, str], dict[str, Any]]:
    """Drop base-URL noise and method-agnostic duplicates of a known-method route."""

    def is_bare_prefix(template: str) -> bool:
        segments = [segment for segment in template.strip("/").split("/") if segment]
        if not segments:
            return True
        return all(
            segment.lower() in API_PREFIX_SEGMENTS
            or re.fullmatch(r"v\d+(\.\d+)?", segment.lower()) is not None
            for segment in segments
        )

    cleaned = {
        key: value
        for key, value in routes.items()
        if not is_bare_prefix(key[0])
    }
    specific_paths = {path for (path, method) in cleaned if method != "ANY"}
    return {
        key: value
        for key, value in cleaned.items()
        if not (key[1] == "ANY" and key[0] in specific_paths)
    }


def routes_from_sourcemap(
    text: str,
    source_url: str | None,
    allowed_hosts: set[str],
    routes: dict[tuple[str, str], dict[str, Any]],
    limit: int,
) -> int:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return 0
    contents = payload.get("sourcesContent") or []
    found = 0
    for index, content in enumerate(contents):
        if not isinstance(content, str):
            continue
        label = "sourcemap"
        names = payload.get("sources") or []
        if index < len(names) and isinstance(names[index], str):
            label = f"sourcemap:{names[index].rsplit('/', 1)[-1]}"
        found += extract_routes(content, label, source_url, allowed_hosts, routes, limit)
    return found


# --------------------------------------------------------------------------------------
# WebSocket / SSE aggregation
# --------------------------------------------------------------------------------------


def channel_of(payload: Any) -> str:
    if isinstance(payload, dict):
        for key in CHANNEL_KEYS:
            value = payload.get(key)
            if isinstance(value, (str, int)) and str(value):
                return str(value)[:80]
        keys = sorted(payload)
        return f"object:{keys[0]}" if keys else "object"
    return f"scalar:{json_type(payload)}"


def process_stream(
    path: Path | None,
    kind: str,
    max_samples: int,
    enum_max: int,
    stats: dict[str, int],
) -> dict[str, Any]:
    if path is None:
        return {"channel": kind, "provided": False, "channels": [], "non_json_samples": 0}
    channels: dict[tuple[str, str], dict[str, Any]] = {}
    non_json = 0
    lines = 0
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            lines += 1
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                non_json += 1
                continue
            if not isinstance(record, dict):
                non_json += 1
                continue
            raw = record.get("data")
            payload: Any | None = None
            if isinstance(raw, str):
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    payload = None
            if payload is None:
                non_json += 1
                continue
            direction = "client->server" if record.get("direction") in {"sent", "client"} else "server->client"
            name = channel_of(payload)
            bucket = channels.setdefault((name, direction), {"samples": [], "count": 0})
            bucket["count"] += 1
            if len(bucket["samples"]) < max_samples:
                bucket["samples"].append(payload)

    stats[f"{kind}_messages"] += lines
    output = []
    for (name, direction) in sorted(channels):
        bucket = channels[(name, direction)]
        output.append(
            {
                "name": name,
                "direction": direction,
                "count": bucket["count"],
                "schema": infer_schema(bucket["samples"], enum_max),
                "provenance": "OBSERVED",
            }
        )
    return {
        "channel": kind,
        "provided": True,
        "messages": lines,
        "non_json_samples": non_json,
        "channels": output,
    }


# --------------------------------------------------------------------------------------
# Main pipeline
# --------------------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="parse_har.py",
        description=(
            "Distil a HAR capture into deterministic endpoint and JSON-schema contracts. "
            "Static assets are dropped, dynamic path segments templated, secrets and PII masked."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Outputs (in --out):\n"
            "  endpoints.json  deduplicated operations with request/response schemas\n"
            "  schemas.json    named schema registry referenced by endpoints.json\n"
            "  js_routes.json  routes found only in JS bundles/source maps (INFERRED)\n"
            "  parse_report.json counts, masking totals, input hashes, warnings\n"
        ),
    )
    parser.add_argument("--har", required=True, help="path to network.har")
    parser.add_argument("--out", required=True, help="output directory")
    parser.add_argument("--ws", help="path to websocket.jsonl from capture_traffic.py")
    parser.add_argument("--sse", help="path to sse.jsonl from capture_traffic.py")
    parser.add_argument(
        "--origin",
        action="append",
        default=[],
        metavar="HOST",
        help="only keep endpoints on this host (repeatable); defaults to every captured host",
    )
    parser.add_argument(
        "--max-body-bytes",
        type=int,
        default=2_000_000,
        help="skip bodies larger than this (default: 2000000)",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=25,
        help="maximum body samples per endpoint/status used for schema inference (default: 25)",
    )
    parser.add_argument(
        "--max-bundle-bytes",
        type=int,
        default=8_000_000,
        help="skip JS bundles larger than this when scanning for routes (default: 8000000)",
    )
    parser.add_argument(
        "--max-routes",
        type=int,
        default=2000,
        help="cap on routes extracted from bundles (default: 2000)",
    )
    parser.add_argument(
        "--enum-max",
        type=int,
        default=12,
        help="emit enum when a string field has at most this many distinct values (default: 12)",
    )
    parser.add_argument(
        "--no-mask-pii",
        action="store_true",
        help="keep emails/phones/card-like values (still masks credentials and tokens)",
    )
    parser.add_argument(
        "--no-js-routes",
        action="store_true",
        help="skip bundle/source-map route extraction",
    )
    parser.add_argument("--version", action="version", version=f"{TOOL} {TOOL_VERSION}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    har_path = Path(args.har).expanduser()
    out_dir = Path(args.out).expanduser()
    mask_pii = not args.no_mask_pii

    if not har_path.exists():
        print(f"[parse_har] error: HAR not found: {har_path}", file=sys.stderr)
        return 2
    try:
        har = json.loads(har_path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        print(f"[parse_har] error: invalid HAR JSON: {exc}", file=sys.stderr)
        return 2

    out_dir.mkdir(parents=True, exist_ok=True)

    stats: dict[str, Any] = {
        "entries_total": 0,
        "kept_api": 0,
        "dropped_static": 0,
        "dropped_page": 0,
        "dropped_other": 0,
        "dropped_offorigin": 0,
        "bundles_scanned": 0,
        "bundles_skipped_oversize": 0,
        "sourcemaps_scanned": 0,
        "bodies_skipped_oversize": 0,
        "non_json_bodies": 0,
        "secret_headers": 0,
        "secret_values": 0,
        "pii_values": 0,
        "token_values": 0,
        "websocket_messages": 0,
        "sse_messages": 0,
    }
    warnings: list[str] = []
    allowed_hosts = {host.lower() for host in args.origin}
    origins: set[str] = set()

    endpoints: dict[tuple[str, str], dict[str, Any]] = {}
    registry: dict[str, Any] = {}
    routes: dict[tuple[str, str], dict[str, Any]] = {}
    route_hits = 0

    for index, entry in enumerate(har_entries(har)):
        stats["entries_total"] += 1
        request = entry.get("request") or {}
        response = entry.get("response") or {}
        url = str(request.get("url") or "")
        if not url:
            stats["dropped_other"] += 1
            continue
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        kind = classify(entry)

        if kind == "bundle":
            if args.no_js_routes:
                continue
            text = content_text(response)
            if text is None:
                continue
            if len(text) > args.max_bundle_bytes:
                stats["bundles_skipped_oversize"] += 1
                continue
            stats["bundles_scanned"] += 1
            route_hits += extract_routes(
                text, "bundle", url.split("?")[0], allowed_hosts, routes, args.max_routes
            )
            continue
        if kind == "sourcemap":
            if args.no_js_routes:
                continue
            text = content_text(response)
            if text is None or len(text) > args.max_bundle_bytes:
                stats["bundles_skipped_oversize"] += 1
                continue
            stats["sourcemaps_scanned"] += 1
            route_hits += routes_from_sourcemap(
                text, url.split("?")[0], allowed_hosts, routes, args.max_routes
            )
            continue
        if kind == "static":
            stats["dropped_static"] += 1
            continue
        if kind == "page":
            stats["dropped_page"] += 1
            continue
        if kind != "api":
            stats["dropped_other"] += 1
            continue
        if allowed_hosts and host not in allowed_hosts:
            stats["dropped_offorigin"] += 1
            continue

        stats["kept_api"] += 1
        origins.add(f"{parts.scheme}://{parts.netloc}")
        method = str(request.get("method") or "GET").upper()
        path = parts.path or "/"
        template, path_params = template_path(path)
        key = (method, template)
        endpoint = endpoints.get(key)
        if endpoint is None:
            endpoint = new_endpoint(method, template, path_params)
            endpoints[key] = endpoint

        endpoint["count"] += 1
        endpoint["har_indices"].append(index)
        status = int(response.get("status") or 0)
        endpoint["_statuses"].add(status)
        mime = mime_of(response)
        if mime:
            endpoint["_content_types"].add(mime)

        request_headers = header_list(entry, "request")
        request_cookies = [str(cookie.get("name", "")) for cookie in (request.get("cookies") or []) if isinstance(cookie, dict)]
        auth = detect_auth(request_headers, request_cookies)
        endpoint["_auth_schemes"].update(auth["schemes"])
        endpoint["_auth_headers"].update(auth["header_names"])
        endpoint["_cookie_names"].update(auth["cookie_names"])
        if auth["schemes"]:
            endpoint["_auth_seen"] += 1
        else:
            endpoint["_noauth_seen"] += 1
        stats["secret_headers"] += sum(
            1 for header in request_headers if str(header.get("name", "")).lower() in SECRET_HEADERS
        ) + sum(
            1
            for header in header_list(entry, "response")
            if str(header.get("name", "")).lower() in SECRET_HEADERS
        )

        record_query(endpoint, parts.query, stats, mask_pii)

        post_data = request.get("postData") or {}
        post_text = post_data.get("text")
        post_mime = str(post_data.get("mimeType") or "")
        if post_text:
            if post_mime:
                endpoint["_request_content_types"].add(post_mime.split(";")[0].strip().lower())
            body = parse_body(str(post_text), post_mime, stats, args.max_body_bytes, mask_pii)
            if body is not None and len(endpoint["_request_samples"]) < args.max_samples:
                endpoint["_request_samples"].append(body)
                if isinstance(body, dict) and isinstance(body.get("query"), str):
                    match = GRAPHQL_OP_RE.search(body["query"])
                    endpoint["_graphql_ops"].add(match.group(1) if match else "anonymous")
        elif post_data.get("params"):
            params = [p for p in post_data["params"] if isinstance(p, dict)]
            if params:
                body = {str(p.get("name")): str(p.get("value", "")) for p in params}
                endpoint["_request_samples"].append(mask_json(body, stats, mask_pii))

        body_text = content_text(response)
        response_body = parse_body(
            body_text, mime, stats, args.max_body_bytes, mask_pii
        )
        bucket = endpoint["_responses"].setdefault(
            str(status), {"samples": [], "content_types": set()}
        )
        if mime:
            bucket["content_types"].add(mime)
        if response_body is not None and len(bucket["samples"]) < args.max_samples:
            bucket["samples"].append(response_body)

        stamp = utc_from_iso(str(entry.get("startedDateTime") or ""))
        if stamp is not None:
            endpoint["_timestamps"].append(stamp)

    finalized = [
        finalize_endpoint(endpoint, registry, args.enum_max)
        for _, endpoint in sorted(endpoints.items())
    ]

    ws_doc = process_stream(
        Path(args.ws).expanduser() if args.ws else None,
        "websocket",
        args.max_samples,
        args.enum_max,
        stats,
    )
    sse_doc = process_stream(
        Path(args.sse).expanduser() if args.sse else None,
        "sse",
        args.max_samples,
        args.enum_max,
        stats,
    )

    if not finalized:
        warnings.append(
            "no API responses were kept; the capture may contain only a page load, "
            "or every response was static. Re-run capture_traffic.py over real flows."
        )
    if stats["bundles_scanned"] == 0 and not args.no_js_routes:
        warnings.append("no JS bundles were scanned; js_routes.json is empty")
    if stats["bodies_skipped_oversize"]:
        warnings.append(
            f"{stats['bodies_skipped_oversize']} bodies exceeded --max-body-bytes and were skipped"
        )

    route_list = []
    for (template, method) in sorted(prune_routes(routes)):
        record = routes[(template, method)]
        route_list.append(
            {
                "path_template": record["path_template"],
                "method": record["method"],
                "sources": sorted(record["sources"]),
                "bundle_urls": sorted(record["bundle_urls"])[:10],
                "line_hints": sorted(record["line_hints"])[:5],
                "provenance": "INFERRED",
            }
        )

    inputs = []
    for label, path_value in (("har", har_path), ("ws", args.ws), ("sse", args.sse)):
        if not path_value:
            continue
        candidate = Path(path_value).expanduser()
        if candidate.exists():
            inputs.append(
                {"role": label, "sha256": sha256_file(candidate), "bytes": candidate.stat().st_size}
            )

    endpoints_doc = {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL,
        "tool_version": TOOL_VERSION,
        "capture": {
            "origins": sorted(origins),
            "har_sha256": sha256_file(har_path),
            "entries": stats["entries_total"],
        },
        "endpoints": finalized,
        "websocket": ws_doc,
        "sse": sse_doc,
        "stats": {
            "endpoint_count": len(finalized),
            "path_count": len({item["path_template"] for item in finalized}),
            "status_count": len({status for item in finalized for status in item["statuses"]}),
        },
    }
    report = {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL,
        "tool_version": TOOL_VERSION,
        "inputs": inputs,
        "counts": stats,
        "masking": {
            "pii_masked": mask_pii,
            "sentinels": sorted(MASK_SENTINELS),
            "secret_headers": stats["secret_headers"],
            "secret_values": stats["secret_values"],
            "pii_values": stats["pii_values"],
            "token_values": stats["token_values"],
        },
        "outputs": {
            "endpoints": len(finalized),
            "schemas": len(registry),
            "js_routes": len(route_list),
            "route_hits": route_hits,
            "ws_channels": len(ws_doc["channels"]),
            "sse_channels": len(sse_doc["channels"]),
        },
        "warnings": warnings,
    }

    write_json(out_dir / "endpoints.json", endpoints_doc)
    write_json(
        out_dir / "schemas.json",
        {"schema_version": SCHEMA_VERSION, "tool": TOOL, "schemas": dict(sorted(registry.items()))},
    )
    write_json(
        out_dir / "js_routes.json",
        {
            "schema_version": SCHEMA_VERSION,
            "tool": TOOL,
            "provenance_note": (
                "Routes found only in client bundles or source maps. These were NOT observed "
                "on the wire; treat them as hypotheses, not contracts."
            ),
            "routes": route_list,
        },
    )
    write_json(out_dir / "parse_report.json", report)

    print(
        json.dumps(
            {
                "status": "ok",
                "out": str(out_dir),
                "endpoints": len(finalized),
                "schemas": len(registry),
                "js_routes": len(route_list),
                "warnings": warnings,
                "next_step": (
                    f"python3 generate_openapi.py --endpoints {out_dir / 'endpoints.json'} "
                    f"--schemas {out_dir / 'schemas.json'} "
                    f"--routes {out_dir / 'js_routes.json'} --out recon/openapi.yaml"
                ),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
