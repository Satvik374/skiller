#!/usr/bin/env python3
"""Fetch authored 3D assets from Sketchfab, with licence bookkeeping.

Reads SKETCHFAB_TOKEN from the environment (or a .env in the working
directory). Never pass the token on the command line — it lands in shell
history and process listings.

    export SKETCHFAB_TOKEN='...'

    # find candidates (filters for downloadable, animated, licence and face count)
    python3 sketchfab_fetch.py search "abandoned warehouse interior" --animated --max-faces 150000

    # download one into public/assets/env/, register it, write CREDITS.md
    python3 sketchfab_fetch.py download 49d97ca2fbf34f85b6c88ae8ebc7514f --slug warehouse

The download endpoint returns a short-lived archive URL (~5 min), so the
script requests and fetches it in one go, then extracts and records:
  - assets/registry.json  machine record (uid, author, licence, audit numbers)
  - CREDITS.md            human/licence record, also used by the in-game credits
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

API = "https://api.sketchfab.com/v3"
UID_RE = re.compile(r"([0-9a-f]{32})")


def load_dotenv() -> None:
    for name in (".env", ".env.local"):
        path = Path.cwd() / name
        if not path.is_file():
            continue
        for line in path.read_text(errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip().removeprefix("export ").strip()
            if key and key not in os.environ:
                os.environ[key] = value.strip().strip("'\"")


def token() -> str:
    value = os.environ.get("SKETCHFAB_TOKEN", "").strip()
    if not value:
        sys.exit(
            "SKETCHFAB_TOKEN is not set.\n"
            "Get one from Sketchfab -> Settings -> Password & API -> API token,\n"
            "put it in .env as SKETCHFAB_TOKEN=..., and re-run. Do not commit it."
        )
    return value


def auth_header(bearer: bool) -> dict[str, str]:
    return {"Authorization": f"{'Bearer' if bearer else 'Token'} {token()}"}


def request(url: str, headers: dict[str, str], *, retries: int = 3) -> bytes:
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, headers={**headers, "User-Agent": "game-builder/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")[:400]
            if exc.code == 429 and attempt < retries:
                wait = int(exc.headers.get("Retry-After", "5")) + attempt * 5
                print(f"rate limited, waiting {wait}s", file=sys.stderr)
                time.sleep(wait)
                continue
            raise ApiError(exc.code, body) from exc
        except urllib.error.URLError as exc:
            if attempt < retries:
                time.sleep(2 + attempt * 3)
                continue
            raise ApiError(0, str(exc.reason)) from exc
    raise ApiError(0, "unreachable")


class ApiError(Exception):
    def __init__(self, code: int, body: str):
        super().__init__(f"HTTP {code}: {body}")
        self.code = code


def explain(code: int) -> str:
    return {
        400: "model is marked not downloadable by its author — pick another model",
        401: "token missing or invalid — check SKETCHFAB_TOKEN",
        403: "token has no access (store/paid model) — pick another model",
        404: "model uid not found",
        429: "rate limited",
    }.get(code, "unexpected API error")


def cmd_search(args: argparse.Namespace) -> int:
    params = {
        "type": "models",
        "q": args.query,
        "downloadable": "true",
        "count": str(min(args.count, 24)),
        "sort_by": args.sort,
    }
    if args.animated:
        params["animated"] = "true"
    if args.rigged:
        params["rigged"] = "true"
    if args.license:
        params["license"] = args.license
    if args.max_faces:
        params["max_face_count"] = str(args.max_faces)
    if args.min_faces:
        params["min_face_count"] = str(args.min_faces)

    url = f"{API}/search?" + urllib.parse.urlencode(params)
    data = json.loads(request(url, auth_header(args.bearer)))
    results = data.get("results", [])
    if not results:
        print("no results — loosen the filters (try without --max-faces)")
        return 1

    print(f"{'uid':<34} {'faces':>8} {'anim':>4}  {'licence':<12} {'author':<18} name")
    for item in results:
        lic = (item.get("license") or {}).get("slug") or "?"
        author = (item.get("user") or {}).get("username", "?")[:18]
        print(
            f"{item['uid']:<34} {item.get('faceCount') or 0:>8,} "
            f"{'yes' if item.get('animationCount') else '-':>4}  {lic:<12} {author:<18} "
            f"{item.get('name', '')[:60]}"
        )
    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=2))
        print(f"\nwrote {args.json}")
    print("\nCopy the uid of the one you want into: download <uid> --slug <name>")
    return 0


def resolve_uid(value: str) -> str:
    match = UID_RE.search(value)
    if not match:
        sys.exit(f"could not find a 32-char model uid in '{value}'")
    return match.group(1)


def safe_extract(archive: zipfile.ZipFile, dest: Path) -> None:
    dest = dest.resolve()
    for member in archive.infolist():
        target = (dest / member.filename).resolve()
        if not str(target).startswith(str(dest)):
            sys.exit(f"refusing unsafe path in archive: {member.filename}")
    archive.extractall(dest)


def pick_entry(extracted: Path, allowed_ext: tuple[str, ...]) -> Path | None:
    candidates = [p for p in extracted.rglob("*") if p.suffix.lower() in allowed_ext and p.is_file()]
    if not candidates:
        return None
    # largest file wins: Sketchfab archives contain preview thumbs and lod variants
    return max(candidates, key=lambda p: p.stat().st_size)


def regenerate_credits(out: Path, registry: dict) -> None:
    lines = [
        "# Credits",
        "",
        "3D assets used by this project, with the licence they are shipped under.",
        "Generated by `sketchfab_fetch.py` — do not edit by hand.",
        "",
    ]
    for slug, entry in sorted(registry.items()):
        lines.append(f"## {entry.get('title') or slug}")
        lines.append("")
        lines.append(f"- File: `{entry['file']}`")
        if entry.get("author"):
            lines.append(f"- Author: [{entry['author']}]({entry.get('author_url', '')})")
        lines.append(f"- Licence: {entry.get('license', 'unknown')}")
        if entry.get("attribution_required"):
            lines.append("- **Attribution required.** Keep this credit visible in-game.")
        if entry.get("url"):
            lines.append(f"- Source: {entry['url']}")
        lines.append("")
    (out / "CREDITS.md").write_text("\n".join(lines))
    print(f"updated {out / 'CREDITS.md'}")


def cmd_download(args: argparse.Namespace) -> int:
    uid = resolve_uid(args.model)
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    headers = auth_header(args.bearer)

    meta_url = f"{API}/models/{uid}"
    try:
        model = json.loads(request(meta_url, headers))
    except ApiError as exc:
        model = {}
        print(f"warning: metadata unavailable ({exc})", file=sys.stderr)

    slug = args.slug or re.sub(r"[^a-z0-9]+", "_", (model.get("name") or uid).lower()).strip("_")[:48]
    slug = slug or uid
    print(f"model   {model.get('name', uid)}  by {(model.get('user') or {}).get('username', '?')}")
    print(f"licence {(model.get('license') or {}).get('label', 'unknown')}")
    print(f"slug    {slug}")

    try:
        payload = json.loads(request(f"{API}/models/{uid}/download", headers))
    except ApiError as exc:
        print(f"download refused: {explain(exc.code)}\n  {exc}", file=sys.stderr)
        return 1

    gltf = payload.get("gltf") or {}
    if not gltf.get("url"):
        print("no glTF archive available for this model (usdz only?)", file=sys.stderr)
        return 1
    if gltf.get("expires") and gltf["expires"] < 120:
        print(f"note: archive link expires in {gltf['expires']}s — fetching now")

    with tempfile.TemporaryDirectory(prefix="skfb_") as tmp:
        tmp_path = Path(tmp)
        archive_path = tmp_path / "model.zip"
        print(f"fetching {gltf.get('size', 0) / 1048576:.1f} MB archive…")
        archive_path.write_bytes(request("https://" + gltf["url"].lstrip("/").removeprefix("https://"), {}))

        dest = tmp_path / "extracted"
        dest.mkdir()
        with zipfile.ZipFile(archive_path) as zf:
            safe_extract(zf, dest)

        glb = pick_entry(dest, (".glb",))
        gltf_file = pick_entry(dest, (".gltf",))
        target_dir = out / slug
        if target_dir.exists():
            shutil.rmtree(target_dir)
        target_dir.mkdir(parents=True)

        if glb:
            final = target_dir / f"{slug}.glb"
            shutil.copy2(glb, final)
        elif gltf_file:
            # keep the whole tree: .gltf references .bin + external textures
            shutil.copytree(gltf_file.parent, target_dir, dirs_exist_ok=True)
            final = target_dir / gltf_file.name
        else:
            print("archive contained no .glb or .gltf", file=sys.stderr)
            return 1

        rel = final.relative_to(Path.cwd()) if final.is_relative_to(Path.cwd()) else final
        print(f"wrote   {rel}  ({final.stat().st_size / 1048576:.2f} MB)")

        registry_path = out / "registry.json"
        registry = json.loads(registry_path.read_text()) if registry_path.is_file() else {}
        licence = model.get("license") or {}
        registry[slug] = {
            "file": str(rel),
            "source": "sketchfab",
            "uid": uid,
            "url": model.get("viewerUrl") or f"https://sketchfab.com/3d-models/{uid}",
            "title": model.get("name"),
            "author": (model.get("user") or {}).get("username"),
            "author_url": (model.get("user") or {}).get("profileUrl"),
            "license": licence.get("label") or licence.get("slug") or "unknown",
            "attribution_required": bool(licence.get("requirements")) or "cc" in str(licence.get("slug", "")),
            "downloaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "faces": model.get("faceCount"),
            "clips": model.get("animationCount"),
        }
        registry_path.write_text(json.dumps(registry, indent=2, sort_keys=True))
        print(f"updated {registry_path}")
        regenerate_credits(out, registry)

        if "nc" in str(licence.get("slug", "")).lower():
            print("WARNING: non-commercial licence — do not ship this in a paid build", file=sys.stderr)
        if "nd" in str(licence.get("slug", "")).lower():
            print("WARNING: no-derivatives licence — you may not optimise or retarget it", file=sys.stderr)

        print("\nnext:")
        print(f"  python3 game-builder/scripts/glb_audit.py {rel} --budget hero")
        print(f"  bash game-builder/scripts/optimize_assets.sh {rel}")
    return 0


def main() -> int:
    load_dotenv()
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--bearer", action="store_true", help="token is an OAuth access token, not an API token")
    sub = ap.add_subparsers(dest="command", required=True)

    search = sub.add_parser("search", help="search downloadable models")
    search.add_argument("query")
    search.add_argument("--animated", action="store_true")
    search.add_argument("--rigged", action="store_true")
    search.add_argument("--license", help="cc0,by,by-sa,by-nd,by-nc …")
    search.add_argument("--max-faces", type=int, help="skip scans that cannot run in a browser")
    search.add_argument("--min-faces", type=int)
    search.add_argument("--count", type=int, default=20)
    search.add_argument("--sort", default="-likeCount")
    search.add_argument("--json")
    search.set_defaults(func=cmd_search)

    dl = sub.add_parser("download", help="download a model's glTF archive")
    dl.add_argument("model", help="model uid or sketchfab URL")
    dl.add_argument("--slug", help="folder/file name (default: from the model name)")
    dl.add_argument("--out", default="public/assets", help="destination root (default: public/assets)")
    dl.set_defaults(func=cmd_download)

    args = ap.parse_args()
    try:
        return args.func(args)
    except ApiError as exc:
        print(f"{explain(exc.code)}\n  {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
