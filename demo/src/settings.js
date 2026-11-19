/* Settings UI ported from game-builder/assets/settings-menu.html.
   Structure and tokens are the reference's; the schema is trimmed to the
   settings this demo actually implements (every row changes a real value). */

const DEFAULTS = {
  fov: 62,
  resolutionScale: 100,
  shadows: "high",
  bloom: 0.35,
  exposure: 1.15,
  reduceMotion: false,
};

const SCHEMA = [
  {
    id: "graphics",
    label: "Graphics",
    glyph: "◈",
    title: "Graphics",
    desc: "Every option below is wired to the renderer. Changes preview immediately and persist.",
    rows: [
      { section: "Image" },
      { id: "fov", label: "Field of view", kind: "slider", min: 50, max: 95, step: 1, unit: "°",
        hint: "Wider shows more of the harbour, at the cost of distortion at the edges." },
      { id: "resolutionScale", label: "Resolution scale", kind: "slider", min: 50, max: 100, step: 5, unit: "%",
        hint: "The biggest lever on frame time. Applies to the canvas pixel ratio." },
      { section: "Lighting" },
      { id: "shadows", label: "Shadow quality", kind: "segmented",
        options: [["Off", "off"], ["Low", "low"], ["High", "high"]] },
      { id: "exposure", label: "Exposure", kind: "slider", min: 0.4, max: 2, step: 0.05, unit: "EV" },
      { section: "Effects" },
      { id: "bloom", label: "Bloom", kind: "slider", min: 0, max: 2, step: 0.05, unit: "" },
      { section: "Comfort" },
      { id: "reduceMotion", label: "Reduce motion", kind: "toggle",
        hint: "Removes camera bob and the sprint FOV kick." },
    ],
  },
];

const STORAGE_KEY = "harbour.settings.v1";

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

function load() {
  const base = structuredClone(DEFAULTS);
  try {
    const raw = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
    return raw ? { ...base, ...raw } : base;
  } catch {
    return base;
  }
}

export function createSettings({ root, onChange, onClose }) {
  let committed = load();
  let draft = structuredClone(committed);
  let tab = 0;
  let focus = 0;

  const el = (tag, cls, html) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (html != null) n.innerHTML = html;
    return n;
  };

  const applyAll = (values) => {
    for (const [key, value] of Object.entries(values)) onChange(key, value);
  };

  function render() {
    root.innerHTML = "";
    const shell = el("div", "s-shell");
    shell.style.display = "flex";
    shell.style.flex = "1";
    shell.style.minHeight = "0";

    const rail = el("aside", "s-rail");
    rail.append(el("span", "eyebrow", "System"), el("h1", null, "OPTIONS"));

    SCHEMA.forEach((t, i) => {
      const b = el("button", "s-tab", `<span>${t.glyph}</span><span>${t.label}</span>`);
      b.setAttribute("aria-selected", String(i === tab));
      b.onclick = () => { tab = i; focus = 0; render(); };
      rail.append(b);
    });
    shell.append(rail);

    const panel = el("section", "s-panel");
    const head = el("header", "s-head");
    const headText = el("div");
    headText.append(el("h2", null, SCHEMA[tab].title), el("p", null, SCHEMA[tab].desc));
    head.append(headText);
    panel.append(head);

    const rows = el("div", "s-rows");
    let index = 0;
    for (const row of SCHEMA[tab].rows) {
      if (row.section) {
        rows.append(el("div", "s-section", row.section));
        continue;
      }
      const node = el("div", "s-row");
      node.tabIndex = 0;
      node.dataset.index = String(index);
      if (index === focus) node.classList.add("focused");
      const label = el("div");
      label.append(el("span", "name", row.label));
      if (row.hint) label.append(el("span", "hint", row.hint));
      const ctl = el("div", "s-ctl");
      ctl.append(control(row));
      node.append(label, ctl);
      node.onclick = () => { focus = Number(node.dataset.index); render(); };
      rows.append(node);
      index++;
    }
    panel.append(rows);

    const footer = el("footer", "s-footer");
    const note = el("span", "note", "Changes apply on confirm · every row is wired");
    const spacer = el("span", "spacer");
    const back = el("button", "s-btn", "Back");
    back.onclick = () => { root.hidden = true; onClose?.(); };
    const cancel = el("button", "s-btn", "Cancel");
    const apply = el("button", "s-btn primary", "Apply");
    apply.disabled = !dirty();
    cancel.onclick = () => { draft = structuredClone(committed); applyAll(draft); render(); };
    apply.onclick = () => {
      committed = structuredClone(draft);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(committed));
      applyAll(committed);
      render();
    };
    footer.append(back, note, spacer, cancel, apply);
    panel.append(footer);

    shell.append(panel);
    root.append(shell);
  }

  function control(row) {
    const value = draft[row.id];

    if (row.kind === "segmented") {
      const wrap = el("div", "s-seg");
      for (const [label, val] of row.options) {
        const b = el("button", null, label);
        b.setAttribute("aria-pressed", String(value === val));
        if (row.disabled) b.disabled = true;
        b.onclick = (e) => { e.stopPropagation(); set(row, val); };
        wrap.append(b);
      }
      return wrap;
    }

    if (row.kind === "toggle") {
      const b = el("button", "s-toggle");
      b.setAttribute("aria-pressed", String(Boolean(value)));
      b.innerHTML = `<span class="track"><span class="knob"></span></span>
                     <span class="state">${value ? "On" : "Off"}</span>`;
      if (row.disabled) b.disabled = true;
      b.onclick = (e) => { e.stopPropagation(); set(row, !value); };
      return b;
    }

    const wrap = el("div", "s-slider");
    const input = el("input");
    input.type = "range";
    input.min = row.min;
    input.max = row.max;
    input.step = row.step;
    input.value = value;
    input.disabled = Boolean(row.disabled);
    input.setAttribute("aria-label", row.label);
    input.style.setProperty("--p", `${((value - row.min) / (row.max - row.min)) * 100}%`);
    const out = el("span", "s-value", `${format(row, value)}<span class="unit">${row.unit || ""}</span>`);
    input.oninput = () => {
      draft[row.id] = Number(input.value);
      out.innerHTML = `${format(row, Number(input.value))}<span class="unit">${row.unit || ""}</span>`;
      input.style.setProperty("--p", `${((input.value - row.min) / (row.max - row.min)) * 100}%`);
      onChange(row.id, Number(input.value));
      apply.disabled = !dirty();
    };
    input.onclick = (e) => e.stopPropagation();
    wrap.append(input, out);
    return wrap;
  }

  const format = (row, v) => (row.step < 1 ? Number(v).toFixed(2) : String(Math.round(Number(v))));
  const dirty = () => JSON.stringify(committed) !== JSON.stringify(draft);

  function set(row, value) {
    draft[row.id] = value;
    onChange(row.id, value);
    render();
  }

  function onKey(e) {
    if (root.hidden) return;
    const rows = [...root.querySelectorAll(".s-row")];
    if (!rows.length) return;
    const tag = e.target?.tagName;
    if (tag === "INPUT" || tag === "SELECT") return;

    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      focus = clamp(focus + (e.key === "ArrowDown" ? 1 : -1), 0, rows.length - 1);
      rows.forEach((r, i) => r.classList.toggle("focused", i === focus));
      rows[focus].scrollIntoView({ block: "nearest" });
    }
    if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
      e.preventDefault();
      const def = SCHEMA[tab].rows.filter((r) => !r.section)[focus];
      if (!def || def.disabled) return;
      const dir = e.key === "ArrowRight" ? 1 : -1;
      if (def.kind === "segmented") {
        const i = def.options.findIndex(([, v]) => v === draft[def.id]);
        set(def, def.options[clamp(i + dir, 0, def.options.length - 1)][1]);
      } else if (def.kind === "slider") {
        set(def, clamp(Number(draft[def.id]) + def.step * dir, def.min, def.max));
      } else if (def.kind === "toggle") {
        set(def, !draft[def.id]);
      }
    }
  }
  document.addEventListener("keydown", onKey);

  applyAll(committed);
  render();

  return {
    open() { root.hidden = false; render(); },
    close() { root.hidden = true; },
    isOpen: () => !root.hidden,
    get values() { return structuredClone(committed); },
    set(key, value) {
      draft[key] = value;
      committed[key] = value;
      localStorage.setItem(STORAGE_KEY, JSON.stringify(committed));
      onChange(key, value);
      render();
    },
  };
}
