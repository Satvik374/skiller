import * as THREE from 'three';
import { baseHeight } from './heightfield.js';
import { bannerTexture, checkerTexture, dashTexture } from '../core/canvasTextures.js';

export const ROAD_HALF = 7.2;
const SAMPLE_STEP = 2.5;

/** Control points of the alpine circuit (XZ metres). */
const CONTROL = [
  [0, 470],
  [210, 430],
  [360, 320],
  [440, 150],
  [400, -40],
  [300, -190],
  [150, -290],
  [-40, -340],
  [-240, -320],
  [-390, -200],
  [-450, -10],
  [-400, 200],
  [-250, 380],
];

export class Circuit {
  constructor(textures) {
    this.tex = textures;
    this.curve = new THREE.CatmullRomCurve3(
      CONTROL.map(([x, z]) => new THREE.Vector3(x, 0, z)),
      true,
      'catmullrom',
      0.5
    );
    this.curve.arcLengthDivisions = 3000;
    this.length = this.curve.getLength();
    this.#buildSamples();
    this.#buildLookup();
  }

  #buildSamples() {
    const count = Math.max(64, Math.round(this.length / SAMPLE_STEP));
    const points = this.curve.getSpacedPoints(count); // count + 1, last == first
    this.samples = [];
    this.count = count;
    for (let i = 0; i < count; i++) {
      const p = points[i];
      this.samples.push({ x: p.x, z: p.z, y: 0, len: (i / count) * this.length, u: i / count });
    }

    // Elevation: follow the landscape but heavily smoothed, so the road is a
    // graded corridor rather than a rollercoaster.
    let heights = this.samples.map((s) => baseHeight(s.x, s.z));
    for (let pass = 0; pass < 4; pass++) {
      const out = new Array(count);
      const W = 20;
      for (let i = 0; i < count; i++) {
        let sum = 0;
        for (let k = -W; k <= W; k++) sum += heights[(i + k + count) % count];
        out[i] = sum / (2 * W + 1);
      }
      heights = out;
    }
    // Damp the sharpest grades a little further and lift the racing surface.
    for (let i = 0; i < count; i++) {
      this.samples[i].y = heights[i] + 0.35;
    }

    // Tangents / right vectors.
    for (let i = 0; i < count; i++) {
      const a = this.samples[(i - 1 + count) % count];
      const b = this.samples[(i + 1) % count];
      const tx = b.x - a.x;
      const tz = b.z - a.z;
      const tl = Math.hypot(tx, tz) || 1;
      this.samples[i].tx = tx / tl;
      this.samples[i].tz = tz / tl;
      this.samples[i].nx = -this.samples[i].tz;
      this.samples[i].nz = this.samples[i].tx;
    }
  }

  #buildLookup() {
    this.cell = 20;
    this.grid = new Map();
    for (let i = 0; i < this.samples.length; i++) {
      const s = this.samples[i];
      const key = `${Math.floor(s.x / this.cell)},${Math.floor(s.z / this.cell)}`;
      if (!this.grid.has(key)) this.grid.set(key, []);
      this.grid.get(key).push(i);
    }
  }

  /** Nearest point on the road: distance in metres plus that point's height. */
  nearest(x, z, radius = 44) {
    const keys = Math.max(1, Math.ceil(radius / this.cell));
    const cx = Math.floor(x / this.cell);
    const cz = Math.floor(z / this.cell);
    let best = Infinity;
    let bestIndex = -1;
    for (let dz = -keys; dz <= keys; dz++) {
      for (let dx = -keys; dx <= keys; dx++) {
        const bucket = this.grid.get(`${cx + dx},${cz + dz}`);
        if (!bucket) continue;
        for (const i of bucket) {
          const s = this.samples[i];
          const d = (s.x - x) ** 2 + (s.z - z) ** 2;
          if (d < best) {
            best = d;
            bestIndex = i;
          }
        }
      }
    }
    if (bestIndex < 0) return { dist: Infinity, y: 0, index: 0 };
    return { dist: Math.sqrt(best), y: this.samples[bestIndex].y, index: bestIndex };
  }

  sampleAt(u) {
    const i = Math.floor((u % 1) * this.count);
    return this.samples[(i + this.count) % this.count];
  }

  /** Position on the circuit at normalised distance u (0..1). */
  pointAt(u, out = new THREE.Vector3()) {
    const s = this.sampleAt(u);
    return out.set(s.x, s.y, s.z);
  }

  startTransform() {
    const s = this.samples[0];
    return { position: new THREE.Vector3(s.x, s.y, s.z), yaw: Math.atan2(s.tx, s.tz) };
  }

  gridStart() {
    const s = this.sampleAt(0);
    return s;
  }

  // ---------------------------------------------------------------------
  // Geometry
  // ---------------------------------------------------------------------
  build() {
    const group = new THREE.Group();
    group.name = 'circuit';

    const asphalt = new THREE.MeshStandardMaterial({
      map: this.tex.asphalt.map,
      normalMap: this.tex.asphalt.normal,
      roughnessMap: this.tex.asphalt.rough,
      aoMap: this.tex.asphalt.ao,
      aoMapIntensity: 0.9,
      roughness: 1,
      metalness: 0.02,
      color: 0xcfcfcf,
      normalScale: new THREE.Vector2(0.85, 0.85),
    });

    const road = new THREE.Mesh(this.#ribbonGeometry(-ROAD_HALF, ROAD_HALF, 1, (s) => s.len / 9, 1.05), asphalt);
    road.receiveShadow = true;
    road.name = 'road_surface';
    group.add(road);

    // Painted centre dashes + solid edge lines.
    const dashMat = new THREE.MeshStandardMaterial({
      map: dashTexture(),
      transparent: true,
      roughness: 0.7,
      metalness: 0,
      polygonOffset: true,
      polygonOffsetFactor: -2,
      depthWrite: false,
    });
    dashMat.map.repeat.set(1, 1);
    const dashes = new THREE.Mesh(this.#ribbonGeometry(-0.16, 0.16, 0.02, (s, v) => (s.len / 12) % 1 + (v > 0.5 ? 0 : 0), 0.0), dashMat);
    dashes.renderOrder = 2;
    group.add(dashes);

    const lineMat = new THREE.MeshStandardMaterial({
      color: 0xe9e6d8,
      roughness: 0.82,
      polygonOffset: true,
      polygonOffsetFactor: -2,
    });
    for (const side of [-1, 1]) {
      const edge = new THREE.Mesh(
        this.#ribbonGeometry(side * (ROAD_HALF - 0.75) - 0.11, side * (ROAD_HALF - 0.75) + 0.11, 0.018, () => 0, 0.0),
        lineMat
      );
      group.add(edge);
    }

    // Concrete parapet on the outside of every corner + along the straights.
    const barrierMat = new THREE.MeshStandardMaterial({
      map: this.tex.concrete.map,
      normalMap: this.tex.concrete.normal,
      roughnessMap: this.tex.concrete.rough,
      roughness: 1,
      color: 0xb9b6ae,
      side: THREE.DoubleSide,
    });
    for (const side of [-1, 1]) {
      const barrier = new THREE.Mesh(this.#wallGeometry(side), barrierMat);
      barrier.castShadow = true;
      barrier.receiveShadow = true;
      group.add(barrier);
    }

    group.add(this.#startGantry());
    group.add(this.#checkerStrip());
    this.gates = this.#buildGates();
    group.add(this.gates.group);

    return group;
  }

  #ribbonGeometry(inner, outer, lift = 0, uFn = (s) => s.len / 9, vRepeat = 1) {
    const n = this.samples.length;
    const positions = new Float32Array(n * 2 * 3);
    const uvs = new Float32Array(n * 2 * 2);
    const normals = new Float32Array(n * 2 * 3);
    const indices = [];

    for (let i = 0; i < n; i++) {
      const s = this.samples[i];
      for (let side = 0; side < 2; side++) {
        const offset = side === 0 ? inner : outer;
        const idx = (i * 2 + side) * 3;
        positions[idx] = s.x + s.nx * offset;
        positions[idx + 1] = s.y + lift;
        positions[idx + 2] = s.z + s.nz * offset;
        normals[idx] = 0;
        normals[idx + 1] = 1;
        normals[idx + 2] = 0;
        const uvIdx = (i * 2 + side) * 2;
        uvs[uvIdx] = side === 0 ? 0 : (outer - inner) / 9;
        uvs[uvIdx + 1] = uFn(s, side);
      }
      const a = (i * 2) % (n * 2);
      const b = (i * 2 + 1) % (n * 2);
      const c = ((i + 1) * 2) % (n * 2);
      const d = ((i + 1) * 2 + 1) % (n * 2);
      indices.push(a, c, b, b, c, d);
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geo.setAttribute('normal', new THREE.BufferAttribute(normals, 3));
    geo.setAttribute('uv', new THREE.BufferAttribute(uvs, 2));
    geo.setAttribute('uv1', new THREE.BufferAttribute(uvs.slice(), 2));
    geo.setIndex(indices);
    geo.computeVertexNormals();
    return geo;
  }

  #wallGeometry(side) {
    const n = this.samples.length;
    // Skip a short run at the start line so the paddock is open.
    const positions = [];
    const uvs = [];
    const indices = [];
    let ring = 0;
    const offset = side * (ROAD_HALF + 2.4);
    const height = 0.95;
    for (let i = 0; i < n; i++) {
      const s = this.samples[i];
      const skip = s.len < 26 || s.len > this.length - 26;
      if (skip) continue;
      const bx = s.x + s.nx * offset;
      const bz = s.z + s.nz * offset;
      positions.push(bx, s.y, bz, bx, s.y + height, bz);
      const u = s.len / 6;
      uvs.push(u, 0, u, 1);
      if (ring > 0) {
        const a = (ring - 1) * 2;
        const b = (ring - 1) * 2 + 1;
        const c = ring * 2;
        const d = ring * 2 + 1;
        indices.push(a, b, c, b, d, c);
      }
      ring++;
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    geo.setAttribute('uv', new THREE.Float32BufferAttribute(uvs, 2));
    geo.setAttribute('uv1', new THREE.Float32BufferAttribute(uvs.slice(), 2));
    geo.setIndex(indices);
    geo.computeVertexNormals();
    return geo;
  }

  #startGantry() {
    const g = new THREE.Group();
    const s = this.samples[0];
    const concrete = new THREE.MeshStandardMaterial({
      map: this.tex.concrete.map,
      normalMap: this.tex.concrete.normal,
      roughness: 0.9,
      color: 0x9a9a96,
    });
    const steel = new THREE.MeshStandardMaterial({ color: 0x2a2f36, metalness: 0.85, roughness: 0.38 });

    const yaw = Math.atan2(s.tx, s.tz);
    g.position.set(s.x, s.y, s.z);
    g.rotation.y = yaw;

    for (const side of [-1, 1]) {
      const pylon = new THREE.Mesh(new THREE.BoxGeometry(0.9, 8.4, 0.9), steel);
      pylon.position.set(side * (ROAD_HALF + 1.6), 4.2, 0);
      pylon.castShadow = true;
      g.add(pylon);
      const base = new THREE.Mesh(new THREE.BoxGeometry(1.8, 0.55, 1.8), concrete);
      base.position.set(side * (ROAD_HALF + 1.6), 0.27, 0);
      base.castShadow = true;
      base.receiveShadow = true;
      g.add(base);
    }

    const banner = new THREE.Mesh(
      new THREE.PlaneGeometry((ROAD_HALF + 2) * 2, 3.1),
      new THREE.MeshStandardMaterial({
        map: bannerTexture('VELOCITY RIDGE', 'START · FINISH'),
        emissiveMap: bannerTexture('VELOCITY RIDGE', 'START · FINISH'),
        emissive: 0xffffff,
        emissiveIntensity: 0.22,
        roughness: 0.8,
        side: THREE.DoubleSide,
      })
    );
    banner.position.set(0, 7.3, -0.2);
    banner.rotation.y = Math.PI;
    g.add(banner);
    g.userData.banner = banner;
    return g;
  }

  #checkerStrip() {
    const geo = this.#ribbonGeometry(-ROAD_HALF + 0.2, ROAD_HALF - 0.2, 0.03, (s) => (s.len / 2.4) % 1, 0.0);
    const mat = new THREE.MeshStandardMaterial({
      map: checkerTexture(),
      roughness: 0.75,
      polygonOffset: true,
      polygonOffsetFactor: -3,
    });
    mat.map.repeat.set(1, 1);
    const mesh = new THREE.Mesh(geo, mat);
    // Trim the ribbon to just the start line so it reads as one strip.
    const n = this.samples.length;
    const keep = Math.max(4, Math.floor(4 / (this.length / n)));
    const indices = [];
    for (let i = 0; i < keep; i++) {
      const a = (i * 2) % (n * 2);
      const b = (i * 2 + 1) % (n * 2);
      const c = ((i + 1) * 2) % (n * 2);
      const d = ((i + 1) * 2 + 1) % (n * 2);
      indices.push(a, c, b, b, c, d);
    }
    geo.setIndex(indices);
    return mesh;
  }

  #buildGates(count = 8) {
    const group = new THREE.Group();
    const postMat = new THREE.MeshStandardMaterial({
      color: 0x151a21,
      metalness: 0.7,
      roughness: 0.4,
      emissive: 0x1f7fa0,
      emissiveIntensity: 0.35,
    });
    const glowMat = new THREE.MeshStandardMaterial({
      color: 0x35d0ff,
      emissive: 0x35d0ff,
      emissiveIntensity: 2.2,
      roughness: 0.3,
    });
    const gates = [];
    for (let i = 0; i < count; i++) {
      const s = this.sampleAt(i / count + 0.5 / count);
      const yaw = Math.atan2(s.tx, s.tz);
      const gate = new THREE.Group();
      gate.position.set(s.x, s.y, s.z);
      gate.rotation.y = yaw;

      for (const side of [-1, 1]) {
        const post = new THREE.Mesh(new THREE.BoxGeometry(0.34, 6.2, 0.34), postMat);
        post.position.set(side * (ROAD_HALF + 0.9), 3.1, 0);
        post.castShadow = true;
        gate.add(post);
        const strip = new THREE.Mesh(new THREE.BoxGeometry(0.1, 5.2, 0.1), glowMat);
        strip.position.set(side * (ROAD_HALF + 0.72), 3.2, 0.28);
        gate.add(strip);
      }
      const beam = new THREE.Mesh(new THREE.BoxGeometry((ROAD_HALF + 1.2) * 2, 0.5, 0.5), postMat);
      beam.position.y = 6.2;
      gate.add(beam);
      const lightBar = new THREE.Mesh(new THREE.BoxGeometry(ROAD_HALF * 2, 0.14, 0.14), glowMat);
      lightBar.position.y = 5.9;
      gate.add(lightBar);

      gate.visible = false; // only the active checkpoint gate is drawn
      group.add(gate);
      gates.push({ group: gate, position: new THREE.Vector3(s.x, s.y, s.z), index: i, u: i / count });
    }
    return { group, list: gates };
  }

  /** World position of checkpoint i (0 = start/finish). */
  checkpointPosition(i, out = new THREE.Vector3()) {
    const s = this.sampleAt(0);
    if (i === 0) return out.set(s.x, s.y, s.z);
    return this.pointAt(i / (this.gates.list.length || 8), out);
  }
}
