import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { ROAD_HALF } from '../world/circuit.js';

export const CAR_CONFIG = {
  bmw: {
    label: 'BMW M3 E30',
    url: '/assets/car_bmw_m3_e30/scene.gltf',
    maxSpeed: 56,
    accel: 12.5,
    brake: 24,
    reverseMax: 13,
    grip: 7.4,
    driftGrip: 1.9,
    steer: 0.62,
    wheelbase: 2.62,
    yawOffset: 0,
    bodyYaw: 0,
  },
  skyline: {
    label: 'Nissan Skyline R32',
    url: '/assets/car_skyline_r32/scene.gltf',
    maxSpeed: 63,
    accel: 14.5,
    brake: 26,
    reverseMax: 14,
    grip: 8.2,
    driftGrip: 2.2,
    steer: 0.66,
    wheelbase: 2.66,
    yawOffset: 0,
    bodyYaw: 0,
  },
};

const cellLoader = new GLTFLoader();

export async function loadCarModel(url) {
  const gltf = await new Promise((resolve, reject) => cellLoader.load(url, resolve, undefined, reject));
  const model = gltf.scene;
  model.updateMatrixWorld(true);

  const wheels = [];
  const tailMaterials = [];
  model.traverse((o) => {
    if (o.isMesh) {
      o.castShadow = true;
      o.receiveShadow = true;
      if (o.material) {
        o.material.envMapIntensity = 1.15;
        if (o.material.clearcoat !== undefined) o.material.clearcoat = Math.max(o.material.clearcoat, 0.6);
        // Transmission re-renders the whole scene for every pane of glass.
        if (o.material.transmission > 0) {
          o.material.transmission = 0;
          o.material.transparent = true;
          o.material.opacity = 0.55;
          o.material.depthWrite = false;
        }
        if (/taillight|tail_light|brake/i.test(o.material.name || '')) {
          o.material.emissive = new THREE.Color(0xff2a12);
          o.material.emissiveIntensity = 0.4;
          tailMaterials.push(o.material);
        }
      }
      if (/wheel|rim|tyre|tire/i.test(o.name) || /wheel|rim/i.test(o.parent?.name || '')) {
        wheels.push(o);
      }
    }
  });

  const box = new THREE.Box3().setFromObject(model);
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());

  const holder = new THREE.Group();
  const inner = new THREE.Group();
  inner.add(model);
  model.position.x -= center.x;
  model.position.z -= center.z;
  model.position.y -= box.min.y;
  holder.add(inner);

  return { root: holder, wheels, tailMaterials, size };
}

/** Clone a loaded car (sharing geometry/textures) and re-collect its parts. */
export function instantiateCar(source) {
  const root = source.root.clone(true);
  const wheels = [];
  const tailMaterials = [];
  root.traverse((o) => {
    if (!o.isMesh) return;
    o.castShadow = true;
    o.receiveShadow = true;
    if (o.material && /taillight|tail_light|brake/i.test(o.material.name || '')) tailMaterials.push(o.material);
    if (/wheel|rim|tyre|tire/i.test(o.name) || /wheel|rim/i.test(o.parent?.name || '')) wheels.push(o);
  });
  return { root, wheels, tailMaterials, size: source.size };
}

const UP = new THREE.Vector3(0, 1, 0);

export class Car {
  constructor({ scene, model, terrain, circuit, colliders, config }) {
    this.scene = scene;
    this.terrain = terrain;
    this.circuit = circuit;
    this.colliders = colliders;
    this.config = config;

    this.root = new THREE.Group();
    this.root.name = 'car';
    this.tiltGroup = new THREE.Group();
    this.tiltGroup.add(model.root);
    this.root.add(this.tiltGroup);
    scene.add(this.root);

    this.model = model;
    this.wheels = model.wheels || [];
    this.tailMaterials = model.tailMaterials || [];

    this.position = new THREE.Vector3();
    this.velocity = new THREE.Vector3();
    this.yaw = 0;
    this.steerAngle = 0;
    this.wheelSpin = 0;
    this.speed = 0;
    this.forwardSpeed = 0;
    this.grounded = true;
    this.nitro = 1;
    this.boosting = false;
    this.groundNormal = new THREE.Vector3(0, 1, 0);
    this.rollAngle = 0;
    this.pitchAngle = 0;
    this.suspension = 0;
    this.impact = 0;
    this.odometer = 0;
    this.skid = 0;
    this.size = model.size || new THREE.Vector3(1.8, 1.4, 4.4);
  }

  reset() {
    const start = this.circuit.startTransform();
    this.position.copy(start.position);
    this.position.y = this.terrain.heightAt(start.position.x, start.position.z) + 0.05;
    this.velocity.set(0, 0, 0);
    this.yaw = start.yaw;
    this.steerAngle = 0;
    this.speed = 0;
    this.nitro = 1;
    this.#syncTransform(1);
  }

  teleport(x, z, yaw = this.yaw) {
    this.position.set(x, this.terrain.heightAt(x, z) + 0.05, z);
    this.velocity.set(0, 0, 0);
    this.yaw = yaw;
  }

  get forward() {
    return new THREE.Vector3(Math.sin(this.yaw), 0, Math.cos(this.yaw));
  }

  update(dt, input) {
    const cfg = this.config;
    const throttle = input.throttle;
    const forward = this.forward;
    const right = new THREE.Vector3(forward.z, 0, -forward.x);

    let vForward = this.velocity.dot(forward);
    let vSide = this.velocity.dot(right);

    const onRoad = this.circuit.nearest(this.position.x, this.position.z, 20).dist < ROAD_HALF + 1.5;
    const surfaceGrip = onRoad ? 1 : 0.62;

    // Nitro
    this.boosting = input.boost && this.nitro > 0.02 && vForward > 2;
    if (this.boosting) this.nitro = Math.max(0, this.nitro - dt * 0.28);
    else this.nitro = Math.min(1, this.nitro + dt * 0.06);
    const boostMul = this.boosting ? 1.42 : 1;

    // Engine / brakes
    const maxSpeed = cfg.maxSpeed * boostMul * (onRoad ? 1 : 0.78);
    if (throttle > 0) {
      if (vForward < 0) {
        this.velocity.addScaledVector(forward, cfg.brake * dt * throttle);
      } else {
        const headroom = 1 - Math.min(1, vForward / maxSpeed);
        const curve = Math.pow(Math.max(0, headroom), 0.55);
        this.velocity.addScaledVector(forward, cfg.accel * boostMul * curve * throttle * dt);
      }
    } else if (throttle < 0) {
      if (vForward > 0.5) {
        this.velocity.addScaledVector(forward, cfg.brake * throttle * dt);
      } else {
        const reverseHeadroom = 1 - Math.min(1, Math.abs(vForward) / cfg.reverseMax);
        this.velocity.addScaledVector(forward, cfg.accel * 0.55 * reverseHeadroom * throttle * dt);
      }
    }

    // Rolling resistance + aero drag
    const drag = 0.42 + (onRoad ? 0 : 1.5);
    vForward = this.velocity.dot(forward);
    this.velocity.addScaledVector(forward, -vForward * drag * dt * 0.1);
    this.velocity.multiplyScalar(1 - Math.min(1, Math.abs(vForward) * 0.0016 * dt * 60 * 0.016));

    // Lateral grip: this is the whole drift model.
    vSide = this.velocity.dot(right);
    const grip = (input.handbrake ? cfg.driftGrip : cfg.grip) * surfaceGrip;
    const sideKill = 1 - Math.exp(-grip * dt);
    this.velocity.addScaledVector(right, -vSide * sideKill);

    // Steering: bicycle model, with the lock reduced as speed rises.
    vForward = this.velocity.dot(forward);
    const speedFactor = 1 - 0.62 * Math.min(1, Math.abs(vForward) / 48);
    const targetSteer = input.steer * cfg.steer * speedFactor;
    this.steerAngle += (targetSteer - this.steerAngle) * Math.min(1, 9 * dt);
    if (Math.abs(vForward) > 0.35) {
      const yawRate = (vForward / cfg.wheelbase) * Math.tan(this.steerAngle);
      this.yaw += yawRate * dt;
      // A touch of the yaw rate bleeds into velocity so drifts carry.
      const newForward = this.forward;
      const along = this.velocity.dot(newForward);
      this.velocity.addScaledVector(newForward, (along - this.velocity.dot(newForward)) * 0.5);
    }
    if (input.handbrake) {
      const slide = this.velocity.dot(right);
      this.yaw += slide * dt * 0.05;
    }

    // Gravity along the slope (so hills actually matter).
    const normal = this.terrain.normalAt(this.position.x, this.position.z, this.groundNormal);
    this.velocity.x += normal.x * 9.81 * dt * 1.15;
    this.velocity.z += normal.z * 9.81 * dt * 1.15;

    // Integrate
    this.position.addScaledVector(this.velocity, dt);
    this.#resolveCollisions();

    // Terrain contact + suspension smoothing
    const groundY = this.terrain.heightAt(this.position.x, this.position.z);
    const targetY = groundY + 0.02;
    this.position.y += (targetY - this.position.y) * Math.min(1, 14 * dt);
    this.suspension = THREE.MathUtils.damp(this.suspension, targetY - this.position.y, 10, dt);

    this.speed = this.velocity.length();
    this.forwardSpeed = this.velocity.dot(this.forward);
    this.odometer += this.speed * dt;
    this.skid = THREE.MathUtils.damp(this.skid, Math.abs(this.velocity.dot(right)) > 4 ? 1 : 0, 6, dt);

    this.#animate(dt, input);
    this.#syncTransform(dt);
  }

  #resolveCollisions() {
    const radius = 1.15;
    for (const c of this.colliders) {
      const dx = this.position.x - c.x;
      const dz = this.position.z - c.z;
      const d2 = dx * dx + dz * dz;
      const minDist = c.radius + radius;
      if (d2 > minDist * minDist || d2 < 1e-4) continue;
      const d = Math.sqrt(d2);
      const nx = dx / d;
      const nz = dz / d;
      const push = minDist - d;
      this.position.x += nx * push;
      this.position.z += nz * push;
      const vn = this.velocity.x * nx + this.velocity.z * nz;
      if (vn < 0) {
        this.velocity.x -= nx * vn * 1.35;
        this.velocity.z -= nz * vn * 1.35;
        this.velocity.multiplyScalar(0.72);
        this.impact = Math.min(1, Math.abs(vn) / 18);
      }
    }

    // Soft world boundary inside the mountain ring.
    const limit = 620;
    if (Math.abs(this.position.x) > limit) {
      this.position.x = Math.sign(this.position.x) * limit;
      this.velocity.x *= -0.3;
    }
    if (Math.abs(this.position.z) > limit) {
      this.position.z = Math.sign(this.position.z) * limit;
      this.velocity.z *= -0.3;
    }
  }

  #animate(dt, input) {
    // Wheel spin + steering on every wheel we could identify.
    this.wheelSpin -= (this.forwardSpeed / 0.34) * dt;
    for (const wheel of this.wheels) {
      wheel.rotation.x = this.wheelSpin;
      if (/front/i.test(wheel.name) || /front/i.test(wheel.parent?.name || '')) {
        wheel.rotation.y = -this.steerAngle * 0.9;
      }
    }
    const braking = input.throttle < -0.1 && this.forwardSpeed > 0.5;
    for (const mat of this.tailMaterials) {
      mat.emissiveIntensity = THREE.MathUtils.damp(mat.emissiveIntensity, braking ? 3.2 : 0.35, 8, dt);
    }
    this.impact = Math.max(0, this.impact - dt * 2.2);
  }

  #syncTransform(dt) {
    this.root.position.copy(this.position);
    this.root.rotation.y = this.yaw + this.config.bodyYaw;

    // Align the body to the slope with a soft, speed-limited lean.
    const n = this.terrain.normalAt(this.position.x, this.position.z, this.groundNormal);
    const targetPitch = Math.asin(THREE.MathUtils.clamp(-n.z, -1, 1)) * 0.85;
    const targetRoll = Math.asin(THREE.MathUtils.clamp(n.x, -1, 1)) * 0.85;
    const k = Math.min(1, 6 * dt);
    this.pitchAngle += (targetPitch - this.pitchAngle) * k;
    this.rollAngle += (targetRoll - this.rollAngle) * k;

    const lateral = this.velocity.x * Math.cos(this.yaw) - this.velocity.z * Math.sin(this.yaw);
    const bodyRoll = THREE.MathUtils.clamp(-lateral * 0.012, -0.14, 0.14);
    const accelPitch = THREE.MathUtils.clamp(this.forwardSpeed * 0.0006, -0.05, 0.05);

    this.tiltGroup.rotation.set(this.pitchAngle + accelPitch, 0, this.rollAngle + bodyRoll);
  }

  get speedKmh() {
    return Math.abs(this.forwardSpeed) * 3.6;
  }

  get gear() {
    const s = this.speedKmh;
    if (s < 1) return 'N';
    if (this.forwardSpeed < -0.5) return 'R';
    const ratios = [0, 34, 62, 92, 124, 160, 400];
    for (let i = 1; i < ratios.length; i++) {
      if (s < ratios[i]) return String(i);
    }
    return '6';
  }

  get rpm() {
    const s = this.speedKmh;
    if (this.forwardSpeed < -0.5) return 0.25 + Math.min(1, s / 40) * 0.4;
    if (s < 1) return 0.12;
    const ratios = [0, 34, 62, 92, 124, 160, 400];
    for (let i = 1; i < ratios.length; i++) {
      if (s < ratios[i]) {
        const lo = ratios[i - 1];
        const t = (s - lo) / (ratios[i] - lo);
        return 0.28 + t * 0.72;
      }
    }
    return 1;
  }
}
