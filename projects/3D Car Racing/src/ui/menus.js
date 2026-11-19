const $ = (id) => document.getElementById(id);

export const PRESETS = {
  low: { resScale: 0.7, shadow: 1024, bloom: false, desc: 'Lean settings for integrated GPUs — no bloom, 1024 shadows.' },
  medium: { resScale: 0.85, shadow: 1024, bloom: true, desc: 'Balanced: bloom on, softer shadows, 85% resolution.' },
  high: { resScale: 1.0, shadow: 2048, bloom: true, desc: 'Cascaded shadows, full bloom, native resolution.' },
  ultra: { resScale: 1.0, shadow: 4096, bloom: true, desc: '4K shadow maps and native resolution. Needs a discrete GPU.' },
};

export const DEFAULT_SETTINGS = {
  preset: 'high',
  resScale: 1,
  fov: 72,
  shadow: 2048,
  bloom: true,
  fovKick: true,
  tod: 15,
  sens: 1,
  shake: true,
  motion: false,
  audio: true,
};

const STORAGE_KEY = 'velocity-ridge.settings.v1';

export class Menus {
  constructor({ onStart, onSettingsApply, onResume, onRestart, onQuit }) {
    this.onStart = onStart;
    this.onSettingsApply = onSettingsApply;
    this.onResume = onResume;
    this.onRestart = onRestart;
    this.onQuit = onQuit;

    this.settings = this.load();
    this.draft = { ...this.settings };
    this.selectedCar = 'bmw';
    this.settingsOrigin = 'title';

    this.screens = {
      title: $('title'),
      pause: $('pause'),
      settings: $('settings'),
      credits: $('credits'),
    };
    this.#bind();
    this.syncControls();
  }

  load() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return { ...DEFAULT_SETTINGS };
      const parsed = JSON.parse(raw);
      return { ...DEFAULT_SETTINGS, ...parsed };
    } catch {
      return { ...DEFAULT_SETTINGS };
    }
  }

  save() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(this.settings));
    } catch {
      /* storage can be blocked — settings still apply for the session */
    }
  }

  #bind() {
    document.querySelectorAll('.car-card').forEach((card) => {
      card.addEventListener('click', () => {
        document.querySelectorAll('.car-card').forEach((c) => c.classList.remove('selected'));
        card.classList.add('selected');
        this.selectedCar = card.dataset.car;
      });
    });

    $('btn-start').addEventListener('click', () => this.onStart('race', this.selectedCar));
    $('btn-roam').addEventListener('click', () => this.onStart('roam', this.selectedCar));

    $('btn-settings').addEventListener('click', () => this.openSettings('title'));
    $('btn-pause-settings').addEventListener('click', () => this.openSettings('pause'));
    $('btn-credits').addEventListener('click', () => this.openCredits());
    $('btn-close-credits').addEventListener('click', () => this.show('title'));

    $('btn-resume').addEventListener('click', () => this.onResume());
    $('btn-restart').addEventListener('click', () => this.onRestart());
    $('btn-quit').addEventListener('click', () => this.onQuit());

    document.querySelectorAll('#preset-seg button').forEach((btn) => {
      btn.addEventListener('click', () => {
        this.draft.preset = btn.dataset.preset;
        Object.assign(this.draft, PRESETS[btn.dataset.preset]);
        this.draft.resScale = PRESETS[btn.dataset.preset].resScale;
        this.draft.shadow = PRESETS[btn.dataset.preset].shadow;
        this.draft.bloom = PRESETS[btn.dataset.preset].bloom;
        this.syncControls();
      });
    });

    const bindSlider = (id, key, labelId, format) => {
      const el = $(id);
      el.addEventListener('input', () => {
        this.draft[key] = Number(el.value);
        if (labelId) $(labelId).textContent = format(this.draft[key]);
      });
    };
    bindSlider('opt-res', 'resScale', 'res-value', (v) => `${Math.round(v * 100)}%`);
    bindSlider('opt-fov', 'fov', 'fov-value', (v) => `${Math.round(v)}°`);
    bindSlider('opt-shadow', 'shadow', 'shadow-value', (v) => String(v));
    bindSlider('opt-tod', 'tod', 'tod-value', (v) => this.formatHour(v));
    bindSlider('opt-sens', 'sens', 'sens-value', (v) => v.toFixed(2));

    const bindToggle = (id, key) => {
      const el = $(id);
      el.addEventListener('change', () => {
        this.draft[key] = el.checked;
      });
    };
    bindToggle('opt-bloom', 'bloom');
    bindToggle('opt-fovkick', 'fovKick');
    bindToggle('opt-shake', 'shake');
    bindToggle('opt-motion', 'motion');
    bindToggle('opt-audio', 'audio');

    $('btn-apply-settings').addEventListener('click', () => {
      this.settings = { ...this.draft };
      this.save();
      this.onSettingsApply(this.settings);
      this.show(this.settingsOrigin);
    });
    $('btn-cancel-settings').addEventListener('click', () => {
      this.draft = { ...this.settings };
      this.syncControls();
      this.show(this.settingsOrigin);
    });
    $('btn-reset-settings').addEventListener('click', () => {
      this.draft = { ...DEFAULT_SETTINGS };
      this.syncControls();
    });
  }

  formatHour(v) {
    const h = Math.floor(v);
    const m = Math.round((v - h) * 60);
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
  }

  syncControls() {
    const s = this.draft;
    $('opt-res').value = s.resScale;
    $('res-value').textContent = `${Math.round(s.resScale * 100)}%`;
    $('opt-fov').value = s.fov;
    $('fov-value').textContent = `${Math.round(s.fov)}°`;
    $('opt-shadow').value = s.shadow;
    $('shadow-value').textContent = String(s.shadow);
    $('opt-tod').value = s.tod;
    $('tod-value').textContent = this.formatHour(s.tod);
    $('opt-sens').value = s.sens;
    $('sens-value').textContent = Number(s.sens).toFixed(2);
    $('opt-bloom').checked = !!s.bloom;
    $('opt-fovkick').checked = !!s.fovKick;
    $('opt-shake').checked = !!s.shake;
    $('opt-motion').checked = !!s.motion;
    $('opt-audio').checked = !!s.audio;

    document.querySelectorAll('#preset-seg button').forEach((b) => {
      b.classList.toggle('active', b.dataset.preset === s.preset);
    });
    $('preset-desc').textContent = PRESETS[s.preset]?.desc || PRESETS.high.desc;
  }

  setDetected(preset) {
    $('detected-preset').textContent = preset.toUpperCase();
  }

  openSettings(origin) {
    this.settingsOrigin = origin;
    this.draft = { ...this.settings };
    this.syncControls();
    this.show('settings');
  }

  show(name) {
    Object.entries(this.screens).forEach(([key, el]) => {
      el.classList.toggle('hidden', key !== name);
    });
  }

  hideAll() {
    Object.values(this.screens).forEach((el) => el.classList.add('hidden'));
  }

  async openCredits() {
    this.show('credits');
    const list = $('credits-list');
    if (list.dataset.loaded) return;
    try {
      const res = await fetch('/assets/registry.json');
      const registry = await res.json();
      const rows = Object.entries(registry).map(([slug, a]) => {
        const author = a.author ? `<a href="${a.author_url || '#'}" target="_blank" rel="noopener">${a.author}</a>` : 'Unknown';
        return `<div class="credit">
            <b>${a.title || slug}</b>
            ${author} · <span class="lic">${(a.license || 'unknown').toUpperCase()}</span>
            ${a.url ? `<br /><a href="${a.url}" target="_blank" rel="noopener">${a.url}</a>` : ''}
          </div>`;
      });
      rows.push(`<div class="credit">
          <b>Environment surfaces</b>
          Poly Haven — Poly Haven HDRI &amp; PBR textures · <span class="lic">CC0</span>
        </div>`);
      list.innerHTML = rows.join('');
      list.dataset.loaded = '1';
    } catch (err) {
      list.innerHTML = `<div class="credits-empty">Registry unavailable: ${String(err)}</div>`;
    }
  }
}
