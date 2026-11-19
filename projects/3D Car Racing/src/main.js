import * as THREE from 'three';
import { Circuit } from './world/circuit.js';
import { Terrain } from './world/terrain.js';
import { Scenery } from './world/scenery.js';
import { SkySystem } from './world/sky.js';
import { PostFX } from './core/postfx.js';
import { Input } from './game/input.js';
import { Car, CAR_CONFIG, loadCarModel, instantiateCar } from './game/car.js';
import { ChaseCamera } from './game/camera.js';
import { Rival } from './game/ai.js';
import { RaceManager } from './game/race.js';
import { EngineAudio } from './game/audio.js';
import { HUD } from './ui/hud.js';
import { Menus, PRESETS } from './ui/menus.js';

const FIXED_STEP = 1 / 60;
const $ = (id) => document.getElementById(id);

let renderer;
let scene;
let camera;
let postfx;
let sky;
let terrain;
let circuit;
let scenery;
let car;
let rivals = [];
let chase;
let race;
let hud;
let audio;
let input;
let menus;
let carModels = {};
let state = 'loading';
let paused = false;
let elapsed = 0;
let accumulator = 0;
let lastCountdown = '';
let settings = null;

const frameTimes = [];
let benchmarkSamples = 0;
const clock = new THREE.Clock(false);

init().catch((err) => {
  console.error(err);
  showError(err);
});

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------
async function init() {
  setupRenderer();
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(72, innerWidth / innerHeight, 0.35, 6000);
  camera.position.set(0, 6, 20);

  audio = new EngineAudio();
  input = new Input();

  setProgress(0.04, 'mixing materials');
  const textures = await loadTextures();

  setProgress(0.2, 'lighting the valley');
  sky = new SkySystem(scene, renderer);
  try {
    await sky.loadEnvironment();
  } catch (err) {
    console.warn('[sky] HDRI unavailable, falling back to analytic sky lighting', err);
  }
  sky.setTimeOfDay(15);

  setProgress(0.32, 'paving the circuit');
  circuit = new Circuit(textures);
  const circuitGroup = circuit.build();
  circuitGroup.traverse((o) => {
    if (o.isMesh) {
      o.receiveShadow = true;
      o.castShadow = o.castShadow || o.geometry.attributes.position.count < 20000;
    }
  });
  scene.add(circuitGroup);

  setProgress(0.45, 'carving terrain');
  terrain = new Terrain(circuit, textures);
  scene.add(terrain.build());

  setProgress(0.58, 'planting the ridge');
  scenery = new Scenery({
    scene,
    terrain,
    circuit,
    textures,
    onProgress: (label) => setProgress(0.62, label),
  });
  await scenery.build();

  setProgress(0.8, 'loading vehicles');
  const [bmw, skyline] = await Promise.all([
    loadCarModel(CAR_CONFIG.bmw.url),
    loadCarModel(CAR_CONFIG.skyline.url),
  ]);
  carModels = {
    bmw: { model: bmw, config: CAR_CONFIG.bmw },
    skyline: { model: skyline, config: CAR_CONFIG.skyline },
  };

  setProgress(0.9, 'post-processing');
  postfx = new PostFX(renderer, scene, camera);
  race = new RaceManager(circuit);
  chase = new ChaseCamera(camera, null, terrain);
  hud = new HUD({ circuit, race });

  rivals = [
    new Rival({ scene, model: instantiateCar(skyline), circuit, config: CAR_CONFIG.skyline, seed: 3, skill: 0.94 }),
    new Rival({ scene, model: instantiateCar(bmw), circuit, config: CAR_CONFIG.bmw, seed: 7, skill: 0.9 }),
  ];

  spawnCar('bmw');
  chase.cinematic = true;

  race.onGate = (index) => {
    hud.toast(index === 0 ? 'CHECKPOINT 1' : `CHECKPOINT ${index + 1}`);
    audio.blip?.();
  };
  race.onLap = (lap) => hud.toast(lap > 3 ? 'RACE COMPLETE' : `LAP ${Math.min(lap, 3)} OF 3`);
  race.onFinish = (time) => hud.toast(`FINISHED — ${race.formatTime(time)}`, 8);

  menus = new Menus({
    onStart: (mode, carKey) => startGame(mode, carKey),
    onSettingsApply: applySettings,
    onResume: resume,
    onRestart: () => {
      startGame('race', menus.selectedCar);
    },
    onQuit: quitToTitle,
  });
  settings = menus.settings;
  applySettings(settings);
  menus.show('title');

  addEventListener('resize', onResize);
  addEventListener('visibilitychange', () => {
    if (document.hidden && state === 'playing') pause();
  });

  setProgress(1, 'ready');
  $('loading').classList.add('hidden');
  state = 'title';
  clock.start();
  renderer.setAnimationLoop(frame);
}

function setupRenderer() {
  renderer = new THREE.WebGLRenderer({
    canvas: $('scene'),
    antialias: false,
    alpha: false,
    powerPreference: 'high-performance',
    stencil: false,
  });
  renderer.setSize(innerWidth, innerHeight);
  renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 1.5));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
}

async function loadTextures() {
  const loader = new THREE.TextureLoader();
  const maxAniso = renderer.capabilities.getMaxAnisotropy();

  async function tex(url, srgb) {
    const t = await loader.loadAsync(url);
    t.wrapS = THREE.RepeatWrapping;
    t.wrapT = THREE.RepeatWrapping;
    t.anisotropy = Math.min(8, maxAniso);
    if (srgb) t.colorSpace = THREE.SRGBColorSpace;
    return t;
  }

  const [grassMap, grassNormal, grassRough, asphaltMap, asphaltNormal, asphaltRough, asphaltAO, dirtMap, concreteMap, concreteNormal, concreteRough] =
    await Promise.all([
      tex('/assets/tex/grass_diffuse.jpg', true),
      tex('/assets/tex/grass_nor_gl.jpg', false),
      tex('/assets/tex/grass_rough.jpg', false),
      tex('/assets/tex/asphalt_diffuse.jpg', true),
      tex('/assets/tex/asphalt_nor_gl.jpg', false),
      tex('/assets/tex/asphalt_rough.jpg', false),
      tex('/assets/tex/asphalt_ao.jpg', false),
      tex('/assets/tex/dirt_diffuse.jpg', true),
      tex('/assets/tex/concrete_diffuse.jpg', true),
      tex('/assets/tex/concrete_nor_gl.jpg', false),
      tex('/assets/tex/concrete_rough.jpg', false),
    ]);

  return {
    grass: { map: grassMap, normal: grassNormal, rough: grassRough },
    asphalt: { map: asphaltMap, normal: asphaltNormal, rough: asphaltRough, ao: asphaltAO },
    dirt: { map: dirtMap },
    concrete: { map: concreteMap, normal: concreteNormal, rough: concreteRough },
  };
}

// ---------------------------------------------------------------------------
// Game state
// ---------------------------------------------------------------------------
function spawnCar(key) {
  if (car) {
    scene.remove(car.root);
  }
  const entry = carModels[key] || carModels.bmw;
  car = new Car({
    scene,
    model: entry.model,
    terrain,
    circuit,
    colliders: scenery.colliders,
    config: { ...entry.config },
  });
  car.reset();
  chase.car = car;
  chase.snap();
}

function startGame(mode, carKey) {
  const needsRespawn = !car || menus.selectedCar !== carKey;
  if (needsRespawn) spawnCar(carKey);
  car.reset();
  chase.cinematic = false;
  chase.snap();
  chase.addTrauma(0);
  rivals.forEach((r, i) => r.reset(0.0035 + i * 0.004));
  race.start(mode);
  lastCountdown = '';
  input.reset();
  accumulator = 0;
  state = 'playing';
  paused = false;
  menus.hideAll();
  hud.show();
  audio.resume();
  hud.toast(mode === 'race' ? 'RACE START' : 'FREE ROAM', 1.6);
}

function pause() {
  if (state !== 'playing') return;
  paused = true;
  state = 'paused';
  menus.show('pause');
}

function resume() {
  if (state !== 'paused') return;
  paused = false;
  state = 'playing';
  menus.hideAll();
  clock.getDelta();
}

function quitToTitle() {
  state = 'title';
  paused = false;
  hud.hide();
  menus.show('title');
  chase.cinematic = true;
  race.reset();
  car.reset();
}

function applySettings(s) {
  settings = s;
  const base = Math.min(devicePixelRatio || 1, 1.5);
  const ratio = base * s.resScale;
  renderer.setPixelRatio(ratio);
  postfx?.setPixelRatio(ratio);
  postfx?.setSize(innerWidth, innerHeight);
  postfx?.setBloom(s.bloom);
  sky?.setShadowQuality(s.shadow);
  if (chase) {
    chase.setBaseFov(s.fov);
    chase.shakeEnabled = s.shake;
    chase.motionReduction = s.motion;
    chase.fovKick = s.fovKick;
  }
  input.sensitivity = s.sens;
  sky?.setTimeOfDay(s.tod);
  audio?.setEnabled(s.audio);
  renderer.shadowMap.enabled = s.shadow > 0;
  onResize();
}

function onResize() {
  const w = innerWidth;
  const h = innerHeight;
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  renderer.setSize(w, h);
  postfx?.setSize(w, h);
}

// ---------------------------------------------------------------------------
// Loop
// ---------------------------------------------------------------------------
function frame() {
  const dt = Math.min(clock.getDelta(), 0.1);
  elapsed += dt;
  const t0 = performance.now();

  if (state === 'playing' && !paused) {
    const inputState = input.update(dt);
    const pressed = input.consumePressed();

    if (pressed.has('pause')) pause();
    if (pressed.has('camera')) {
      const mode = chase.cycleMode();
      hud.toast(`CAMERA · ${mode.toUpperCase()}`, 1.1);
    }
    if (pressed.has('reset')) {
      car.reset();
      hud.toast('RESET TO START LINE', 1.2);
    }

    const locked = race.countdown > 0;
    const controls = locked
      ? { throttle: 0, steer: 0, handbrake: true, boost: false }
      : inputState;

    accumulator += dt;
    let steps = 0;
    while (accumulator >= FIXED_STEP && steps < 4) {
      car.update(FIXED_STEP, controls);
      accumulator -= FIXED_STEP;
      steps++;
    }

    const playerProgress = race.progressOf(car);
    for (const rival of rivals) rival.update(dt, playerProgress);
    race.update(dt, car, rivals, playerProgress);

    chase.update(dt, Math.min(1, car.speed / 58));
    if (car.impact > 0.05) chase.addTrauma(car.impact * 0.8);
    hud.update(dt, { car, rivals, fps: 1 / Math.max(dt, 1e-3) });
    audio.update(car.rpm, Math.min(1, car.speed / 60), car.boosting, car.skid > 0.5);

    const cd = race.countdownValue();
    if (cd && cd !== lastCountdown) {
      lastCountdown = cd;
      hud.toast(cd, 0.8);
    }
  } else if (state === 'title') {
    chase.update(dt, 0);
    race.update(dt, car, rivals, 0);
    for (const rival of rivals) rival.update(dt);
    hud.update(dt, { car, rivals, fps: 1 / Math.max(dt, 1e-3) });
  } else if (state === 'paused') {
    // Keep the frame warm without advancing the simulation.
  }

  sky.update(car.position, camera);
  postfx.render(dt, elapsed);

  frameTimes.push(performance.now() - t0);
  if (frameTimes.length > 240) frameTimes.shift();

  if (state === 'title') benchmarkSamples++;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function setProgress(value, label) {
  $('load-bar').style.width = `${Math.round(value * 100)}%`;
  if (label) $('load-status').textContent = label;
}

function showError(err) {
  $('loading')?.classList.add('hidden');
  const el = $('error');
  el.classList.remove('hidden');
  el.textContent = `Failed to start Velocity Ridge: ${err?.message || err}`;
}

// Detect a sensible starting preset once the title scene has rendered a while.
setInterval(() => {
  if (state !== 'title' || frameTimes.length < 60) return;
  const sorted = [...frameTimes].sort((a, b) => a - b);
  const p50 = sorted[Math.floor(sorted.length * 0.5)];
  let detected = 'high';
  if (p50 > 30) detected = 'low';
  else if (p50 > 19) detected = 'medium';
  else if (p50 < 8.5) detected = 'ultra';
  menus?.setDetected(detected);
  $('title-perf').textContent = `${p50.toFixed(1)} MS FRAME · AUTO ${detected.toUpperCase()}`;
  if (!localStorage.getItem('velocity-ridge.settings.v1') && detected !== settings?.preset) {
    settings = { ...settings, preset: detected, ...PRESETS[detected], resScale: PRESETS[detected].resScale };
    menus.settings = { ...settings };
    menus.draft = { ...settings };
    menus.syncControls();
    applySettings(settings);
  }
}, 1200);
