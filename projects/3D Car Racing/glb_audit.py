#!/usr/bin/env python3
"""Audit glTF/GLB assets against a game budget.

Dependency-free: parses the container, reads accessors, and reports what a
browser runtime will actually pay for. Exit code 1 when a budget is exceeded,
so it can gate a build.

Examples
--------
    # one file against prop budgets
    python3 glb_audit.py public/assets/props/crate.glb --budget prop

    # a character, including animation loop seams
    python3 glb_audit.py hero.glb --budget character --loop-check

    # everything under a tree, machine readable, failing the build on breaches
    python3 glb_audit.py public/assets --recursive --budget preset:env \
        --json assets/audit.json
"""

from __future__ import annotations

import argparse
import json
import math
import struct
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

GLB_MAGIC = 0x46546C67
CHUNK_JSON = 0x4E4F534A
CHUNK_BIN = 0x004E4942

COMPONENT = {
    5120: ("b", 1),
    5121: ("B", 1),
    5122: ("h", 2),
    5123: ("H", 2),
    5125: ("I", 4),
    5126: ("f", 4),
}
NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT2": 4, "MAT3": 9, "MAT4": 16}

# name -> (max_tris, max_texture, max_materials, max_bones, max_mb)
BUDGETS = {
    "prop": (20_000, 1024, 3, 0, 4.0),
    "hero": (120_000, 2048, 8, 120, 40.0),
    "character": (120_000, 2048, 8, 120, 40.0),
    "env": (250_000, 2048, 20, 0, 60.0),
    "unlimited": (10**9, 8192, 10**4, 10**4, 10**6),
}


@dataclass
class Report:
    path: str
    ok: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    bytes: int = 0
    meshes: int = 0
    primitives: int = 0
    triangles: int = 0
    vertices: int = 0
    materials: int = 0
    textures: int = 0
    texture_max: int = 0
    texture_bytes: int = 0
    images: list[dict] = field(default_factory=list)
    slots: list[str] = field(default_factory=list)
    animations: list[dict] = field(default_factory=list)
    skins: int = 0
    bones: int = 0
    morph_targets: int = 0
    bbox: dict | None = None
    vertex_colors: bool = False
    extensions: list[str] = field(default_factory=list)
    loop_check: bool = True


def load(path: Path) -> tuple[dict, list[bytes]]:
    data = path.read_bytes()
    if data[:4] == b"glTF":
        magic, version, _length = struct.unpack_from("<III", data, 0)
        if magic != GLB_MAGIC or version != 2:
            raise ValueError("not a glTF 2.0 binary")
        offset, json_chunk, bin_chunks = 12, None, []
        while offset < len(data):
            clen, ctype = struct.unpack_from("<II", data, offset)
            body = data[offset + 8 : offset + 8 + clen]
            if ctype == CHUNK_JSON:
                json_chunk = body
            elif ctype == CHUNK_BIN:
                bin_chunks.append(body)
            offset += 8 + clen + ((4 - clen % 4) % 4 if clen % 4 else 0)
        if json_chunk is None:
            raise ValueError("GLB has no JSON chunk")
        return json.loads(json_chunk.decode("utf-8")), bin_chunks

    gltf = json.loads(data.decode("utf-8"))
    buffers = []
    for buf in gltf.get("buffers", []):
        uri = buf.get("uri", "")
        if not uri or uri.startswith("data:"):
            buffers.append(b"")
            continue
        candidate = (path.parent / uri).resolve()
        buffers.append(candidate.read_bytes() if candidate.is_file() else b"")
    return gltf, buffers


def buffer_view_bytes(gltf: dict, buffers: list[bytes], index: int) -> bytes | None:
    view = gltf["bufferViews"][index]
    blob = buffers[view.get("buffer", 0)] if view.get("buffer", 0) < len(buffers) else b""
    if not blob:
        return None
    start = view.get("byteOffset", 0)
    length = view["byteLength"]
    if start + length > len(blob):
        return None
    return blob[start : start + length]


def read_accessor(gltf: dict, buffers: list[bytes], index: int) -> list[tuple] | None:
    acc = gltf["accessors"][index]
    if "sparse" in acc:
        return None
    fmt, size = COMPONENT[acc["componentType"]]
    n = NCOMP[acc["type"]]
    count = acc["count"]
    if "bufferView" not in acc:
        return [(0.0,) * n] * count
    raw = buffer_view_bytes(gltf, buffers, acc["bufferView"])
    if raw is None:
        return None
    stride = gltf["bufferViews"][acc["bufferView"]].get("byteStride") or size * n
    base = acc.get("byteOffset", 0)
    out = []
    for i in range(count):
        off = base + i * stride
        if off + size * n > len(raw):
            break
        out.append(struct.unpack_from("<" + fmt * n, raw, off))
    return out


def image_dims(blob: bytes) -> tuple[int | None, int | None]:
    if blob[:8] == b"\x89PNG\r\n\x1a\n" and len(blob) >= 24:
        w, h = struct.unpack_from(">II", blob, 16)
        return w, h
    if blob[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(blob):
            if blob[i] != 0xFF:
                i += 1
                continue
            marker = blob[i + 1]
            if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            seglen = struct.unpack_from(">H", blob, i + 2)[0]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h, w = struct.unpack_from(">HH", blob, i + 5)
                return w, h
            i += 2 + seglen
    return None, None


def quad_angle(a, b) -> float:
    dot = abs(sum(x * y for x, y in zip(a, b)))
    dot = min(1.0, max(-1.0, dot))
    return math.degrees(2.0 * math.acos(dot))


def audit(path: Path, *, loop_check: bool = True) -> Report:
    rep = Report(path=str(path), loop_check=loop_check)
    rep.bytes = path.stat().st_size
    try:
        gltf, buffers = load(path)
    except Exception as exc:  # noqa: BLE001 - report, don't crash the batch
        rep.ok = False
        rep.errors.append(f"parse failed: {exc}")
        return rep

    rep.extensions = sorted(set(gltf.get("extensionsUsed", [])) | set(gltf.get("extensionsRequired", [])))

    positions: list[tuple] = []
    for mesh_index, mesh in enumerate(gltf.get("meshes", [])):
        rep.meshes += 1
        for prim in mesh.get("primitives", []):
            rep.primitives += 1
            attrs = prim.get("attributes", {})
            mode = prim.get("mode", 4)
            if "indices" in prim:
                idx = gltf["accessors"][prim["indices"]]
                count = idx["count"]
            else:
                count = gltf["accessors"][attrs["POSITION"]]["count"] if "POSITION" in attrs else 0
            if mode == 4:
                rep.triangles += count // 3
            elif mode in (5, 6):
                rep.triangles += max(0, count - 2)
            rep.vertices += gltf["accessors"][attrs["POSITION"]]["count"] if "POSITION" in attrs else 0
            if "COLOR_0" in attrs:
                rep.vertex_colors = True
            if "targets" in prim:
                rep.morph_targets += len(prim["targets"])
            if "POSITION" in attrs:
                acc = gltf["accessors"][attrs["POSITION"]]
                if acc.get("min") and acc.get("max"):
                    positions.append((acc["min"], acc["max"]))

    rep.materials = len(gltf.get("materials", []))
    rep.textures = len(gltf.get("textures", []))
    for img in gltf.get("images", []):
        entry = {"name": img.get("name") or img.get("mimeType") or "image", "width": None, "height": None, "bytes": 0}
        if "bufferView" in img:
            blob = buffer_view_bytes(gltf, buffers, img["bufferView"])
            if blob is None:
                rep.warnings.append(f"image {entry['name']}: buffer view unreadable (external .bin missing?)")
            else:
                entry["bytes"] = len(blob)
                w, h = image_dims(blob)
                entry["width"], entry["height"] = w, h
                rep.texture_bytes += len(blob)
                if w and h:
                    rep.texture_max = max(rep.texture_max, w, h)
        elif "uri" in img:
            uri = img["uri"]
            local = (path.parent / uri).resolve()
            if local.is_file():
                blob = local.read_bytes()
                entry["bytes"] = len(blob)
                w, h = image_dims(blob)
                entry["width"], entry["height"] = w, h
                rep.texture_bytes += len(blob)
                if w and h:
                    rep.texture_max = max(rep.texture_max, w, h)
            elif not uri.startswith("data:"):
                rep.warnings.append(f"image {entry['name']}: missing file {uri}")
        rep.images.append(entry)

    if positions:
        lo = [min(p[0][i] for p in positions) for i in range(3)]
        hi = [max(p[1][i] for p in positions) for i in range(3)]
        rep.bbox = {
            "min": [round(v, 4) for v in lo],
            "max": [round(v, 4) for v in hi],
            "size": [round(hi[i] - lo[i], 4) for i in range(3)],
        }

    for skin in gltf.get("skins", []):
        rep.skins += 1
        rep.bones = max(rep.bones, len(skin.get("joints", [])))

    for anim in gltf.get("animations", []):
        name = anim.get("name") or f"anim_{len(rep.animations)}"
        duration = 0.0
        channels = len(anim.get("channels", []))
        max_rot_delta = 0.0
        max_pos_delta = 0.0
        worst_channel = None
        for ch in anim.get("channels", []):
            sampler = anim["samplers"][ch["sampler"]]
            times = read_accessor(gltf, buffers, sampler["input"])
            if times:
                duration = max(duration, times[-1][0])
            if not loop_check:
                continue
            target = ch.get("target", {})
            path_name = target.get("path")
            if path_name not in ("rotation", "translation"):
                continue
            values = read_accessor(gltf, buffers, sampler["output"])
            if not values or len(values) < 2:
                continue
            first, last = values[0], values[-1]
            if path_name == "rotation":
                delta = quad_angle(first, last)
                if delta > max_rot_delta:
                    max_rot_delta, worst_channel = delta, target.get("node")
            else:
                delta = math.dist(first, last)
                if delta > max_pos_delta:
                    max_pos_delta, worst_channel = delta, target.get("node")
        rep.animations.append(
            {
                "name": name,
                "duration": round(duration, 3),
                "channels": channels,
                "loop_rotation_delta_deg": round(max_rot_delta, 2),
                "loop_position_delta": round(max_pos_delta, 4),
                "worst_node": worst_channel,
                "loops": (max_rot_delta < 2.0 and max_pos_delta < 0.02) if loop_check else None,
            }
        )

    for ext in rep.extensions:
        if ext in ("KHR_draco_mesh_compression", "EXT_meshopt_compression"):
            rep.warnings.append(f"{ext} present — the matching decoder must be registered")
        elif ext == "KHR_texture_basisu":
            rep.warnings.append("KHR_texture_basisu present — needs KTX2Loader + transcoder")
        elif ext.startswith("KHR_materials_"):
            pass
        else:
            rep.warnings.append(f"unsupported extension {ext}")
    return rep


def check(rep: Report, limits: tuple[int, int, int, int, float]) -> None:
    tris, tex, mats, bones, mb = limits
    size_mb = rep.bytes / (1024 * 1024)
    if rep.triangles > tris:
        rep.ok = False
        rep.errors.append(f"{rep.triangles:,} triangles > {tris:,}")
    if rep.texture_max > tex:
        rep.ok = False
        rep.errors.append(f"texture {rep.texture_max}px > {tex}px")
    if rep.materials > mats:
        rep.ok = False
        rep.errors.append(f"{rep.materials} materials > {mats}")
    if bones and rep.bones > bones:
        rep.ok = False
        rep.errors.append(f"{rep.bones} bones > {bones}")
    if size_mb > mb:
        rep.ok = False
        rep.errors.append(f"{size_mb:.1f} MB > {mb:.0f} MB")
    if rep.bbox:
        tallest = max(rep.bbox["size"])
        if tallest < 0.02:
            rep.ok = False
            rep.errors.append(f"suspicious bbox {tallest:.3f} m — wrong units?")
        elif tallest > 500:
            rep.ok = False
            rep.errors.append(f"suspicious bbox {tallest:.0f} m — wrong units?")
    if rep.animations and rep.skins == 0:
        rep.warnings.append("animations but no skin — it cannot animate a character")
    for anim in rep.animations:
        if anim["duration"] <= 0:
            rep.ok = False
            rep.errors.append(f"clip {anim['name']} has zero duration")
        elif anim["loops"] is False:
            rep.warnings.append(f"clip {anim['name']} does not loop cleanly ({anim['loop_rotation_delta_deg']}°)")
    missing = [i for i in rep.images if i["width"] is None and i["bytes"] == 0]
    if missing:
        rep.warnings.append(f"{len(missing)} image(s) unresolved — the model will render naked")


def fmt_row(rep: Report) -> str:
    status = "ok  " if rep.ok else "FAIL"
    return (
        f"{status} {Path(rep.path).name[:34]:<34} "
        f"{rep.triangles:>9,} {rep.texture_max or '-':>6} "
        f"{rep.materials:>4} {len(rep.animations):>3} {rep.bones:>4} "
        f"{rep.bytes / 1048576:>6.1f}MB"
    )


def print_detail(rep: Report) -> None:
    print(f"\n{rep.path}")
    print(f"  size        {rep.bytes / 1048576:.2f} MB")
    print(f"  geometry    {rep.triangles:,} tris, {rep.vertices:,} verts, {rep.meshes} mesh(es), {rep.primitives} primitive(s)")
    print(f"  materials   {rep.materials}   textures {rep.textures}   max {rep.texture_max or '-'}px   {rep.texture_bytes / 1048576:.1f} MB")
    if rep.bbox:
        print(f"  bbox        {rep.bbox['size']} m (x,y,z)")
    if rep.skins:
        print(f"  rig         {rep.skins} skin(s), {rep.bones} bones")
    if rep.morph_targets:
        print(f"  morphs      {rep.morph_targets} target(s)")
    for anim in rep.animations:
        loop = "loop" if anim["loops"] else ("no-loop" if anim["loops"] is False else "?")
        print(
            f"  clip        {anim['name'][:28]:<28} {anim['duration']:>6.2f}s "
            f"{anim['channels']:>3}ch  seam {anim['loop_rotation_delta_deg']:>5.1f}° {loop}"
        )
    if rep.extensions:
        print(f"  extensions  {', '.join(rep.extensions)}")
    for warning in rep.warnings:
        print(f"  warn        {warning}")
    for error in rep.errors:
        print(f"  ERROR       {error}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+", help="GLB/glTF files, or directories")
    ap.add_argument("--recursive", action="store_true", help="descend into directories")
    ap.add_argument("--budget", default="prop", help="prop|hero|character|env|unlimited, or preset:<name>")
    ap.add_argument("--max-tris", type=int)
    ap.add_argument("--max-texture", type=int)
    ap.add_argument("--max-materials", type=int)
    ap.add_argument("--max-bones", type=int, default=0)
    ap.add_argument("--max-mb", type=float)
    ap.add_argument("--loop-check", action="store_true", help="compare first/last keyframes per clip")
    ap.add_argument("--json", help="write the full report to this path")
    args = ap.parse_args()

    preset = args.budget.removeprefix("preset:")
    if preset not in BUDGETS:
        print(f"unknown budget '{args.budget}' (choose {', '.join(BUDGETS)})", file=sys.stderr)
        return 2
    tris, tex, mats, bones, mb = BUDGETS[preset]
    limits = (
        args.max_tris or tris,
        args.max_texture or tex,
        args.max_materials or mats,
        args.max_bones or bones,
        args.max_mb or mb,
    )

    files: list[Path] = []
    for raw in args.paths:
        p = Path(raw)
        if p.is_dir():
            prefix = "**/" if args.recursive else ""
            found: set[Path] = set()
            for ext in ("glb", "gltf"):
                found.update(x for x in p.glob(f"{prefix}*.{ext}") if x.is_file())
            files.extend(sorted(found))
        elif p.is_file():
            files.append(p)
        else:
            print(f"skipping missing path {p}", file=sys.stderr)
    if not files:
        print("no .glb/.gltf files found", file=sys.stderr)
        return 2

    print(f"budget: {preset}  (tris<={limits[0]:,}, tex<={limits[1]}, mats<={limits[2]}, "
          f"bones<={limits[3] or '-'}, size<={limits[4]:.0f}MB)")
    print(f"{'':5} {'file':<34} {'tris':>9} {'tex':>6} {'mat':>4} {'clips':>5} {'bones':>5} {'size':>8}")

    reports = []
    failures = 0
    for path in files:
        rep = audit(path, loop_check=args.loop_check)
        if rep.ok:
            check(rep, limits)
        if not rep.ok:
            failures += 1
        reports.append(rep)
        print(fmt_row(rep))

    for rep in reports:
        if not rep.ok or rep.warnings or args.loop_check:
            print_detail(rep)

    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"budget": preset, "limits": limits, "files": [asdict(r) for r in reports]}, indent=2))
        print(f"\nwrote {out}")

    print(f"\n{len(reports) - failures}/{len(reports)} within budget")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
