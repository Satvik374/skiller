import * as THREE from 'three';
import { baseHeight, WORLD_HALF, WORLD_SIZE } from './heightfield.js';
import { ROAD_HALF } from './circuit.js';

const SEGMENTS = 320;
const FLAT_RADIUS = ROAD_HALF + 3.5;
const BLEND_RADIUS = ROAD_HALF + 34;

/**
 * Terrain built from a height grid so the physics can sample exactly the
 * surface that is drawn — no mismatch between visuals and collision.
 */
export class Terrain {
  constructor(circuit, textures) {
    this.circuit = circuit;
    this.tex = textures;
    this.size = WORLD_SIZE;
    this.segments = SEGMENTS;
    this.step = WORLD_SIZE / SEGMENTS;
    this.n = SEGMENTS + 1;
    this.heights = new Float32Array(this.n * this.n);
    this.#generate();
  }

  #generate() {
    const { n, step } = this;
    for (let iz = 0; iz < n; iz++) {
      const z = -WORLD_HALF + iz * step;
      for (let ix = 0; ix < n; ix++) {
        const x = -WORLD_HALF + ix * step;
        const base = baseHeight(x, z);
        const near = this.circuit.nearest(x, z, 60);
        let h = base;
        if (near.dist < BLEND_RADIUS) {
          // Flat corridor at the road's graded height, then an embankment.
          const t = THREE.MathUtils.smoothstep(near.dist, FLAT_RADIUS, BLEND_RADIUS);
          const roadBed = near.y - 0.32;
          h = roadBed * (1 - t) + base * t;
        }
        this.heights[iz * n + ix] = h;
      }
    }
  }

  heightAt(x, z) {
    const { n, step } = this;
    const fx = (x + WORLD_HALF) / step;
    const fz = (z + WORLD_HALF) / step;
    const ix = Math.floor(fx);
    const iz = Math.floor(fz);
    if (ix < 0 || iz < 0 || ix >= n - 1 || iz >= n - 1) {
      return baseHeight(x, z);
    }
    const tx = fx - ix;
    const tz = fz - iz;
    const h00 = this.heights[iz * n + ix];
    const h10 = this.heights[iz * n + ix + 1];
    const h01 = this.heights[(iz + 1) * n + ix];
    const h11 = this.heights[(iz + 1) * n + ix + 1];
    return (
      h00 * (1 - tx) * (1 - tz) +
      h10 * tx * (1 - tz) +
      h01 * (1 - tx) * tz +
      h11 * tx * tz
    );
  }

  normalAt(x, z, out = new THREE.Vector3()) {
    const e = 2.2;
    const hL = this.heightAt(x - e, z);
    const hR = this.heightAt(x + e, z);
    const hD = this.heightAt(x, z - e);
    const hU = this.heightAt(x, z + e);
    return out.set(hL - hR, 2 * e, hD - hU).normalize();
  }

  slopeAt(x, z) {
    const nrm = this.normalAt(x, z, new THREE.Vector3());
    return 1 - nrm.y;
  }

  build() {
    const { n, step } = this;
    const positions = new Float32Array(n * n * 3);
    const uvs = new Float32Array(n * n * 2);
    const colors = new Float32Array(n * n * 3);
    const indices = [];

    for (let iz = 0; iz < n; iz++) {
      for (let ix = 0; ix < n; ix++) {
        const i = iz * n + ix;
        const x = -WORLD_HALF + ix * step;
        const z = -WORLD_HALF + iz * step;
        positions[i * 3] = x;
        positions[i * 3 + 1] = this.heights[i];
        positions[i * 3 + 2] = z;
        uvs[i * 2] = x / 11;
        uvs[i * 2 + 1] = z / 11;

        // Macro variation: large-scale tint so no two hills read identical.
        const v = 0.82 + 0.18 * Math.sin(x * 0.013) * Math.cos(z * 0.011);
        colors[i * 3] = v;
        colors[i * 3 + 1] = v * 0.99;
        colors[i * 3 + 2] = v * 0.94;
      }
    }

    for (let iz = 0; iz < n - 1; iz++) {
      for (let ix = 0; ix < n - 1; ix++) {
        const a = iz * n + ix;
        const b = a + 1;
        const c = a + n;
        const d = c + 1;
        indices.push(a, c, b, b, c, d);
      }
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geo.setAttribute('uv', new THREE.BufferAttribute(uvs, 2));
    geo.setAttribute('uv1', new THREE.BufferAttribute(uvs.slice(), 2));
    geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    geo.setIndex(indices);
    geo.computeVertexNormals();
    geo.computeBoundingSphere();

    const grass = this.tex.grass;
    const material = new THREE.MeshStandardMaterial({
      map: grass.map,
      normalMap: grass.normal,
      roughnessMap: grass.rough,
      roughness: 1,
      metalness: 0,
      vertexColors: true,
      normalScale: new THREE.Vector2(0.6, 0.6),
      color: 0xffffff,
    });

    material.onBeforeCompile = (shader) => {
      shader.uniforms.uDirtMap = { value: this.tex.dirt.map };
      shader.vertexShader = `varying vec3 vWPos;\nvarying float vSlopeT;\n${shader.vertexShader}`;
      shader.vertexShader = shader.vertexShader.replace(
        '#include <begin_vertex>',
        `#include <begin_vertex>
         vec4 worldPos = modelMatrix * vec4( transformed, 1.0 );
         vWPos = worldPos.xyz;
         vSlopeT = 1.0 - clamp( normal.y, 0.0, 1.0 );`
      );
      shader.fragmentShader = `uniform sampler2D uDirtMap;\nvarying vec3 vWPos;\nvarying float vSlopeT;\n${shader.fragmentShader}`;
      shader.fragmentShader = shader.fragmentShader.replace(
        '#include <map_fragment>',
        `vec3 grassCol = texture2D( map, vMapUv ).rgb;
         vec3 dirtCol = texture2D( uDirtMap, vMapUv * 0.65 ).rgb;
         float slopeMix = smoothstep( 0.16, 0.52, vSlopeT );
         float macro = 0.5 + 0.5 * sin( vWPos.x * 0.031 ) * cos( vWPos.z * 0.027 );
         float mixT = clamp( slopeMix + macro * 0.12, 0.0, 1.0 );
         vec3 terrainCol = mix( grassCol * vec3( 0.86, 0.98, 0.78 ), dirtCol * vec3( 1.04, 0.96, 0.88 ), mixT );
         diffuseColor.rgb *= terrainCol * 1.45;`
      );
    };
    material.customProgramCacheKey = () => 'velocity-ridge-terrain';

    const mesh = new THREE.Mesh(geo, material);
    mesh.name = 'terrain';
    mesh.receiveShadow = true;
    mesh.castShadow = false;
    this.mesh = mesh;
    return mesh;
  }
}
