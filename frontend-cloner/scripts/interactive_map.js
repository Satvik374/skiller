/*
 * frontend-cloner — interactive control map (manual path).
 *
 * Paste this whole file into DevTools on the target page, then:
 *
 *   __interactiveMap                       // inspect
 *   copy(JSON.stringify(__interactiveMap, null, 2))
 *
 * Click each entry marked click=true by hand, in order, capturing a before
 * element crop and an after viewport screenshot. Save them as
 * reference/interactions/<page>/shots/NNN-<slug>-{before,after}.png and record
 * the same fields the automated script writes in manifest.json.
 *
 * Entries with click=false are skipped for a stated reason. Never click them
 * anyway; a destructive control is not made safe by being manual.
 */
(() => {
  "use strict";

  const SELECTOR = [
    "a[href]", "button", "input:not([type=hidden])", "select", "textarea",
    "summary", "[role=button]", "[role=tab]", "[role=menuitem]",
    "[role=menuitemcheckbox]", "[role=menuitemradio]", "[role=switch]",
    "[role=checkbox]", "[role=radio]", "[role=link]", "[role=combobox]",
    "[onclick]", "[aria-expanded]", "[aria-controls]", "[aria-haspopup]",
    "[tabindex]:not([tabindex='-1'])",
  ].join(",");

  const RISKY = new RegExp(
    "\\b(delete|remove|destroy|erase|wipe|deactivate|log\\s?out|sign\\s?out|" +
    "unsubscribe|cancel\\s+(subscription|plan|account)|close\\s+account|" +
    "purchase|buy\\s+now|checkout|place\\s+order|pay\\s+now|donate|" +
    "send|confirm\\s+(payment|order)|reset\\s+all|clear\\s+all)\\b", "i");

  const BINARY = /\.(png|jpe?g|gif|svg|webp|avif|ico|pdf|zip|mp4|mp3|woff2?|ttf|otf)(\?|$)/i;

  const round = (n) => Math.round(n * 10) / 10;
  const clip = (s, n) => {
    const t = String(s || "").replace(/\s+/g, " ").trim();
    return t.length > n ? t.slice(0, n) + "…" : t;
  };
  const slug = (s) => String(s || "control").toLowerCase()
    .replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 32) || "control";

  function cssPath(el) {
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
        if (same.length > 1) {
          part += ":nth-of-type(" + (same.indexOf(node) + 1) + ")";
        }
      }
      parts.unshift(part);
      if (part === "body") break;
      node = parent;
    }
    return parts.join(" > ");
  }

  function visible(el) {
    const cs = getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden" ||
        cs.visibility === "collapse") return false;
    const r = el.getBoundingClientRect();
    return r.width > 0.5 && r.height > 0.5;
  }

  const origin = location.origin;
  const seen = new Set();
  const out = [];

  for (const el of document.querySelectorAll(SELECTOR)) {
    if (!visible(el)) continue;
    const path = cssPath(el);
    if (seen.has(path)) continue;
    seen.add(path);

    const text = clip(el.innerText || el.value ||
      el.getAttribute("aria-label") || el.getAttribute("title") || "", 120);
    const label = [text, el.getAttribute("aria-label"),
      el.getAttribute("title"), el.getAttribute("name"),
      path].filter(Boolean).join(" ");
    const type = el.getAttribute("type");
    const href = el.href || null;
    const target = el.getAttribute("target");

    let reason = null;
    if (el.disabled || el.getAttribute("aria-disabled") === "true") {
      reason = "disabled";
    } else if (el.tagName === "INPUT" && (type === "password" || type === "file")) {
      reason = "sensitive-input";
    } else if (target === "_blank") {
      reason = "external-navigation";
    } else if (el.hasAttribute("download")) {
      reason = "download";
    } else if (href) {
      const scheme = (href.split(":")[0] || "").toLowerCase();
      if (["mailto", "tel", "javascript", "data"].includes(scheme)) {
        reason = "non-http-link";
      } else if (href.startsWith("http") && new URL(href).origin !== origin) {
        reason = "external-navigation";
      } else if (BINARY.test(new URL(href, location.href).pathname)) {
        reason = "binary-link";
      }
    } else if (type === "submit") {
      reason = "form-submit";
    }
    if (!reason && RISKY.test(label)) reason = "destructive-action";

    const r = el.getBoundingClientRect();
    out.push({
      id: String(out.length + 1).padStart(3, "0"),
      path: path,
      tag: el.tagName.toLowerCase(),
      role: el.getAttribute("role"),
      type: type,
      label: text,
      href: href,
      box: {
        x: round(r.left + window.scrollX),
        y: round(r.top + window.scrollY),
        w: round(r.width),
        h: round(r.height),
      },
      click: reason === null,
      skipReason: reason,
      suggestedShot: String(out.length + 1).padStart(3, "0") + "-" + slug(text || el.tagName),
    });
  }

  window.__interactiveMap = out;
  const clickable = out.filter((x) => x.click).length;
  console.table(out.map((x) => ({
    id: x.id, click: x.click, reason: x.skipReason || "",
    tag: x.tag, label: x.label.slice(0, 40), path: x.path.slice(0, 60),
  })));
  console.info("%d controls: %d to click, %d skipped",
    out.length, clickable, out.length - clickable);
  console.info("Copy with: copy(JSON.stringify(__interactiveMap, null, 2))");
  return out;
})();
