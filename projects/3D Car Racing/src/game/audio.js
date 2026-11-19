// Procedural engine note: no audio files, no licences, and it follows RPM.
export class EngineAudio {
  constructor() {
    this.enabled = true;
    this.ctx = null;
    this.started = false;
  }

  init() {
    if (this.started) return;
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return;
    this.ctx = new Ctx();
    this.master = this.ctx.createGain();
    this.master.gain.value = 0.0;
    this.master.connect(this.ctx.destination);

    this.filter = this.ctx.createBiquadFilter();
    this.filter.type = 'lowpass';
    this.filter.frequency.value = 900;
    this.filter.Q.value = 3.2;

    this.engineGain = this.ctx.createGain();
    this.engineGain.gain.value = 0.16;
    this.filter.connect(this.engineGain).connect(this.master);

    this.oscA = this.ctx.createOscillator();
    this.oscA.type = 'sawtooth';
    this.oscA.frequency.value = 70;
    this.oscA.connect(this.filter);

    this.oscB = this.ctx.createOscillator();
    this.oscB.type = 'square';
    this.oscB.frequency.value = 36;
    this.subGain = this.ctx.createGain();
    this.subGain.gain.value = 0.35;
    this.oscB.connect(this.subGain).connect(this.filter);

    // Wind: filtered white noise whose gain follows speed.
    const len = this.ctx.sampleRate * 2;
    const buffer = this.ctx.createBuffer(1, len, this.ctx.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < len; i++) data[i] = Math.random() * 2 - 1;
    this.noise = this.ctx.createBufferSource();
    this.noise.buffer = buffer;
    this.noise.loop = true;
    this.noiseFilter = this.ctx.createBiquadFilter();
    this.noiseFilter.type = 'bandpass';
    this.noiseFilter.frequency.value = 1100;
    this.noiseFilter.Q.value = 0.7;
    this.windGain = this.ctx.createGain();
    this.windGain.gain.value = 0;
    this.noise.connect(this.noiseFilter).connect(this.windGain).connect(this.master);

    this.oscA.start();
    this.oscB.start();
    this.noise.start();
    this.started = true;
  }

  resume() {
    this.init();
    if (this.ctx && this.ctx.state === 'suspended') this.ctx.resume();
  }

  setEnabled(on) {
    this.enabled = on;
    if (!this.master) return;
    this.master.gain.setTargetAtTime(on ? 0.5 : 0, this.ctx.currentTime, 0.1);
  }

  update(rpm, speedRatio, boosting, skidding) {
    if (!this.started || !this.ctx) return;
    const t = this.ctx.currentTime;
    const base = 52 + rpm * 135 + (boosting ? 26 : 0);
    this.oscA.frequency.setTargetAtTime(base, t, 0.05);
    this.oscB.frequency.setTargetAtTime(base * 0.5, t, 0.05);
    this.filter.frequency.setTargetAtTime(520 + rpm * 2400 + speedRatio * 900, t, 0.06);
    this.engineGain.gain.setTargetAtTime(0.1 + rpm * 0.12, t, 0.08);
    this.windGain.gain.setTargetAtTime(0.02 + speedRatio * speedRatio * 0.16 + (skidding ? 0.05 : 0), t, 0.12);
    this.noiseFilter.frequency.setTargetAtTime(700 + speedRatio * 2200, t, 0.1);
    if (this.master.gain.value === 0 && this.enabled) this.master.gain.setTargetAtTime(0.5, t, 0.2);
  }
}
