#!/usr/bin/env python3
"""Exercise every interactive control on a page. Observation only.

Loads each page, enumerates the controls a visitor can see, clicks them one at
a time from a clean page load, and records the rendered before/after state:

    reference/interactions/
    |-- index.json                  coverage per page + totals
    `-- <page>/
        |-- manifest.json           one entry per discovered control
        `-- shots/
            |-- 001-menu-before.png
            |-- 001-menu-after.png
            `-- 001-menu-after-element.png

It never saves the page HTML, CSS or JS, and never downloads an asset.
Screenshots and JSON are reference material for rebuilding the UI from
observation.

    python3 explore_interactions.py https://example.com --out clones/example
    python3 explore_interactions.py https://example.com --out clones/example \
        --crawl-depth 1 --max-clicks 300 --dry-run

Requires: pip install playwright && playwright install chromium
"""
import argparse
import datetime
import json
import os
import re
import sys
import urllib.parse

CONTROL_SELECTOR = (
    "a[href], button, input:not([type=hidden]), select, textarea, summary, "
    "[role=button], [role=tab], [role=menuitem], [role=menuitemcheckbox], "
    "[role=menuitemradio], [role=switch], [role=checkbox], [role=radio], "
    "[role=link], [role=combobox], [onclick], [aria-expanded], "
    "[aria-controls], [aria-haspopup], [tabindex]:not([tabindex='-1'])"
)

# Controls that change shared, external or account state. Never clicked.
RISKY = re.compile(
    r"\b(delete|remove|destroy|erase|wipe|deactivate|log\s?out|sign\s?out|"
    r"unsubscribe|cancel\s+(subscription|plan|account)|close\s+account|"
    r"purchase|buy\s+now|checkout|place\s+order|pay\s+now|donate|"
    r"send|confirm\s+(payment|order)|reset\s+all|clear\s+all)\b",
    re.IGNORECASE,
)

BINARY_LINK = re.compile(
    r"\.(png|jpe?g|gif|svg|webp|avif|ico|bmp|tiff?|pdf|zip|gz|tar|mp4|mov|"
    r"webm|mp3|wav|ogg|css|js|mjs|json|xml|woff2?|ttf|otf|eot)(\?|$)",
    re.IGNORECASE,
)

JS_HELPERS = r"""
function __fcClip(s, n) {
  const t = String(s || "").replace(/\s+/g, " ").trim();
  return t.length > n ? t.slice(0, n) + "\u2026" : t;
}
function __fcRound(n) { return Math.round(n * 10) / 10; }
function __fcPath(el) {
  const parts = [];
  let node = el;
  while (node && node.nodeType === 1 && node !== document.documentElement) {
    let part = node.tagName.toLowerCase();
    if (node.id) {
      let id = node.id;
      try { id = CSS.escape(id); } catch (e) { /* older browsers */ }
      parts.unshift(part + "#" + id);
      break;
    }
    const parent = node.parentElement;
    if (parent) {
      const same = Array.prototype.filter.call(
        parent.children, (c) => c.tagName === node.tagName);
      if (same.length > 1) part += ":nth-of-type(" + (same.indexOf(node) + 1) + ")";
    }
    parts.unshift(part);
    if (part === "body") break;
    node = parent;
  }
  return parts.join(" > ");
}
function __fcVisible(el, cs) {
  cs = cs || getComputedStyle(el);
  if (cs.display === "none" || cs.visibility === "hidden" ||
      cs.visibility === "collapse") return false;
  const r = el.getBoundingClientRect();
  return r.width > 0.5 && r.height > 0.5;
}
function __fcBox(el) {
  const r = el.getBoundingClientRect();
  return {
    x: __fcRound(r.left + window.scrollX),
    y: __fcRound(r.top + window.scrollY),
    w: __fcRound(r.width),
    h: __fcRound(r.height)
  };
}
"""

ENUMERATE_JS = (
    "(selector) => {\n"
    + JS_HELPERS
    + r"""
  const out = [];
  const seen = new Set();
  for (const el of document.querySelectorAll(selector)) {
    if (out.length >= 5000) break;
    const cs = getComputedStyle(el);
    if (!__fcVisible(el, cs)) continue;
    const path = __fcPath(el);
    if (seen.has(path)) continue;
    seen.add(path);
    out.push({
      path: path,
      tag: el.tagName.toLowerCase(),
      role: el.getAttribute("role"),
      type: el.getAttribute("type"),
      text: __fcClip(el.innerText || el.value ||
                     el.getAttribute("aria-label") ||
                     el.getAttribute("title") || "", 120),
      ariaLabel: el.getAttribute("aria-label"),
      title: el.getAttribute("title"),
      name: el.getAttribute("name"),
      href: el.getAttribute("href"),
      absHref: el.href || null,
      target: el.getAttribute("target"),
      disabled: !!(el.disabled || el.getAttribute("aria-disabled") === "true"),
      expanded: el.getAttribute("aria-expanded"),
      pressed: el.getAttribute("aria-pressed"),
      checked: (el.type === "checkbox" || el.type === "radio")
        ? !!el.checked : null,
      download: el.hasAttribute("download"),
      formMethod: el.form ? (el.form.getAttribute("method") || "get") : null,
      formAction: el.form ? el.form.action : null,
      box: __fcBox(el)
    });
  }
  return out;
}
"""
)

STATE_JS = (
    "(path) => {\n"
    + JS_HELPERS
    + r"""
  const el = path ? document.querySelector(path) : null;
  const OVERLAY = "[role=dialog],dialog,[aria-modal='true'],[role=menu]," +
    "[role=listbox],[role=tooltip],[role=alert],[role=alertdialog]," +
    ".modal,.popover,.dropdown,.drawer,[data-state='open']";
  const PROPS = ["color", "backgroundColor", "backgroundImage", "borderColor",
    "borderTopColor", "borderRadius", "boxShadow", "transform", "opacity",
    "filter", "outline", "textDecorationLine", "padding", "fontSize",
    "fontWeight", "lineHeight", "display", "visibility"];
  const styleOf = (node) => {
    const cs = getComputedStyle(node);
    const out = {};
    for (const p of PROPS) out[p] = cs[p];
    return out;
  };
  const overlays = [];
  for (const node of document.querySelectorAll(OVERLAY)) {
    const cs = getComputedStyle(node);
    if (cs.display === "none" || cs.visibility === "hidden" ||
        cs.opacity === "0") continue;
    const r = node.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) continue;
    overlays.push({
      path: __fcPath(node),
      tag: node.tagName.toLowerCase(),
      role: node.getAttribute("role"),
      text: __fcClip(node.innerText, 160),
      box: __fcBox(node),
      style: styleOf(node)
    });
  }
  return {
    url: location.href,
    title: document.title,
    scrollY: Math.round(window.scrollY),
    bodyOverflow: getComputedStyle(document.body).overflow,
    nodes: document.querySelectorAll("*").length,
    textLength: (document.body.innerText || "").length,
    overlays: overlays,
    control: el ? {
      expanded: el.getAttribute("aria-expanded"),
      pressed: el.getAttribute("aria-pressed"),
      checked: (el.type === "checkbox" || el.type === "radio")
        ? !!el.checked : null,
      box: __fcBox(el),
      style: styleOf(el)
    } : null
  };
}
"""
)

LINKS_JS = (
    "() => Array.from(document.querySelectorAll('a[href]'))"
    ".map((a) => a.href)"
)


def slugify(text, limit=32):
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return slug[:limit] or "control"


def page_slug(url):
    path = urllib.parse.urlsplit(url).path.strip("/")
    if not path:
        return "index"
    return slugify(path.replace("/", "-"), 60) or "index"


def normalize(url):
    parts = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, parts.path or "/", parts.query, "")
    )


def origin_of(url):
    parts = urllib.parse.urlsplit(url)
    return "%s://%s" % (parts.scheme, parts.netloc)


def skip_reason(entry, origin, allow_form_submit):
    """Return a reason to skip, or None to click."""
    if entry["disabled"]:
        return "disabled"
    if entry["tag"] == "input" and entry["type"] in ("password", "file"):
        return "sensitive-input"
    if entry["target"] == "_blank":
        return "external-navigation"
    if entry["download"]:
        return "download"
    href = entry.get("absHref")
    if href:
        parts = urllib.parse.urlsplit(href)
        if parts.scheme in ("mailto", "tel", "javascript", "data"):
            return "non-http-link"
        if parts.scheme in ("http", "https") and origin_of(href) != origin:
            return "external-navigation"
    action = entry.get("formAction")
    if action and origin_of(action) != origin:
        return "cross-origin-form"
    if entry["type"] == "submit" and not allow_form_submit:
        return "form-submit"
    label = " ".join(
        filter(None, [entry.get("text"), entry.get("ariaLabel"),
                      entry.get("title"), entry.get("name"),
                      entry.get("path")])
    )
    if RISKY.search(label):
        return "destructive-action"
    return None


def style_delta(before, after):
    b = (before or {}).get("style") or {}
    a = (after or {}).get("style") or {}
    out = {}
    for prop, value in a.items():
        if b.get(prop) != value:
            out[prop] = {"from": b.get(prop), "to": value}
    return out


def new_overlays(before, after):
    seen = {o["path"] for o in (before or {}).get("overlays", [])}
    return [o for o in after.get("overlays", []) if o["path"] not in seen]


def classify(before, after, appeared):
    if after["url"] != before["url"]:
        return "navigation"
    if appeared:
        return "overlay"
    bc = before.get("control") or {}
    ac = after.get("control") or {}
    if bc.get("expanded") != ac.get("expanded"):
        return "expanded"
    if (bc.get("pressed") != ac.get("pressed") or
            bc.get("checked") != ac.get("checked")):
        return "toggled"
    if (after["textLength"] != before["textLength"] or
            after["nodes"] != before["nodes"]):
        return "content-change"
    return "no-visible-change"


def settle_scroll(page, step, pause):
    """Scroll the page so entrance animations and lazy content fire."""
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(max(80, pause // 2))
    height = page.evaluate("document.documentElement.scrollHeight")
    viewport = page.viewport_size["height"]
    y = 0
    while y < height:
        y += step
        page.evaluate("window.scrollTo(0, %d)" % y)
        page.wait_for_timeout(pause)
        height = page.evaluate("document.documentElement.scrollHeight")
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(pause)


def load(page, url, args):
    page.goto(url, wait_until="domcontentloaded", timeout=args.timeout)
    try:
        page.wait_for_load_state("networkidle", timeout=5000)
    except Exception:
        pass
    page.wait_for_timeout(args.settle)
    if not args.no_scroll_settle:
        settle_scroll(page, args.scroll_step, min(args.settle, 250))


def discover_pages(page, seeds, depth, timeout):
    """Breadth-first same-origin crawl. Depth 0 returns the seeds only."""
    order = []
    seen = set()
    for url in seeds:
        norm = normalize(url)
        if norm not in seen:
            seen.add(norm)
            order.append(url)
    frontier = list(order)
    for _ in range(depth):
        following = []
        for url in frontier:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            try:
                links = page.evaluate(LINKS_JS)
            except Exception:
                continue
            for link in links:
                norm = normalize(link)
                if norm in seen:
                    continue
                if origin_of(norm) != origin_of(url):
                    continue
                if BINARY_LINK.search(urllib.parse.urlsplit(norm).path):
                    continue
                seen.add(norm)
                following.append(norm)
        order.extend(following)
        frontier = following
        if not frontier:
            break
    return order


def write_json(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)


def read_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def build_manifest(url, args, controls, origin):
    return {
        "url": url,
        "origin": origin,
        "viewport": "%dx%d" % (args.width, args.height),
        "startedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "finishedAt": None,
        "selector": CONTROL_SELECTOR,
        "discovered": len(controls),
        "clicked": 0,
        "skipped": 0,
        "failed": 0,
        "truncated": len(controls) > args.max_clicks,
        "complete": False,
        "interactions": [],
        "remaining": [
            {"path": c["path"], "text": c["text"]}
            for c in controls[args.max_clicks:]
        ],
    }


def run_page(browser, url, args):
    slug = page_slug(url)
    base = os.path.join(args.out, "reference", "interactions")
    page_dir = os.path.join(base, slug)
    shots = os.path.join(page_dir, "shots")
    os.makedirs(shots, exist_ok=True)
    manifest_path = os.path.join(page_dir, "manifest.json")

    context = browser.new_context(
        viewport={"width": args.width, "height": args.height},
        device_scale_factor=args.device_scale,
        is_mobile=args.width < 500,
        has_touch=args.width < 500,
        reduced_motion="no-preference",
    )
    popups = []
    page = context.new_page()

    def on_popup(popup):
        if popup is page:
            return
        popups.append(popup.url)
        try:
            popup.close()
        except Exception:
            pass

    context.on("page", on_popup)
    dialogs = []

    def on_dialog(dialog):
        dialogs.append({"type": dialog.type, "message": dialog.message[:200]})
        try:
            dialog.dismiss()
        except Exception:
            pass

    page.on("dialog", on_dialog)
    page.set_default_timeout(args.click_timeout)

    try:
        load(page, url, args)
        origin = origin_of(url)
        controls = page.evaluate(ENUMERATE_JS, CONTROL_SELECTOR)
        for control in controls:
            control["skipReason"] = skip_reason(
                control, origin, args.allow_form_submit
            )

        manifest = build_manifest(url, args, controls, origin)
        existing = read_json(manifest_path) if args.resume else None
        done = {}
        if existing:
            for item in existing.get("interactions", []):
                if item.get("decision") in ("clicked", "skipped"):
                    done[item["path"]] = item
            manifest["startedAt"] = existing.get("startedAt",
                                                manifest["startedAt"])

        if args.dry_run:
            print("dry run: %s — %d controls, %d would be skipped"
                  % (url, len(controls),
                     sum(1 for c in controls if c["skipReason"])))
            for control in controls[:args.max_clicks]:
                print("  %-12s %-18s %s"
                      % (control["skipReason"] or "click",
                         control["tag"], control["text"][:60]))
            return {"url": url, "slug": slug, "manifest": None,
                    "discovered": len(controls), "clicked": 0, "skipped": 0,
                    "failed": 0, "truncated": manifest["truncated"],
                    "complete": False}

        for index, control in enumerate(controls[:args.max_clicks], 1):
            path = control["path"]
            if path in done:
                manifest["interactions"].append(done.pop(path))
                continue

            entry = {
                "id": "%03d" % index,
                "path": path,
                "tag": control["tag"],
                "role": control["role"],
                "type": control["type"],
                "label": control["text"],
                "href": control.get("absHref"),
                "box": control["box"],
                "decision": None,
                "skipReason": control["skipReason"],
                "change": None,
                "before": None,
                "after": None,
                "newVisible": [],
                "styleDelta": {},
                "dialog": None,
                "popups": [],
                "screenshots": {"before": None, "after": None,
                                "afterElement": None},
                "restored": None,
                "error": None,
            }

            if control["skipReason"]:
                entry["decision"] = "skipped"
                entry["restored"] = "not-clicked"
                manifest["skipped"] += 1
                manifest["interactions"].append(entry)
                write_json(manifest_path, manifest)
                print("  [%03d] skipped %-18s %s (%s)"
                      % (index, control["tag"], control["text"][:50],
                         control["skipReason"]))
                continue

            # Every click starts from a clean page so states cannot leak.
            try:
                load(page, url, args)
            except Exception as exc:
                entry["decision"] = "failed"
                entry["error"] = "reload failed: %s" % str(exc)[:200]
                manifest["failed"] += 1
                manifest["interactions"].append(entry)
                write_json(manifest_path, manifest)
                print("  [%03d] failed reload: %s" % (index, entry["error"]))
                continue

            name = "%03d-%s" % (index, slugify(control["text"] or control["tag"]))
            before_png = os.path.join(shots, name + "-before.png")
            after_png = os.path.join(shots, name + "-after.png")

            try:
                locator = page.locator(path).first
                locator.scroll_into_view_if_needed(timeout=args.click_timeout)
                page.wait_for_timeout(max(120, args.settle // 3))
                entry["before"] = page.evaluate(STATE_JS, path)
                try:
                    locator.screenshot(path=before_png, animations="disabled")
                    entry["screenshots"]["before"] = os.path.relpath(
                        before_png, args.out)
                except Exception:
                    page.screenshot(path=before_png, animations="disabled")
                    entry["screenshots"]["before"] = os.path.relpath(
                        before_png, args.out)

                dialogs.clear()
                popups.clear()
                locator.click(timeout=args.click_timeout)
                page.wait_for_timeout(args.settle)
                try:
                    page.wait_for_load_state("networkidle", timeout=3000)
                except Exception:
                    pass
                page.wait_for_timeout(args.delay)

                navigated = normalize(page.url) != normalize(url)
                try:
                    entry["after"] = page.evaluate(
                        STATE_JS, None if navigated else path)
                except Exception as exc:
                    entry["after"] = {
                        "url": page.url, "title": "", "scrollY": 0,
                        "bodyOverflow": "", "nodes": 0, "textLength": 0,
                        "overlays": [], "control": None,
                    }
                    entry["error"] = "after-state: %s" % str(exc)[:160]
                entry["dialog"] = dialogs[0] if dialogs else None
                entry["popups"] = list(popups)
                appeared = new_overlays(entry["before"], entry["after"])
                entry["newVisible"] = appeared
                entry["styleDelta"] = style_delta(entry["before"],
                                                  entry["after"])
                entry["change"] = classify(entry["before"], entry["after"],
                                           appeared)

                try:
                    page.screenshot(path=after_png,
                                    full_page=args.full_after,
                                    animations="disabled")
                except Exception as exc:
                    raise RuntimeError(
                        "after screenshot failed: %s" % str(exc)[:160])
                entry["screenshots"]["after"] = os.path.relpath(
                    after_png, args.out)

                # Close-up of the control itself after the click, when it still
                # exists (a link that navigated away has no successor here).
                if not navigated:
                    try:
                        after_el_png = os.path.join(
                            shots, name + "-after-element.png")
                        target = page.locator(path).first
                        if target.count() and target.is_visible():
                            target.screenshot(path=after_el_png,
                                              animations="disabled")
                            entry["screenshots"]["afterElement"] = (
                                os.path.relpath(after_el_png, args.out))
                    except Exception:
                        pass
                entry["decision"] = "clicked"
                manifest["clicked"] += 1
                print("  [%03d] clicked %-18s %-40s -> %s"
                      % (index, control["tag"], control["text"][:40],
                         entry["change"]))
            except Exception as exc:
                entry["decision"] = "failed"
                entry["error"] = str(exc)[:300]
                manifest["failed"] += 1
                print("  [%03d] failed  %-18s %s (%s)"
                      % (index, control["tag"], control["text"][:40],
                         entry["error"][:80]))
            finally:
                manifest["interactions"].append(entry)
                write_json(manifest_path, manifest)

        manifest["interactions"].sort(key=lambda x: int(x["id"]))
        manifest["clicked"] = sum(
            1 for x in manifest["interactions"] if x["decision"] == "clicked")
        manifest["skipped"] = sum(
            1 for x in manifest["interactions"] if x["decision"] == "skipped")
        manifest["failed"] = sum(
            1 for x in manifest["interactions"] if x["decision"] == "failed")
        manifest["discovered"] = len(controls)
        covered = manifest["clicked"] + manifest["skipped"]
        manifest["complete"] = (
            covered == len(manifest["interactions"])
            and manifest["failed"] == 0
            and not manifest["truncated"]
        )
        manifest["finishedAt"] = datetime.datetime.now(
            datetime.timezone.utc).isoformat()
        write_json(manifest_path, manifest)

        print("  %d controls: %d clicked, %d skipped, %d failed, complete=%s"
              % (manifest["discovered"], manifest["clicked"],
                 manifest["skipped"], manifest["failed"],
                 str(manifest["complete"]).lower()))
        result = {
            "url": url,
            "manifest": os.path.relpath(manifest_path, args.out),
            "discovered": manifest["discovered"],
            "clicked": manifest["clicked"],
            "skipped": manifest["skipped"],
            "failed": manifest["failed"],
            "truncated": manifest["truncated"],
            "complete": manifest["complete"],
        }
    finally:
        context.close()

    return result


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0].strip())
    parser.add_argument("urls", nargs="*", help="page URLs in scope")
    parser.add_argument("--out", required=True,
                        help="artifact folder, e.g. clones/example")
    parser.add_argument("--pages-file", help="one URL per line")
    parser.add_argument("--pages", default=None,
                        help="comma-separated URLs (alternative to positional)")
    parser.add_argument("--crawl-depth", type=int, default=0,
                        help="follow same-origin links N levels (default 0)")
    parser.add_argument("--max-clicks", type=int, default=300,
                        help="hard cap per page; a truncated run is not complete")
    parser.add_argument("--viewport", default="1440x900",
                        help="WxH measurement viewport (default 1440x900)")
    parser.add_argument("--device-scale", type=float, default=1.0)
    parser.add_argument("--settle", type=int, default=600,
                        help="ms to wait after load and after each click")
    parser.add_argument("--delay", type=int, default=150,
                        help="extra ms between interactions")
    parser.add_argument("--scroll-step", type=int, default=800)
    parser.add_argument("--no-scroll-settle", action="store_true",
                        help="skip the scroll pass before each click")
    parser.add_argument("--timeout", type=int, default=45000,
                        help="navigation timeout in ms")
    parser.add_argument("--click-timeout", type=int, default=5000,
                        help="per-control action timeout in ms")
    parser.add_argument("--allow-form-submit", action="store_true",
                        help="click submit controls (may send data; off by default)")
    parser.add_argument("--full-after", action="store_true",
                        help="make each after shot full-page (larger files)")
    parser.add_argument("--resume", action="store_true",
                        help="skip controls already recorded in manifest.json")
    parser.add_argument("--dry-run", action="store_true",
                        help="enumerate and print the plan, click nothing")
    parser.add_argument("--headed", action="store_true", help="show the browser")
    args = parser.parse_args(argv)

    urls = list(args.urls)
    if args.pages:
        urls.extend(u.strip() for u in args.pages.split(",") if u.strip())
    if args.pages_file:
        with open(args.pages_file, encoding="utf-8") as fh:
            urls.extend(line.strip() for line in fh
                        if line.strip() and not line.startswith("#"))
    if not urls:
        parser.error("give at least one URL (positional, --pages or --pages-file)")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("explore_interactions.py: playwright is not installed.\n"
              "  pip install playwright && playwright install chromium\n"
              "Or use scripts/interactive_map.js in DevTools.",
              file=sys.stderr)
        return 2

    dimensions = args.viewport.lower().split("x")
    if len(dimensions) != 2 or not all(d.isdigit() for d in dimensions):
        parser.error("bad --viewport %r, expected WxH" % args.viewport)
    args.width, args.height = int(dimensions[0]), int(dimensions[1])

    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(headless=not args.headed)
        except Exception as exc:
            print("explore_interactions.py: could not launch Chromium: %s\n"
                  "  run: playwright install chromium" % exc, file=sys.stderr)
            return 2
        try:
            pages = discover_pages(browser.new_page(), urls,
                                   args.crawl_depth, args.timeout)
            print("pages in scope: %d" % len(pages))
            results = [run_page(browser, url, args) for url in pages]
        finally:
            browser.close()

    base = os.path.join(args.out, "reference", "interactions")
    index = {
        "generatedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "viewport": "%dx%d" % (args.width, args.height),
        "pages": results,
        "totals": {
            "discovered": sum(r["discovered"] for r in results),
            "clicked": sum(r["clicked"] for r in results),
            "skipped": sum(r["skipped"] for r in results),
            "failed": sum(r["failed"] for r in results),
        },
    }
    index["complete"] = all(r["complete"] for r in results)
    write_json(os.path.join(base, "index.json"), index)

    print("\ninteraction log: %s" % base)
    print("complete=%s — %d clicked, %d skipped, %d failed"
          % (str(index["complete"]).lower(), index["totals"]["clicked"],
             index["totals"]["skipped"], index["totals"]["failed"]))
    if not index["complete"]:
        print("note: incomplete coverage. Raise --max-clicks, resolve failures,")
        print("      or list the uncovered controls in DESIGN.md.")
    print("next: read references/analysis.md §4.1 and fill DESIGN.md §4b.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
