#!/usr/bin/env python3
"""Downscale every texture in a glTF folder to a max edge, repack non-alpha
maps as JPEG and rewrite the .gltf image URIs to match.

    python3 tools/optimize_textures.py public/assets/tree_pine 1024

Sketchfab archives routinely ship 4K-8K PNGs. A browser cannot stream that
without a multi-second stall, so this runs before anything is loaded.
"""
from __future__ import annotations

import glob
import os
import sys

from PIL import Image

Image.MAX_IMAGE_PIXELS = 200_000_000


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    root = sys.argv[1].rstrip("/")
    max_edge = int(sys.argv[2]) if len(sys.argv) > 2 else 1024
    quality = int(sys.argv[3]) if len(sys.argv) > 3 else 88

    renames: dict[str, str] = {}
    saved = 0
    for path in sorted(glob.glob(f"{root}/**/*.*", recursive=True)):
        if os.path.splitext(path)[1].lower() not in (".png", ".jpg", ".jpeg", ".webp"):
            continue
        before = os.path.getsize(path)
        try:
            im = Image.open(path)
        except Exception as exc:  # noqa: BLE001
            print(f"skip {path}: {exc}")
            continue
        if im.mode == "P":
            im = im.convert("RGBA")
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGB")
        if max(im.size) > max_edge:
            im = im.resize((max_edge, max_edge), Image.LANCZOS)

        has_alpha = im.mode == "RGBA" and im.getchannel("A").getextrema()[0] < 250
        if has_alpha:
            im.save(path, optimize=True)
        else:
            base = os.path.splitext(path)[0]
            target = base + ".jpg"
            im.convert("RGB").save(target, quality=quality, optimize=True)
            if target != path:
                os.remove(path)
                renames[os.path.basename(path)] = os.path.basename(target)
        after = os.path.getsize(os.path.splitext(path)[0] + (".jpg" if not has_alpha else os.path.splitext(path)[1]))
        saved += before - after
        print(f"{os.path.relpath(path, root):<52} {before // 1024:>7} KB -> {after // 1024:>6} KB")

    for gltf in glob.glob(f"{root}/**/*.gltf", recursive=True):
        text = open(gltf, encoding="utf-8").read()
        for old, new in renames.items():
            text = text.replace(old, new)
        open(gltf, "w", encoding="utf-8").write(text)
    print(f"\n{saved / 1048576:.1f} MB saved across {len(renames)} repacked images")
    return 0


if __name__ == "__main__":
    sys.exit(main())
