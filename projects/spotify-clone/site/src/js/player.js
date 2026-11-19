// Playback state. There is no audio stream in this demo: the transport runs a
// simulated clock so progress, seeking and the queue behave like the real thing.
import { trackById, entityTracks, likedSongs } from './content.js';

const listeners = new Set();

const load = (key, fallback) => {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
};
const save = (key, value) => {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* storage can be unavailable; playback still works */
  }
};

export const state = {
  queue: [],
  index: 0,
  playing: false,
  position: 0,
  volume: load('wp.volume', 0.7),
  muted: false,
  shuffle: false,
  repeat: load('wp.repeat', 'off'),
  liked: new Set(load('wp.liked', likedSongs)),
  context: null,
};

const emit = () => listeners.forEach((fn) => fn());

export const subscribe = (fn) => {
  listeners.add(fn);
  return () => listeners.delete(fn);
};

export const currentTrack = () => trackById(state.queue[state.index]) || null;
export const isLiked = (id) => state.liked.has(id);

export const setQueue = (ids, startIndex = 0, context = null) => {
  if (!ids || !ids.length) return;
  state.queue = ids.slice();
  state.index = Math.max(0, Math.min(startIndex, ids.length - 1));
  state.position = 0;
  state.context = context;
  emit();
};

export const playEntity = (type, id, { shuffle = false } = {}) => {
  const list = entityTracks(type, id);
  if (!list.length) return;
  let ids = list.map((t) => t.id);
  let start = 0;
  if (shuffle) {
    start = Math.floor(Math.random() * ids.length);
    ids = [ids[start], ...ids.filter((_, i) => i !== start)];
    state.shuffle = true;
  }
  setQueue(ids, start, { type, id });
  state.playing = true;
  emit();
};

export const playTrack = (id, context = null) => {
  const existing = state.queue.indexOf(id);
  if (existing > -1) {
    state.index = existing;
    state.position = 0;
  } else {
    state.queue = [id];
    state.index = 0;
    state.position = 0;
    state.context = context;
  }
  state.playing = true;
  emit();
};

export const toggle = () => {
  if (!state.queue.length) {
    // nothing loaded yet: start the first library playlist so the transport works
    playEntity('playlist', 'late-night-drive');
    return;
  }
  state.playing = !state.playing;
  emit();
};

export const play = () => {
  if (!state.queue.length) return toggle();
  state.playing = true;
  emit();
};

export const pause = () => {
  state.playing = false;
  emit();
};

export const next = ({ auto = false } = {}) => {
  if (!state.queue.length) return;
  if (auto && state.repeat === 'track') {
    state.position = 0;
    emit();
    return;
  }
  const last = state.index >= state.queue.length - 1;
  if (last) {
    if (state.repeat === 'context' || !auto) {
      state.index = 0;
      state.position = 0;
      emit();
      return;
    }
    state.playing = false;
    state.position = 0;
    emit();
    return;
  }
  state.index += 1;
  state.position = 0;
  emit();
};

export const prev = () => {
  if (!state.queue.length) return;
  if (state.position > 3) {
    state.position = 0;
    emit();
    return;
  }
  state.index = state.index <= 0 ? state.queue.length - 1 : state.index - 1;
  state.position = 0;
  emit();
};

export const seekTo = (seconds) => {
  const track = currentTrack();
  const max = track ? track.dur : 0;
  state.position = Math.max(0, Math.min(seconds, max));
  emit();
};

export const seekRatio = (ratio) => {
  const track = currentTrack();
  if (!track) return;
  seekTo(ratio * track.dur);
};

export const setVolume = (v) => {
  state.volume = Math.max(0, Math.min(1, v));
  state.muted = state.volume === 0;
  save('wp.volume', state.volume);
  emit();
};

export const toggleMute = () => {
  state.muted = !state.muted;
  emit();
};

export const toggleShuffle = () => {
  state.shuffle = !state.shuffle;
  emit();
};

export const cycleRepeat = () => {
  state.repeat = state.repeat === 'off' ? 'context' : state.repeat === 'context' ? 'track' : 'off';
  save('wp.repeat', state.repeat);
  emit();
};

export const toggleLike = (id) => {
  if (state.liked.has(id)) state.liked.delete(id);
  else state.liked.add(id);
  save('wp.liked', [...state.liked]);
  emit();
  return state.liked.has(id);
};

export const addToQueue = (id) => {
  state.queue.push(id);
  emit();
};

// simulated clock
let last = 0;
setInterval(() => {
  if (!state.playing) return;
  const track = currentTrack();
  if (!track) return;
  state.position += 0.25;
  if (state.position >= track.dur) {
    state.position = track.dur;
    next({ auto: true });
    return;
  }
  emit();
}, 250);

// keep time across tabs honestly when the tab was throttled
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') last = 0;
});
