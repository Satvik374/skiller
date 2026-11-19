import * as THREE from 'three';

const $ = (id) => document.getElementById(id);

export class HUD {
  constructor({ circuit, race }) {
    this.circuit = circuit;
    this.race = race;
    this.root = $('hud');
    this.el = {
      lap: $('hud-lap'),
      time: $('hud-time'),
      best: $('hud-best'),
      pos: $('hud-pos'),
      mode: $('hud-mode'),
      fps: $('hud-fps'),
      cp: $('hud-cp'),
      cpDist: $('hud-cp-dist'),
      navArrow: $('hud-nav-arrow'),
      gear: $('hud-gear'),
      toast: $('toast'),
    };
    this.speedo = $('speedo');
    this.speedoCtx = this.speedo.getContext('2d');
    this.minimap = $('minimap');
    this.minimapCtx = this.minimap.getContext('2d');
    this.dpr = Math.min(window.devicePixelRatio || 1, 2);
    this.speedo.width = 240 * this.dpr;
    this.speedo.height = 150 * this.dpr;
    this.minimap.width = 380;
    this.minimap.height = 380;
    this.fpsAccum = 0;
    this.fpsFrames = 0;
    this.toastTimer = 0;
    this.#prepareMinimap();
  }

  show() {
    this.root.classList.remove('hidden');
  }

  hide() {
    this.root.classList.add('hidden');
  }

  toast(text, duration = 2.2) {
    this.el.toast.textContent = text;
    this.el.toast.classList.add('show');
    this.toastTimer = duration;
  }

  #prepareMinimap() {
    const pts = this.circuit.samples;
    let minX = Infinity;
    let maxX = -Infinity;
    let minZ = Infinity;
    let maxZ = -Infinity;
    for (const p of pts) {
      minX = Math.min(minX, p.x);
      maxX = Math.max(maxX, p.x);
      minZ = Math.min(minZ, p.z);
      maxZ = Math.max(maxZ, p.z);
    }
    const pad = 28;
    const w = this.minimap.width;
    const h = this.minimap.height;
    const scale = Math.min((w - pad * 2) / (maxX - minX), (h - pad * 2) / (maxZ - minZ));
    this.map = {
      minX, minZ, scale,
      offsetX: (w - (maxX - minX) * scale) / 2,
      offsetY: (h - (maxZ - minZ) * scale) / 2,
      w, h,
    };
    this.mapPath = pts.map((p) => {
      const x = (p.x - minX) * scale + this.map.offsetX;
      const y = (p.z - minZ) * scale + this.map.offsetY;
      return [x, y];
    });
  }

  #project(x, z) {
    const m = this.map;
    return [
      (x - m.minX) * m.scale + m.offsetX,
      (z - m.minZ) * m.scale + m.offsetY,
    ];
  }

  update(dt, { car, rivals, fps }) {
    const race = this.race;

    // ------- text -------
    this.el.lap.textContent = race.mode === 'race' ? `${Math.min(race.lap, 3)} / 3` : 'FREE ROAM';
    this.el.time.textContent = race.formatTime(race.mode === 'race' ? race.lapTime : race.totalTime);
    this.el.best.textContent = race.formatTime(race.bestLap);
    this.el.pos.textContent = race.mode === 'race' ? `${race.position} / ${1 + rivals.length}` : '—';
    this.el.mode.textContent = race.mode === 'race' ? 'RACE' : 'ROAM';
    this.el.cp.textContent = race.mode === 'race' ? race.label : 'OPEN WORLD';
    this.el.gear.textContent = car.gear;

    const dist = race.distanceToTarget(car);
    this.el.cpDist.textContent = race.mode === 'race' ? `${Math.round(dist)} m` : 'EXPLORE';

    const targetAngle = race.headingToTarget(car);
    const relative = targetAngle - car.yaw;
    this.el.navArrow.style.transform = `rotate(${-relative * (180 / Math.PI)}rad)`;

    this.fpsAccum += dt;
    this.fpsFrames++;
    if (this.fpsAccum > 0.5) {
      this.el.fps.textContent = `${Math.round(this.fpsFrames / this.fpsAccum)} fps`;
      this.fpsAccum = 0;
      this.fpsFrames = 0;
    }

    if (this.toastTimer > 0) {
      this.toastTimer -= dt;
      if (this.toastTimer <= 0) this.el.toast.classList.remove('show');
    }

    this.#drawSpeedo(car);
    this.#drawMinimap(car, rivals);
  }

  #drawSpeedo(car) {
    const ctx = this.speedoCtx;
    const dpr = this.dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, 240, 150);

    const cx = 120;
    const cy = 138;
    const r = 104;
    const start = Math.PI * 0.78;
    const sweep = Math.PI * 1.44;
    const maxKmh = 260;
    const ratio = Math.min(1, car.speedKmh / maxKmh);

    // Track
    ctx.lineWidth = 9;
    ctx.lineCap = 'round';
    ctx.strokeStyle = 'rgba(255,255,255,0.08)';
    ctx.beginPath();
    ctx.arc(cx, cy, r, start, start + sweep);
    ctx.stroke();

    // RPM fill
    const rpmRatio = Math.min(1, car.rpm);
    const grad = ctx.createLinearGradient(0, cy, 240, cy);
    grad.addColorStop(0, '#35d0ff');
    grad.addColorStop(0.65, '#ffb347');
    grad.addColorStop(1, '#ff4a1f');
    ctx.strokeStyle = grad;
    ctx.lineWidth = 9;
    ctx.beginPath();
    ctx.arc(cx, cy, r, start, start + sweep * rpmRatio);
    ctx.stroke();

    // Speed arc (thin, inside)
    ctx.strokeStyle = 'rgba(255,255,255,0.55)';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(cx, cy, r - 15, start, start + sweep * ratio);
    ctx.stroke();

    // Ticks
    for (let i = 0; i <= 13; i++) {
      const a = start + (sweep * i) / 13;
      const inner = r - 26;
      const outer = r - (i % 2 === 0 ? 36 : 31);
      ctx.strokeStyle = i % 2 === 0 ? 'rgba(255,255,255,0.5)' : 'rgba(255,255,255,0.2)';
      ctx.lineWidth = i % 2 === 0 ? 2 : 1;
      ctx.beginPath();
      ctx.moveTo(cx + Math.cos(a) * inner, cy + Math.sin(a) * inner);
      ctx.lineTo(cx + Math.cos(a) * outer, cy + Math.sin(a) * outer);
      ctx.stroke();
      if (i % 2 === 0) {
        ctx.fillStyle = 'rgba(180,196,210,0.55)';
        ctx.font = '600 9px "Rajdhani", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(String(Math.round((maxKmh * i) / 13)), cx + Math.cos(a) * (r - 50), cy + Math.sin(a) * (r - 50));
      }
    }

    // Needle
    const angle = start + sweep * ratio;
    ctx.strokeStyle = '#ff5a1f';
    ctx.lineWidth = 2.5;
    ctx.shadowColor = 'rgba(255,90,31,0.8)';
    ctx.shadowBlur = 10;
    ctx.beginPath();
    ctx.moveTo(cx - Math.cos(angle) * 8, cy - Math.sin(angle) * 8);
    ctx.lineTo(cx + Math.cos(angle) * (r - 22), cy + Math.sin(angle) * (r - 22));
    ctx.stroke();
    ctx.shadowBlur = 0;

    // Speed value
    ctx.fillStyle = '#f2f6fa';
    ctx.font = '700 46px "Rajdhani", sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(String(Math.round(car.speedKmh)), cx, cy - 24);
    ctx.fillStyle = 'rgba(150,165,180,0.8)';
    ctx.font = '600 11px "Barlow Condensed", sans-serif';
    ctx.fillText('KM/H', cx, cy - 8);

    // Nitro bar
    const nx = 54;
    const ny = 142;
    const nw = 132;
    ctx.fillStyle = 'rgba(255,255,255,0.1)';
    ctx.fillRect(nx, ny, nw, 3);
    ctx.fillStyle = car.boosting ? '#ff5a1f' : '#35d0ff';
    ctx.fillRect(nx, ny, nw * car.nitro, 3);
  }

  #drawMinimap(car, rivals) {
    const ctx = this.minimapCtx;
    const { w, h } = this.map;
    ctx.clearRect(0, 0, w, h);

    // Road
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';
    for (const [width, color] of [[13, 'rgba(255,255,255,0.06)'], [6, 'rgba(210,225,240,0.42)']]) {
      ctx.beginPath();
      this.mapPath.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
      ctx.closePath();
      ctx.strokeStyle = color;
      ctx.lineWidth = width;
      ctx.stroke();
    }

    // Checkpoints
    if (this.race.mode === 'race') {
      this.race.checkpoints.forEach((cp, i) => {
        const [x, y] = this.#project(cp.x, cp.z);
        const active = i === this.race.nextIndex;
        ctx.beginPath();
        ctx.arc(x, y, active ? 5.5 : 2.6, 0, Math.PI * 2);
        ctx.fillStyle = active ? '#35d0ff' : 'rgba(255,255,255,0.35)';
        ctx.fill();
        if (active) {
          ctx.strokeStyle = 'rgba(53,208,255,0.5)';
          ctx.lineWidth = 2;
          ctx.beginPath();
          ctx.arc(x, y, 11, 0, Math.PI * 2);
          ctx.stroke();
        }
      });
    }

    // Rivals
    for (const rival of rivals) {
      const [x, y] = this.#project(rival.position.x, rival.position.z);
      ctx.beginPath();
      ctx.arc(x, y, 3.4, 0, Math.PI * 2);
      ctx.fillStyle = '#ff4a1f';
      ctx.fill();
    }

    // Player
    const [px, py] = this.#project(car.position.x, car.position.z);
    ctx.save();
    ctx.translate(px, py);
    ctx.rotate(-car.yaw + Math.PI);
    ctx.beginPath();
    ctx.moveTo(0, -7);
    ctx.lineTo(4.6, 5);
    ctx.lineTo(0, 2.6);
    ctx.lineTo(-4.6, 5);
    ctx.closePath();
    ctx.fillStyle = '#ffffff';
    ctx.shadowColor = 'rgba(255,255,255,0.7)';
    ctx.shadowBlur = 8;
    ctx.fill();
    ctx.restore();
  }
}
