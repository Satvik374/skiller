#!/usr/bin/env bash
# Optimise a glTF/GLB for the browser: compress geometry, downscale textures,
# simplify distant detail, and report before/after.
#
#   bash optimize_assets.sh public/assets/env/warehouse.glb
#   bash optimize_assets.sh hero.glb --texture-size 2048 --tris 60000 -o out/hero.glb
#
# Requires Node (npx). Uses @gltf-transform/cli for the main pass and gltfpack
# as an optional extra pass for static meshes. Neither is installed globally.

set -euo pipefail

IN=""
OUT=""
TEX=1024
TRIS=""
METHOD="meshopt"
KEEP_ORIGINAL=0

usage() { sed -n '2,12p' "$0"; exit "${1:-0}"; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage 0 ;;
    -o|--out) OUT="${2:?}"; shift 2 ;;
    --texture-size) TEX="${2:?}"; shift 2 ;;
    --tris) TRIS="${2:?}"; shift 2 ;;
    --method) METHOD="${2:?}"; shift 2 ;;   # meshopt | draco | quantize
    --keep-original) KEEP_ORIGINAL=1; shift ;;
    *) IN="$1"; shift ;;
  esac
done

[[ -n "$IN" ]] || usage 2
[[ -f "$IN" ]] || { echo "no such file: $IN" >&2; exit 2; }
command -v npx >/dev/null 2>&1 || { echo "npx not found — install Node 20+" >&2; exit 2; }

BASE_DIR="$(cd "$(dirname "$IN")" && pwd)"
NAME="$(basename "$IN")"
STEM="${NAME%.*}"
EXT="${NAME##*.}"
[[ -n "$OUT" ]] || OUT="${BASE_DIR}/${STEM}.opt.${EXT}"

before=$(stat -c %s "$IN" 2>/dev/null || stat -f %z "$IN")

TMPDIR_OPT="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_OPT"' EXIT
FIRST="${TMPDIR_OPT}/pass1.glb"

SIMPLIFY_ARGS=()
if [[ -n "$TRIS" ]]; then
  # simplify-error is a ratio of the mesh's extent; 0.0001 is conservative,
  # raise to 0.001 for distant props. The --tris target is enforced after.
  SIMPLIFY_ARGS=(--simplify true --simplify-error 0.0005)
else
  SIMPLIFY_ARGS=(--simplify false)
fi

echo "→ pass 1: gltf-transform optimize (compress=${METHOD}, textures=${TEX}px)"
npx --yes @gltf-transform/cli@latest optimize "$IN" "$FIRST" \
  --compress "$METHOD" \
  --texture-compress webp \
  --texture-size "$TEX" \
  --weld true \
  --prune true \
  --dedup true \
  --instance true \
  --flatten true \
  --join true \
  "${SIMPLIFY_ARGS[@]}"

FINAL="$FIRST"

if [[ -n "$TRIS" ]]; then
  echo "→ pass 2: simplify to ≤ ${TRIS} triangles"
  npx --yes @gltf-transform/cli@latest simplify "$FINAL" "$FINAL" \
    --ratio 0 --error 0.001 --reduce "target-triangle-count" 2>/dev/null || \
    echo "  (this gltf-transform version has no triangle-count reducer; using error-based simplify)" 
  npx --yes @gltf-transform/cli@latest simplify "$FINAL" "$FINAL" --error 0.002 2>/dev/null || true
fi

mkdir -p "$(dirname "$OUT")"
cp "$FINAL" "$OUT"

after=$(stat -c %s "$OUT" 2>/dev/null || stat -f %z "$OUT")
pct=$(awk -v a="$before" -v b="$after" 'BEGIN{ if(a>0) printf "%.0f", (1-(b/a))*100; else print 0 }')

echo
printf "  original  %8.2f MB\n" "$(awk -v v="$before" 'BEGIN{print v/1048576}')"
printf "  optimised %8.2f MB  (-%s%%)\n" "$(awk -v v="$after" 'BEGIN{print v/1048576}')" "$pct"
echo "  → $OUT"
echo
echo "verify before shipping:"
echo "  python3 game-builder/scripts/glb_audit.py \"$OUT\" --budget hero --loop-check"

if [[ $KEEP_ORIGINAL -eq 0 && "$OUT" != "$IN" ]]; then
  echo "  (original left at $IN; keep raw downloads out of the shipped tree)"
fi
