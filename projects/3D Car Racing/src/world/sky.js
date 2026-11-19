import * as THREE from 'three';
import { Sky } from 'three/addons/objects/Sky.js';
import { RGBELoader } from 'three/addons/loaders/RGBELoader.js';

const KEYFRAMES = [
  { h: 5.0, elev: -9, sun: 0x2a3f5c, intensity: 0.04, fog: 0x0a0f17, exposure: 0.55, env: 0.25, fogFar: 700 },
  { h: 6.6, elev: 3, sun: 0xff9a55, intensity: 1.5, fog: 0x8c7f7c, exposure: 0.82, env: 0.65, fogFar: 900 },
  { h: 8.0, elev: 17, sun: 0xffc48c, intensity: 3.0, fog: 0xb7b6ae, exposure: 0.95, env: 0.9, fogFar: 1150 },
  { h: 12.0, elev: 68, sun: 0xfff6e8, intensity: 4.3, fog: 0xa9bfd2, exposure: 1.0, env: 1.0, fogFar: 1300 },
  { h: 16.5, elev: 30, sun: 0xffe1b8, intensity: 3.7, fog: 0xc4bda9, exposure: 1.02, env: 0.95, fogFar: 1200 },
  { h: 18.8, elev: 4, sun: 0xff8a4a, intensity: 1.9, fog: 0x9c7a70, exposure: 0.88, env: 0.7, fogFar: 950 },
  { h: 20.2, elev: -6, sun: 0x3b4a6b, intensity: 0.15, fog: 0x1a1d26, exposure: 0.65, env: 0.35, fogFar: 760 },
  { h: 22.0, elev: -14, sun: 0x1d2a3f, intensity: 0.04, fog: 0x080b11, exposure: 0.55, env: 0.22, fogFar: 700 },
];

function lerpColor(a, b, t, out) {
  return out.copy(new THREE.Color(a)).lerp(new THREE.Color(b), t);
}

export class SkySystem {
  constructor(scene, renderer) {
    this.scene = scene;
    this.renderer = renderer;

    this.sky = new Sky();
    this.sky.scale.setScalar(30000);
    this.sky.name = 'sky';
    scene.add(this.sky);

    const u = this.sky.material.uniforms;
    u.turbidity.value = 6;
    u.rayleigh.value = 1.6;
    u.mieCoefficient.value = 0.004;
    u.mieDirectionalG.value = 0.8;
    this.uniforms = u;

    this.sun = new THREE.DirectionalLight(0xffffff, 3);
    this.sun.castShadow = true;
    this.sun.shadow.mapSize.set(2048, 2048);
    this.sun.shadow.camera.near = 1;
    this.sun.shadow.camera.far = 420;
    this.sun.shadow.camera.left = -85;
    this.sun.shadow.camera.right = 85;
    this.sun.shadow.camera.top = 85;
    this.sun.shadow.camera.bottom = -85;
    this.sun.shadow.bias = -0.0004;
    this.sun.shadow.normalBias = 0.045;
    scene.add(this.sun);
    scene.add(this.sun.target);

    this.hemi = new THREE.HemisphereLight(0xbcd4ee, 0x4a4438, 0.55);
    scene.add(this.hemi);

    this.fog = new THREE.Fog(0xa9bfd2, 220, 1200);
    scene.fog = this.fog;

    this.sunDirection = new THREE.Vector3(0.4, 0.7, 0.2).normalize();
    this.hour = 15;
    this.envIntensity = 1;
    this.tmpColor = new THREE.Color();
  }

  async loadEnvironment(url = '/assets/hdri/sky_1k.hdr') {
    const pmrem = new THREE.PMREMGenerator(this.renderer);
    pmrem.compileEquirectangularShader();
    const hdr = await new RGBELoader().loadAsync(url);
    this.envMap = pmrem.fromEquirectangular(hdr.texture).texture;
    this.scene.environment = this.envMap;
    hdr.dispose();
    pmrem.dispose();
    this.scene.environmentIntensity = 1;
  }

  setShadowQuality(pixels) {
    if (this.sun.shadow.mapSize.x === pixels) return;
    this.sun.shadow.mapSize.set(pixels, pixels);
    if (this.sun.shadow.map) {
      this.sun.shadow.map.dispose();
      this.sun.shadow.map = null;
    }
  }

  setTimeOfDay(hour) {
    this.hour = hour;
    let a = KEYFRAMES[0];
    let b = KEYFRAMES[KEYFRAMES.length - 1];
    for (let i = 0; i < KEYFRAMES.length - 1; i++) {
      if (hour >= KEYFRAMES[i].h && hour <= KEYFRAMES[i + 1].h) {
        a = KEYFRAMES[i];
        b = KEYFRAMES[i + 1];
        break;
      }
    }
    if (hour < KEYFRAMES[0].h) {
      a = b = KEYFRAMES[0];
    } else if (hour > KEYFRAMES[KEYFRAMES.length - 1].h) {
      a = b = KEYFRAMES[KEYFRAMES.length - 1];
    }
    const span = b.h - a.h || 1;
    const t = THREE.MathUtils.clamp((hour - a.h) / span, 0, 1);

    const elevation = THREE.MathUtils.lerp(a.elev, b.elev, t);
    const azimuth = 180 * ((hour - 6) / 12) - 30;
    const phi = THREE.MathUtils.degToRad(90 - elevation);
    const theta = THREE.MathUtils.degToRad(azimuth);
    this.sunDirection.setFromSphericalCoords(1, phi, theta);
    this.uniforms.sunPosition.value.copy(this.sunDirection);

    this.sun.color.copy(lerpColor(a.sun, b.sun, t, this.tmpColor));
    this.sun.intensity = THREE.MathUtils.lerp(a.intensity, b.intensity, t);
    this.hemi.intensity = THREE.MathUtils.lerp(
      0.12 + Math.max(0, elevation) * 0.012,
      0.12 + Math.max(0, elevation) * 0.012,
      0
    ) + 0.18;

    this.fog.color.copy(lerpColor(a.fog, b.fog, t, this.tmpColor));
    this.fog.far = THREE.MathUtils.lerp(a.fogFar, b.fogFar, t);
    this.fog.near = this.fog.far * 0.16;

    this.renderer.toneMappingExposure = THREE.MathUtils.lerp(a.exposure, b.exposure, t);
    this.envIntensity = THREE.MathUtils.lerp(a.env, b.env, t);
    this.scene.environmentIntensity = this.envIntensity;

    // Sky shader needs a real sun position when it is below the horizon.
    this.uniforms.turbidity.value = 4 + 8 * (1 - Math.abs(t - 0.5) * 2);
    return { elevation };
  }

  /** Keep the shadow frustum centred on the car and the sky anchored to camera. */
  update(focus, camera) {
    this.sun.target.position.copy(focus);
    this.sun.position.copy(focus).addScaledVector(this.sunDirection, 200);
    this.sun.target.updateMatrixWorld();
    this.sky.position.copy(camera.position);
  }
}
