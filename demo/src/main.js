/* Harbour — a small demo built with the game-builder skill.
   Pipeline: CC0/CC-BY authored assets (audited) → HDR IBL → ACES → animated
   fox with a locomotion blend → damped spring-arm camera → wired settings. */

import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { RGBELoader } from "three/addons/loaders/RGBELoader.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";
import { createSettings } from "./settings.js";

/* ---------- renderer ---------- */
const canvas = document.querySelector("#view");
const renderer = new THREE.WebGLRenderer({ canvas, antialias: false, powerPreference: "high-performance" });
renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
renderer.setSize(innerWidth, innerHeight, false);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.15;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
// The post chain renders several passes; without this the counters report
// only the last fullscreen quad (1 call / 1 triangle).
renderer.info.autoReset = false;

const scene = new THREE.Scene();
// Fog colour is sampled from the HDR's horizon so distance dissolves into the
// sky instead of ending on a hard line (references/rendering.md § 2).
scene.fog = new THREE.FogExp2(0xaebbc8, 0.019);

const camera = new THREE.PerspectiveCamera(62, innerWidth / innerHeight, 0.1, 400);
camera.position.set(0, 2.4, 5);

/* ---------- post ---------- */
const composer = new EffectComposer(renderer);
composer.addPass(new RenderPass(scene, camera));
const bloomPass = new UnrealBloomPass(new THREE.Vector2(innerWidth, innerHeight), 0.35, 0.55, 1.05);
composer.addPass(bloomPass);
composer.addPass(new OutputPass());

/* ---------- light ---------- */
const sun = new THREE.DirectionalLight(0xffd7a8, 2.4);
sun.position.set(-9, 7, 5);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
sun.shadow.camera.near = 0.5;
sun.shadow.camera.far = 40;
sun.shadow.camera.left = -10;
sun.shadow.camera.right = 10;
sun.shadow.camera.top = 10;
sun.shadow.camera.bottom = -10;
// A single 220 m ground quad at a grazing sun angle self-shadows across the
// whole frustum unless the bias clears one shadow texel; this is the fix that
// removes the dark wedge (references/rendering.md § 4).
sun.shadow.bias = -0.0012;
sun.shadow.normalBias = 0.06;
scene.add(sun);

/* ---------- authored ground maps (procedural, not an asset) ---------- */
function groundMaps(size = 512) {
  const mk = () => {
    const c = document.createElement("canvas");
    c.width = c.height = size;
    return [c, c.getContext("2d")];
  };
  const [aC, a] = mk();
  const [rC, r] = mk();
  const [bC, b] = mk();

  a.fillStyle = "#191d21"; a.fillRect(0, 0, size, size);
  r.fillStyle = "#d4d4d4"; r.fillRect(0, 0, size, size); // mostly rough
  b.fillStyle = "#808080"; b.fillRect(0, 0, size, size);

  for (let i = 0; i < 9000; i++) {
    const x = Math.random() * size, y = Math.random() * size;
    const v = 18 + Math.random() * 46;
    a.fillStyle = `rgba(${v},${v + 3},${v + 5},${0.25 + Math.random() * 0.5})`;
    a.fillRect(x, y, 1 + Math.random() * 2, 1 + Math.random() * 2);
  }
  // puddles: dark, smooth, slightly raised in the bump channel
  for (let i = 0; i < 16; i++) {
    const x = Math.random() * size, y = Math.random() * size, rad = 18 + Math.random() * 70;
    const g = a.createRadialGradient(x, y, 0, x, y, rad);
    g.addColorStop(0, "rgba(8,10,12,0.9)");
    g.addColorStop(1, "rgba(8,10,12,0)");
    a.fillStyle = g; a.beginPath(); a.arc(x, y, rad, 0, Math.PI * 2); a.fill();

    const rg = r.createRadialGradient(x, y, 0, x, y, rad);
    rg.addColorStop(0, "rgba(38,38,38,1)");
    rg.addColorStop(1, "rgba(38,38,38,0)");
    r.fillStyle = rg; r.beginPath(); r.arc(x, y, rad, 0, Math.PI * 2); r.fill();

    const bg = b.createRadialGradient(x, y, 0, x, y, rad);
    bg.addColorStop(0, "rgba(70,70,70,1)");
    bg.addColorStop(1, "rgba(70,70,70,0)");
    b.fillStyle = bg; b.beginPath(); b.arc(x, y, rad, 0, Math.PI * 2); b.fill();
  }

  const tex = (c, srgb) => {
    const t = new THREE.CanvasTexture(c);
    t.wrapS = t.wrapT = THREE.RepeatWrapping;
    t.repeat.set(26, 26);
    t.anisotropy = renderer.capabilities.getMaxAnisotropy();
    if (srgb) t.colorSpace = THREE.SRGBColorSpace;
    return t;
  };

  // A real tangent-space normal map from the height canvas. A bumpMap would
  // shade per screen-space derivative, which flips across large quads and
  // paints rectangular patches on the ground at grazing angles.
  const normalMap = normalFrom(bC, 2.2);
  normalMap.repeat.set(26, 26);
  normalMap.anisotropy = renderer.capabilities.getMaxAnisotropy();

  return { map: tex(aC, true), roughnessMap: tex(rC, false), normalMap };
}

function normalFrom(heightCanvas, strength = 2) {
  const w = heightCanvas.width, h = heightCanvas.height;
  const src = heightCanvas.getContext("2d").getImageData(0, 0, w, h).data;
  const out = new Uint8Array(w * h * 4);
  const lum = (x, y) => {
    const i = (((y + h) % h) * w + ((x + w) % w)) * 4;
    return (src[i] + src[i + 1] + src[i + 2]) / 765;
  };
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const dx = (lum(x + 1, y) - lum(x - 1, y)) * strength;
      const dy = (lum(x, y + 1) - lum(x, y - 1)) * strength;
      const nx = -dx, ny = -dy, nz = 1;
      const len = Math.hypot(nx, ny, nz);
      const i = (y * w + x) * 4;
      out[i] = ((nx / len) * 0.5 + 0.5) * 255;
      out[i + 1] = ((ny / len) * 0.5 + 0.5) * 255;
      out[i + 2] = ((nz / len) * 0.5 + 0.5) * 255;
      out[i + 3] = 255;
    }
  }
  const t = new THREE.DataTexture(out, w, h, THREE.RGBAFormat);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.needsUpdate = true;
  return t;
}

const maps = groundMaps();
const ground = new THREE.Mesh(
  // Subdivided: a 2-triangle plane at this size gives screen-space derivative
  // bump mapping opposite signs across its diagonal, which shades one triangle
  // darker. Small triangles keep the derivatives consistent.
  new THREE.PlaneGeometry(220, 220, 48, 48),
  new THREE.MeshStandardMaterial({
    ...maps,
    color: 0x9aa4ad,
    metalness: 0.28,
    roughness: 1.0,
    normalScale: new THREE.Vector2(0.5, 0.5),
    envMapIntensity: 1.1,
  }),
);
ground.rotation.x = -Math.PI / 2;
ground.receiveShadow = true;
scene.add(ground);

/* ---------- state ---------- */
const keys = { forward: false, back: false, left: false, right: false, run: false };
const velocity = new THREE.Vector3();
const clock = new THREE.Clock();
let fox = null;
let mixer = null;
let actions = null;
let helmet = null;
let camDist = 4.2;
let yaw = 0.35;
let pitch = 0.22;
const camTarget = new THREE.Vector3(0, 0.55, 0);
const raycaster = new THREE.Raycaster();
let ready = false;

/* ---------- settings ---------- */
const settings = createSettings({
  root: document.querySelector("#settings-root"),
  onChange: (key, value) => applySetting(key, value),
});

function applySetting(key, value) {
  switch (key) {
    case "fov":
      camera.fov = value;
      camera.updateProjectionMatrix();
      break;
    case "resolutionScale":
      // 100% = the capped device ratio; scaling multiplies it.
      renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5) * (value / 100));
      composer.setPixelRatio(Math.min(devicePixelRatio, 1.5) * (value / 100));
      composer.setSize(innerWidth, innerHeight);
      break;
    case "shadows": {
      const on = value !== "off";
      renderer.shadowMap.enabled = on;
      sun.castShadow = on;
      const size = value === "high" ? 2048 : value === "low" ? 1024 : 512;
      if (sun.shadow.mapSize.width !== size) {
        sun.shadow.mapSize.set(size, size);
        if (sun.shadow.map) { sun.shadow.map.dispose(); sun.shadow.map = null; }
      }
      scene.traverse((o) => { if (o.isMesh) o.material.needsUpdate = true; });
      break;
    }
    case "bloom":
      bloomPass.strength = value;
      break;
    case "exposure":
      renderer.toneMappingExposure = value;
      break;
    case "reduceMotion":
      break;
  }
}

/* ---------- load ---------- */
const loadEl = document.querySelector("#loading");
const barEl = document.querySelector("#load-bar");
const statusEl = document.querySelector("#load-status");
const setProgress = (pct, text) => {
  barEl.style.width = `${pct}%`;
  if (text) statusEl.textContent = text;
};

// base-relative so the build works when served from a subpath
const asset = (p) => import.meta.env.BASE_URL + p;

async function boot() {
  setProgress(10, "Loading HDR environment…");
  const pmrem = new THREE.PMREMGenerator(renderer);
  pmrem.compileEquirectangularShader();
  const hdr = await new RGBELoader().loadAsync(asset("assets/dusk_1k.hdr"));
  // RGBELoader resolves with the DataTexture itself (older builds nested it
  // under .texture); accept both so a three bump cannot break the boot.
  const equirect = hdr.texture ?? hdr;
  equirect.mapping = THREE.EquirectangularReflectionMapping;
  const envRT = pmrem.fromEquirectangular(equirect);
  scene.environment = envRT.texture;
  scene.background = equirect;
  scene.backgroundBlurriness = 0.42;
  scene.backgroundIntensity = 0.85;
  pmrem.dispose();

  setProgress(45, "Loading fox…");
  const gltf = await new GLTFLoader().loadAsync(asset("assets/fox.glb"));
  const model = gltf.scene;
  model.scale.setScalar(0.01); // authored in cm — fixed at import, not in game code
  model.traverse((o) => {
    if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; o.frustumCulled = false; }
  });
  scene.add(model);
  fox = model;

  mixer = new THREE.AnimationMixer(model);
  const byName = Object.fromEntries(gltf.animations.map((c) => [c.name, c]));
  actions = {
    idle: mixer.clipAction(byName.Survey),
    walk: mixer.clipAction(byName.Walk),
    run: mixer.clipAction(byName.Run),
  };
  for (const action of Object.values(actions)) {
    action.play();
    action.setEffectiveWeight(0);
  }
  actions.idle.setEffectiveWeight(1);

  setProgress(80, "Placing hero prop…");
  const helmetGltf = await new GLTFLoader().loadAsync(asset("assets/helmet.glb"));
  helmet = helmetGltf.scene;
  helmet.scale.setScalar(0.16); // 2 m authored → 32 cm helmet
  helmet.position.set(2.4, 0.16, -1.6);
  helmet.rotation.y = -0.9;
  helmet.traverse((o) => {
    if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; }
  });
  scene.add(helmet);

  setProgress(100, "Ready");
  loadEl.classList.add("done");
  ready = true;
  setTimeout(() => loadEl.remove(), 700);
}

/* ---------- input ---------- */
const hint = document.querySelector("#lock-hint");
const keymap = {
  KeyW: "forward", ArrowUp: "forward",
  KeyS: "back", ArrowDown: "back",
  KeyA: "left", ArrowLeft: "left",
  KeyD: "right", ArrowRight: "right",
  ShiftLeft: "run", ShiftRight: "run",
};

addEventListener("keydown", (e) => {
  if (e.code === "Escape") {
    if (settings.isOpen()) settings.close();
    else settings.open();
    document.exitPointerLock?.();
    return;
  }
  if (keymap[e.code]) { keys[keymap[e.code]] = true; e.preventDefault(); }
});
addEventListener("keyup", (e) => {
  if (keymap[e.code]) keys[keymap[e.code]] = false;
});

canvas.addEventListener("click", () => {
  if (!settings.isOpen()) canvas.requestPointerLock?.();
});
document.addEventListener("pointerlockchange", () => {
  hint.classList.toggle("hidden", document.pointerLockElement === canvas);
});
document.addEventListener("mousemove", (e) => {
  if (document.pointerLockElement !== canvas) return;
  yaw -= e.movementX * 0.0022;
  // Negative pitch raises the look direction toward the sky, which puts the
  // boom under the floor; keep a small negative range and clamp the position.
  pitch = THREE.MathUtils.clamp(pitch + e.movementY * 0.0022, -0.04, 1.15);
});

document.querySelector("#open-settings").onclick = () => {
  settings.open();
  document.exitPointerLock?.();
};

// The HUD is a game-layer element; it must not bleed through the menu glass.
for (const id of ["#hud", "#lock-hint"]) {
  const node = document.querySelector(id);
  const sync = () => { node.style.visibility = settings.isOpen() ? "hidden" : ""; };
  new MutationObserver(sync).observe(document.querySelector("#settings-root"), {
    attributes: true, attributeFilter: ["hidden"],
  });
  sync();
}

/* ---------- update ---------- */
const forward = new THREE.Vector3();
const right = new THREE.Vector3();
const wish = new THREE.Vector3();
const focus = new THREE.Vector3();

function update(dt) {
  if (!fox) return;

  forward.set(-Math.sin(yaw), 0, -Math.cos(yaw));
  right.set(Math.cos(yaw), 0, -Math.sin(yaw));
  wish.set(0, 0, 0);
  if (keys.forward) wish.add(forward);
  if (keys.back) wish.sub(forward);
  if (keys.right) wish.add(right);
  if (keys.left) wish.sub(right);
  if (wish.lengthSq() > 0) wish.normalize();

  const targetSpeed = wish.lengthSq() ? (keys.run ? 3.6 : 1.35) : 0;
  const accel = wish.lengthSq() ? 14 : 9;
  const desired = wish.multiplyScalar(targetSpeed);
  velocity.x = THREE.MathUtils.damp(velocity.x, desired.x, accel, dt);
  velocity.z = THREE.MathUtils.damp(velocity.z, desired.z, accel, dt);
  fox.position.addScaledVector(velocity, dt);

  const speed = Math.hypot(velocity.x, velocity.z);

  // face the movement direction (the authored mesh looks down -Z)
  if (speed > 0.05) {
    const targetYaw = Math.atan2(velocity.x, velocity.z);
    let delta = ((targetYaw - fox.rotation.y + Math.PI) % (Math.PI * 2)) - Math.PI;
    fox.rotation.y += delta * Math.min(1, 12 * dt);
  }

  // locomotion blend: idle → walk → run, normalised, playback matched to speed
  const wIdle = THREE.MathUtils.clamp(1 - speed / 0.9, 0, 1);
  const wWalk = THREE.MathUtils.clamp(Math.min(speed / 0.9, (3.2 - speed) / 1.4), 0, 1);
  const wRun = THREE.MathUtils.clamp((speed - 1.9) / 1.5, 0, 1);
  const sum = wIdle + wWalk + wRun || 1;
  actions.idle.setEffectiveWeight(wIdle / sum);
  actions.walk.setEffectiveWeight(wWalk / sum);
  actions.run.setEffectiveWeight(wRun / sum);
  actions.walk.timeScale = THREE.MathUtils.clamp(speed / 1.35, 0.5, 1.8);
  actions.run.timeScale = THREE.MathUtils.clamp(speed / 3.6, 0.6, 1.4);
  mixer.update(dt);

  // spring arm with collision
  camTarget.set(fox.position.x, fox.position.y + 0.55, fox.position.z);
  const dir = new THREE.Vector3(
    Math.sin(yaw) * Math.cos(pitch),
    Math.sin(pitch),
    Math.cos(yaw) * Math.cos(pitch),
  );
  raycaster.set(camTarget, dir);
  raycaster.far = 4.4;
  const hits = raycaster.intersectObjects([ground, helmet], false);
  const wanted = hits.length ? Math.max(0.8, hits[0].distance - 0.18) : 4.2;
  camDist = THREE.MathUtils.damp(camDist, wanted, hits.length ? 18 : 6, dt);

  const desiredPos = camTarget.clone().addScaledVector(dir, camDist);
  desiredPos.y = Math.max(desiredPos.y, 0.35); // never let the camera reach the floor
  camera.position.x = THREE.MathUtils.damp(camera.position.x, desiredPos.x, 14, dt);
  camera.position.y = THREE.MathUtils.damp(camera.position.y, desiredPos.y, 14, dt);
  camera.position.z = THREE.MathUtils.damp(camera.position.z, desiredPos.z, 14, dt);
  focus.copy(camTarget).add(new THREE.Vector3(0, 0.12, 0));
  camera.lookAt(focus);

  const motion = settings.values.reduceMotion;
  const targetFov = settings.values.fov + (!motion && keys.run && speed > 3 ? 5 : 0);
  camera.fov = THREE.MathUtils.damp(camera.fov, targetFov, 6, dt);
  camera.updateProjectionMatrix();

  sun.target.position.copy(fox.position);
  sun.target.updateMatrixWorld();
  sun.position.set(fox.position.x - 9, 7, fox.position.z + 5);
}

/* ---------- loop + hud ---------- */
let acc = 0, frames = 0, fps = 0;
function frame() {
  const dt = Math.min(clock.getDelta(), 0.05);
  if (!settings.isOpen()) update(dt);
  renderer.info.reset();
  composer.render();

  acc += dt; frames++;
  if (acc >= 0.5) {
    fps = Math.round(frames / acc);
    acc = 0; frames = 0;
    document.querySelector("#stat-fps").textContent = String(fps);
    document.querySelector("#stat-tris").textContent = renderer.info.render.triangles.toLocaleString();
    document.querySelector("#stat-calls").textContent = String(renderer.info.render.calls);
  }
}

addEventListener("resize", () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight, false);
  composer.setSize(innerWidth, innerHeight);
});

/* ---------- self test (the skill's verification harness, trimmed) ---------- */
function advance(seconds, step = 1 / 60) {
  for (let t = 0; t < seconds; t += step) update(step);
}

function runSelfTest() {
  const out = [];
  const check = (name, ok, detail = "") => out.push(`${ok ? "PASS" : "FAIL"}  ${name}  ${detail}`);
  if (!fox || !helmet) { out.push("FAIL  assets not loaded"); return out; }

  const start = fox.position.clone();
  keys.forward = true;
  advance(1.0);
  const walked = fox.position.distanceTo(start);
  keys.forward = false;
  check("walk speed", walked > 0.9 && walked < 1.9, `${walked.toFixed(2)} m/s`);

  keys.forward = true; keys.run = true;
  const startRun = fox.position.clone();
  advance(1.0);
  const ran = fox.position.distanceTo(startRun);
  keys.forward = false; keys.run = false;
  check("run speed", ran > 2.4 && ran < 4.2, `${ran.toFixed(2)} m/s`);

  const weights = ["idle", "walk", "run"].map((k) => actions[k].getEffectiveWeight());
  const total = weights.reduce((a, b) => a + b, 0);
  check("blend normalised", Math.abs(total - 1) < 0.02, weights.map((w) => w.toFixed(2)).join(" / "));

  advance(1.0); // let the spring arm settle before measuring the boom
  const camDelta = camera.position.distanceTo(camTarget);
  check("camera within boom", camDelta > 0.75 && camDelta < 4.35, `${camDelta.toFixed(2)} m`);
  check("camera settles", Math.abs(camDelta - 4.2) < 0.1, `${camDelta.toFixed(2)} m at rest`);
  check("camera above ground", camera.position.y > 0.2, `y=${camera.position.y.toFixed(2)}`);

  const before = { ...settings.values };
  applySetting("fov", 88);
  check("setting: fov", Math.abs(camera.fov - 88) < 0.5, `${camera.fov.toFixed(1)}°`);
  applySetting("bloom", 1.4);
  check("setting: bloom", Math.abs(bloomPass.strength - 1.4) < 1e-6, bloomPass.strength.toFixed(2));
  applySetting("shadows", "off");
  check("setting: shadows", renderer.shadowMap.enabled === false, "disabled");
  applySetting("resolutionScale", 50);
  check("setting: pixel ratio", renderer.getPixelRatio() < 1.0, renderer.getPixelRatio().toFixed(2));

  applySetting("fov", before.fov);
  applySetting("bloom", before.bloom);
  applySetting("shadows", before.shadows);
  applySetting("resolutionScale", before.resolutionScale);

  check("draw calls", renderer.info.render.calls > 0, String(renderer.info.render.calls));
  check("triangles", renderer.info.render.triangles > 1000, renderer.info.render.triangles.toLocaleString());
  return out;
}

renderer.setAnimationLoop(frame);
boot().catch((err) => {
  statusEl.textContent = `Failed: ${err.message}`;
  console.error(err);
});

window.__demo = {
  get ready() { return ready; },
  get values() { return settings.values; },
  applySetting,
  runSelfTest,
  get stats() {
    return { fps, calls: renderer.info.render.calls, tris: renderer.info.render.triangles, camDist };
  },
};
