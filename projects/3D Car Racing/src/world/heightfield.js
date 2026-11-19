import { fbm, ridged } from '../core/noise.js';

export const WORLD_SIZE = 1400;
export const WORLD_HALF = WORLD_SIZE / 2;

/**
 * The raw landscape before the road is carved into it.
 * Long rolling ridges + a few sharp peaks so the horizon is never a flat line.
 */
export function baseHeight(x, z) {
  const hills = fbm(x * 0.0019 + 11.3, z * 0.0019 - 4.1, 4) - 0.5;
  const rolls = fbm(x * 0.0072 - 3.7, z * 0.0072 + 8.9, 3) - 0.5;
  let h = hills * 96 + rolls * 11;

  // Mountain ring: keeps the playable basin enclosed without invisible walls.
  const edge = Math.max(Math.abs(x), Math.abs(z)) / WORLD_HALF;
  const rim = Math.max(0, (edge - 0.58) / 0.42);
  h += Math.pow(rim, 1.7) * (70 + ridged(x * 0.0042, z * 0.0042, 4) * 150);

  // A shallow lake basin in the north-west corner.
  const lake = Math.hypot(x + 330, z + 300);
  h -= Math.max(0, 1 - lake / 150) * 26;

  return h;
}

export function slopeOf(x, z, eps = 4) {
  const hx = baseHeight(x + eps, z) - baseHeight(x - eps, z);
  const hz = baseHeight(x, z + eps) - baseHeight(x, z - eps);
  return Math.hypot(hx, hz) / (2 * eps);
}
