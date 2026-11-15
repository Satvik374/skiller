#!/usr/bin/env python3
"""Capture HTTP, WebSocket and Server-Sent-Event traffic from an authorized web app.

The recorder opens a real browser, writes a full HAR of every request, logs WebSocket
frames, mirrors EventSource messages, and saves the authenticated storage state so later
phases can replay the session without re-authenticating.

    python3 capture_traffic.py --url https://app.example.com --out recon/capture --headed

Drive the application as an ordinary user. Press Enter in the terminal (or create the
--stop-file) to finish. Use --flow to replay a fixed step list instead of navigating by hand.

AUTHORIZATION: run this only against a target you own or have written permission to inspect,
using your own account. The --origin allowlist keeps the session on the authorized site; the
script deliberately provides no way to bypass authentication, paywalls or rate limits.

Exit codes: 0 ok, 1 error, 2 bad usage, 3 playwright missing, 4 scope violation.
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

TOOL = "capture_traffic"
TOOL_VERSION = "1.0.0"

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_NO_PLAYWRIGHT = 3
EXIT_SCOPE = 4

FLOW_ACTIONS = (
    "goto",
    "click",
    "fill",
    "press",
    "wait",
    "wait_for",
    "wait_for_text",
    "scroll",
    "select",
    "hover",
    "check",
    "screenshot",
)

SSE_INIT_SCRIPT = r"""
(() => {
  const KEY = "__backendClonerSSE";
  if (window[KEY]) { return; }
  window[KEY] = [];
  if (typeof window.EventSource !== "function") { return; }
  const Native = window.EventSource;
  const push = (rec) => { try { window[KEY].push(rec); } catch (e) {} };
  const track = (url, ev, kind) => push({
    kind: kind,
    url: String(url),
    ts: Date.now(),
    type: (ev && ev.type) ? String(ev.type) : null,
    data: (ev && ev.data !== undefined) ? String(ev.data) : null,
    last_event_id: (ev && ev.lastEventId) ? String(ev.lastEventId) : null
  });
  function Tracked(url, init) {
    const es = new Native(url, init);
    track(url, null, "open");
    const mirrored = Object.create(null);
    const mirror = (t) => {
      if (mirrored[t]) { return; }
      mirrored[t] = true;
      Native.prototype.addEventListener.call(es, t, (ev) => track(url, ev, "event"));
    };
    ["message", "open", "error"].forEach(mirror);
    const add = es.addEventListener;
    es.addEventListener = function (t, fn, opts) {
      try { mirror(t); } catch (e) {}
      return add.call(es, t, fn, opts);
    };
    return es;
  }
  Tracked.prototype = Native.prototype;
  ["CONNECTING", "OPEN", "CLOSED"].forEach((k) => { Tracked[k] = Native[k]; });
  window.EventSource = Tracked;
})();
"""

HARVEST_SSE_JS = (
    "() => { const K = '__backendClonerSSE'; const q = window[K] || [];"
    " window[K] = []; return q; }"
)


class ScopeViolation(RuntimeError):
    """Raised when the session tries to leave the authorized origin set."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def failure_text(request: Any) -> str | None:
    """Playwright returns the failure as a string; tolerate object-shaped results too."""
    try:
        failure = request.failure
    except Exception:
        return None
    if failure is None:
        return None
    if isinstance(failure, str):
        return failure[:500]
    return str(getattr(failure, "error_text", failure))[:500]


def normalize_origin(url: str) -> tuple[str, str]:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise ValueError(f"unsupported scheme in {url!r}; use http or https")
    host = (parts.hostname or "").lower()
    if not host:
        raise ValueError(f"missing host in {url!r}")
    default_port = 443 if parts.scheme == "https" else 80
    netloc = host if parts.port in (None, default_port) else f"{host}:{parts.port}"
    return f"{parts.scheme}://{netloc}", host


class Scope:
    """Origin allowlist for the capture session."""

    def __init__(self, origins: list[str], allow_subdomains: bool = False) -> None:
        self.origins: list[str] = []
        self.hosts: list[str] = []
        for origin in origins:
            normalized, host = normalize_origin(origin)
            if normalized not in self.origins:
                self.origins.append(normalized)
            if host not in self.hosts:
                self.hosts.append(host)
        self.allow_subdomains = allow_subdomains

    def allows(self, url: str) -> bool:
        parts = urlsplit(url)
        if parts.scheme in ("about", "data", "blob", "chrome", "devtools"):
            return True
        if parts.scheme not in ("http", "https"):
            return False
        host = (parts.hostname or "").lower()
        for allowed in self.hosts:
            if host == allowed:
                return True
            if self.allow_subdomains and host.endswith("." + allowed):
                return True
        return False

    def describe(self) -> dict[str, Any]:
        return {
            "origins": list(self.origins),
            "hosts": list(self.hosts),
            "allow_subdomains": self.allow_subdomains,
        }


class Recorder:
    """Append-only JSONL writers for WebSocket, SSE and console events."""

    def __init__(self, outdir: Path, max_frame_bytes: int) -> None:
        outdir.mkdir(parents=True, exist_ok=True)
        self.outdir = outdir
        self.max_frame_bytes = max_frame_bytes
        self._ws = (outdir / "websocket.jsonl").open("w", encoding="utf-8")
        self._sse = (outdir / "sse.jsonl").open("w", encoding="utf-8")
        self._console = (outdir / "console.jsonl").open("w", encoding="utf-8")
        self._seq = {"ws": 0, "sse": 0, "console": 0}
        self._sockets: dict[int, str] = {}
        self._socket_count = 0
        self.counts = {
            "ws_frames_sent": 0,
            "ws_frames_received": 0,
            "sse_events": 0,
            "console_messages": 0,
            "page_errors": 0,
            "failed_requests": 0,
            "scope_denials": 0,
            "sockets": 0,
        }
        self.out_of_scope_requests: list[str] = []
        self.scope_violation: str | None = None

    def _write(self, handle, record: dict[str, Any]) -> None:
        handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
        handle.flush()

    def socket_id(self, ws: Any) -> str:
        key = id(ws)
        if key not in self._sockets:
            self._socket_count += 1
            self._sockets[key] = f"ws-{self._socket_count}"
            self.counts["sockets"] = self._socket_count
        return self._sockets[key]

    def ws_frame(self, ws: Any, direction: str, payload: Any) -> None:
        raw: bytes
        encoding = "utf-8"
        if isinstance(payload, (bytes, bytearray)):
            raw = bytes(payload)
            encoding = "base64"
        else:
            raw = str(payload).encode("utf-8", errors="replace")
        truncated = len(raw) > self.max_frame_bytes
        if truncated:
            raw = raw[: self.max_frame_bytes]
        data = (
            base64.b64encode(raw).decode("ascii")
            if encoding == "base64"
            else raw.decode("utf-8", errors="replace")
        )
        self._seq["ws"] += 1
        self.counts["ws_frames_sent" if direction == "sent" else "ws_frames_received"] += 1
        self._write(
            self._ws,
            {
                "channel": "ws",
                "seq": self._seq["ws"],
                "socket": self.socket_id(ws),
                "url": getattr(ws, "url", None),
                "direction": direction,
                "encoding": encoding,
                "bytes": len(raw),
                "truncated": truncated,
                "ts": utc_now(),
                "data": data,
            },
        )

    def sse(self, events: list[dict[str, Any]]) -> None:
        for event in events:
            self._seq["sse"] += 1
            self.counts["sse_events"] += 1
            record = {
                "channel": "sse",
                "seq": self._seq["sse"],
                "ts": utc_now(),
                "source": "eventsource",
                "direction": "received",
            }
            record.update(event)
            self._write(self._sse, record)

    def console(self, kind: str, **fields: Any) -> None:
        self._seq["console"] += 1
        if kind == "console":
            self.counts["console_messages"] += 1
        elif kind == "pageerror":
            self.counts["page_errors"] += 1
        elif kind == "requestfailed":
            self.counts["failed_requests"] += 1
        elif kind == "scope":
            self.counts["scope_denials"] += 1
        record = {"seq": self._seq["console"], "ts": utc_now(), "kind": kind}
        record.update(fields)
        self._write(self._console, record)

    def harvest(self, page: Any) -> None:
        """Drain buffered EventSource events out of the page."""
        try:
            events = page.evaluate(HARVEST_SSE_JS)
        except Exception:
            return
        if events:
            self.sse(events)

    def close(self) -> None:
        for handle in (self._ws, self._sse, self._console):
            try:
                handle.close()
            except Exception:
                pass


def load_flow(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("steps")
    if not isinstance(data, list) or not data:
        raise ValueError("flow file must be a non-empty JSON list of steps, or {\"steps\": [...]}")
    for index, step in enumerate(data):
        if not isinstance(step, dict):
            raise ValueError(f"flow step {index} is not an object")
        action = str(step.get("action", "")).lower()
        if action not in FLOW_ACTIONS:
            raise ValueError(
                f"flow step {index} has unsupported action {action!r}; "
                f"supported: {', '.join(FLOW_ACTIONS)}"
            )
    return data


def run_flow(
    page: Any,
    steps: list[dict[str, Any]],
    base_url: str,
    scope: Scope,
    recorder: Recorder,
    timeout_ms: int,
) -> None:
    for index, step in enumerate(steps):
        action = str(step["action"]).lower()
        optional = bool(step.get("optional", False))
        selector = step.get("selector") or step.get("locator")
        value = step.get("value", step.get("text"))
        wait_ms = int(step.get("ms", step.get("timeout_ms", timeout_ms)))
        try:
            if action == "goto":
                target = str(value or step.get("url") or "")
                if not target:
                    raise ValueError("goto requires a url in 'value'")
                target = urljoin(base_url, target)
                if not scope.allows(target):
                    raise ScopeViolation(f"flow step {index}: navigation outside scope: {target}")
                page.goto(target, wait_until="domcontentloaded", timeout=wait_ms)
            elif action == "click":
                page.locator(str(selector)).first.click(timeout=wait_ms)
            elif action == "fill":
                page.locator(str(selector)).first.fill(str(value or ""), timeout=wait_ms)
            elif action == "press":
                key = str(step.get("key") or value or "Enter")
                if selector:
                    page.locator(str(selector)).first.press(key, timeout=wait_ms)
                else:
                    page.keyboard.press(key)
            elif action == "wait":
                page.wait_for_timeout(int(step.get("ms", 1000)))
            elif action == "wait_for":
                page.locator(str(selector)).first.wait_for(
                    state=str(step.get("state", "visible")), timeout=wait_ms
                )
            elif action == "wait_for_text":
                page.get_by_text(str(value or ""), exact=False).first.wait_for(timeout=wait_ms)
            elif action == "scroll":
                page.mouse.wheel(int(step.get("x", 0)), int(step.get("y", 600)))
                page.wait_for_timeout(int(step.get("ms", 300)))
            elif action == "select":
                page.locator(str(selector)).first.select_option(str(value or ""), timeout=wait_ms)
            elif action == "hover":
                page.locator(str(selector)).first.hover(timeout=wait_ms)
            elif action == "check":
                page.locator(str(selector)).first.check(timeout=wait_ms)
            elif action == "screenshot":
                name = str(step.get("name") or f"step-{index:03d}.png")
                page.screenshot(path=str(Path(recorder.outdir) / name), full_page=False)
            recorder.console("flow", step=index, action=action, status="ok")
        except ScopeViolation:
            raise
        except Exception as exc:  # noqa: BLE001 - flow steps are best-effort unless required
            recorder.console(
                "flow", step=index, action=action, status="error", error=type(exc).__name__
            )
            if not optional:
                raise


def wait_for_operator(
    page: Any,
    recorder: Recorder,
    duration: int,
    stop: threading.Event,
    stop_file: Path | None,
) -> None:
    deadline = time.time() + max(0, duration)
    interactive = sys.stdin is not None and sys.stdin.isatty()
    if interactive:
        print(
            "\n[capture] Recording. Navigate every flow you need, then press Enter to stop.\n",
            flush=True,
        )

        def _reader() -> None:
            try:
                sys.stdin.readline()
            except Exception:
                pass
            stop.set()

        threading.Thread(target=_reader, daemon=True).start()
    else:
        print(
            f"[capture] Non-interactive session: recording for up to {duration}s "
            f"(or until the stop file appears).",
            flush=True,
        )

    while not stop.is_set() and time.time() < deadline:
        if stop_file is not None and stop_file.exists():
            print(f"[capture] Stop file {stop_file} detected.", flush=True)
            break
        try:
            page.wait_for_timeout(250)
        except Exception:
            break
        recorder.harvest(page)
        if recorder.scope_violation:
            break


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="capture_traffic.py",
        description=(
            "Record HAR + WebSocket + SSE traffic from an authorized web application. "
            "Use only on targets you own or are permitted to inspect."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  capture_traffic.py --url https://app.example.com --out recon/capture --headed\n"
            "  capture_traffic.py --url https://app.example.com --out recon/capture \\\n"
            "      --flow recon/flows.json --duration 180\n"
            "  capture_traffic.py --url https://app.example.com --out recon/capture \\\n"
            "      --storage-state recon/capture/storage_state.json --duration 60\n"
            "\n"
            "Flow file format (JSON list, or {\"steps\": [...]}):\n"
            "  [{\"action\": \"goto\", \"value\": \"/login\"},\n"
            "   {\"action\": \"fill\", \"selector\": \"#email\", \"value\": \"test@example.com\"},\n"
            "   {\"action\": \"click\", \"selector\": \"button[type=submit]\"},\n"
            "   {\"action\": \"wait_for\", \"selector\": \"[data-testid=dashboard]\"}]\n"
            f"  Supported actions: {', '.join(FLOW_ACTIONS)}\n"
            "  Add \"optional\": true to tolerate a failing step.\n"
        ),
    )
    parser.add_argument("--url", required=True, help="starting URL of the authorized target")
    parser.add_argument("--out", required=True, help="output directory for capture artifacts")
    parser.add_argument(
        "--origin",
        action="append",
        default=[],
        metavar="ORIGIN",
        help="authorized origin (repeatable). Defaults to the origin of --url",
    )
    parser.add_argument(
        "--allow-subdomains",
        action="store_true",
        help="treat subdomains of the allowed origins as in scope",
    )
    parser.add_argument(
        "--flow",
        metavar="PATH",
        help="JSON step list to replay instead of navigating interactively",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=300,
        metavar="SECONDS",
        help="maximum recording time (default: 300); interactive sessions can stop earlier",
    )
    parser.add_argument(
        "--stop-file",
        metavar="PATH",
        help="finish the capture when this file appears (handy for scripted runs)",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="run with a visible browser window (recommended for manual navigation)",
    )
    parser.add_argument(
        "--browser",
        default="chromium",
        choices=["chromium", "chrome", "firefox", "webkit"],
        help="browser engine (default: chromium)",
    )
    parser.add_argument(
        "--har-content",
        default="embed",
        choices=["embed", "omit", "attach"],
        help="HAR body capture mode (default: embed; 'omit' is smaller but blocks schema inference)",
    )
    parser.add_argument(
        "--storage-state",
        metavar="PATH",
        help="load a previously saved storage_state.json to skip re-authentication",
    )
    parser.add_argument(
        "--headers-file",
        metavar="PATH",
        help="JSON object of extra HTTP headers (keep credentials out of argv)",
    )
    parser.add_argument(
        "--ignore-https-errors",
        action="store_true",
        help="accept invalid TLS certificates (local/test environments only)",
    )
    parser.add_argument("--width", type=int, default=1440, help="viewport width (default: 1440)")
    parser.add_argument("--height", type=int, default=900, help="viewport height (default: 900)")
    parser.add_argument(
        "--timeout-ms", type=int, default=15000, help="per-action timeout in ms (default: 15000)"
    )
    parser.add_argument(
        "--max-frame-bytes",
        type=int,
        default=262144,
        help="truncate WebSocket frames larger than this (default: 262144)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="write into a non-empty output directory",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate configuration, print the resolved plan, and exit without a browser",
    )
    parser.add_argument("--version", action="version", version=f"{TOOL} {TOOL_VERSION}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        start_origin, start_host = normalize_origin(args.url)
    except ValueError as exc:
        print(f"[capture] error: {exc}", file=sys.stderr)
        return EXIT_USAGE

    origins = args.origin or [start_origin]
    try:
        scope = Scope(origins, allow_subdomains=args.allow_subdomains)
    except ValueError as exc:
        print(f"[capture] error: {exc}", file=sys.stderr)
        return EXIT_USAGE

    outdir = Path(args.out).expanduser()
    stop_file = Path(args.stop_file).expanduser() if args.stop_file else None
    flow_steps: list[dict[str, Any]] = []
    if args.flow:
        try:
            flow_steps = load_flow(Path(args.flow).expanduser())
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"[capture] error: invalid flow file: {exc}", file=sys.stderr)
            return EXIT_USAGE

    headers: dict[str, str] = {}
    if args.headers_file:
        try:
            raw_headers = json.loads(Path(args.headers_file).expanduser().read_text("utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[capture] error: invalid headers file: {exc}", file=sys.stderr)
            return EXIT_USAGE
        if not isinstance(raw_headers, dict):
            print("[capture] error: headers file must contain a JSON object", file=sys.stderr)
            return EXIT_USAGE
        headers = {str(k): str(v) for k, v in raw_headers.items()}

    plan = {
        "tool": TOOL,
        "tool_version": TOOL_VERSION,
        "target": {"url": args.url, "origin": start_origin, "host": start_host},
        "scope": scope.describe(),
        "out": str(outdir),
        "mode": "flow" if flow_steps else "interactive",
        "flow_steps": len(flow_steps),
        "browser": args.browser,
        "headed": bool(args.headed),
        "har_content": args.har_content,
        "duration_seconds": args.duration,
        "artifacts": [
            "network.har",
            "websocket.jsonl",
            "sse.jsonl",
            "console.jsonl",
            "storage_state.json",
            "session.json",
        ],
        "authorization_reminder": (
            "Capture only an app you own or may inspect, with your own account. "
            "This tool cannot bypass auth, paywalls or rate limits, by design."
        ),
    }
    if args.dry_run:
        print(json.dumps(plan, indent=2, sort_keys=True))
        return EXIT_OK

    if outdir.exists() and any(outdir.iterdir()) and not args.force:
        print(
            f"[capture] error: {outdir} is not empty; pass --force to add files anyway",
            file=sys.stderr,
        )
        return EXIT_USAGE
    outdir.mkdir(parents=True, exist_ok=True)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "[capture] error: the 'playwright' package is required for capture.\n"
            "  pip install playwright && playwright install chromium",
            file=sys.stderr,
        )
        return EXIT_NO_PLAYWRIGHT

    recorder = Recorder(outdir, args.max_frame_bytes)
    started_at = utc_now()
    started_monotonic = time.monotonic()
    stop = threading.Event()
    scope_errors: list[str] = []
    browser = None
    context = None
    exit_code = EXIT_OK
    browser_meta: dict[str, Any] = {"name": args.browser}

    try:
        with sync_playwright() as playwright:
            engine = getattr(playwright, args.browser)
            launch_kwargs: dict[str, Any] = {"headless": not args.headed}
            browser = engine.launch(**launch_kwargs)
            browser_meta["version"] = browser.version

            context_kwargs: dict[str, Any] = {
                "viewport": {"width": args.width, "height": args.height},
                "record_har_path": str(outdir / "network.har"),
                "record_har_content": args.har_content,
                "ignore_https_errors": bool(args.ignore_https_errors),
            }
            if args.storage_state:
                state_path = Path(args.storage_state).expanduser()
                if not state_path.exists():
                    raise FileNotFoundError(f"storage state not found: {state_path}")
                context_kwargs["storage_state"] = str(state_path)
            context = browser.new_context(**context_kwargs)
            context.add_init_script(SSE_INIT_SCRIPT)
            if headers:
                context.set_extra_http_headers(headers)

            page = context.new_page()
            page.set_default_timeout(args.timeout_ms)
            browser_meta["user_agent"] = page.evaluate("() => navigator.userAgent")

            def on_websocket(ws: Any) -> None:
                ws.on("framesent", lambda payload: recorder.ws_frame(ws, "sent", payload))
                ws.on(
                    "framereceived", lambda payload: recorder.ws_frame(ws, "received", payload)
                )
                ws.on(
                    "socketerror",
                    lambda error: recorder.console("socketerror", error=str(error)[:500]),
                )

            page.on("websocket", on_websocket)
            page.on(
                "console",
                lambda msg: recorder.console(
                    "console", level=msg.type, text=msg.text[:2000]
                ),
            )
            page.on(
                "pageerror", lambda err: recorder.console("pageerror", error=str(err)[:2000])
            )
            page.on(
                "requestfailed",
                lambda req: recorder.console(
                    "requestfailed",
                    url=req.url.split("?")[0][:500],
                    method=req.method,
                    failure=failure_text(req),
                ),
            )

            def on_request(request: Any) -> None:
                if scope.allows(request.url):
                    return
                recorder.console(
                    "scope",
                    event="out_of_scope_request",
                    host=(urlsplit(request.url).hostname or "").lower(),
                    method=request.method,
                    resource_type=request.resource_type,
                )
                if len(recorder.out_of_scope_requests) < 50:
                    recorder.out_of_scope_requests.append(request.url.split("?")[0][:500])

            def on_navigated(frame: Any) -> None:
                if frame.parent_frame is not None:
                    return
                if scope.allows(frame.url):
                    return
                recorder.scope_violation = f"navigation left the authorized scope: {frame.url}"
                scope_errors.append(frame.url)

            page.on("request", on_request)
            page.on("framenavigated", on_navigated)

            print(f"[capture] Opening {args.url}", flush=True)
            page.goto(args.url, wait_until="domcontentloaded", timeout=args.timeout_ms)
            recorder.harvest(page)

            if flow_steps:
                run_flow(page, flow_steps, args.url, scope, recorder, args.timeout_ms)
                # Let late XHR/WS traffic settle after the final step.
                page.wait_for_timeout(1500)
                recorder.harvest(page)
            else:
                wait_for_operator(page, recorder, args.duration, stop, stop_file)

            recorder.harvest(page)

            # Persist the authenticated session for later phases (sensitive: contains cookies).
            context.storage_state(path=str(outdir / "storage_state.json"))

            if recorder.scope_violation:
                print(f"[capture] scope violation: {recorder.scope_violation}", file=sys.stderr)
                exit_code = EXIT_SCOPE

            context.close()  # flushes the HAR
            context = None
            browser.close()
            browser = None
    except ScopeViolation as exc:
        print(f"[capture] scope violation: {exc}", file=sys.stderr)
        scope_errors.append(str(exc))
        exit_code = EXIT_SCOPE
    except Exception as exc:  # noqa: BLE001 - report a clean failure for the operator
        print(f"[capture] error: {type(exc).__name__}: {exc}", file=sys.stderr)
        exit_code = EXIT_ERROR
    finally:
        if context is not None:
            try:
                context.close()
            except Exception:
                pass
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass
        recorder.close()

    duration = round(time.monotonic() - started_monotonic, 2)
    session = {
        "tool": TOOL,
        "tool_version": TOOL_VERSION,
        "target": {"start_url": args.url, "origin": start_origin, "host": start_host},
        "scope": scope.describe(),
        "browser": browser_meta,
        "mode": "flow" if flow_steps else "interactive",
        "flow_steps": len(flow_steps),
        "har_content": args.har_content,
        "started_at": started_at,
        "ended_at": utc_now(),
        "duration_seconds": duration,
        "counts": recorder.counts,
        "scope_violations": scope_errors,
        "out_of_scope_requests": sorted(set(recorder.out_of_scope_requests)),
        "artifacts": {
            "har": str(outdir / "network.har"),
            "websocket": str(outdir / "websocket.jsonl"),
            "sse": str(outdir / "sse.jsonl"),
            "console": str(outdir / "console.jsonl"),
            "storage_state": str(outdir / "storage_state.json"),
            "session": str(outdir / "session.json"),
        },
        "sensitivity": (
            "storage_state.json holds live cookies and the HAR holds unmasked bodies. "
            "Never commit or share this directory."
        ),
        "next_step": (
            f"python3 parse_har.py --har {outdir / 'network.har'} --out recon/distilled"
        ),
    }
    (outdir / "session.json").write_text(
        json.dumps(session, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    har_path = outdir / "network.har"
    summary = {
        "status": "ok" if exit_code == EXIT_OK else "incomplete",
        "exit_code": exit_code,
        "duration_seconds": duration,
        "har_bytes": har_path.stat().st_size if har_path.exists() else 0,
        "counts": recorder.counts,
        "session": str(outdir / "session.json"),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
