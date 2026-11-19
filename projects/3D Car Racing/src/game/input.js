// Maps physical devices to game actions. Gameplay never reads key codes.
const KEY_MAP = {
  KeyW: 'up', ArrowUp: 'up',
  KeyS: 'down', ArrowDown: 'down',
  KeyA: 'left', ArrowLeft: 'left',
  KeyD: 'right', ArrowRight: 'right',
  ShiftLeft: 'boost', ShiftRight: 'boost',
  Space: 'handbrake',
  KeyC: 'camera',
  KeyR: 'reset',
  Escape: 'pause',
  Enter: 'confirm',
};

export class Input {
  constructor() {
    this.keys = new Set();
    this.pressed = new Set();
    this.state = {
      throttle: 0,
      steer: 0,
      handbrake: false,
      boost: false,
      rawSteer: 0,
    };
    this.steer = 0;
    this.sensitivity = 1;
    this.enabled = true;

    addEventListener('keydown', (e) => {
      if (e.repeat) return;
      const action = KEY_MAP[e.code];
      if (!action) return;
      if (['up', 'down', 'left', 'right', 'space'].includes(action) || e.code === 'Space') e.preventDefault();
      this.keys.add(action);
      this.pressed.add(action);
    });
    addEventListener('keyup', (e) => {
      const action = KEY_MAP[e.code];
      if (!action) return;
      this.keys.delete(action);
    });
    addEventListener('blur', () => this.keys.clear());
  }

  consumePressed() {
    const list = new Set(this.pressed);
    this.pressed.clear();
    return list;
  }

  update(dt) {
    let throttle = 0;
    if (this.keys.has('up')) throttle += 1;
    if (this.keys.has('down')) throttle -= 1;

    let steerTarget = 0;
    if (this.keys.has('left')) steerTarget += 1;
    if (this.keys.has('right')) steerTarget -= 1;

    let handbrake = this.keys.has('handbrake');
    let boost = this.keys.has('boost');

    // Gamepad: radial deadzone, so diagonals are not lopsided.
    const pads = navigator.getGamepads ? navigator.getGamepads() : [];
    for (const pad of pads) {
      if (!pad) continue;
      const ax = pad.axes[0] || 0;
      const ay = pad.axes[1] || 0;
      const mag = Math.hypot(ax, ay);
      if (mag > 0.18) {
        const scaled = Math.min(1, (mag - 0.18) / 0.82);
        steerTarget += (-ax / mag) * scaled;
        throttle += (-ay / mag) * scaled;
      }
      if (pad.buttons[7]?.value > 0.1) throttle += pad.buttons[7].value;
      if (pad.buttons[6]?.value > 0.1) throttle -= pad.buttons[6].value;
      if (pad.buttons[0]?.pressed) handbrake = true;
      if (pad.buttons[2]?.pressed) boost = true;
      break;
    }

    this.state.throttle = Math.max(-1, Math.min(1, throttle));
    steerTarget = Math.max(-1, Math.min(1, steerTarget * this.sensitivity));
    this.state.rawSteer = steerTarget;
    this.state.handbrake = handbrake;
    this.state.boost = boost;

    // Steering rack damping: fast enough to feel immediate, slow enough to be smooth.
    const rate = 6.5;
    this.steer += (this.state.rawSteer - this.steer) * Math.min(1, rate * dt);
    this.state.steer = this.steer;
    return this.state;
  }

  reset() {
    this.keys.clear();
    this.pressed.clear();
    this.steer = 0;
  }
}
