// App controller: shell chrome, hash router, delegated actions, overlays.
import { icon } from './icons.js';
import * as player from './player.js';
import * as views from './views.js';
import {
  user, playlists, libraryItems, likedSongs, entityTracks, trackById,
} from './content.js';

const app = document.getElementById('app');

const state = {
  libFilter: 'playlists',
  homeChip: 'All',
  panelMode: 'nowplaying',
  query: '',
};

let lastTrackId = null;
let drag = null;
let searchTimer = null;

// --- chrome ---------------------------------------------------------------
const topbar = () => `
  <header class="topbar">
    <div class="topbar__left">
      <a class="brand" href="#/" data-nav="#/" aria-label="Home">${icon('logo')}</a>
    </div>
    <div class="topbar__center">
      <div class="history">
        <button class="icon-btn" data-action="back" aria-label="Go back">${icon('arrowLeft')}</button>
        <button class="icon-btn" data-action="forward" aria-label="Go forward">${icon('arrowRight')}</button>
      </div>
      <div class="nav-cluster">
        <a class="icon-btn icon-btn--round48 is-active" id="homeBtn" href="#/" data-nav="#/" aria-label="Home">${icon('homeSolid')}</a>
        <form class="searchfield" id="searchForm" role="search">
          ${icon('search')}
          <input id="searchInput" type="search" placeholder="What do you want to play?" aria-label="What do you want to play?" autocomplete="off" spellcheck="false">
          <span class="searchfield__sep" aria-hidden="true"></span>
          <button class="searchfield__browse" type="button" data-nav="#/search" aria-label="Browse">${icon('folder')}</button>
        </form>
      </div>
    </div>
    <div class="topbar__right">
      <button class="btn btn--light" data-action="toast" data-msg="Premium is already active on this demo account">Explore Premium</button>
      <button class="install-link" data-action="toast" data-msg="Installing the desktop app is outside this demo">${icon('install')} Install App</button>
      <button class="icon-btn" data-action="notifications" aria-label="What's new">${icon('bell')}</button>
      <button class="icon-btn" data-action="whats-new" aria-label="Listening activity">${icon('new')}</button>
      <button class="avatar" data-action="account" aria-label="Account menu" aria-haspopup="menu">${user.initial}</button>
    </div>
  </header>`;

const bottomNav = () => `
  <nav class="bottom-nav" aria-label="Main">
    <a class="bottom-nav__item" id="bnHome" href="#/" data-nav="#/">${icon('homeSolid')}<span>Home</span></a>
    <a class="bottom-nav__item" id="bnSearch" href="#/search" data-nav="#/search">${icon('search')}<span>Search</span></a>
    <a class="bottom-nav__item" id="bnLibrary" href="#/library" data-nav="#/library">${icon('librarySolid')}<span>Your Library</span></a>
  </nav>`;

const playerBar = () => `
  <footer class="player" aria-label="Playback controls">
    <div class="player__now">
      <div class="art player__art" id="npArt" style="--h1:268;--h2:210" aria-hidden="true"></div>
      <div class="player__meta" style="min-width:0">
        <div class="player__title truncate" id="npTitle">Nothing playing</div>
        <div class="player__artist truncate" id="npArtist">Pick something to play</div>
      </div>
      <button class="icon-btn" id="playerLike" data-action="like-player" aria-label="Save to Liked Songs">${icon('heart')}</button>
    </div>
    <div class="player__center">
      <div class="transport">
        <button class="icon-btn" id="shuffleBtn" data-action="shuffle" aria-label="Enable shuffle">${icon('shuffle')}</button>
        <button class="icon-btn" data-action="prev" aria-label="Previous">${icon('prev')}</button>
        <button class="transport__play" id="playBtn" data-action="toggle" aria-label="Play">${icon('play')}</button>
        <button class="icon-btn" data-action="next" aria-label="Next">${icon('next')}</button>
        <button class="icon-btn" id="repeatBtn" data-action="repeat" aria-label="Enable repeat">${icon('repeat')}</button>
      </div>
      <div class="progress">
        <span class="progress__time" id="curTime">0:00</span>
        <div class="progress__track" id="seek" role="slider" tabindex="0" aria-label="Seek" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0">
          <div class="progress__rail">
            <div class="progress__fill" id="seekFill"></div>
            <div class="progress__thumb" id="seekThumb"></div>
          </div>
        </div>
        <span class="progress__time" id="durTime">0:00</span>
      </div>
    </div>
    <div class="player__right">
      <button class="icon-btn" data-action="panel" data-mode="lyrics" aria-label="Lyrics">${icon('lyrics')}</button>
      <button class="icon-btn" data-action="panel" data-mode="queue" aria-label="Queue">${icon('queue')}</button>
      <button class="icon-btn" data-action="panel" data-mode="connect" aria-label="Connect to a device">${icon('device')}</button>
      <div class="volume">
        <button class="icon-btn" id="volBtn" data-action="mute" aria-label="Mute">${icon('volume')}</button>
        <div class="volume__track" id="volume" role="slider" tabindex="0" aria-label="Volume" aria-valuemin="0" aria-valuemax="100" aria-valuenow="70">
          <div class="volume__rail">
            <div class="volume__fill" id="volFill"></div>
            <div class="volume__thumb" id="volThumb"></div>
          </div>
        </div>
      </div>
      <button class="icon-btn" data-action="toast" data-msg="Miniplayer is outside this demo" aria-label="Miniplayer">${icon('pip')}</button>
      <button class="icon-btn" data-action="toast" data-msg="Full screen is outside this demo" aria-label="Full screen">${icon('fullscreen')}</button>
    </div>
  </footer>`;

const mountShell = () => {
  app.innerHTML = `
    ${topbar()}
    <div class="shell" id="shell">
      <aside class="sidebar" id="sidebar">${views.renderSidebar(state)}</aside>
      <main class="main" id="main">
        <div class="main__scroll" id="scroll">
          <div class="main__inner" id="mainInner"></div>
        </div>
      </main>
      <aside class="panel" id="panel">${views.renderPanel(state.panelMode)}</aside>
    </div>
    <div class="playerzone">
      ${playerBar()}
      ${bottomNav()}
    </div>`;
  bindSearch();
  updatePlayer();
};

// --- routing -------------------------------------------------------------
const parse = () => {
  const raw = location.hash.replace(/^#\/?/, '');
  const [path, qs] = raw.split('?');
  const parts = path.split('/').filter(Boolean).map(decodeURIComponent);
  return { parts, params: new URLSearchParams(qs || '') };
};

const infoPage = (title, body) => `
  <div class="view"><div class="view__pad">
    <div class="view__head"><h1>${title}</h1></div>
    <div class="about-card" style="margin-top:0">${body}</div>
  </div></div>`;

const routeView = () => {
  const { parts, params } = parse();
  if (!parts.length) return views.renderHome(state);
  const [first, second] = parts;
  if (first === 'search') {
    state.query = params.get('q') || '';
    return state.query ? views.renderSearchResults(state.query) : views.renderBrowse();
  }
  if (first === 'library') return views.renderLibrary(state);
  if (first === 'liked') return views.renderLiked();
  if (first === 'playlist') return views.renderPlaylist(second);
  if (first === 'album') return views.renderAlbum(second);
  if (first === 'artist') return views.renderArtist(second);
  if (first === 'show') return views.renderShow(second);
  if (first === 'legal') {
    return infoPage('Legal', `
      <p style="margin-bottom:16px">This is a study replica of a music web player interface. It is not affiliated with, endorsed by, or connected to any music service.</p>
      <p style="margin-bottom:8px">All artists, albums, playlists, podcasts and artwork in this demo are invented for the build. No audio is streamed: playback is simulated.</p>
      <p>Brand names and logos of any third party must be replaced before this UI is used publicly.</p>`);
  }
  return views.renderNotFound();
};

const renderRoute = ({ resetScroll = true } = {}) => {
  const { parts } = parse();
  const inner = document.getElementById('mainInner');
  if (!inner) return;
  inner.innerHTML = routeView();
  if (resetScroll) {
    const scroll = document.getElementById('scroll');
    if (scroll) scroll.scrollTop = 0;
  }
  // active states
  const root = parts[0] || 'home';
  document.getElementById('homeBtn')?.classList.toggle('is-active', root === 'home');
  ['home', 'search', 'library'].forEach((key) => {
    const el = document.getElementById('bn' + key[0].toUpperCase() + key.slice(1));
    if (el) el.classList.toggle('is-active', root === key);
  });
  syncSearchValue();
  fitTitles();
  if (!player.currentTrack()) document.title = 'Music Web Player';
};

// Long titles shrink to fit the hero instead of wrapping into a second line,
// which is what the reference does at this viewport.
const fitTitles = () => {
  document.querySelectorAll('.hero__title, .artist-hero__title, .top-result__name').forEach((el) => {
    el.style.fontSize = '';
    const container = el.parentElement.clientWidth;
    let size = parseFloat(getComputedStyle(el).fontSize);
    const range = document.createRange();
    const overflows = () => {
      range.selectNodeContents(el);
      const rects = Array.from(range.getClientRects());
      if (!rects.length) return false;
      const lines = new Set(rects.map((r) => Math.round(r.top))).size;
      const widest = Math.max(...rects.map((r) => r.width));
      return lines > 1 || widest > container;
    };
    let guard = 0;
    while (size > 32 && overflows() && guard < 40) {
      size -= 4;
      el.style.fontSize = `${size}px`;
      guard += 1;
    }
  });
};

window.addEventListener('resize', () => {
  clearTimeout(window.__fitTimer);
  window.__fitTimer = setTimeout(fitTitles, 150);
});

// the substitute webfont changes text widths, so fit again once it is loaded
document.fonts?.ready.then(fitTitles);

const syncSearchValue = () => {
  const input = document.getElementById('searchInput');
  if (!input) return;
  const { parts, params } = parse();
  const q = parts[0] === 'search' ? params.get('q') || '' : '';
  if (document.activeElement !== input) input.value = q;
};

const navigate = (href) => {
  if (!href) return;
  if (location.hash === href) {
    renderRoute();
    return;
  }
  location.hash = href;
};

// --- overlay helpers ------------------------------------------------------
let toastEl = null;
let toastTimer = null;
const toast = (msg) => {
  if (!msg) return;
  if (!toastEl) {
    toastEl = document.createElement('div');
    toastEl.className = 'toast';
    toastEl.setAttribute('role', 'status');
    document.body.appendChild(toastEl);
  }
  toastEl.textContent = msg;
  requestAnimationFrame(() => toastEl.classList.add('is-visible'));
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toastEl.classList.remove('is-visible'), 2600);
};

const closeOverlays = () => {
  document.querySelectorAll('.menu, .popover, .modal-backdrop').forEach((el) => el.remove());
};

const openMenu = (anchor, items) => {
  closeOverlays();
  const menu = document.createElement('div');
  menu.className = 'menu';
  menu.setAttribute('role', 'menu');
  menu.innerHTML = items.map((it) => it.sep
    ? '<div class="menu__sep"></div>'
    : `<button class="menu__item" role="menuitem" data-action="${it.action}" ${it.track ? `data-track="${it.track}"` : ''} ${it.msg ? `data-msg="${it.msg}"` : ''}>${it.label}${it.icon ? icon(it.icon) : ''}</button>`).join('');
  document.body.appendChild(menu);
  const r = anchor.getBoundingClientRect();
  const mw = menu.offsetWidth;
  const mh = menu.offsetHeight;
  const left = Math.min(r.left, window.innerWidth - mw - 8);
  const top = r.bottom + 8 + mh > window.innerHeight ? r.top - mh - 8 : r.bottom + 8;
  menu.style.left = `${Math.max(8, left)}px`;
  menu.style.top = `${Math.max(8, top)}px`;
};

const openTrackMenu = (el) => {
  const track = trackById(el.dataset.track);
  if (!track) return;
  openMenu(el, [
    { action: 'menu-play', track: track.id, label: 'Play now' },
    { action: 'menu-queue', track: track.id, label: 'Add to queue' },
    { action: 'menu-like', track: track.id, label: player.isLiked(track.id) ? 'Remove from Liked Songs' : 'Save to Liked Songs' },
    { sep: true },
    { action: 'menu-artist', track: track.id, label: 'Go to artist' },
    { action: 'menu-album', track: track.id, label: 'Go to album' },
    { action: 'toast', msg: 'Link copied to clipboard', label: 'Copy song link' },
  ]);
};

const openPlaylistModal = () => {
  closeOverlays();
  const wrap = document.createElement('div');
  wrap.className = 'modal-backdrop';
  wrap.innerHTML = `
    <form class="modal" id="playlistForm" aria-labelledby="plTitle">
      <div class="modal__head">
        <div>
          <h2 id="plTitle">Create playlist</h2>
        </div>
        <button type="button" class="icon-btn" data-action="close-overlays" aria-label="Close">${icon('close')}</button>
      </div>
      <div class="modal__field">
        <label for="plName">Name</label>
        <input id="plName" name="name" maxlength="60" placeholder="My playlist" required>
      </div>
      <div class="modal__field">
        <label for="plDesc">Description</label>
        <textarea id="plDesc" name="desc" rows="3" maxlength="200" placeholder="Add an optional description"></textarea>
      </div>
      <div class="modal__actions">
        <button type="button" class="btn btn--ghost" data-action="close-overlays">Cancel</button>
        <button type="submit" class="btn btn--light">Create</button>
      </div>
    </form>`;
  document.body.appendChild(wrap);
  wrap.querySelector('#plName').focus();
  wrap.addEventListener('submit', (e) => {
    e.preventDefault();
    const name = wrap.querySelector('#plName').value.trim();
    if (!name) return;
    const desc = wrap.querySelector('#plDesc').value.trim();
    const id = `custom-${Date.now().toString(36)}`;
    const hue = Math.floor(Math.random() * 360);
    playlists.unshift({
      id, title: name, desc: desc || 'A playlist made in this demo.',
      owner: user.name, ownerId: 'alex', h1: hue, h2: (hue + 48) % 360,
      tracks: ['t1', 't10', 't18', 't20', 't27'],
    });
    libraryItems.unshift({ type: 'playlist', id });
    closeOverlays();
    renderSidebar();
    navigate(`#/playlist/${id}`);
    toast(`Playlist “${name}” created`);
  });
};

const renderSidebar = () => {
  const sb = document.getElementById('sidebar');
  if (sb) sb.innerHTML = views.renderSidebar(state);
};

const renderPanel = () => {
  const panel = document.getElementById('panel');
  if (panel) panel.innerHTML = views.renderPanel(state.panelMode);
};

// --- player chrome updates ------------------------------------------------
const updatePlayer = () => {
  const track = player.currentTrack();
  const s = player.state;
  const art = document.getElementById('npArt');
  const title = document.getElementById('npTitle');
  const artist = document.getElementById('npArtist');
  const like = document.getElementById('playerLike');
  const playBtn = document.getElementById('playBtn');
  const curTime = document.getElementById('curTime');
  const durTime = document.getElementById('durTime');
  const seek = document.getElementById('seek');
  const fill = document.getElementById('seekFill');
  const thumb = document.getElementById('seekThumb');

  if (title) title.textContent = track ? track.title : 'Nothing playing';
  if (artist) artist.textContent = track ? track.artist : 'Pick something to play';
  if (art) {
    art.style.setProperty('--h1', track ? track.h1 ?? (track.artistId.length * 37) % 360 : 268);
    art.style.setProperty('--h2', track ? track.h2 ?? (track.artistId.length * 61) % 360 : 210);
  }
  if (like) {
    const liked = track ? player.isLiked(track.id) : false;
    like.innerHTML = icon(liked ? 'heartSolid' : 'heart');
    like.classList.toggle('is-liked', liked);
    like.style.color = liked ? 'var(--accent)' : '';
    like.setAttribute('aria-label', liked ? 'Remove from Liked Songs' : 'Save to Liked Songs');
  }
  if (playBtn) {
    playBtn.innerHTML = icon(s.playing ? 'pause' : 'play');
    playBtn.setAttribute('aria-label', s.playing ? 'Pause' : 'Play');
  }
  const ratio = track && track.dur ? Math.min(1, s.position / track.dur) : 0;
  if (curTime) curTime.textContent = format(s.position);
  if (durTime) durTime.textContent = track ? format(track.dur) : '0:00';
  if (fill) fill.style.width = `${ratio * 100}%`;
  if (thumb) thumb.style.left = `${ratio * 100}%`;
  if (seek) seek.setAttribute('aria-valuenow', String(Math.round(ratio * 100)));

  const shuffle = document.getElementById('shuffleBtn');
  if (shuffle) {
    shuffle.setAttribute('aria-pressed', String(s.shuffle));
    shuffle.style.color = s.shuffle ? 'var(--accent)' : '';
  }
  const repeat = document.getElementById('repeatBtn');
  if (repeat) {
    repeat.innerHTML = icon(s.repeat === 'track' ? 'repeatOne' : 'repeat');
    repeat.setAttribute('aria-pressed', String(s.repeat !== 'off'));
    repeat.style.color = s.repeat !== 'off' ? 'var(--accent)' : '';
    repeat.setAttribute('aria-label', s.repeat === 'off' ? 'Enable repeat' : s.repeat === 'context' ? 'Repeat context' : 'Repeat track');
  }
  const vf = document.getElementById('volFill');
  const vt = document.getElementById('volThumb');
  const vBtn = document.getElementById('volBtn');
  const vol = s.muted ? 0 : s.volume;
  if (vf) vf.style.width = `${vol * 100}%`;
  if (vt) vt.style.left = `${vol * 100}%`;
  if (vBtn) vBtn.innerHTML = icon(vol === 0 ? 'mute' : 'volume');
  const volume = document.getElementById('volume');
  if (volume) volume.setAttribute('aria-valuenow', String(Math.round(vol * 100)));

  // per-track dependent chrome
  if (track && track.id !== lastTrackId) {
    lastTrackId = track.id;
    renderPanel();
    highlightCurrentRow(track.id);
    document.title = `${track.title} • ${track.artist}`;
  }
};

const format = (secs) => {
  const s = Math.max(0, Math.floor(secs || 0));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
};

const highlightCurrentRow = (id) => {
  document.querySelectorAll('.tl__row.is-current, .popular__row.is-current').forEach((el) => el.classList.remove('is-current'));
  document.querySelectorAll(`[data-action="play-track"][data-track="${id}"]`).forEach((el) => el.classList.add('is-current'));
};

// --- playback helpers -----------------------------------------------------
const playEntity = (type, id, { shuffle = false } = {}) => {
  if (type === 'liked') {
    const ids = likedSongs.slice();
    if (!ids.length) return;
    const start = shuffle ? Math.floor(Math.random() * ids.length) : 0;
    player.setQueue(ids, start, { type: 'liked', id: 'liked' });
    player.state.shuffle = shuffle;
    player.play();
    return;
  }
  if (type === 'show') return playEntity('playlist', 'late-night-drive');
  player.playEntity(type, id, { shuffle });
};

const playFromContext = (el) => {
  const id = el.dataset.track;
  const ctxType = el.dataset.contextType;
  const ctxId = el.dataset.contextId;
  if (ctxType && ctxId) {
    const list = ctxType === 'liked' ? likedSongs.map(trackById).filter(Boolean) : entityTracks(ctxType, ctxId);
    if (list.length) {
      player.setQueue(list.map((t) => t.id), Math.max(0, list.findIndex((t) => t.id === id)), { type: ctxType, id: ctxId });
      player.play();
      return;
    }
  }
  player.playTrack(id);
};

// --- actions --------------------------------------------------------------
const handleAction = (el) => {
  const action = el.dataset.action;
  switch (action) {
    case 'toggle': player.toggle(); break;
    case 'next': player.next(); break;
    case 'prev': player.prev(); break;
    case 'shuffle': player.toggleShuffle(); break;
    case 'repeat': player.cycleRepeat(); break;
    case 'mute': player.toggleMute(); break;
    case 'like-player': {
      const t = player.currentTrack();
      if (t) player.toggleLike(t.id);
      break;
    }
    case 'play-entity':
      playEntity(el.dataset.type, el.dataset.id);
      break;
    case 'shuffle-entity':
      playEntity(el.dataset.type, el.dataset.id, { shuffle: true });
      toast('Shuffling');
      break;
    case 'play-track':
      playFromContext(el);
      break;
    case 'like': {
      const id = el.dataset.track;
      const liked = player.toggleLike(id);
      document.querySelectorAll(`[data-action="like"][data-track="${id}"]`).forEach((b) => {
        b.classList.toggle('is-liked', liked);
        b.innerHTML = icon(liked ? 'heartSolid' : 'heart');
      });
      if (player.currentTrack()?.id === id) updatePlayer();
      toast(liked ? 'Added to Liked Songs' : 'Removed from Liked Songs');
      break;
    }
    case 'track-menu':
      openTrackMenu(el);
      break;
    case 'menu-play': player.playTrack(el.dataset.track); closeOverlays(); break;
    case 'menu-queue':
      player.addToQueue(el.dataset.track);
      toast('Added to queue');
      closeOverlays();
      break;
    case 'menu-like': {
      player.toggleLike(el.dataset.track);
      toast('Liked Songs updated');
      updatePlayer();
      closeOverlays();
      break;
    }
    case 'menu-artist': {
      const t = trackById(el.dataset.track);
      closeOverlays();
      if (t) navigate(`#/artist/${t.artistId}`);
      break;
    }
    case 'menu-album': {
      const t = trackById(el.dataset.track);
      closeOverlays();
      if (t) navigate(`#/album/${t.albumId}`);
      break;
    }
    case 'new-playlist': openPlaylistModal(); break;
    case 'close-overlays': closeOverlays(); break;
    case 'lib-filter':
      state.libFilter = el.dataset.filter;
      renderSidebar();
      renderRoute({ resetScroll: false });
      break;
    case 'home-chip':
      state.homeChip = el.dataset.chip;
      renderRoute({ resetScroll: false });
      break;
    case 'panel':
      state.panelMode = el.dataset.mode;
      renderPanel();
      break;
    case 'toggle-save': {
      el.classList.toggle('is-following');
      const on = el.classList.contains('is-following');
      el.textContent = on ? (el.dataset.type === 'album' || el.dataset.type === 'playlist' ? 'Saved' : 'Following') : (el.dataset.type === 'artist' || el.dataset.type === 'show' ? 'Follow' : 'Save');
      toast(on ? 'Saved to your Library' : 'Removed from your Library');
      break;
    }
    case 'account': {
      openMenu(el, [
        { action: 'toast', msg: 'Account settings are outside this demo', label: 'Account' },
        { action: 'toast', msg: 'Profile pages are outside this demo', label: 'Profile' },
        { action: 'toast', msg: 'Premium is active on this demo account', label: 'Upgrade to Premium' },
        { sep: true },
        { action: 'toast', msg: 'This demo has no sign-out flow', label: 'Log out' },
      ]);
      break;
    }
    case 'notifications':
    case 'whats-new':
      toast('No new activity in this demo');
      break;
    case 'back': history.back(); break;
    case 'forward': history.forward(); break;
    case 'toast': toast(el.dataset.msg); break;
    default: break;
  }
};

// --- events ---------------------------------------------------------------
document.addEventListener('click', (e) => {
  const el = e.target.closest('[data-action],[data-nav]');
  const insideOverlay = e.target.closest('.menu, .popover, .modal');
  if (!el) {
    if (!insideOverlay) closeOverlays();
    return;
  }
  if (el.hasAttribute('data-nav') && !el.hasAttribute('data-action')) {
    e.preventDefault();
    closeOverlays();
    navigate(el.dataset.nav);
    return;
  }
  const keepsOverlay = ['track-menu', 'account', 'new-playlist', 'close-overlays'].includes(el.dataset.action);
  handleAction(el);
  if (!keepsOverlay && !e.target.closest('.menu, .modal')) closeOverlays();
});

document.addEventListener('keydown', (e) => {
  const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName || '');
  if (e.key === 'Escape') {
    closeOverlays();
    if (typing) document.activeElement.blur();
    return;
  }
  if (typing) return;
  if (e.code === 'Space') {
    e.preventDefault();
    player.toggle();
  } else if (e.key === 'ArrowRight' && e.altKey === false && document.activeElement?.id !== 'seek' && document.activeElement?.id !== 'volume') {
    player.seekTo(player.state.position + 5);
  } else if (e.key === 'ArrowLeft' && document.activeElement?.id !== 'seek' && document.activeElement?.id !== 'volume') {
    player.seekTo(player.state.position - 5);
  } else if (e.key === 'm') {
    player.toggleMute();
  } else if (e.key === '/') {
    e.preventDefault();
    document.getElementById('searchInput')?.focus();
  }
});

// pointer drag for seek + volume
const applyDrag = (x) => {
  if (!drag) return;
  const ratio = Math.max(0, Math.min(1, (x - drag.rect.left) / drag.rect.width));
  if (drag.kind === 'seek') player.seekRatio(ratio);
  else player.setVolume(ratio);
};

document.addEventListener('pointerdown', (e) => {
  const seek = e.target.closest('#seek');
  const vol = e.target.closest('#volume');
  if (seek) {
    drag = { kind: 'seek', rect: seek.getBoundingClientRect() };
    applyDrag(e.clientX);
  } else if (vol) {
    drag = { kind: 'volume', rect: vol.getBoundingClientRect() };
    applyDrag(e.clientX);
  }
});
document.addEventListener('pointermove', (e) => {
  if (drag) applyDrag(e.clientX);
});
document.addEventListener('pointerup', () => { drag = null; });
document.addEventListener('pointercancel', () => { drag = null; });

const bindSearch = () => {
  const input = document.getElementById('searchInput');
  const form = document.getElementById('searchForm');
  if (!input || !form) return;
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    clearTimeout(searchTimer);
    const v = input.value.trim();
    navigate(v ? `#/search?q=${encodeURIComponent(v)}` : '#/search');
  });
  input.addEventListener('input', () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      const v = input.value.trim();
      if (v) navigate(`#/search?q=${encodeURIComponent(v)}`);
      else if (location.hash.startsWith('#/search')) navigate('#/search');
    }, 240);
  });
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      input.value = '';
      navigate('#/search');
    }
  });
};

window.addEventListener('hashchange', () => {
  renderRoute();
  syncSearchValue();
});
player.subscribe(updatePlayer);

mountShell();
renderRoute();
