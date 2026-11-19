import * as THREE from 'three';

export function makeCanvasTexture(width, height, draw, { repeat = false, aniso = 4 } = {}) {
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  draw(ctx, width, height);
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = aniso;
  if (repeat) {
    tex.wrapS = THREE.RepeatWrapping;
    tex.wrapT = THREE.RepeatWrapping;
  }
  return tex;
}

export function dashTexture() {
  return makeCanvasTexture(
    16,
    256,
    (ctx, w, h) => {
      ctx.clearRect(0, 0, w, h);
      ctx.fillStyle = '#f2f0e6';
      ctx.fillRect(2, 20, w - 4, 108);
    },
    { repeat: true }
  );
}

export function checkerTexture() {
  return makeCanvasTexture(256, 64, (ctx, w, h) => {
    const s = 32;
    for (let y = 0; y < h / s; y++) {
      for (let x = 0; x < w / s; x++) {
        ctx.fillStyle = (x + y) % 2 === 0 ? '#f2f0e6' : '#14161a';
        ctx.fillRect(x * s, y * s, s, s);
      }
    }
  });
}

export function bannerTexture(title = 'VELOCITY RIDGE', sub = 'START · FINISH') {
  return makeCanvasTexture(1024, 256, (ctx, w, h) => {
    const g = ctx.createLinearGradient(0, 0, w, h);
    g.addColorStop(0, '#14181f');
    g.addColorStop(1, '#0a0c10');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, w, h);
    ctx.fillStyle = '#ff5a1f';
    ctx.fillRect(0, 0, w, 10);
    ctx.fillRect(0, h - 10, w, 10);
    ctx.fillStyle = '#f4f6f8';
    ctx.font = '700 92px "Barlow Condensed", sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(title, w / 2, h / 2 - 14);
    ctx.fillStyle = '#ff8a4d';
    ctx.font = '600 34px "Barlow Condensed", sans-serif';
    ctx.letterSpacing = '10px';
    ctx.fillText(sub, w / 2, h / 2 + 62);
  });
}

export function billboardTexture(lines, accent = '#ff5a1f') {
  return makeCanvasTexture(512, 256, (ctx, w, h) => {
    ctx.fillStyle = '#0e1116';
    ctx.fillRect(0, 0, w, h);
    ctx.strokeStyle = 'rgba(255,255,255,0.14)';
    ctx.lineWidth = 6;
    ctx.strokeRect(3, 3, w - 6, h - 6);
    ctx.fillStyle = accent;
    ctx.fillRect(0, 0, 16, h);
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    lines.forEach((line, i) => {
      ctx.fillStyle = i === 0 ? '#f4f6f8' : '#a8b4c2';
      ctx.font = i === 0 ? '700 62px "Barlow Condensed", sans-serif' : '500 40px "Barlow Condensed", sans-serif';
      ctx.fillText(line, 46, 92 + i * 76);
    });
  });
}
