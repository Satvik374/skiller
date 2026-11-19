import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { mulberry32, fbm } from '../core/noise.js';
import { ROAD_HALF } from './circuit.js';
import { billboardTexture } from '../core/canvasTextures.js';

function loadGLTF(loader, url) {
  return new Promise((resolve, reject) => loader.load(url, resolve, undefined, reject));
}

function cleanGeometry(source) {
  const geo = source.index ? source.toNonIndexed() : source.clone();
  for (const name of Object.keys(geo.attributes)) {
    if (!['position', 'normal', 'uv'].includes(name)) geo.deleteAttribute(name);
  }
  if (!geo.attributes.uv) {
    geo.setAttribute('uv', new THREE.BufferAttribute(new Float32Array(geo.attributes.position.count * 2), 2));
  }
  if (!geo.attributes.normal) geo.computeVertexNormals();
  return geo;
}

export class Scenery {
  constructor({ scene, terrain, circuit, textures, onProgress }) {
    this.scene = scene;
    this.terrain = terrain;
    this.circuit = circuit;
    this.tex = textures;
    this.onProgress = onProgress || (() => {});
    this.loader = new GLTFLoader();
    this.colliders = [];
    this.group = new THREE.Group();
    this.group.name = 'scenery';
    this.rand = mulberry32(20261119);
  }

  async build() {
    this.scene.add(this.group);
    this.#buildStreetLights();
    this.#buildBillboards();
    await this.#buildTrees();
    await this.#buildTown();
    return this.group;
  }

  // ------------------------------------------------------------------
  // Street furniture — authored in code with real PBR materials.
  // ------------------------------------------------------------------
  #buildStreetLights() {
    const poleGeo = new THREE.CylinderGeometry(0.11, 0.16, 8.2, 10);
    poleGeo.translate(0, 4.1, 0);
    const armGeo = new THREE.BoxGeometry(1.9, 0.13, 0.13);
    armGeo.translate(0.9, 8.1, 0);
    const headGeo = new THREE.BoxGeometry(0.72, 0.14, 0.3);
    headGeo.translate(1.75, 8.02, 0);
    const mast = mergeGeometries([poleGeo, armGeo]);
    const metal = new THREE.MeshStandardMaterial({ color: 0x2c3138, metalness: 0.85, roughness: 0.42 });
    const lampMat = new THREE.MeshStandardMaterial({
      color: 0xffe9c9,
      emissive: 0xffc36b,
      emissiveIntensity: 2.4,
      roughness: 0.4,
    });

    const positions = [];
    const n = this.circuit.samples.length;
    const stride = Math.max(1, Math.round(38 / (this.circuit.length / n)));
    for (let i = 12; i < n - 8; i += stride) {
      const s = this.circuit.samples[i];
      const side = i % 2 === 0 ? 1 : -1;
      positions.push({ s, side });
    }

    const masts = new THREE.InstancedMesh(mast, metal, positions.length);
    const heads = new THREE.InstancedMesh(headGeo, lampMat, positions.length);
    masts.castShadow = true;
    const m = new THREE.Matrix4();
    const q = new THREE.Quaternion();
    const up = new THREE.Vector3(0, 1, 0);
    positions.forEach(({ s, side }, i) => {
      const x = s.x + s.nx * (ROAD_HALF + 1.9) * side;
      const z = s.z + s.nz * (ROAD_HALF + 1.9) * side;
      const y = this.terrain.heightAt(x, z);
      const yaw = Math.atan2(s.tx, s.tz) + (side > 0 ? Math.PI : 0);
      q.setFromAxisAngle(up, yaw);
      m.compose(new THREE.Vector3(x, y, z), q, new THREE.Vector3(1, 1, 1));
      masts.setMatrixAt(i, m);
      heads.setMatrixAt(i, m);
      this.colliders.push({ x, z, radius: 0.4, top: y + 8.2, type: 'pole' });
    });
    masts.instanceMatrix.needsUpdate = true;
    heads.instanceMatrix.needsUpdate = true;
    this.group.add(masts, heads);
  }

  #buildBillboards() {
    const content = [
      ['RIDGE PASS', 'SECTOR 2 · 1.8 km'],
      ['SUMMIT MOTEL', 'NEXT EXIT 400 m'],
      ['ALPINE FUEL', 'OPEN 24 HOURS'],
      ['DANGER', 'STEEP GRADE'],
    ];
    const postMat = new THREE.MeshStandardMaterial({ color: 0x30353c, metalness: 0.7, roughness: 0.5 });
    const anchors = [0.22, 0.43, 0.68, 0.86];
    anchors.forEach((u, i) => {
      const s = this.circuit.sampleAt(u);
      const side = i % 2 === 0 ? 1 : -1;
      const offset = ROAD_HALF + 9;
      const x = s.x + s.nx * offset * side;
      const z = s.z + s.nz * offset * side;
      const y = this.terrain.heightAt(x, z);

      const g = new THREE.Group();
      g.position.set(x, y, z);
      g.rotation.y = Math.atan2(s.tx, s.tz) + Math.PI + (side > 0 ? 0.25 : -0.25);

      for (const px of [-2.2, 2.2]) {
        const post = new THREE.Mesh(new THREE.BoxGeometry(0.22, 6.4, 0.22), postMat);
        post.position.set(px, 3.2, 0);
        post.castShadow = true;
        g.add(post);
      }
      const board = new THREE.Mesh(
        new THREE.PlaneGeometry(5.6, 2.8),
        new THREE.MeshStandardMaterial({
          map: billboardTexture(content[i]),
          roughness: 0.62,
          metalness: 0.1,
          side: THREE.DoubleSide,
        })
      );
      board.position.set(0, 5.4, 0.06);
      board.castShadow = true;
      g.add(board);
      this.group.add(g);
      this.colliders.push({ x, z, radius: 2.6, top: y + 6.4, type: 'sign' });
    });
  }

  // ------------------------------------------------------------------
  // Trees — Sketchfab pine, merged by material and drawn instanced.
  // ------------------------------------------------------------------
  async #buildTrees() {
    this.onProgress('loading vegetation');
    let gltf;
    try {
      gltf = await loadGLTF(this.loader, '/assets/tree_pine/scene.gltf');
    } catch (err) {
      console.warn('[scenery] tree asset missing — continuing without trees', err);
      return;
    }

    const root = gltf.scene;
    root.updateMatrixWorld(true);
    const byMaterial = new Map();
    root.traverse((o) => {
      if (!o.isMesh) return;
      const geo = cleanGeometry(o.geometry);
      geo.applyMatrix4(o.matrixWorld);
      const key = o.material;
      if (!byMaterial.has(key)) byMaterial.set(key, []);
      byMaterial.get(key).push(geo);
    });

    const materials = [];
    for (const [mat, geos] of byMaterial) {
      const merged = geos.length > 1 ? mergeGeometries(geos, false) : geos[0];
      if (!merged) continue;
      mat.envMapIntensity = 0.9;
      mat.side = THREE.DoubleSide;
      materials.push({ geometry: merged, material: mat });
    }

    // Placement: forest clumps on gentle ground away from the road.
    const count = 110;
    const placements = [];
    let guard = 0;
    while (placements.length < count && guard < count * 60) {
      guard++;
      const angle = this.rand() * Math.PI * 2;
      const radius = 60 + Math.sqrt(this.rand()) * 460;
      const x = Math.cos(angle) * radius;
      const z = Math.sin(angle) * radius;
      if (Math.abs(x) > 600 || Math.abs(z) > 600) continue;
      const near = this.circuit.nearest(x, z, 40);
      if (near.dist < ROAD_HALF + 13) continue;
      if (this.terrain.slopeAt(x, z) > 0.32) continue;
      // Clumping mask so trees form groves instead of an even sprinkle.
      const density = fbm(x * 0.004 + 7, z * 0.004 - 2, 3);
      if (density < 0.5 && this.rand() < 0.82) continue;
      if (this.colliders.some((c) => Math.hypot(c.x - x, c.z - z) < 12)) continue;
      if (placements.some((p) => Math.hypot(p.x - x, p.z - z) < 8)) continue;
      placements.push({ x, z, y: this.terrain.heightAt(x, z), s: 0.42 + this.rand() * 0.34, r: this.rand() * Math.PI * 2 });
    }

    const m = new THREE.Matrix4();
    const q = new THREE.Quaternion();
    const up = new THREE.Vector3(0, 1, 0);
    const color = new THREE.Color();
    for (const { geometry, material } of materials) {
      const mesh = new THREE.InstancedMesh(geometry, material, placements.length);
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      placements.forEach((p, i) => {
        q.setFromAxisAngle(up, p.r);
        m.compose(new THREE.Vector3(p.x, p.y - 0.15, p.z), q, new THREE.Vector3(p.s, p.s, p.s));
        mesh.setMatrixAt(i, m);
        color.setHSL(0.27 + this.rand() * 0.05, 0.35, 0.42 + this.rand() * 0.14);
        mesh.setColorAt(i, color);
        this.colliders.push({ x: p.x, z: p.z, radius: 0.55 * p.s * 4, top: p.y + 12, type: 'tree' });
      });
      mesh.instanceMatrix.needsUpdate = true;
      if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
      this.group.add(mesh);
    }
    console.info(`[scenery] ${placements.length} trees planted`);
  }

  // ------------------------------------------------------------------
  // Town — authored buildings from Sketchfab, aligned to the ground.
  // ------------------------------------------------------------------
  async #buildTown() {
    this.onProgress('placing town');
    const specs = [
      { url: '/assets/building_modern/scene.gltf', count: 13, height: [9, 22] },
      { url: '/assets/building_shop/scene.gltf', count: 5, height: [7, 12] },
    ];
    const rand = mulberry32(4242);
    let slot = 0;

    for (const spec of specs) {
      let gltf;
      try {
        gltf = await loadGLTF(this.loader, spec.url);
      } catch (err) {
        console.warn('[scenery] building asset missing', spec.url, err);
        continue;
      }
      const template = gltf.scene;
      template.updateMatrixWorld(true);
      template.traverse((o) => {
        if (!o.isMesh) return;
        o.castShadow = true;
        o.receiveShadow = true;
        if (o.material) {
          o.material.envMapIntensity = 1.0;
          if (o.material.normalMap) o.material.normalScale = new THREE.Vector2(0.8, 0.8);
        }
      });
      const box = new THREE.Box3().setFromObject(template);
      const size = box.getSize(new THREE.Vector3());

      for (let i = 0; i < spec.count; i++) {
        const u = 0.015 + (slot % 9) * 0.017 + rand() * 0.008;
        const s = this.circuit.sampleAt(u);
        const side = slot % 3 === 0 ? -1 : 1;
        const offset = 44 + rand() * 66;
        const along = (rand() - 0.5) * 40;
        const x = s.x + s.nx * offset * side + s.tx * along;
        const z = s.z + s.nz * offset * side + s.tz * along;
        if (this.circuit.nearest(x, z, 60).dist < ROAD_HALF + 10) continue;

        const clone = template.clone(true);
        const targetHeight = spec.height[0] + rand() * (spec.height[1] - spec.height[0]);
        const scale = targetHeight / (size.y || 10);
        clone.scale.setScalar(scale);
        clone.rotation.y = rand() * Math.PI * 2;

        // Sink the footprint slightly so the base never floats on a slope.
        const ground = this.terrain.heightAt(x, z);
        const corner = Math.min(
          this.terrain.heightAt(x + size.x * scale * 0.4, z + size.z * scale * 0.4),
          this.terrain.heightAt(x - size.x * scale * 0.4, z - size.z * scale * 0.4)
        );
        clone.position.set(x, Math.min(ground, corner) - 0.6, z);
        this.group.add(clone);

        const halfX = (size.x * scale) / 2;
        const halfZ = (size.z * scale) / 2;
        this.colliders.push({
          x, z, radius: Math.max(halfX, halfZ) * 0.82, top: clone.position.y + targetHeight, type: 'building',
        });
        slot++;
      }
    }
  }
}
