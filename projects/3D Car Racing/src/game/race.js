import * as THREE from 'three';

export const TOTAL_LAPS = 3;

export class RaceManager {
  constructor(circuit) {
    this.circuit = circuit;
    this.mode = 'race';
    this.gates = circuit.gates.list;
    this.checkpoints = this.gates.map((g) => g.position.clone());
    this.checkpoints.push(circuit.gates.list[0].position.clone()); // start/finish
    this.reset();
  }

  reset() {
    this.lap = 1;
    this.nextIndex = 0;
    this.lapTime = 0;
    this.totalTime = 0;
    this.bestLap = null;
    this.lastLap = null;
    this.finished = false;
    this.countdown = 3.6;
    this.goShown = false;
    this.racing = false;
    this.started = false;
    this.position = 1;
    this.lapTimes = [];
    this.gates.forEach((g) => (g.group.visible = false));
    this.#showGate(0);
  }

  get target() {
    return this.checkpoints[this.nextIndex];
  }

  get label() {
    if (this.nextIndex >= this.gates.length) return 'FINISH LINE';
    return `CHECKPOINT ${this.nextIndex + 1} / ${this.gates.length}`;
  }

  start(mode = 'race') {
    this.reset();
    this.mode = mode;
    if (mode === 'roam') {
      this.countdown = 0;
      this.racing = true;
      this.started = true;
      this.checkpoints.forEach(() => {});
    }
  }

  #showGate(index) {
    this.gates.forEach((g, i) => (g.group.visible = i === index));
  }

  update(dt, car, rivals, playerProgress) {
    if (this.countdown > 0) {
      this.countdown -= dt;
      if (this.countdown <= 0) {
        this.racing = true;
        this.started = true;
      }
    }

    if (this.countdownValue() === 'GO' && !this.goShown) {
      this.goShown = true;
      this.onCountdown?.('GO');
    }

    if (!this.racing || this.finished) {
      this.#standings(rivals, playerProgress);
      return;
    }

    if (this.mode === 'race') {
      this.lapTime += dt;
      this.totalTime += dt;
    }

    const target = this.checkpoints[this.nextIndex];
    if (target && car.position.distanceTo(target) < 30) {
      this.#advanceLap();
    }

    this.#standings(rivals, playerProgress);
  }

  #advanceLap() {
    this.nextIndex++;
    this.onGate?.(this.nextIndex - 1);
    if (this.nextIndex >= this.checkpoints.length) {
      this.nextIndex = 0;
      this.lastLap = this.lapTime;
      this.lapTimes.push(this.lapTime);
      if (this.bestLap === null || this.lapTime < this.bestLap) this.bestLap = this.lapTime;
      this.lapTime = 0;
      this.lap++;
      if (this.mode === 'race' && this.lap > TOTAL_LAPS) {
        this.finished = true;
        this.racing = false;
        this.onFinish?.(this.totalTime);
        this.#showGate(-1);
        return;
      }
      this.onLap?.(this.lap, this.lastLap);
    }
    this.#showGate(this.nextIndex);
  }

  #standings(rivals, playerProgress) {
    if (playerProgress === undefined) return;
    let pos = 1;
    for (const rival of rivals) {
      if (rival.lap + rival.u > playerProgress) pos++;
    }
    this.position = pos;
  }

  countdownValue() {
    if (this.countdown <= 0) return '';
    if (this.countdown > 2.6) return '3';
    if (this.countdown > 1.6) return '2';
    if (this.countdown > 0.6) return '1';
    return 'GO';
  }

  /** Normalised progress around the circuit for standings. */
  progressOf(car) {
    const near = this.circuit.nearest(car.position.x, car.position.z, 60);
    const u = near.index / this.circuit.count;
    const laps = this.lap - 1;
    return laps + u;
  }

  formatTime(seconds) {
    if (seconds === null || seconds === undefined) return '--:--.--';
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    const cs = Math.floor((seconds % 1) * 100);
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}.${String(cs).padStart(2, '0')}`;
  }

  headingToTarget(car) {
    const target = this.target;
    if (!target) return 0;
    const dx = target.x - car.position.x;
    const dz = target.z - car.position.z;
    const angle = Math.atan2(dx, dz);
    return angle;
  }

  distanceToTarget(car) {
    const target = this.target;
    if (!target) return 0;
    return car.position.distanceTo(target);
  }
}
