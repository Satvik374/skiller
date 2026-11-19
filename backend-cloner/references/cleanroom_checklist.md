# Cleanroom Checklist — Zero-Copy Verification

> Run this before you claim the reconstruction is finished, and attach the completed
> attestation to `recon/cleanroom-attestation.md`. The point of a cleanroom rebuild is that
> the output is **yours**: independently designed code that satisfies an observed contract.
> If any check below fails, fix it or report the failure — do not tick it and move on.

## 0. What the rule actually prohibits

Prohibited to copy, vendor, decompile into, transcribe or minimally rename:

- Original server source, internal libraries, internal API handlers, GraphQL resolvers.
- Minified/bundled client JavaScript, or source maps used as implementation input.
- Any license header, docstring, comment block or identifier set from the original.
- Database dumps, production fixtures, seed data, or real user rows.
- Media, images, icons, illustrations, fonts, audio, video, Lottie/GLB assets.
- Long verbatim UI copy, marketing text, help articles, email templates.
- Their OpenAPI/JSON-Schema documents reused as your schema file.

Permitted, because it is functional interface fact rather than expression:

- HTTP methods, paths, parameter names, field names, enum wire values, status codes.
- Content types, header names, cookie attributes, error `code` strings the client matches on.
- Auth *scheme* (`bearer`, session cookie, API key header) — implemented with your own code.
- Public standards (RFC 9110, OAuth 2.0, OpenAPI 3.0) and public third-party API docs.

When unsure whether something is interface or expression: **retype it from your own spec**.
If the only way to get a value is to copy a chunk of their artifact, the value is not needed
for parity.

## 1. Pre-flight (before writing code)

- [ ] `recon/00-scope.md` records authorization, origins, accounts, and an out-of-scope list.
- [ ] Raw capture is gitignored: `recon/capture/` never enters version control.
- [ ] A provenance ledger exists for every entity, column and endpoint (`architecture.md` §2, §4).
- [ ] The implementation plan was written from `recon/openapi.yaml` + `recon/architecture.md` only.
- [ ] No original bundle, `.map` file, HAR body or DB export is on the implementation path.
- [ ] Working agreement noted: implementers do not read original source; reviewers check output, not input.

Suggested `.gitignore` additions:

```gitignore
recon/capture/
recon/distilled/
*.har
*.har.zip
storage_state.json
.env
```

## 2. During implementation

- [ ] Every route traces to an entry in `openapi.yaml` (`OBSERVED`) or a row in
      `architecture.md` §6 marked `INFERRED` with an assumption noted.
- [ ] Unobserved behaviour raises or documents `501`/`404` rather than being invented silently.
- [ ] Auth is a real implementation — own password hashing (`argon2`/`bcrypt`), own token
      signing — never a hardcoded bypass, never a copied token format with copied secrets.
- [ ] ORM models, migrations, service layers and validation are newly authored.
- [ ] Seed data is **synthetic**: fabricated names, `example.com` emails, generated images
      (none), numbers that match observed *shapes* but not real values.
- [ ] No asset is downloaded from the target and reused; icons are from a permissively
      licensed set or drawn for this project.
- [ ] Error messages are your own wording; only machine-readable `code` values match.
- [ ] Client-facing copy that must match verbatim for parity is minimal, listed in
      `architecture.md` §9, and justified as functional.

## 3. Automated scans

Run from the implementation root. Each command should return no hits, or hits you have
written down and justified.

```bash
# 1. Copied build artifacts / bundles / maps in the tree
rg -n --hidden -g '!recon/**' -g '!.git/**' -e '\.min\.js$' -e '\.map$' -l . || true
find . -path ./recon -prune -o \( -name '*.min.js' -o -name '*.map' -o -name '*.har' \) -print

# 2. Embedding or data-URI blobs (vendored assets hiding in source)
rg -n --hidden -g '!recon/**' 'data:(image|font|video|audio)/[a-z0-9.+-]+;base64' . || true

# 3. Original license/copyright headers
rg -n --hidden -g '!recon/**' -i 'copyright|all rights reserved|proprietary|confidential' . || true

# 4. Long string literals (likely pasted copy or embedded minified code)
rg -n --hidden -g '!recon/**' -g '!*.lock' -g '!package-lock.json' '"[^"\n]{300,}"' . || true

# 5. Secrets and live tokens
rg -n --hidden -g '!recon/**' -e 'eyJ[A-Za-z0-9_-]{10,}\.' -e 'sk_live_' -e 'AKIA[0-9A-Z]{16}' -e '(?i)bearer\s+[A-Za-z0-9._-]{20,}' . || true

# 6. Real user data leaking into seeds/fixtures
rg -n --hidden -g '!recon/**' -e '@(gmail|yahoo|hotmail|outlook)\.com' -e '\b\d{3}-\d{2}-\d{4}\b' . || true

# 7. Fingerprint match against captured bundle (strongest check)
#    Hash each captured script body; confirm no implementation file matches.
python3 - <<'PY'
import hashlib, json, pathlib
har = json.loads(pathlib.Path("recon/capture/network.har").read_text())
hashes = {}
for e in har["log"]["entries"]:
    url = e["request"]["url"]
    if url.endswith((".js", ".mjs")) or "javascript" in e["response"]["content"].get("mimeType", ""):
        text = e["response"]["content"].get("text") or ""
        if text:
            hashes[hashlib.sha256(text.encode()).hexdigest()] = url
hits = []
for p in pathlib.Path(".").rglob("*"):
    if p.is_file() and p.suffix in {".py", ".ts", ".js", ".tsx", ".sql"} and "recon" not in p.parts and "node_modules" not in p.parts:
        if hashlib.sha256(p.read_bytes()).hexdigest() in hashes:
            hits.append(str(p))
print(json.dumps({"fingerprint_matches": hits}, indent=2))
PY
```

## 4. Review pass

- [ ] Read the diff as a reviewer who has never seen the target: does every file look like
      a normal, independently designed service?
- [ ] Identifier naming follows your project's conventions, not names lifted from the bundle.
      Rename anything suspicious even if it works.
- [ ] File/module layout is your architecture (routers, services, repositories) — not a
      mirror of their bundle chunk names.
- [ ] Migrations build the schema from an empty database: `alembic upgrade head` on a fresh DB.
- [ ] `docker compose up` from a clean clone yields a working API with seeded mock data.
- [ ] No network call to the target origin from the rebuilt service.
- [ ] No analytics, tracking pixel, or original third-party key carried over.
- [ ] Test fixtures were generated by your own seed script or sanitized by
      `parse_har.py --mask-pii`, never pasted raw from the capture.

## 5. Data and privacy

- [ ] `recon/capture/` deleted or archived offline once the spec was extracted, per the
      user's retention preference.
- [ ] Anything shared (PR, issue, chat, screenshot) contains masked output only.
- [ ] Reports reference request bodies by field name; secret values appear as `<redacted>`.
- [ ] If a live credential was captured, it was reported to the user and rotated — not
      quietly reused.

## 6. Attestation

Copy this into `recon/cleanroom-attestation.md`, fill it in, and keep it with the deliverable.

```markdown
# Cleanroom Attestation — <TARGET>

Date: <YYYY-MM-DD>            Skill: backend-cloner 1.0.0
Authorization basis: <owner / written permission / own session>

## Sources used to write the implementation
- [x] recon/openapi.yaml (OBSERVED contract)
- [x] recon/architecture.md (INFERRED design)
- [ ] original server source — not consulted
- [ ] original client bundle / source maps — not used as implementation input
- [ ] database export / production data — not used
- [ ] media, fonts, icon assets — not copied

## Statements
- No original source code, bundled JavaScript, or source-map content was copied into this
  repository.
- No database dump, production fixture, or real user record was imported.
- No media, font, icon, or illustration asset was downloaded from the target.
- Seed data is synthetic and generated by scripts/seed.py.
- Auth is an independent implementation of the observed scheme; no bypass is present.
- Inferred behaviour is labeled INFERRED with assumptions recorded; unobserved behaviour is
  labeled UNKNOWN rather than invented.

## Scan results
| Check | Result | Notes |
|---|---|---|
| Copied bundles / maps | pass | |
| base64 asset embeds | pass | |
| copyright headers | pass | |
| long string literals | pass | 2 justified in §9 |
| secrets | pass | |
| real user data | pass | |
| bundle fingerprint match | pass | 0 matches |

## Deviations
| Area | Observed | Rebuild | Reason |
|---|---|---|---|

Signed: <name / agent id>
```

## 7. When a check cannot pass

Some checks are genuinely impossible for a given target — for example, field names *are* the
contract, so identical names are expected and fine. Record the exception, its justification,
and the reviewer who accepted it. Never omit a failed check from the attestation: an
attestation with a documented exception is trustworthy; a clean-looking one with a hidden
copy is not.

This checklist is engineering guidance, not legal advice. Licensing, terms of service and
database rights vary by jurisdiction and by target; when the deliverable will be distributed
or used commercially, tell the user to obtain their own legal review.
