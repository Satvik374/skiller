// All copy and catalogue data for the clone. Invented artists, albums and shows:
// no real recordings, artwork or names from any service.

export const user = {
  name: 'Alex Rivera',
  first: 'Alex',
  initial: 'A',
  plan: 'Premium Individual',
};

export const artists = [
  { id: 'vela-nova', name: 'Vela Nova', h1: 268, h2: 210, listeners: 12804321, followers: 4210332, verified: true, bio: 'Synth-driven pop from a two-piece who record everything in a converted garage in Lisbon. Known for bright arpeggios and very dry drums.' },
  { id: 'quiet-hours', name: 'The Quiet Hours', h1: 202, h2: 258, listeners: 6420110, followers: 1983320, verified: true, bio: 'Slow-core trio. Long reverbs, patient arrangements, songs that take their time.' },
  { id: 'kaia', name: 'Kaia', h1: 8, h2: 330, listeners: 9128440, followers: 2401277, verified: true, bio: 'Singer and producer writing widescreen break-up pop with a soft centre.' },
  { id: 'meridian', name: 'Meridian', h1: 168, h2: 196, listeners: 4188302, followers: 902331, verified: false, bio: 'Instrumental electronic project built from modular hardware and tape loops.' },
  { id: 'northbound', name: 'Northbound', h1: 22, h2: 344, listeners: 3120984, followers: 612094, verified: true, bio: 'Four-piece guitar band from Leeds with a taste for wide choruses.' },
  { id: 'elio-marsh', name: 'Elio Marsh', h1: 38, h2: 14, listeners: 2094311, followers: 498220, verified: false, bio: 'Songwriter, multi-instrumentalist, and chronic over-dubber of harmonies.' },
  { id: 'juno-park', name: 'Juno Park', h1: 288, h2: 246, listeners: 7721033, followers: 1590044, verified: true, bio: 'R&B-leaning producer and vocalist with a jazz drummer’s sense of space.' },
  { id: 'whalebone', name: 'Whalebone', h1: 196, h2: 172, listeners: 1502334, followers: 302118, verified: false, bio: 'Post-folk duo recording in a coastal cabin, one microphone, no click track.' },
  { id: 'rift-theory', name: 'Rift Theory', h1: 250, h2: 286, listeners: 5603221, followers: 1187402, verified: true, bio: 'Club-facing production duo. Big low end, sharper edges.' },
  { id: 'sable-court', name: 'Sable Court', h1: 232, h2: 306, listeners: 3901744, followers: 883011, verified: true, bio: 'Dream-pop five-piece with choral vocals and a weakness for chorus pedals.' },
  { id: 'nadia-vale', name: 'Nadia Vale', h1: 320, h2: 268, listeners: 1844022, followers: 344920, verified: false, bio: 'Harpist turned electronic composer, layering plucked samples into slow grooves.' },
  { id: 'coastline', name: 'Coastline', h1: 184, h2: 214, listeners: 2443119, followers: 511002, verified: true, bio: 'Indie quartet writing road-trip songs about leaving and coming back.' },
  { id: 'lanterns', name: 'The Lanterns', h1: 46, h2: 30, listeners: 1123094, followers: 244776, verified: false, bio: 'Three friends, one rehearsal room, a lot of tambourine.' },
  { id: 'mara-sol', name: 'Mara Sol', h1: 300, h2: 330, listeners: 6310992, followers: 1402210, verified: true, bio: 'Pop artist with an ear for a chorus that arrives exactly when you want it.' },
  { id: 'peach-motel', name: 'Peach Motel', h1: 12, h2: 348, listeners: 940881, followers: 198233, verified: false, bio: 'Bedroom-pop project with cheap keyboards and expensive melodies.' },
  { id: 'obsidian-choir', name: 'Obsidian Choir', h1: 262, h2: 292, listeners: 3050122, followers: 722113, verified: false, bio: 'Choral group reworking hymns into dark ambient pieces.' },
];

export const albums = [
  { id: 'midnight-static', title: 'Midnight Static', artist: 'Vela Nova', artistId: 'vela-nova', year: 2025, type: 'Album', h1: 268, h2: 200 },
  { id: 'hollow-season', title: 'Hollow Season', artist: 'The Quiet Hours', artistId: 'quiet-hours', year: 2023, type: 'Album', h1: 202, h2: 240 },
  { id: 'undertow', title: 'Undertow', artist: 'Kaia', artistId: 'kaia', year: 2025, type: 'Album', h1: 8, h2: 330 },
  { id: 'static-bloom', title: 'Static Bloom', artist: 'Meridian', artistId: 'meridian', year: 2024, type: 'Album', h1: 168, h2: 196 },
  { id: 'concrete-garden', title: 'Concrete Garden', artist: 'Northbound', artistId: 'northbound', year: 2022, type: 'Album', h1: 22, h2: 344 },
  { id: 'amber-light', title: 'Amber Light', artist: 'Elio Marsh', artistId: 'elio-marsh', year: 2025, type: 'Album', h1: 38, h2: 18 },
  { id: 'parallel-lines', title: 'Parallel Lines', artist: 'Juno Park', artistId: 'juno-park', year: 2023, type: 'Album', h1: 288, h2: 246 },
  { id: 'salt-and-silver', title: 'Salt & Silver', artist: 'Whalebone', artistId: 'whalebone', year: 2021, type: 'Album', h1: 196, h2: 172 },
  { id: 'velocity', title: 'Velocity', artist: 'Rift Theory', artistId: 'rift-theory', year: 2024, type: 'Album', h1: 250, h2: 286 },
  { id: 'blue-hour', title: 'Blue Hour', artist: 'Sable Court', artistId: 'sable-court', year: 2025, type: 'Album', h1: 232, h2: 306 },
  { id: 'soft-focus', title: 'Soft Focus', artist: 'Nadia Vale', artistId: 'nadia-vale', year: 2024, type: 'Album', h1: 320, h2: 268 },
  { id: 'neon-rain', title: 'Neon Rain', artist: 'Mara Sol', artistId: 'mara-sol', year: 2026, type: 'Single', h1: 300, h2: 330 },
];

export const tracks = [
  { id: 't1', title: 'Glass Horizon', artist: 'Vela Nova', artistId: 'vela-nova', album: 'Midnight Static', albumId: 'midnight-static', dur: 222, plays: 88120433 },
  { id: 't2', title: 'Midnight Drive', artist: 'Vela Nova', artistId: 'vela-nova', album: 'Midnight Static', albumId: 'midnight-static', dur: 248, plays: 42103322 },
  { id: 't3', title: 'Feedback Loop', artist: 'Vela Nova', artistId: 'vela-nova', album: 'Midnight Static', albumId: 'midnight-static', dur: 196, plays: 19023344 },
  { id: 't4', title: 'Static Bloom', artist: 'Meridian', artistId: 'meridian', album: 'Static Bloom', albumId: 'static-bloom', dur: 305, plays: 12084333 },
  { id: 't5', title: 'Echo Chamber', artist: 'Meridian', artistId: 'meridian', album: 'Static Bloom', albumId: 'static-bloom', dur: 268, plays: 8023112 },
  { id: 't6', title: 'Hollow Season', artist: 'The Quiet Hours', artistId: 'quiet-hours', album: 'Hollow Season', albumId: 'hollow-season', dur: 274, plays: 30211984 },
  { id: 't7', title: 'Sunday Static', artist: 'The Quiet Hours', artistId: 'quiet-hours', album: 'Hollow Season', albumId: 'hollow-season', dur: 233, plays: 14022911 },
  { id: 't8', title: 'Slow Collapse', artist: 'Northbound', artistId: 'northbound', album: 'Concrete Garden', albumId: 'concrete-garden', dur: 211, plays: 22119004 },
  { id: 't9', title: 'Concrete Garden', artist: 'Northbound', artistId: 'northbound', album: 'Concrete Garden', albumId: 'concrete-garden', dur: 245, plays: 9943120 },
  { id: 't10', title: 'Undertow', artist: 'Kaia', artistId: 'kaia', album: 'Undertow', albumId: 'undertow', dur: 199, plays: 66092112 },
  { id: 't11', title: 'Little Fires', artist: 'Kaia', artistId: 'kaia', album: 'Undertow', albumId: 'undertow', dur: 214, plays: 41288401 },
  { id: 't12', title: 'Amber Light', artist: 'Elio Marsh', artistId: 'elio-marsh', album: 'Amber Light', albumId: 'amber-light', dur: 236, plays: 8102233 },
  { id: 't13', title: 'Golden Hour', artist: 'Elio Marsh', artistId: 'elio-marsh', album: 'Amber Light', albumId: 'amber-light', dur: 258, plays: 5102231 },
  { id: 't14', title: 'Parallel Lines', artist: 'Juno Park', artistId: 'juno-park', album: 'Parallel Lines', albumId: 'parallel-lines', dur: 227, plays: 28110432 },
  { id: 't15', title: 'Wired Hearts', artist: 'Juno Park', artistId: 'juno-park', album: 'Parallel Lines', albumId: 'parallel-lines', dur: 203, plays: 17004421 },
  { id: 't16', title: 'Salt & Silver', artist: 'Whalebone', artistId: 'whalebone', album: 'Salt & Silver', albumId: 'salt-and-silver', dur: 289, plays: 4201199 },
  { id: 't17', title: 'Pale Blue', artist: 'Whalebone', artistId: 'whalebone', album: 'Salt & Silver', albumId: 'salt-and-silver', dur: 262, plays: 3011221 },
  { id: 't18', title: 'Velocity', artist: 'Rift Theory', artistId: 'rift-theory', album: 'Velocity', albumId: 'velocity', dur: 188, plays: 52099112 },
  { id: 't19', title: 'Gravity Well', artist: 'Rift Theory', artistId: 'rift-theory', album: 'Velocity', albumId: 'velocity', dur: 241, plays: 33018822 },
  { id: 't20', title: 'Blue Hour', artist: 'Sable Court', artistId: 'sable-court', album: 'Blue Hour', albumId: 'blue-hour', dur: 254, plays: 19022341 },
  { id: 't21', title: 'Afterglow', artist: 'Sable Court', artistId: 'sable-court', album: 'Blue Hour', albumId: 'blue-hour', dur: 231, plays: 12100922 },
  { id: 't22', title: 'Low Tide', artist: 'Nadia Vale', artistId: 'nadia-vale', album: 'Soft Focus', albumId: 'soft-focus', dur: 298, plays: 4022111 },
  { id: 't23', title: 'Ghost Note', artist: 'Nadia Vale', artistId: 'nadia-vale', album: 'Soft Focus', albumId: 'soft-focus', dur: 276, plays: 2201884 },
  { id: 't24', title: 'Tidal Wave', artist: 'Coastline', artistId: 'coastline', album: 'Long Way Home', albumId: 'concrete-garden', dur: 219, plays: 8802112 },
  { id: 't25', title: 'Ocean Floor', artist: 'Coastline', artistId: 'coastline', album: 'Long Way Home', albumId: 'concrete-garden', dur: 242, plays: 5100991 },
  { id: 't26', title: 'Rooftop Summer', artist: 'The Lanterns', artistId: 'lanterns', album: 'Rooftop Summer', albumId: 'amber-light', dur: 198, plays: 3301221 },
  { id: 't27', title: 'Velvet Static', artist: 'Mara Sol', artistId: 'mara-sol', album: 'Neon Rain', albumId: 'neon-rain', dur: 205, plays: 44102233 },
  { id: 't28', title: 'Neon Rain', artist: 'Mara Sol', artistId: 'mara-sol', album: 'Neon Rain', albumId: 'neon-rain', dur: 193, plays: 61203321 },
  { id: 't29', title: 'Cherry Sky', artist: 'Peach Motel', artistId: 'peach-motel', album: 'Cherry Sky', albumId: 'amber-light', dur: 208, plays: 2801221 },
  { id: 't30', title: 'Nightfall', artist: 'Obsidian Choir', artistId: 'obsidian-choir', album: 'Nightfall', albumId: 'blue-hour', dur: 322, plays: 1902110 },
];

export const playlists = [
  { id: 'late-night-drive', title: 'Late Night Drive', desc: 'Neon-lit synths for empty motorways and 2am fuel stops.', owner: 'Alex Rivera', ownerId: 'alex', h1: 258, h2: 214, pinned: true,
    tracks: ['t1', 't27', 't2', 't18', 't20', 't3', 't28', 't19', 't21', 't4'] },
  { id: 'focus-flow', title: 'Focus Flow', desc: 'Instrumental, low-vocal, no sudden dynamics. Just keep going.', owner: 'Alex Rivera', ownerId: 'alex', h1: 196, h2: 226, pinned: true,
    tracks: ['t4', 't22', 't5', 't23', 't16', 't30', 't17', 't6'] },
  { id: 'sunday-coffee', title: 'Sunday Morning Coffee', desc: 'Warm, slow, unbothered. Playlist for the first hour awake.', owner: 'Alex Rivera', ownerId: 'alex', h1: 36, h2: 20, pinned: true,
    tracks: ['t13', 't29', 't12', 't26', 't7', 't16', 't24'] },
  { id: 'indie-discoveries', title: 'Indie Discoveries', desc: 'The best of what landed in our inbox this week.', owner: 'Web Player', ownerId: 'editorial', h1: 152, h2: 178, pinned: true,
    tracks: ['t8', 't25', 't10', 't6', 't20', 't24', 't29', 't11'] },
  { id: 'synthwave-neon', title: 'Synthwave Neon', desc: 'Arpeggios, gated drums and a permanent sunset.', owner: 'Web Player', ownerId: 'editorial', h1: 296, h2: 268,
    tracks: ['t18', 't27', 't1', 't19', 't2', 't28', 't3', 't4'] },
  { id: 'acoustic-evenings', title: 'Acoustic Evenings', desc: 'One guitar, one voice, one room.', owner: 'Web Player', ownerId: 'editorial', h1: 24, h2: 356,
    tracks: ['t12', 't16', 't7', 't17', 't26', 't13', 't24'] },
  { id: 'gym-heat', title: 'Gym Heat', desc: 'Tempo up, everything else down.', owner: 'Alex Rivera', ownerId: 'alex', h1: 344, h2: 12,
    tracks: ['t18', 't8', 't19', 't10', 't27', 't9', 't28'] },
  { id: 'chill-rap-rotation', title: 'Chill Rap Rotation', desc: 'Laid-back flows over dusty drums.', owner: 'Web Player', ownerId: 'editorial', h1: 276, h2: 300,
    tracks: ['t14', 't15', 't11', 't5', 't23', 't9'] },
  { id: 'road-trip-anthems', title: 'Road Trip Anthems', desc: 'Windows down, volume up, destination negotiable.', owner: 'Web Player', ownerId: 'editorial', h1: 210, h2: 250,
    tracks: ['t24', 't8', 't1', 't25', 't10', 't26', 't14', 't29'] },
  { id: 'deep-focus', title: 'Deep Focus', desc: 'Two hours of ambient texture. No lyrics, no interruptions.', owner: 'Web Player', ownerId: 'editorial', h1: 188, h2: 204,
    tracks: ['t30', 't22', 't4', 't23', 't5', 't17'] },
];

export const shows = [
  { id: 'long-player', title: 'The Long Player', publisher: 'Lantern Audio', h1: 22, h2: 344,
    desc: 'Long conversations with people who make records, about the parts nobody films.', episodes: [
      { id: 'e1', title: 'How a chorus gets written', desc: 'A songwriter takes us through nine drafts of the same eight bars.', dur: 3210, date: 'Nov 12, 2026' },
      { id: 'e2', title: 'The room is the instrument', desc: 'Why the best drum sound on the record was a corridor.', dur: 2740, date: 'Nov 5, 2026' },
      { id: 'e3', title: 'Nobody knows what a producer does', desc: 'Three producers disagree about their own job.', dur: 3580, date: 'Oct 29, 2026' },
    ] },
  { id: 'signal-noise', title: 'Signal & Noise', publisher: 'Field Recordings Co.', h1: 268, h2: 210,
    desc: 'A weekly scan of new electronic music, two records deep, no filler.', episodes: [
      { id: 'e4', title: 'Modular, but make it listenable', desc: 'Six records that use hardware without hiding behind it.', dur: 2460, date: 'Nov 14, 2026' },
      { id: 'e5', title: 'The return of the 2-step', desc: 'Why that shuffle is everywhere again.', dur: 2190, date: 'Nov 7, 2026' },
    ] },
  { id: 'field-notes', title: 'Field Notes', publisher: 'Independent', h1: 152, h2: 190,
    desc: 'Sound, place and memory — recorded on location.', episodes: [
      { id: 'e6', title: 'Harbour at 5am', desc: 'Gulls, ropes, an engine, and a conversation about tides.', dur: 1980, date: 'Nov 9, 2026' },
      { id: 'e7', title: 'The last record shop on the street', desc: 'Thirty years of a shop that refused to move.', dur: 2860, date: 'Oct 26, 2026' },
    ] },
  { id: 'after-hours', title: 'After Hours Radio', publisher: 'Nightshift Media', h1: 232, h2: 302,
    desc: 'A slow mix for the small hours, with guests who are still awake.', episodes: [
      { id: 'e8', title: 'Slow sets with Sable Court', desc: 'An hour of dream-pop and a very long reverb pedal story.', dur: 3720, date: 'Nov 15, 2026' },
    ] },
];

export const categories = [
  { title: 'Pop', h1: 330, h2: 12 }, { title: 'Hip-Hop', h1: 24, h2: 348 },
  { title: 'Podcasts', h1: 210, h2: 260 }, { title: 'Live Events', h1: 268, h2: 300 },
  { title: 'Made For You', h1: 190, h2: 232 }, { title: 'New Releases', h1: 276, h2: 320 },
  { title: 'Charts', h1: 152, h2: 196 }, { title: 'Latin', h1: 8, h2: 340 },
  { title: 'Rock', h1: 300, h2: 240 }, { title: 'Sleep', h1: 220, h2: 282 },
  { title: 'Workout', h1: 344, h2: 18 }, { title: 'Chill', h1: 200, h2: 246 },
  { title: 'Feel Good', h1: 46, h2: 20 }, { title: 'Indie', h1: 262, h2: 208 },
  { title: 'Love', h1: 320, h2: 350 }, { title: 'Party', h1: 284, h2: 320 },
  { title: 'Commute', h1: 180, h2: 212 }, { title: 'Focus', h1: 168, h2: 200 },
  { title: 'Wellness', h1: 140, h2: 178 }, { title: 'Audiobooks', h1: 34, h2: 6 },
];

export const shortcuts = [
  { type: 'playlist', id: 'late-night-drive' },
  { type: 'playlist', id: 'focus-flow' },
  { type: 'played', id: 'liked' },
  { type: 'playlist', id: 'gym-heat' },
  { type: 'playlist', id: 'sunday-coffee' },
  { type: 'playlist', id: 'indie-discoveries' },
  { type: 'show', id: 'long-player' },
  { type: 'album', id: 'blue-hour' },
];

export const homeShelves = [
  { title: 'Made for Alex', items: [
    { type: 'playlist', id: 'late-night-drive' }, { type: 'playlist', id: 'focus-flow' },
    { type: 'playlist', id: 'deep-focus' }, { type: 'playlist', id: 'chill-rap-rotation' },
    { type: 'playlist', id: 'indie-discoveries' }, { type: 'playlist', id: 'synthwave-neon' },
  ] },
  { title: 'Recently played', items: [
    { type: 'album', id: 'midnight-static' }, { type: 'album', id: 'blue-hour' },
    { type: 'album', id: 'velocity' }, { type: 'playlist', id: 'sunday-coffee' },
    { type: 'album', id: 'undertow' }, { type: 'album', id: 'static-bloom' },
  ] },
  { title: 'Jump back in', items: [
    { type: 'album', id: 'concrete-garden' }, { type: 'playlist', id: 'road-trip-anthems' },
    { type: 'playlist', id: 'acoustic-evenings' }, { type: 'album', id: 'parallel-lines' },
    { type: 'show', id: 'signal-noise' }, { type: 'album', id: 'amber-light' },
  ] },
  { title: 'Popular artists', items: [
    { type: 'artist', id: 'vela-nova' }, { type: 'artist', id: 'kaia' },
    { type: 'artist', id: 'juno-park' }, { type: 'artist', id: 'rift-theory' },
    { type: 'artist', id: 'sable-court' }, { type: 'artist', id: 'mara-sol' },
  ] },
  { title: 'Popular albums and singles', items: [
    { type: 'album', id: 'neon-rain' }, { type: 'album', id: 'undertow' },
    { type: 'album', id: 'velocity' }, { type: 'album', id: 'parallel-lines' },
    { type: 'album', id: 'midnight-static' }, { type: 'album', id: 'blue-hour' },
  ] },
  { title: 'Podcasts for you', items: [
    { type: 'show', id: 'long-player' }, { type: 'show', id: 'signal-noise' },
    { type: 'show', id: 'field-notes' }, { type: 'show', id: 'after-hours' },
  ] },
];

export const libraryItems = [
  { type: 'liked', id: 'liked' },
  ...playlists.filter((p) => p.ownerId === 'alex').map((p) => ({ type: 'playlist', id: p.id })),
  { type: 'artist', id: 'vela-nova' }, { type: 'artist', id: 'kaia' },
  { type: 'album', id: 'blue-hour' }, { type: 'album', id: 'midnight-static' },
  { type: 'show', id: 'long-player' },
];

export const likedSongs = ['t1', 't10', 't18', 't20', 't27', 't14', 't6', 't8', 't22', 't2'];

export const devices = [
  { id: 'browser', name: 'This web browser', type: 'browser', active: true },
  { id: 'phone', name: "Alex's Pixel", type: 'phone', active: false },
  { id: 'speaker', name: 'Living Room Speaker', type: 'speaker', active: false },
  { id: 'laptop', name: 'Studio MacBook', type: 'laptop', active: false },
];

export const lyrics = [
  ['Glass horizon', 0], ['and the city keeps its lights on', 6], ['for no one in particular', 12],
  ['We were driving', 19], ['past the exits that we memorised', 24], ['and never took', 30],
  ['Say it slowly', 37], ['like the words might break if we let go', 42],
  ['Glass horizon', 50], ['hold the wheel and watch the morning come', 55],
  ['come up anyway', 62], ['anyway', 67],
];

// --- lookups ---------------------------------------------------------------
export const trackById = (id) => tracks.find((t) => t.id === id);
export const artistById = (id) => artists.find((a) => a.id === id);
export const albumById = (id) => albums.find((a) => a.id === id);
export const playlistById = (id) => playlists.find((p) => p.id === id);
export const showById = (id) => shows.find((s) => s.id === id);

export const albumTracks = (albumId) => tracks.filter((t) => t.albumId === albumId);
export const artistTracks = (artistId) => tracks.filter((t) => t.artistId === artistId);
export const artistAlbums = (artistId) => albums.filter((a) => a.artistId === artistId);

export const entity = (type, id) => {
  if (type === 'playlist') return playlistById(id);
  if (type === 'album') return albumById(id);
  if (type === 'artist') return artistById(id);
  if (type === 'show') return showById(id);
  return null;
};

export const entityTracks = (type, id) => {
  if (type === 'playlist') return (playlistById(id)?.tracks || []).map(trackById).filter(Boolean);
  if (type === 'album') return albumTracks(id);
  if (type === 'artist') return artistTracks(id).slice(0, 10);
  if (type === 'show') return [];
  return [];
};

export const totalDuration = (list) => list.reduce((sum, t) => sum + (t?.dur || 0), 0);

export const formatTime = (secs) => {
  const s = Math.max(0, Math.floor(secs || 0));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h) return `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
  return `${m}:${String(sec).padStart(2, '0')}`;
};

export const formatLong = (secs) => {
  const h = Math.floor(secs / 3600);
  const m = Math.round((secs % 3600) / 60);
  return h ? `${h} hr ${m} min` : `${m} min`;
};

export const formatCount = (n) => n.toLocaleString('en-US');
