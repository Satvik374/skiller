import * as THREE from 'three';

const damp = (a, b, lambda, dt) => THREE.MathUtils.lerp(a, b, 1 - Math.exp(-lambda * dt));

const MODES = [
  { name: 'chase', distance: 8.4, height: 3.1, lookAhead: 9, fov: 0, shoulder: 0.6 },
  { name: 'far', distance: 13.5, height: 5.4, lookAhead: 12, fov: -4, shoulder: 0.2 },
  { name: 'hood', distance: 0.2, height: 1.28, lookAhead: 14, fov: 4, shoulder: 0.35 },
];

export class ChaseCamera {
  constructor(camera, car, terrain) {
    this.camera = camera;
    this.car = car;
    this.terrain = terrain;
    this.modeIndex = 0;
    this.baseFov = 72;
    this.fovKick = true;
    this.motionReduction = false;
    this.shakeEnabled = true;
    this.trauma = 0;

    this.position = new THREE.Vector3();
    this.lookAt = new THREE.Vector3();
    this.currentFov = this.baseFov;
    this.initialised = false;

    // A cinematic orbit used on the title screen.
    this.cinematic = false;
    this.cinematicAngle = 0;
  }

  get mode() {
    return MODES[this.modeIndex].name;
  }

  cycleMode() {
    this.modeIndex = (this.modeIndex + 1) % MODES.length;
    return this.mode;
  }

  setBaseFov(fov) {
    this.baseFov = fov;
  }

  addTrauma(amount) {
    if (!this.shakeEnabled) return;
    this.trauma = Math.min(1, this.trauma + amount);
  }

  snap() {
    this.initialised = false;
  }

  update(dt, speedRatio = 0) {
    const car = this.car;
    const mode = MODES[this.modeIndex];
    const forward = new THREE.Vector3(Math.sin(car.yaw), 0, Math.cos(car.yaw));
    const right = new THREE.Vector3(forward.z, 0, -forward.x);

    if (this.cinematic) {
      this.cinematicAngle += dt * 0.16;
      const radius = 11;
      const target = car.position.clone();
      this.position.set(
        target.x + Math.cos(this.cinematicAngle) * radius,
        target.y + 3.4,
        target.z + Math.sin(this.cinematicAngle) * radius
      );
      this.lookAt.copy(target).add(new THREE.Vector3(0, 1.1, 0));
      this.camera.position.copy(this.position);
      this.camera.lookAt(this.lookAt);
      this.currentFov = THREE.MathUtils.damp(this.currentFov, this.baseFov - 8, 4, dt);
      this.camera.fov = this.currentFov;
      this.camera.updateProjectionMatrix();
      return;
    }

    const speed = car.speed;
    const back = mode.distance + Math.min(2.4, speed * 0.045);
    const desired = car.position.clone()
      .addScaledVector(forward, -back)
      .addScaledVector(right, mode.shoulder)
      .add(new THREE.Vector3(0, mode.height + Math.min(0.5, speed * 0.012), 0));

    // Never let the boom go under the ground.
    const groundAtCam = this.terrain.heightAt(desired.x, desired.z) + 0.75;
    if (desired.y < groundAtCam) desired.y = groundAtCam;

    if (!this.initialised) {
      this.position.copy(desired);
      this.initialised = true;
    } else {
      const lambda = mode.name === 'hood' ? 30 : 9.5;
      this.position.x = damp(this.position.x, desired.x, lambda, dt);
      this.position.y = damp(this.position.y, desired.y, lambda, dt);
      this.position.z = damp(this.position.z, desired.z, lambda, dt);
    }

    // Look target leads the car into corners at speed.
    const lookTarget = car.position.clone()
      .addScaledVector(forward, mode.lookAhead)
      .add(new THREE.Vector3(0, 1.1, 0));
    this.lookAt.lerp(lookTarget, 1 - Math.exp(-7 * dt));

    // Trauma-squared shake: punchy but never nauseating.
    let shakeX = 0;
    let shakeY = 0;
    let roll = 0;
    if (!this.motionReduction && this.trauma > 0.001) {
      const t = performance.now() / 1000;
      const amp = this.trauma * this.trauma;
      shakeX = Math.sin(t * 47.3) * amp * 0.16;
      shakeY = Math.sin(t * 39.1 + 1.7) * amp * 0.11;
      roll = Math.sin(t * 33.7) * amp * 0.036;
    }
    this.trauma = Math.max(0, this.trauma - dt * 1.9);

    this.camera.position.copy(this.position);
    this.camera.position.x += shakeX;
    this.camera.position.y += shakeY;
    this.camera.up.set(0, 1, 0);
    this.camera.lookAt(this.lookAt);
    this.camera.rotateZ(roll);

    let targetFov = this.baseFov + mode.fov;
    if (this.fovKick && !this.motionReduction) {
      targetFov += speedRatio * 13;
      if (car.boosting) targetFov += 4;
    }
    this.currentFov = damp(this.currentFov, targetFov, 4.5, dt);
    this.camera.fov = this.currentFov;
    this.camera.updateProjectionMatrix();
  }
}
