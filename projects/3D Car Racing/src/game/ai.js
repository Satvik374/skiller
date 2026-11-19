import * as THREE from 'three';
import { mulberry32 } from '../core/noise.js';

/** A rival that drives the circuit on a racing line with a speed profile. */
export class Rival {
  constructor({ scene, model, circuit, config, seed = 1, skill = 1 }) {
    this.circuit = circuit;
    this.config = config;
    this.skill = skill;
    this.rand = mulberry32(seed * 9781 + 13);

    this.root = new THREE.Group();
    this.wheels = model.wheels || [];
    this.root.add(model.root);
    scene.add(this.root);

    this.u = 0;
    this.lap = 0;
    this.speed = 0;
    this.yaw = 0;
    this.lateral = 0;
    this.lateralTarget = 0;

    this.position = new THREE.Vector3();
    this.lookAhead = 0.004;
    this.wheelSpin = 0;
  }

  reset(u = 0.01) {
    this.u = u;
    this.lap = 0;
    this.speed = 0;
    this.lateral = 0;
    this.#place();
  }

  #curvature(u) {
    const a = this.circuit.sampleAt(u);
    const b = this.circuit.sampleAt(u + 0.012);
    return Math.abs(a.tx * b.tz - a.tz * b.tx);
  }

  update(dt, playerProgress) {
    const curveTightness = this.#curvature(this.u + this.lookAhead);
    const cornerFactor = THREE.MathUtils.clamp(1 - curveTightness * 3.4, 0.55, 1);
    let targetSpeed = this.config.maxSpeed * 0.86 * this.skill * cornerFactor;

    // Rubber-banding: stay near the player without teleporting.
    if (playerProgress !== undefined) {
      const gap = playerProgress - (this.lap + this.u);
      targetSpeed *= 1 + THREE.MathUtils.clamp(gap * 0.5, -0.12, 0.18);
    }

    const accel = this.speed < targetSpeed ? 9 * this.skill : 16;
    this.speed += Math.sign(targetSpeed - this.speed) * Math.min(Math.abs(targetSpeed - this.speed), accel * dt);

    const before = this.u;
    this.u += (this.speed * dt) / this.circuit.length;
    if (this.u >= 1) {
      this.u -= 1;
      this.lap += 1;
    }
    if (before > this.u) this.lap += 0;

    this.lateral += (this.lateralTarget - this.lateral) * Math.min(1, 2 * dt);
    if (this.rand() < dt * 0.5) this.lateralTarget = (this.rand() - 0.5) * 3.4;

    this.#place();
    this.wheelSpin -= (this.speed / 0.34) * dt;
    for (const wheel of this.wheels) wheel.rotation.x = this.wheelSpin;
  }

  #place() {
    const s = this.circuit.sampleAt(this.u);
    this.position.set(
      s.x + s.nx * this.lateral,
      s.y + 0.02,
      s.z + s.nz * this.lateral
    );
    this.yaw = Math.atan2(s.tx, s.tz);
    this.root.position.copy(this.position);
    this.root.rotation.y = this.yaw;
  }
}
