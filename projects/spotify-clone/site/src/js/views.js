// Page + partial renderers. Pure functions returning HTML strings.
import { icon } from './icons.js';
import * as player from './player.js';
import {
  user, artists, albums, playlists, shows, tracks, categories, shortcuts,
  homeShelves, libraryItems, likedSongs, lyrics, devices,
  albumById, artistById, playlistById, showById, trackById,
  albumTracks, artistTracks, artistAlbums,
  entityTracks, formatTime, formatLong, formatCount,
} from './content.js';

const DATES = ['Nov 12, 2026', 'Nov 9, 2026', 'Nov 4, 2026', 'Oct 30, 2026', 'Oct 24, 2026', 'Oct 18, 2026', 'Oct 11, 2026'];
const dateFor = (i) => DATES[i % DATES.length];

export const art = (item, { round = false, liked = false, glyph = null, className = '' } = {}) => {
  const h1 = item?.h1 ?? 220;
  const h2 = item?.h2 ?? 256;
  const heart = liked ? `<span class="art__heart">${icon('heartSolid')}</span>` : '';
  const mark = glyph ? `<span class="art__glyph">${icon(glyph)}</span>` : '';
  return `<div class="art ${round ? 'art--round' : ''} ${liked ? 'art--liked' : ''} ${className}" style="--h1:${h1};--h2:${h2}" aria-hidden="true">${heart}${mark}</div>`;
};

export const routeFor = (type, id) => (type === 'liked' ? '#/liked' : `#/${type}/${id}`);

export const metaFor = (type, id) => {
  if (type === 'playlist') {
    const p = playlistById(id);
    return p ? { title: p.title, sub: p.desc, item: p, glyph: null, round: false } : null;
  }
  if (type === 'album') {
    const a = albumById(id);
    return a ? { title: a.title, sub: `${a.artist} • ${a.year}`, item: a, glyph: null, round: false } : null;
  }
  if (type === 'artist') {
    const a = artistById(id);
    return a ? { title: a.name, sub: 'Artist', item: a, glyph: null, round: true } : null;
  }
  if (type === 'show') {
    const s = showById(id);
    return s ? { title: s.title, sub: s.publisher, item: s, glyph: 'mic', round: false } : null;
  }
  if (type === 'liked') {
    return { title: 'Liked Songs', sub: `Playlist • ${user.name}`, item: { h1: 258, h2: 300 }, glyph: null, round: false, liked: true };
  }
  return null;
};

// --- cards ----------------------------------------------------------------
export const card = (type, id) => {
  const meta = metaFor(type, id);
  if (!meta) return '';
  const tracksHref = routeFor(type, id);
  const playable = type !== 'artist';
  return `
  <article class="card" data-nav="${tracksHref}" tabindex="0" role="link" aria-label="${meta.title}">
    <div class="card__artwrap">
      ${art(meta.item, { round: meta.round, liked: meta.liked, glyph: meta.glyph, className: 'card__art' })}
      ${playable ? `<button class="play-fab card__play" data-action="play-entity" data-type="${type}" data-id="${id}" aria-label="Play ${meta.title}">${icon('play')}</button>` : ''}
    </div>
    <div class="card__title truncate">${meta.title}</div>
    <div class="card__sub clamp-2">${meta.sub || ''}</div>
  </article>`;
};

const shelf = (title, items, href = null) => `
  <section class="shelf" aria-label="${title}">
    <div class="shelf__head">
      <h2>${href ? `<a href="${href}">${title}</a>` : title}</h2>
      ${href ? `<a class="shelf__all" href="${href}">Show all</a>` : ''}
    </div>
    <div class="shelf__row">${items.map((it) => card(it.type, it.id)).join('')}</div>
  </section>`;

const shortcut = (type, id) => {
  const meta = metaFor(type, id);
  if (!meta) return '';
  return `
  <button class="shortcut" data-nav="${routeFor(type, id)}">
    ${art(meta.item, { liked: meta.liked, glyph: meta.glyph, className: 'shortcut__art' })}
    <span class="shortcut__label">${meta.title}</span>
    <span class="play-fab shortcut__play" data-action="play-entity" data-type="${type}" data-id="${id}" aria-hidden="true">${icon('play')}</span>
  </button>`;
};

// --- track list -----------------------------------------------------------
export const trackRow = (track, index, opts = {}) => {
  if (!track) return '';
  const cur = player.currentTrack();
  const isCurrent = cur && cur.id === track.id;
  const liked = player.isLiked(track.id);
  const ctx = opts.context ? `data-context-type="${opts.context.type}" data-context-id="${opts.context.id}"` : '';
  return `
  <div class="tl__row ${isCurrent ? 'is-current' : ''}" role="row" data-action="play-track" data-track="${track.id}" ${ctx} tabindex="0">
    <div class="tl__num" aria-hidden="true"><span>${index + 1}</span>${icon('play')}</div>
    <div class="tl__main">
      ${opts.art ? art(track, { className: 'tl__art' }) : ''}
      <div class="tl__texts">
        <div class="tl__title truncate">${track.title}</div>
        <a class="tl__artist truncate" href="#/artist/${track.artistId}" data-nav="#/artist/${track.artistId}">${track.artist}</a>
      </div>
    </div>
    ${opts.showAlbum ? `<a class="tl__album" href="#/album/${track.albumId}" data-nav="#/album/${track.albumId}">${track.album}</a>` : ''}
    ${opts.showDate ? `<div class="tl__date">${dateFor(index)}</div>` : ''}
    ${opts.showPlays ? `<div class="tl__date">${formatCount(track.plays)}</div>` : ''}
    <div class="tl__end">
      <button class="tl__like ${liked ? 'is-liked' : ''}" data-action="like" data-track="${track.id}" aria-label="${liked ? 'Remove from' : 'Save to'} Liked Songs">${icon(liked ? 'heartSolid' : 'heart')}</button>
      <span class="tl__dur">${formatTime(track.dur)}</span>
      <button class="tl__more" data-action="track-menu" data-track="${track.id}" aria-label="More options for ${track.title}">${icon('more')}</button>
    </div>
  </div>`;
};

const trackList = (list, opts = {}) => {
  if (!list.length) return `<p class="tl__empty">Nothing here yet.</p>`;
  const head = opts.head || ['#', 'Title', 'Album', 'Date added', ''];
  return `
  <div class="tl ${opts.variant || ''}" role="table">
    <div class="tl__head" role="row">
      <span>#</span><span>Title</span>
      ${opts.showAlbum ? '<span class="col-album">Album</span>' : ''}
      ${opts.showDate ? '<span class="col-date">Date added</span>' : ''}
      ${opts.showPlays ? '<span class="col-date">Plays</span>' : ''}
      <span>${icon('clock')}</span>
    </div>
    <div class="tl__body">${list.map((t, i) => trackRow(t, i, opts)).join('')}</div>
  </div>`;
};

// --- hero + action bar ----------------------------------------------------
const heroType = (label) => `<div class="hero__type">${label}</div>`;

const actionBar = ({ type, id, saveLabel = 'Follow', saved = false, right = '', extras = true }) => `
  <div class="actionbar">
    <button class="actionbar__play" data-action="play-entity" data-type="${type}" data-id="${id}" aria-label="Play">${icon('play')}</button>
    <button class="follow-pill ${saved ? 'is-following' : ''}" data-action="toggle-save" data-type="${type}" data-id="${id}">${saved ? 'Following' : saveLabel}</button>
    <button class="actionbar__shuffle" data-action="shuffle-entity" data-type="${type}" data-id="${id}" aria-label="Enable shuffle">${icon('shuffle')}</button>
    ${extras ? `
    <button class="icon-btn actionbar__extra" data-action="toast" data-msg="Added to your Library" aria-label="Add to library">${icon('plusCircle')}</button>
    <button class="icon-btn actionbar__extra" data-action="toast" data-msg="Download queued" aria-label="Download">${icon('download')}</button>` : ''}
    <button class="icon-btn" data-action="toast" data-msg="More options" aria-label="More options">${icon('more')}</button>
    <div class="actionbar__right">${right}</div>
  </div>`;

// --- home -----------------------------------------------------------------
export const renderHome = (viewState = {}) => {
  const chips = ['All', 'Music', 'Podcasts', 'Audiobooks'];
  const active = viewState.homeChip || 'All';
  return `
  <div class="view home">
    <div class="view__pad">
      <div class="home__sticky">
        <div class="chips" role="tablist" aria-label="Filter home">
          ${chips.map((c) => `<button class="chip ${c === active ? 'is-active' : ''}" role="tab" aria-selected="${c === active}" data-action="home-chip" data-chip="${c}">${c}</button>`).join('')}
        </div>
      </div>
      <div class="home__shortcuts">
        ${shortcuts.map((s) => shortcut(s.type, s.id)).join('')}
      </div>
      ${homeShelves
        .filter((sh) => active === 'All' || (active === 'Podcasts' ? sh.title.includes('Podcasts') : !sh.title.includes('Podcasts')))
        .map((sh) => shelf(sh.title, sh.items, sh.title === 'Made for Alex' ? '#/library' : null))
        .join('')}
    </div>
  </div>`;
};

// --- browse / search ------------------------------------------------------
export const renderBrowse = () => `
  <div class="view">
    <div class="view__pad">
      <div class="view__head"><h1>Browse all</h1></div>
      <div class="browse-grid">
        ${categories.map((c) => `
          <button class="cat-tile" style="--h1:${c.h1};--h2:${c.h2}" data-nav="#/search?q=${encodeURIComponent(c.title)}">
            <span class="cat-tile__title">${c.title}</span>
            ${art(c, { className: 'cat-tile__art' })}
          </button>`).join('')}
      </div>
    </div>
  </div>`;

const topResult = (result) => {
  if (!result) return '';
  const { type, id } = result;
  const meta = metaFor(type, id);
  if (!meta) return '';
  return `
  <button class="top-result" data-nav="${routeFor(type, id)}">
    ${art(meta.item, { round: meta.round, glyph: meta.glyph, className: 'top-result__art' })}
    <div class="top-result__name">${meta.title}</div>
    <div class="top-result__type"><span class="badge">${type === 'show' ? 'Podcast' : type.charAt(0).toUpperCase() + type.slice(1)}</span>${meta.sub || ''}</div>
  </button>`;
};

export const renderSearchResults = (query) => {
  const q = (query || '').trim().toLowerCase();
  if (!q) return renderBrowse();
  const match = (s) => (s || '').toLowerCase().includes(q);

  const trackHits = tracks.filter((t) => match(t.title) || match(t.artist) || match(t.album));
  const artistHits = artists.filter((a) => match(a.name));
  const albumHits = albums.filter((a) => match(a.title) || match(a.artist));
  const playlistHits = playlists.filter((p) => match(p.title) || match(p.desc));
  const showHits = shows.filter((s) => match(s.title) || match(s.desc));

  const top = artistHits.length ? { type: 'artist', id: artistHits[0].id }
    : trackHits.length ? { type: 'album', id: trackHits[0].albumId }
      : playlistHits.length ? { type: 'playlist', id: playlistHits[0].id }
        : showHits.length ? { type: 'show', id: showHits[0].id } : null;

  const empty = !trackHits.length && !artistHits.length && !albumHits.length && !playlistHits.length && !showHits.length;
  if (empty) {
    return `<div class="view"><div class="view__pad">
      <div class="search-empty">
        <h2>No results found for “${query}”</h2>
        <p>Please make sure your words are spelled correctly, or use fewer or different keywords.</p>
      </div>
    </div></div>`;
  }

  return `
  <div class="view">
    <div class="view__pad">
      <div class="results">
        <section aria-label="Top result">
          <div class="result-head"><h2>Top result</h2></div>
          ${topResult(top)}
        </section>
        <section aria-label="Songs">
          <div class="result-head"><h2>Songs</h2></div>
          ${trackHits.slice(0, 4).map((t, i) => trackRow(t, i, { art: true, context: { type: 'search', id: q } })).join('')}
        </section>
      </div>
      ${artistHits.length ? `<div class="result-head"><h2>Artists</h2></div><div class="shelf__row">${artistHits.slice(0, 6).map((a) => card('artist', a.id)).join('')}</div>` : ''}
      ${albumHits.length ? `<div class="result-head"><h2>Albums</h2></div><div class="shelf__row">${albumHits.slice(0, 6).map((a) => card('album', a.id)).join('')}</div>` : ''}
      ${playlistHits.length ? `<div class="result-head"><h2>Playlists</h2></div><div class="shelf__row">${playlistHits.slice(0, 6).map((p) => card('playlist', p.id)).join('')}</div>` : ''}
      ${showHits.length ? `<div class="result-head"><h2>Podcasts</h2></div><div class="shelf__row">${showHits.slice(0, 6).map((s) => card('show', s.id)).join('')}</div>` : ''}
    </div>
  </div>`;
};

// --- detail pages ---------------------------------------------------------
export const renderPlaylist = (id) => {
  const p = playlistById(id);
  if (!p) return renderNotFound();
  const list = p.tracks.map(trackById).filter(Boolean);
  const total = list.reduce((s, t) => s + t.dur, 0);
  return `
  <div class="view">
    <div class="hero" style="--h1:${p.h1};--h2:${p.h2}">
      <div class="hero__bg"></div>
      <div class="hero__content">
        ${art(p, { className: 'hero__cover' })}
        <div class="hero__meta">
          ${heroType('Public Playlist')}
          <h1 class="hero__title">${p.title}</h1>
          <p class="hero__desc">${p.desc}</p>
          <div class="hero__sub">
            <span class="avatar avatar--sm">${p.owner.slice(0, 1)}</span>
            <strong>${p.owner}</strong>
            <span class="hero__dot">${list.length} songs,</span>
            <span>${formatLong(total)}</span>
          </div>
        </div>
      </div>
    </div>
    ${actionBar({
      type: 'playlist', id: p.id, saveLabel: 'Save on Spotify', saved: false,
      right: `<button class="icon-btn" data-action="toast" data-msg="List view">${icon('list')}</button>`,
    })}
    ${trackList(list, { showAlbum: true, showDate: true, context: { type: 'playlist', id: p.id } })}
    <div class="tl__footer" style="padding: 0 40px 32px">
      <p>${list.length} songs, ${formatLong(total)}</p>
    </div>
  </div>`;
};

export const renderAlbum = (id) => {
  const a = albumById(id);
  if (!a) return renderNotFound();
  const list = albumTracks(a.id);
  const total = list.reduce((s, t) => s + t.dur, 0);
  return `
  <div class="view">
    <div class="hero" style="--h1:${a.h1};--h2:${a.h2}">
      <div class="hero__bg"></div>
      <div class="hero__content">
        ${art(a, { className: 'hero__cover' })}
        <div class="hero__meta">
          ${heroType(a.type)}
          <h1 class="hero__title">${a.title}</h1>
          <div class="hero__sub">
            <a href="#/artist/${a.artistId}" data-nav="#/artist/${a.artistId}"><strong>${a.artist}</strong></a>
            <span class="hero__dot">${a.year}</span>
            <span>${list.length} songs, ${formatLong(total)}</span>
          </div>
        </div>
      </div>
    </div>
    ${actionBar({ type: 'album', id: a.id, saveLabel: 'Save on Spotify', right: `<button class="icon-btn" data-action="toast" data-msg="More options">${icon('more')}</button>` })}
    ${trackList(list, { variant: 'tl--album', showPlays: true, context: { type: 'album', id: a.id } })}
    <div class="tl__footer" style="padding: 0 40px 32px">
      <p>${a.year} · ${list.length} songs, ${formatLong(total)}</p>
      <p>℗ 2026 Northlight Recordings, under exclusive licence to this demo</p>
    </div>
  </div>`;
};

export const renderArtist = (id) => {
  const a = artistById(id);
  if (!a) return renderNotFound();
  const popular = artistTracks(a.id).slice(0, 5);
  const discs = artistAlbums(a.id);
  const similar = artists.filter((x) => x.id !== a.id).slice(0, 6);
  return `
  <div class="view">
    <div class="artist-hero" style="--h1:${a.h1};--h2:${a.h2}">
      <div class="artist-hero__bg">${art(a)}</div>
      <div class="artist-hero__inner">
        ${a.verified ? `<div class="artist-hero__verified">${icon('verifiedText')} Verified artist</div>` : ''}
        <h1 class="artist-hero__title">${a.name}</h1>
        <div class="artist-hero__listeners">${formatCount(a.listeners)} monthly listeners</div>
      </div>
    </div>
    ${actionBar({ type: 'artist', id: a.id, saveLabel: 'Follow', right: `<button class="icon-btn" data-action="toast" data-msg="More options">${icon('more')}</button>` })}
    <div class="view__pad">
      <section class="popular" aria-label="Popular">
        <div class="result-head"><h2>Popular</h2></div>
        ${popular.map((t, i) => `
          <button class="popular__row ${player.currentTrack()?.id === t.id ? 'is-current' : ''}" data-action="play-track" data-track="${t.id}" data-context-type="artist" data-context-id="${a.id}">
            <div class="tl__num"><span>${i + 1}</span>${icon('play')}</div>
            ${art(t, { className: 'tl__art' })}
            <div class="tl__texts"><div class="tl__title truncate">${t.title}</div></div>
            <div class="popular__plays">${formatCount(t.plays)}</div>
            <div class="tl__end"><span class="tl__dur">${formatTime(t.dur)}</span></div>
          </button>`).join('')}
      </section>
      ${discs.length ? `<div class="result-head"><h2>Discography</h2><a class="shelf__all" href="#/library">Show all</a></div>
      <div class="shelf__row">${discs.map((al) => card('album', al.id)).join('')}</div>` : ''}
      <div class="result-head"><h2>Fans also like</h2></div>
      <div class="shelf__row">${similar.map((s) => card('artist', s.id)).join('')}</div>
      <section class="about-card">
        <h2>About</h2>
        <p>${a.bio}</p>
        <p style="margin-top:12px">${formatCount(a.followers)} followers</p>
      </section>
    </div>
  </div>`;
};

export const renderShow = (id) => {
  const s = showById(id);
  if (!s) return renderNotFound();
  return `
  <div class="view">
    <div class="hero" style="--h1:${s.h1};--h2:${s.h2}">
      <div class="hero__bg"></div>
      <div class="hero__content">
        ${art(s, { glyph: 'mic', className: 'hero__cover' })}
        <div class="hero__meta">
          ${heroType('Podcast')}
          <h1 class="hero__title">${s.title}</h1>
          <p class="hero__desc">${s.desc}</p>
          <div class="hero__sub"><strong>${s.publisher}</strong></div>
        </div>
      </div>
    </div>
    ${actionBar({ type: 'show', id: s.id, saveLabel: 'Follow', right: `<button class="icon-btn" data-action="toast" data-msg="More options">${icon('more')}</button>` })}
    <div class="view__pad">
      <div class="result-head"><h2>All episodes</h2><button class="shelf__all" data-action="toast" data-msg="Sorted by newest">Sort by newest</button></div>
      ${s.episodes.map((ep, i) => `
        <article class="episode">
          <div>
            <div class="episode__date">${ep.date}</div>
            <h3 class="episode__title">${ep.title}</h3>
            <p class="episode__desc">${ep.desc}</p>
            <div class="episode__dur">${formatLong(ep.dur)} · Episode ${s.episodes.length - i}</div>
          </div>
          <button class="episode__play" data-action="toast" data-msg="Episode playback is not part of this demo" aria-label="Play ${ep.title}">${icon('play')}</button>
        </article>`).join('')}
    </div>
  </div>`;
};

export const renderLiked = () => {
  const list = likedSongs.map(trackById).filter(Boolean);
  const total = list.reduce((s, t) => s + t.dur, 0);
  return `
  <div class="view">
    <div class="hero" style="--h1:258;--h2:300">
      <div class="hero__bg"></div>
      <div class="hero__content">
        ${art({ h1: 258, h2: 300 }, { liked: true, className: 'hero__cover' })}
        <div class="hero__meta">
          ${heroType('Playlist')}
          <h1 class="hero__title">Liked Songs</h1>
          <div class="hero__sub"><span class="avatar avatar--sm">${user.initial}</span><strong>${user.name}</strong><span class="hero__dot">${list.length} songs</span><span class="hero__dot">${formatLong(total)}</span></div>
        </div>
      </div>
    </div>
    ${actionBar({ type: 'liked', id: 'liked', saveLabel: 'Add to playlist', right: `<button class="icon-btn" data-action="toast" data-msg="List view">${icon('list')}</button>` })}
    ${trackList(list, { variant: 'tl--liked', showAlbum: true, context: { type: 'liked', id: 'liked' } })}
    <div class="tl__footer" style="padding: 0 40px 32px"><p>${list.length} songs, ${formatLong(total)}</p></div>
  </div>`;
};

export const renderLibrary = (viewState = {}) => {
  const filter = viewState.libFilter || 'playlists';
  const allowed = { playlists: ['liked', 'playlist'], artists: ['artist'], albums: ['album'], podcasts: ['show'] }[filter] || [];
  const items = libraryItems.filter((it) => allowed.includes(it.type));
  const chips = ['playlists', 'artists', 'albums', 'podcasts'];
  return `
  <div class="view">
    <div class="view__pad">
      <div class="lib-head">
        <div class="view__head" style="padding: 8px 0 12px"><h1>Your Library</h1>
          <div class="actionbar__right">
            <button class="icon-btn" data-action="toast" data-msg="Sorted by recent activity" aria-label="Sort">${icon('sort')}</button>
          </div>
        </div>
        <div class="chips" role="tablist" aria-label="Filter library">
          ${chips.map((c) => `<button class="chip ${c === filter ? 'is-active' : ''}" role="tab" aria-selected="${c === filter}" data-action="lib-filter" data-filter="${c}">${c.charAt(0).toUpperCase() + c.slice(1)}</button>`).join('')}
        </div>
      </div>
      ${items.length ? `<div class="lib-grid">${items.map((it) => card(it.type, it.id)).join('')}</div>` : `
        <div class="empty-panel">
          <h2>Nothing here yet</h2>
          <p>When you save ${filter}, they will show up here.</p>
          <button class="btn btn--light" data-nav="#/search">Find something to save</button>
        </div>`}
    </div>
  </div>`;
};

export const renderNotFound = () => `
  <div class="view"><div class="view__pad">
    <div class="search-empty">
      <h2>Page not found</h2>
      <p>The page you asked for is not part of this demo.</p>
      <p style="margin-top:16px"><a class="btn btn--light" href="#/" data-nav="#/">Go home</a></p>
    </div>
  </div></div>`;

// --- sidebar --------------------------------------------------------------
export const renderSidebar = (viewState = {}) => {
  const filter = viewState.libFilter || 'playlists';
  const allowed = { playlists: ['liked', 'playlist'], artists: ['artist'], albums: ['album'], podcasts: ['show'] }[filter] || [];
  const items = libraryItems.filter((it) => allowed.includes(it.type));
  return `
  <div class="sb-card sb-library">
    <div class="sb-head">
      <button class="sb-title" data-nav="#/library">${icon('librarySolid')}Your Library</button>
      <div class="sb-head__actions">
        <button class="icon-btn" data-action="new-playlist" aria-label="Create playlist">${icon('plus')}</button>
        <button class="icon-btn" data-nav="#/library" aria-label="Expand Your Library">${icon('arrowRight')}</button>
      </div>
    </div>
    <div class="sb-chips" role="tablist" aria-label="Filter library">
      ${['playlists', 'artists', 'albums', 'podcasts'].map((c) => `<button class="chip ${c === filter ? 'is-active' : ''}" role="tab" aria-selected="${c === filter}" data-action="lib-filter" data-filter="${c}">${c.charAt(0).toUpperCase() + c.slice(1)}</button>`).join('')}
    </div>
    <div class="sb-tools">
      <div class="sb-tools__left">
        <button class="icon-btn" data-nav="#/search" aria-label="Search in Your Library">${icon('search')}</button>
      </div>
      <button class="sb-sort" data-action="toast" data-msg="Sorted by recent activity">Recents ${icon('list')}</button>
    </div>
    <div class="sb-list">
      ${items.map((it) => {
        const meta = metaFor(it.type, it.id);
        if (!meta) return '';
        return `
        <button class="lib-row" data-nav="${routeFor(it.type, it.id)}">
          ${art(meta.item, { liked: meta.liked, glyph: meta.glyph, round: meta.round, className: 'lib-row__art' })}
          <span style="min-width:0">
            <span class="lib-row__title truncate" style="display:block">${meta.title}</span>
            <span class="lib-row__sub truncate">
              ${(it.type === 'playlist' || it.type === 'liked') ? icon('pin') : ''}
              ${it.type === 'playset' ? '' : ''}
              ${it.type === 'playlist' ? `Playlist • ${meta.item.owner}` : ''}
              ${it.type === 'liked' ? `Playlist • ${user.name}` : ''}
              ${it.type === 'artist' ? 'Artist' : ''}
              ${it.type === 'album' ? `Album • ${meta.item.artist}` : ''}
              ${it.type === 'show' ? 'Podcast' : ''}
            </span>
          </span>
          <span class="lib-row__play" data-action="play-entity" data-type="${it.type}" data-id="${it.id}" aria-label="Play ${meta.title}">${icon('play')}</span>
        </button>`;
      }).join('')}
    </div>
    <div class="sb-footer">
      <div class="sb-legal">
        <a href="#/legal" data-nav="#/legal">Legal</a>
        <a href="#/legal" data-nav="#/legal">Safety &amp; Privacy Center</a>
        <a href="#/legal" data-nav="#/legal">Privacy Policy</a>
        <a href="#/legal" data-nav="#/legal">Cookies</a>
        <a href="#/legal" data-nav="#/legal">About Ads</a>
        <a href="#/legal" data-nav="#/legal">Accessibility</a>
      </div>
      <button class="sb-lang" data-action="toast" data-msg="Only English is bundled in this demo">English</button>
    </div>
  </div>`;
};

// --- right panel ----------------------------------------------------------
const queueRow = (track, { current = false } = {}) => `
  <button class="queue-row ${current ? 'is-current' : ''}" data-action="play-track" data-track="${track.id}">
    ${art(track, { className: 'queue-row__art' })}
    <span style="min-width:0">
      <span class="queue-row__title truncate" style="display:block">${track.title}</span>
      <span class="queue-row__sub truncate" style="display:block">${track.artist}</span>
    </span>
  </button>`;

const aboutArtistCard = (artist) => artist ? `
  <div class="np-card">
    <div class="np-card__media">
      ${art(artist)}
      <span class="np-card__label">About the artist</span>
    </div>
    <div class="np-card__body">
      <div class="np-card__name">${artist.name}${artist.verified ? icon('verifiedText') : ''}</div>
      <div class="np-card__meta">${formatCount(artist.listeners)} monthly listeners</div>
      <button class="follow-pill" data-action="toggle-save" data-type="artist" data-id="${artist.id}">Follow</button>
    </div>
  </div>` : '';

export const renderPanel = (mode = 'nowplaying') => {
  const track = player.currentTrack();
  const tabs = `
    <div class="panel__tabs">
      <button class="icon-btn ${mode === 'nowplaying' ? 'is-active' : ''}" data-action="panel" data-mode="nowplaying" aria-label="Now playing view">${icon('grid')}</button>
      <button class="icon-btn ${mode === 'queue' ? 'is-active' : ''}" data-action="panel" data-mode="queue" aria-label="Queue">${icon('queue')}</button>
      <button class="icon-btn ${mode === 'connect' ? 'is-active' : ''}" data-action="panel" data-mode="connect" aria-label="Connect to a device">${icon('device')}</button>
      <button class="icon-btn ${mode === 'lyrics' ? 'is-active' : ''}" data-action="panel" data-mode="lyrics" aria-label="Lyrics">${icon('lyrics')}</button>
    </div>`;

  if (mode === 'queue') {
    const upNext = state_queue();
    return `
    <div class="panel__head"><div class="panel__titles"><span class="panel__title">Queue</span></div>${tabs}</div>
    <div class="panel__body">
      <div class="queue-section">
        <div class="queue-label">Now playing</div>
        ${track ? queueRow(track, { current: true }) : '<p class="queue-row__sub" style="padding:8px">Nothing playing.</p>'}
        <div class="queue-label" style="margin-top:8px">Next up</div>
        ${upNext.map((t) => queueRow(t)).join('') || '<p class="queue-row__sub" style="padding:8px">Nothing queued.</p>'}
      </div>
    </div>`;
  }

  if (mode === 'connect') {
    return `
    <div class="panel__head"><div class="panel__titles"><span class="panel__title">Connect to a device</span></div>${tabs}</div>
    <div class="panel__body">
      ${devices.map((d) => `
        <button class="device-row ${d.active ? 'is-active' : ''}" data-action="toast" data-msg="Connected to ${d.name}">
          ${icon(d.type === 'speaker' ? 'speaker' : d.type === 'browser' ? 'device' : 'headphones')}
          <span>
            <span class="device-row__name" style="display:block">${d.name}</span>
            <span class="device-row__meta">${d.active ? 'Currently active' : 'Available'}</span>
          </span>
        </button>`).join('')}
      <p class="device-row__meta" style="padding:16px 8px">Tip: this demo lists devices locally; nothing is paired.</p>
    </div>`;
  }

  if (mode === 'lyrics') {
    const pos = player.state.position;
    return `
    <div class="panel__head"><div class="panel__titles"><span class="panel__title">Lyrics</span></div>${tabs}</div>
    <div class="panel__body">
      <div class="lyrics-view">
        <h2>${track ? track.title : 'Nothing playing'}</h2>
        <div class="sub">${track ? track.artist : ''}</div>
        ${lyrics.map(([line, at]) => {
          const idx = lyrics.findIndex((l) => l[1] === at);
          const nextAt = lyrics[idx + 1]?.[1] ?? Infinity;
          const active = pos >= at && pos < nextAt;
          return `<p class="lyric-line ${active ? 'is-active' : pos >= nextAt ? 'is-past' : ''}">${line}</p>`;
        }).join('')}
        <p class="device-row__meta" style="margin-top:24px">Demo lyrics, timed to the simulated playback clock.</p>
      </div>
    </div>`;
  }

  const artist = track ? artistById(track.artistId) : null;
  const upNext = state_queue();
  return `
  <div class="panel__head">
    <div class="panel__titles">
      ${track ? `<span class="panel__title truncate">${track.album}</span>` : '<span class="panel__title">Now playing</span>'}
    </div>
    ${tabs}
  </div>
  <div class="panel__body">
    ${track ? `
      ${art(track, { className: 'np-art' })}
      <div class="np-titlerow">
        <div>
          <div class="np-title">${track.title}</div>
          <a class="np-artist" href="#/artist/${track.artistId}" data-nav="#/artist/${track.artistId}">${track.artist}</a>
        </div>
        <span class="np-check">${icon('verifiedText')}</span>
      </div>` : '<p class="queue-row__sub" style="padding:16px">Pick a track to see it here.</p>'}
    ${aboutArtistCard(artist)}
    <div class="np-card">
      <div class="np-credits">
        <div class="credit-row"><span>Credits</span><span>Show all</span></div>
        <div class="credit-row"><span>${track ? track.artist : '—'}</span><span>Main artist</span></div>
        <div class="credit-row"><span>Northlight Recordings</span><span>Label</span></div>
        <div class="credit-row"><span>${track ? track.album : '—'}</span><span>Album</span></div>
      </div>
    </div>
    <div class="queue-section">
      <div class="queue-label">Next in queue</div>
      ${upNext.slice(0, 3).map((t) => queueRow(t)).join('') || '<p class="queue-row__sub" style="padding:8px">Queue is empty.</p>'}
    </div>
  </div>`;
};

const state_queue = () => {
  const s = player.state;
  return s.queue.slice(s.index + 1).map(trackById).filter(Boolean);
};
