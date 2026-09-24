/**
 * ha-tenup-card behaviour tests.  Run with:  node tests/card/run.mjs
 *
 * What silently goes wrong in this card:
 *   1. the time axis (30-minute lessons next to 60-minute slots, clamped hours);
 *   2. the state of a cell (a free slot that is already over must not be bookable);
 *   3. the service payloads of book and cancel (the wrong court or start books
 *      the wrong slot on a real account);
 *   4. the editor: config-changed must carry detail.config, and HA's echo must
 *      not rebuild the form or erase a value.
 */
process.env.TZ = 'Europe/Paris';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { existsSync } from 'node:fs';
import { loadCard, loadCardTwice, check, contains, report } from './harness.mjs';
const ok = (label, cond) => check(label, !!cond, true);

const HERE = dirname(fileURLToPath(import.meta.url));
const registry = await loadCard(
  process.env.TENUP_CARD ||
    join(HERE, '..', '..', 'custom_components', 'tenup', 'ha-tenup-card.js'),
);
const Card = registry.get('ha-tenup-card');
const Editor = registry.get('ha-tenup-card-editor');
const H = Card._helpers;

// A fixed "now": Thursday 2026-09-10 20:30 Paris.
const NOW = new Date('2026-09-10T20:30:00+02:00').getTime();

const COURTS = [{ id: '21099', name: 'Court COUVERT' }, { id: '21100', name: 'COURT 1' }, { id: '21101', name: 'COURT 2' }];
function slot(court, start, end, state, extra = {}) {
  const c = COURTS.find((x) => x.id === court);
  return { court_id: court, court_name: c.name, start, end, state, label: null, reservation_id: null, ...extra };
}
const DAY1 = {
  date: '2026-09-10',
  slots: [
    slot('21100', '2026-09-10T19:00:00+02:00', '2026-09-10T20:00:00+02:00', 'free'),          // over: must render as past
    slot('21100', '2026-09-10T20:00:00+02:00', '2026-09-10T21:00:00+02:00', 'busy', { label: 'T. HALE' }),
    slot('21100', '2026-09-10T21:00:00+02:00', '2026-09-10T22:00:00+02:00', 'free'),
    slot('21099', '2026-09-10T21:00:00+02:00', '2026-09-10T22:00:00+02:00', 'mine', { label: 'J. PUBLIC', reservation_id: '165841846' }),
    slot('21101', '2026-09-10T20:00:00+02:00', '2026-09-10T21:00:00+02:00', 'free'),
  ],
};
const DAY2 = {
  date: '2026-09-12',
  slots: [
    slot('21100', '2026-09-12T11:00:00+02:00', '2026-09-12T11:30:00+02:00', 'free'),
    slot('21100', '2026-09-12T11:30:00+02:00', '2026-09-12T13:00:00+02:00', 'busy', { label: 'CJ sam 11h30 Alex Robin' }),
    slot('21101', '2026-09-12T10:00:00+02:00', '2026-09-12T11:00:00+02:00', 'free'),
  ],
};
const DATA = { entry_id: 'entry-1', club_code: '87654321', club_name: 'DEMO (TENNIS CLUB)', fetched_at: '2026-09-10T20:25:00+02:00', courts: COURTS, days: [DAY1, DAY2] };

function makeHass(lang = 'en') {
  const calls = [];
  return {
    language: lang, states: {},
    calls,
    callWS: async (msg) => { calls.push({ ws: msg }); return DATA; },
    callService: async (domain, service, data) => { calls.push({ domain, service, data }); return {}; },
  };
}

async function makeCard(config, hass = makeHass()) {
  const card = new Card();
  card.setConfig(Object.freeze({ ...config }));   // Lovelace deep-freezes the stored config
  card.hass = hass;
  await new Promise((r) => setTimeout(r, 0));     // let _fetch resolve
  return card;
}

// ── 1. helpers ───────────────────────────────────────────────────────────────
ok('minutesOf reads local time', H.minutesOf('2026-09-10T21:00:00+02:00') === 21 * 60);
ok('hhmm formats', H.hhmm('2026-09-12T11:30:00+02:00') === '11:30');
ok('a free slot that is over is past', H.slotState(DAY1.slots[0], NOW) === 'past');
ok('a free slot to come stays free', H.slotState(DAY1.slots[2], NOW) === 'free');
ok('my finished reservation is no longer cancellable', H.slotState({ ...DAY1.slots[3], end: '2026-09-10T20:00:00+02:00' }, NOW) === 'mine_past');
ok('my reservation still to come stays cancellable', H.slotState(DAY1.slots[3], NOW) === 'mine');

let axis = H.buildAxis(DAY1.slots);
ok('hourly axis when every slot is on the hour', axis.step === 60 && axis.start === 19 * 60 && axis.end === 22 * 60 && axis.rows === 3);
axis = H.buildAxis(DAY2.slots);
ok('30-minute axis as soon as a slot is not on the hour', axis.step === 30 && axis.start === 10 * 60 && axis.end === 13 * 60 && axis.rows === 6);
axis = H.buildAxis(DAY1.slots, 20, 21);
ok('start_hour / end_hour clamp the axis', axis.start === 20 * 60 && axis.end === 21 * 60 && axis.rows === 1);
ok('sortedJson is key-order independent', H.sortedJson({ b: 1, a: [{ d: 2, c: 3 }] }) === H.sortedJson({ a: [{ c: 3, d: 2 }], b: 1 }));
ok('french strings', H.t({ language: 'fr' }, {}, 'book') === 'Réserver' && H.t({ language: 'fr' }, { language: 'en' }, 'book') === 'Book');

// ── 2. rendering ─────────────────────────────────────────────────────────────
{
  const card = await makeCard({ days: 2 });
  const html = card._markup(NOW);
  contains('title falls back to the club name', html, 'DEMO (TENNIS CLUB)');
  contains('day tabs are rendered', html, 'data-action="day" data-index="1"');
  contains('the free count of the day tab counts only slots to come', html, '<span class="n">2</span>');
  contains('a free slot to come is bookable', html, 'data-action="book" data-court="21100" data-start="2026-09-10T21:00:00+02:00"');
  ok('a free slot that is over is not bookable', !html.includes('data-start="2026-09-10T19:00:00+02:00"'));
  contains('the over slot renders as past', html, 'class="cell past"');
  contains('a busy slot shows who booked it', html, 'T. HALE');
  contains('my slot can be cancelled', html, 'data-action="cancel" data-court="21099" data-start="2026-09-10T21:00:00+02:00"');
  contains('court headers', html, 'COURT 2');
  contains('updated time in the header', html, 'Updated 20:25');
}
{
  const card = await makeCard({ show_names: false });
  ok('show_names=false hides the names', !card._markup(NOW).includes('T. HALE'));
}
{
  const card = await makeCard({ courts: ['21100'] });
  const html = card._markup(NOW);
  ok('courts filter keeps only the listed court', html.includes('COURT 1') && !html.includes('COURT 2') && !html.includes('Court COUVERT'));
  contains('the free count follows the filter', html, '<span class="n">1</span>');
}
{
  const card = await makeCard({ days: 2, language: 'fr' });
  card._day = 1;
  const html = card._markup(NOW);
  contains('second day: the 30-minute grid spans rows', html, 'grid-template-rows:auto repeat(24, 22px)');
  contains('a 90-minute lesson spans three rows', html, 'grid-row:5 / 8');
  contains('french labels', html, 'Réserver');
}
{
  // A single half-hour booking on one day used to shrink that day's cells to 22px
  // while the other days stayed at 36px, so the grid jumped when switching tabs.
  // The axis is now built once over every displayed day.
  const rowsOf = (html) => (html.match(/grid-template-rows:[^"]*/) || [''])[0];
  const card = await makeCard({ days: 2 });
  card._day = 0; const d0 = card._markup(NOW);
  card._day = 1; const d1 = card._markup(NOW);
  ok('every day shares one row height', rowsOf(d0) === rowsOf(d1) && rowsOf(d0) !== '');
  contains('the shared axis keeps the 30-minute step of the busiest day', d0, 'grid-template-rows:auto repeat(24, 22px)');
  ok('the shared axis spans the union of the days (10:00 to 22:00)', (() => {
    const a = H.buildAxis([...DAY1.slots, ...DAY2.slots]);
    return a.start === 10 * 60 && a.end === 22 * 60 && a.step === 30 && a.rows === 24;
  })());
  contains('a 60-minute slot of the hourly day now spans two 30-minute rows', d0, 'grid-row:24 / 26');
  ok('start_hour still clamps the shared axis', (await (async () => {
    const c = await makeCard({ days: 2, start_hour: 20, end_hour: 22 });
    return c._markup(NOW).includes('grid-template-rows:auto repeat(4, 22px)');
  })()));
}

// ── 3. actions ───────────────────────────────────────────────────────────────
{
  const hass = makeHass();
  const card = await makeCard({}, hass);
  const free = card._findSlot('21100', '2026-09-10T21:00:00+02:00');
  card._request('book', free);
  ok('book asks for confirmation by default', card._pending && card._pending.kind === 'book');
  contains('the dialog names the court and the time', card._markup(NOW), 'Book COURT 1 on Thursday 10 September, 21:00 to 22:00?');
  await card._runPending();
  const call = hass.calls.find((c) => c.service === 'book');
  ok('book calls tenup.book with the court and the ISO start', call && call.domain === 'tenup' && call.data.court_id === '21100' && call.data.start === '2026-09-10T21:00:00+02:00');
  ok('the entry id of the planning is passed along', call.data.entry_id === 'entry-1');
  ok('a success toast is shown', card._toast && card._toast.kind === 'ok');
  ok('the dialog is closed', card._pending === null);
}
{
  const hass = makeHass();
  const card = await makeCard({ confirm: false, entry_id: 'entry-9' }, hass);
  const mine = card._findSlot('21099', '2026-09-10T21:00:00+02:00');
  card._request('cancel', mine);
  await new Promise((r) => setTimeout(r, 0));
  const call = hass.calls.find((c) => c.service === 'cancel');
  ok('confirm=false cancels straight away with the reservation id', call && call.data.reservation_id === '165841846');
  ok('a configured entry_id wins over the planning one', call.data.entry_id === 'entry-9');
}
{
  const hass = makeHass();
  hass.callService = async () => { throw { message: "Ten'Up: Réservation impossible. 1 en cours" }; };
  const card = await makeCard({ confirm: false }, hass);
  card._request('book', card._findSlot('21101', '2026-09-10T20:00:00+02:00'));
  await new Promise((r) => setTimeout(r, 0));
  ok('a refusal becomes an error toast with the Ten\'Up message', card._toast && card._toast.kind === 'err' && card._toast.text.includes('Réservation impossible'));
  contains('the error toast is rendered', card._markup(NOW), 'class="toast err"');
}
{
  let threw = false;
  try { new Card().setConfig(Object.freeze({ days: 0 })); } catch (e) { threw = true; }
  ok('days out of range is rejected', threw);
}

// ── 4. editor ────────────────────────────────────────────────────────────────
{
  const editor = new Editor();
  const events = [];
  editor.dispatchEvent = (ev) => { events.push(ev); return true; };
  editor.setConfig(Object.freeze({ days: 3 }));
  editor.hass = { language: 'en', callWS: async () => { throw new Error('no'); } };
  await new Promise((r) => setTimeout(r, 0));
  let builds = 0;
  const origRefresh = editor._refresh.bind(editor);
  editor._refresh = () => { builds++; origRefresh(); };
  editor._onChange({ name: 'Tennis', entry_id: '', days: 2, start_hour: 8, end_hour: '', courts: ['21100'], show_names: true, confirm: false, compact: false, language: 'auto' });
  const ev = events.find((e) => e.type === 'config-changed');
  ok('config-changed carries detail.config', ev && ev.detail && ev.detail.config);
  const cfg = ev.detail.config;
  ok('defaults are dropped, choices are kept', cfg.name === 'Tennis' && cfg.days === 2 && cfg.start_hour === 8 && cfg.end_hour === undefined && cfg.entry_id === undefined && cfg.confirm === false && cfg.show_names === undefined && cfg.language === undefined && JSON.stringify(cfg.courts) === '["21100"]');
  editor.setConfig(Object.freeze({ courts: ['21100'], confirm: false, name: 'Tennis', start_hour: 8, days: 2 }));   // HA echo, keys reordered
  ok('the echo of our own config does not rebuild the form', builds === 0);
  editor.setConfig(Object.freeze({ name: 'Other' }));
  ok('a real external change rebuilds the form', builds === 1);
}

// -- direct "Open on Ten'Up" link (option A) ------------------------------------
{
  const card = await makeCard({ days: 2 });
  const url = card._siteUrl();
  ok('site link uses club code + selected day', url === 'https://tenup.fft.fr/club/87654321/reservations/20260910');
  card._day = 1;
  ok('site link follows the day tab', card._siteUrl() === 'https://tenup.fft.fr/club/87654321/reservations/20260912');
  card._day = 0;
  contains('header shows an Open-on-Ten\'Up anchor to the site', card._markup(NOW), 'href="https://tenup.fft.fr/club/87654321/reservations/20260910"');
  contains('the site link opens in a new tab safely', card._markup(NOW), 'rel="noopener noreferrer"');
}
{
  const noData = new Card();
  noData.setConfig(Object.freeze({}));
  ok('no site link before data is known', noData._siteUrl() === null);
}
{
  const hass = makeHass();
  hass.callService = async () => { throw { message: "Ten'Up: Ce cr\u00e9neau demande 2 joueurs; l'ajout d'un partenaire n'est pas encore pris en charge" }; };
  const card = await makeCard({ confirm: false }, hass);
  card._request('book', card._findSlot('21099', '2026-09-10T21:00:00+02:00') || card._findSlot('21101', '2026-09-10T20:00:00+02:00'));
  await new Promise((r) => setTimeout(r, 0));
  const html = card._markup(NOW);
  contains('a refusal toast offers the direct site link', html, '<a href="https://tenup.fft.fr/club/87654321/reservations/20260910"');
  ok('the refusal keeps the Ten\'Up message', card._toast.kind === 'err' && /2 joueurs/.test(card._toast.text));
}

// -- 2-player courts flagged + linked to the site (option B) --------------------
{
  const card = await makeCard({ days: 1 });
  ok('site link for a date is built from the club code', card._siteUrlForDate('2026-09-11T08:00:00+02:00') === 'https://tenup.fft.fr/club/87654321/reservations/20260911');
  card._data = { ...DATA, days: [{ date: '2026-09-11', slots: [
    slot('21099', '2026-09-11T10:00:00+02:00', '2026-09-11T11:00:00+02:00', 'free', { required_players: 2 }),
    slot('21100', '2026-09-11T10:00:00+02:00', '2026-09-11T11:00:00+02:00', 'free', { required_players: 1 }),
    slot('21101', '2026-09-11T10:00:00+02:00', '2026-09-11T11:00:00+02:00', 'free', {}),
  ] }] };
  card._day = 0;
  const at = new Date('2026-09-11T08:00:00+02:00').getTime();
  const html = card._markup(at);
  contains('a 2-player free slot is now bookable from the grid', html, 'data-action="book2" data-court="21099"');
  ok('and is no longer a bare link to the site', !html.includes('two-players" style="grid-column:2;grid-row:2 / 3" href='));
  contains('the 2-player slot shows the badge', html, '2 players');
  ok('the 2-player slot is NOT bookable in-card', !html.includes('data-action="book" data-court="21099"'));
  contains('a 1-player free slot stays bookable in-card', html, 'data-action="book" data-court="21100"');
  ok('a slot with unknown player count stays bookable (fallback)', html.includes('data-action="book" data-court="21101"'));
}

// ── 5. redraws: the bug that swallowed the first click ───────────────────────
// Home Assistant assigns a fresh hass on every state change of the whole
// instance. The card used to rebuild its DOM on each one, so the cell being
// pressed was replaced between mousedown and mouseup and the browser never
// fired the click: tapping your own reservation appeared to do nothing.
function spyWrites(node) {
  const state = { writes: 0, html: node.innerHTML };
  Object.defineProperty(node, 'innerHTML', {
    configurable: true,
    get() { return state.html; },
    set(v) { state.writes++; state.html = String(v); },
  });
  return state;
}
{
  const hass = makeHass();
  const card = await makeCard({ days: 2 }, hass);
  const spy = spyWrites(card._card);
  card.hass = makeHass();               // a plain state change elsewhere in HA
  card.hass = makeHass();
  ok('a hass update does not rewrite the card DOM', spy.writes === 0);

  card._render();                        // nothing changed -> still no write
  ok('an unchanged render never touches the DOM', spy.writes === 0);

  card._day = 1; card._render();         // a real change -> exactly one write
  ok('a real change writes once', spy.writes === 1);
  card._render();
  ok('re-rendering the same view stays at one write', spy.writes === 1);
}
{
  // clicking your own slot must open the confirmation, and a hass update
  // arriving right after must not wipe it.
  const hass = makeHass();
  const card = await makeCard({ days: 2 }, hass);
  card._onClick({
    stopPropagation() {},
    target: { closest: () => ({ getAttribute: (k) => ({
      'data-action': 'cancel', 'data-court': '21099',
      'data-start': '2026-09-10T21:00:00+02:00',
    }[k]) }) },
  });
  ok('clicking your own slot asks for confirmation', card._pending && card._pending.kind === 'cancel');
  contains('the cancel dialog is rendered', card._markup(NOW), 'data-action="confirm"');
  const spy = spyWrites(card._card);
  card.hass = makeHass();
  ok('a hass update does not close the confirmation', card._pending !== null && spy.writes === 0);
}
{
  // a language switch is the one hass change the card must react to
  const card = await makeCard({ days: 2 }, makeHass('en'));
  const spy = spyWrites(card._card);
  card.hass = makeHass('fr');
  ok('a language change does redraw', spy.writes === 1);
}

// ── 6. cell styling: opaque fills, no washed-out transparency ────────────────
{
  const card = await makeCard({ days: 1 });
  const css = card.shadowRoot.children[0].textContent;
  ok('free cells are an opaque green', css.includes('.cell.free { background: #3d8a44;'));
  ok('2-player cells are an opaque amber', css.includes('.cell.free.two-players { background: #b08800;'));
  ok('booked cells are an opaque red', css.includes('.cell.busy { background: #a43434;'));
  ok('no washed-out fill is left', !/rgba\(76, 175, 80, 0\.18\)|rgba\(211, 47, 47, 0\.22\)|rgba\(255, 193, 7, 0\.22\)/.test(css));
  ok('long labels stay on one line', css.includes('.cell .lbl { white-space: nowrap;'));
}

// ── 7. the cell says what is happening while Ten'Up answers ─────────────────
{
  let release;
  const hass = makeHass();
  hass.callService = (domain, service, data) => {
    hass.calls.push({ domain, service, data });
    return new Promise((r) => { release = r; });
  };
  const card = await makeCard({ days: 2, language: 'fr' }, hass);
  const mine = card._findSlot('21099', '2026-09-10T21:00:00+02:00');
  card._request('cancel', mine);
  contains('la confirmation est demandee d\'abord', card._markup(NOW), 'data-action="confirm"');

  card._runPending();                       // not awaited: we look mid-flight
  await new Promise((r) => setTimeout(r, 0));
  const mid = card._markup(NOW);
  ok('la boite de dialogue se ferme des la confirmation', !mid.includes('data-action="confirm"'));
  contains('la case passe en attente', mid, 'class="cell pending"');
  contains('elle annonce une annulation', mid, 'Annulation');
  ok('la case en attente n\'est plus cliquable',
     !mid.includes('data-action="cancel" data-court="21099" data-start="2026-09-10T21:00:00+02:00"'));
  ok('une seule case est en attente', (mid.match(/class="cell pending"/g) || []).length === 1);
  contains('les autres cases sont intactes', mid, 'data-action="book" data-court="21100"');

  release({});
  await new Promise((r) => setTimeout(r, 0));
  await new Promise((r) => setTimeout(r, 0));
  const after = card._markup(NOW);
  ok('l\'attente est levee une fois la reponse revenue', !after.includes('class="cell pending"'));
  ok('le compte rendu est affiche', card._toast && card._toast.kind === 'ok');
}
{
  const hass = makeHass();
  const card = await makeCard({ days: 2, language: 'en' }, hass);
  card._inflight = { kind: 'book', court_id: '21100', start: '2026-09-10T21:00:00+02:00' };
  const html = card._markup(NOW);
  contains('a booking in flight says Booking', html, 'Booking');
  contains('and waits for Ten\u2019Up', html, 'waiting for Ten');
}

// ── 8. friends: colour, click to add, click to remove ───────────────────────
const F = Card._helpers;
ok('accents and case are ignored', F.fold('VAN DÝKE') === 'van dyke');
ok('a surname matches the Ten\'Up label', F.matchFriend('C. BLACKWELL', ['blackwell']) === 'blackwell');
ok('a double match works on either player', F.matchFriend('W. VAN DYKE C. STONE', ['Stone']) === 'Stone');
ok('a multi-word name matches', F.matchFriend('W. VAN DYKE C. STONE', ['van dyke']) === 'van dyke');
ok('no match returns null', F.matchFriend('R. DYER', ['blackwell']) === null);
ok('a partial word is NOT a match', F.matchFriend('R. DYER', ['said']) === null);
// club lessons are labelled with short standalone codes (MT, CJ, EDT):
// a two-letter entry would match one of them and paint the whole column.
ok('a two-letter entry is refused even on a word boundary', F.matchFriend('MT sam 9h30 Alex', ['MT']) === null);
ok('a three-letter entry is allowed', F.matchFriend('EDT sam 10h30 Alex', ['EDT']) === 'EDT');
ok('a first name in a lesson still matches if asked for', F.matchFriend('EDT sam 10h30 Alex', ['alex']) === 'alex');
ok('the initial is dropped from the suggestion', F.friendGuess('C. BLACKWELL') === 'BLACKWELL');
ok('a label without an initial is kept whole', F.friendGuess('EDT sam 10h30 Alex') === 'EDT sam 10h30 Alex');

{
  const hass = makeHass('fr');
  const ws = [];
  hass.callWS = async (msg) => {
    if (msg.type === 'tenup/friends/set') { ws.push(msg); return { friends: msg.friends }; }
    return { ...DATA, friends: ['HALE'] };
  };
  const card = await makeCard({ days: 2 }, hass);
  let html = card._markup(NOW);
  contains('a friend\'s booking is purple', html, 'class="cell busy friend"');
  contains('and opens the player list on tap', html, 'data-action="friend-open" data-label="T. HALE"');

  // a booking that is not a friend offers to add
  card._data.friends = [];
  html = card._markup(NOW);
  ok('a stranger is not purple', !html.includes('busy friend'));
  contains('a stranger can be followed', html, 'data-action="friend-open" data-label="T. HALE"');

  card._onClick({ stopPropagation() {}, target: { closest: () => ({ getAttribute: (k) => ({
    'data-action': 'friend-open', 'data-label': 'T. HALE' }[k]) }) } });
  ok('the dialog asks before following', card._pending && card._pending.kind === 'friend_pick');
  const pick = card._markup(NOW);
  contains('it offers this player alone', pick, 'data-action="friend-pick" data-friend="T. HALE"');
  contains('or everyone with the surname', pick, 'data-action="friend-pick" data-friend="HALE"');

  card._onClick({ stopPropagation() {}, target: { closest: () => ({ getAttribute: (k) => ({
    'data-action': 'friend-pick', 'data-friend': 'HALE' }[k]) }) } });
  await new Promise((r) => setTimeout(r, 0));
  ok('the list is sent to the integration', ws.length === 1 && ws[0].friends.join() === 'HALE');
  ok('the colours update without refetching the planning', card._data.friends.join() === 'HALE');
  ok('the dialog stays open for a second player', card._pending && card._pending.kind === 'friend_pick');
  ok('a confirmation is shown', card._toast && card._toast.kind === 'ok');

  await card._saveFriend({ kind: 'friend_del', name: 'HALE' });
  ok('removing sends the emptied list', ws.length === 2 && ws[1].friends.length === 0);
  ok('the cell is no longer purple', !card._markup(NOW).includes('busy friend'));
}
{
  const hass = makeHass('fr');
  let sent = 0;
  hass.callWS = async (msg) => { if (msg.type === 'tenup/friends/set') { sent++; return { friends: [] }; } return DATA; };
  const card = await makeCard({ days: 2 }, hass);
  await card._saveFriend({ kind: 'friend_add', name: 'ab' });
  ok('a name under 3 characters is refused before being sent', sent === 0);
  ok('and the dialog explains why', card._pending && card._pending.error === 'friend_short');
}
{
  // hiding the names must not leak them back through an attribute
  const card = await makeCard({ days: 2, show_names: false });
  card._data.friends = ['HALE'];
  const html = card._markup(NOW);
  ok('the raw label never reaches the markup', !html.includes('T. HALE'));
  ok('following is disabled when names are hidden', !html.includes('data-action="friend-add"'));
  contains('but a friend is still highlighted', html, 'class="cell busy friend"');
  ok('and no player list either, it would need the label', !html.includes('friend-open'));
}
{
  // Two players in one booking, one of them followed: the "J. KING M. MOORE" report.
  ok('two players are split', F.labelPlayers('J. KING M. MOORE').join('|') === 'J. KING|M. MOORE');
  ok('a single player stays one', F.labelPlayers('T. HALE').join('|') === 'T. HALE');
  ok('a compound surname is not cut', F.labelPlayers('W. VAN DYKE C. STONE').join('|') === 'W. VAN DYKE|C. STONE');
  ok('a double initial is one player', F.labelPlayers('J.P. MOSS').join('|') === 'J.P. MOSS');
  ok('a club lesson is not a list of players', F.labelPlayers('EDT sam 10h30 Alex').length === 0);
  ok('the suggestion no longer glues two players', F.friendGuess('J. KING M. MOORE') === 'KING');
  const pp = F.playerParts('J. KING');
  ok('a player splits into initial and surname', pp.initial === 'J' && pp.surname === 'KING' && pp.exact === 'J. KING');

  // homonyms: the initial narrows, the surname alone widens
  ok('the surname alone follows the son too', F.matchFriend('P. KING', ['KING']) === 'KING');
  ok('initial and surname leave the namesake out', F.matchFriend('P. KING', ['J. KING']) === null);

  const pair = slot('21100', '2026-09-10T21:00:00+02:00', '2026-09-10T22:00:00+02:00', 'busy', { label: 'J. KING M. MOORE' });
  const short = slot('21101', '2026-09-10T21:00:00+02:00', '2026-09-10T22:00:00+02:00', 'busy', { label: 'K. WU' });
  const lesson = slot('21099', '2026-09-10T21:00:00+02:00', '2026-09-10T22:00:00+02:00', 'busy', { label: 'EDT jeu 21h Alex' });
  const state = { friends: ['MOORE'] };
  const hass = makeHass('fr');
  hass.sent = [];
  hass.callWS = async (msg) => {
    if (msg.type === 'tenup/friends/set') { hass.sent.push(msg.friends); state.friends = msg.friends; return { friends: msg.friends }; }
    return { ...DATA, days: [{ date: '2026-09-10', slots: [pair, short, lesson] }], friends: state.friends };
  };
  const tap = (card, attrs) => card._onClick({ stopPropagation() {}, target: { closest: () => ({ getAttribute: (k) => attrs[k] }) } });
  const card = await makeCard({ days: 1 }, hass);
  const html = card._markup(NOW);
  contains('one friend out of two is enough for purple', html, 'class="cell busy friend"');
  contains('the pair opens the player list', html, 'data-action="friend-open" data-label="J. KING M. MOORE"');
  contains('a club lesson keeps the free field', html, 'data-action="friend-add" data-label="EDT jeu 21h Alex"');

  tap(card, { 'data-action': 'friend-open', 'data-label': 'J. KING M. MOORE' });
  let dlg = card._markup(NOW);
  contains('the followed player shows as a chip', dlg, 'data-action="friend-unpick" data-friend="MOORE"');
  contains('the other one can be followed alone', dlg, 'data-action="friend-pick" data-friend="J. KING"');
  contains('or with the whole surname', dlg, 'data-action="friend-pick" data-friend="KING"');
  ok('the glued suggestion is gone', !dlg.includes('data-friend="KING M. MOORE"'));
  const prows = dlg.match(/<div class="prow">[\s\S]*?<\/div>/g) || [];
  const pall = (dlg.match(/<div class="pall">[\s\S]*?<\/div>/) || [''])[0];
  ok('the whole-surname button is not beside a player', prows.length === 2 && !prows.some((r) => r.includes('data-friend="KING"')));
  contains('it sits under the list instead', pall, 'data-action="friend-pick" data-friend="KING"');
  ok('a surname already followed is not offered again', !dlg.includes('data-action="friend-pick" data-friend="MOORE"'));

  tap(card, { 'data-action': 'friend-pick', 'data-friend': 'J. KING' });
  await new Promise((r) => setTimeout(r, 0));
  ok('following the second player keeps the first', hass.sent.length === 1 && hass.sent[0].join('|') === 'MOORE|J. KING');
  ok('the list stays open', card._pending && card._pending.kind === 'friend_pick');
  contains('and both now show as followed', card._markup(NOW), 'data-action="friend-unpick" data-friend="J. KING"');

  tap(card, { 'data-action': 'friend-unpick', 'data-friend': 'MOORE' });
  await new Promise((r) => setTimeout(r, 0));
  ok('a chip removes only that player', hass.sent.length === 2 && hass.sent[1].join('|') === 'J. KING');
  contains('the pair stays purple through the other friend', card._markup(NOW), 'class="cell busy friend"');

  tap(card, { 'data-action': 'friend-open', 'data-label': 'K. WU' });
  dlg = card._markup(NOW);
  contains('a short surname can still be followed with its initial', dlg, 'data-friend="K. WU"');
  ok('but not bare, it would paint the lessons', !dlg.includes('data-friend="LY"'));
}

{
  // Father and son: one surname, two initials. The surname is offered once, under the list.
  const twins = slot('21100', '2026-09-10T21:00:00+02:00', '2026-09-10T22:00:00+02:00', 'busy', { label: 'P. WOOD L. WOOD' });
  const hass = makeHass('fr');
  hass.callWS = async () => ({ ...DATA, days: [{ date: '2026-09-10', slots: [twins] }], friends: ['P. WOOD'] });
  const card = await makeCard({ days: 1 }, hass);
  card._onClick({ stopPropagation() {}, target: { closest: () => ({ getAttribute: (k) => ({ 'data-action': 'friend-open', 'data-label': 'P. WOOD L. WOOD' }[k]) }) } });
  const dlg = card._markup(NOW);
  contains('the followed father keeps his purple chip', dlg, 'data-action="friend-unpick" data-friend="P. WOOD"');
  contains('the son can be followed alone', dlg, 'data-action="friend-pick" data-friend="L. WOOD"');
  ok('the shared surname is offered once', dlg.split('data-friend="WOOD"').length - 1 === 1);
}

{
  // 11:00-12:00 is over at 12:39: still ours on the grid, but no cancel any more.
  const over = slot('21099', '2026-09-10T19:00:00+02:00', '2026-09-10T20:00:00+02:00', 'mine', { label: 'J. PUBLIC', reservation_id: '1' });
  const soon = slot('21100', '2026-09-10T21:00:00+02:00', '2026-09-10T22:00:00+02:00', 'mine', { label: 'J. PUBLIC', reservation_id: '2' });
  const hass = makeHass('fr');
  hass.callWS = async () => ({ ...DATA, days: [{ date: '2026-09-10', slots: [over, soon] }], friends: [] });
  const card = await makeCard({ days: 1 }, hass);
  const html = card._markup(NOW);
  const cellOver = (html.match(/<div class="cell mine-past"[^>]*>/) || [''])[0];
  ok('a finished reservation of mine is drawn dark blue', cellOver !== '');
  ok('and cannot be tapped', cellOver !== '' && !cellOver.includes('data-action'));
  ok('it is not offered for cancelling', !html.includes('data-action="cancel" data-court="21099"'));
  contains('it still says it was mine', html, 'mine-past" style=');
  contains('one still to come keeps its cancel', html, 'data-action="cancel" data-court="21100" data-start="2026-09-10T21:00:00+02:00"');
}

// ── 9. the friends manager, reachable from the card header ──────────────────
function friendHass(state) {
  const hass = makeHass('fr');
  hass.sent = [];
  hass.callWS = async (msg) => {
    if (msg.type === 'tenup/friends/set') { hass.sent.push(msg.friends); state.friends = msg.friends; return { friends: msg.friends }; }
    return { ...DATA, friends: state.friends };
  };
  return hass;
}
const click = (card, attrs) => card._onClick({
  stopPropagation() {},
  target: { closest: () => ({ getAttribute: (k) => attrs[k] }) },
});
{
  const state = { friends: ['HALE', 'DYER'] };
  const card = await makeCard({ days: 2 }, friendHass(state));
  const head = card._markup(NOW);
  contains('the header offers the friends list', head, 'data-action="friends"');
  contains('and shows how many are followed', head, '<span class="badge">2</span>');

  click(card, { 'data-action': 'friends' });
  const dlg = card._markup(NOW);
  contains('each friend is a chip', dlg, 'data-action="friend-drop" data-friend="HALE"');
  contains('the second one too', dlg, 'data-friend="DYER"');
  contains('a field allows adding one', dlg, 'data-action="friend-push"');

  click(card, { 'data-action': 'friend-drop', 'data-friend': 'DYER' });
  await new Promise((r) => setTimeout(r, 0));
  ok('removing a chip sends the shortened list', card._hass.sent.length === 1 && card._hass.sent[0].join() === 'HALE');
  ok('the manager stays open to chain changes', card._pending && card._pending.kind === 'friends');
  contains('and the removed chip is gone', card._markup(NOW), 'data-friend="HALE"');
  ok('the other chip really left', !card._markup(NOW).includes('data-friend="DYER"'));
}
{
  const state = { friends: [] };
  const card = await makeCard({ days: 2 }, friendHass(state));
  click(card, { 'data-action': 'friends' });
  contains('an empty list says so', card._markup(NOW), 'Personne');
  ok('no badge when nobody is followed', !card._markup(NOW).includes('class="badge"'));

  card._friendInput = () => 'ab';               // too short, typed in the manager
  click(card, { 'data-action': 'friend-push' });
  ok('a short name is not sent from the manager', card._hass.sent.length === 0);
  ok('and the manager explains why', card._pending.kind === 'friends' && card._pending.error === 'friend_short');

  card._friendInput = () => 'BLACKWELL';
  click(card, { 'data-action': 'friend-push' });
  await new Promise((r) => setTimeout(r, 0));
  ok('a valid name is sent', card._hass.sent.length === 1 && card._hass.sent[0].join() === 'BLACKWELL');
  ok('the manager stays open', card._pending && card._pending.kind === 'friends');
}

// -- 2-player booking: pick a partner from the grid ---------------------------
{
  const two = slot('21099', '2026-09-11T10:00:00+02:00', '2026-09-11T11:00:00+02:00', 'free', { required_players: 2 });
  const one = slot('21100', '2026-09-11T10:00:00+02:00', '2026-09-11T11:00:00+02:00', 'free', { required_players: 1 });
  const ws = [];
  const hass = makeHass('fr');
  hass.callWS = async (msg) => {
    ws.push(msg);
    if (msg.type === 'tenup/partner/search') {
      return { results: [
        { choice: 'Eric DOE (222222222)', name: 'Eric DOE' },
        { choice: 'John DOE (111111111)', name: 'John DOE' },
      ] };
    }
    return { ...DATA, days: [{ date: '2026-09-11', slots: [two, one] }] };
  };
  const card = await makeCard({ days: 1 }, hass);

  click(card, { 'data-action': 'book2', 'data-court': '21099', 'data-start': '2026-09-11T10:00:00+02:00' });
  ok('tapping a 2-player slot asks who you play with', card._pending && card._pending.kind === 'partner_pick');
  const dlg = card._markup(NOW);
  contains('the dialog offers a search field', dlg, 'id="tenup-partner"');
  contains('and a search button', dlg, 'data-action="partner-search"');
  contains('the site stays reachable as a way out', dlg, 'href="https://tenup.fft.fr/club/87654321/reservations/20260911"');

  const before = ws.length;
  card._pending = { kind: 'partner_pick', slot: two, query: 'ab' };
  click(card, { 'data-action': 'partner-search' });
  await new Promise((r) => setTimeout(r, 0));
  ok('a search under 3 letters is not sent', ws.length === before);
  ok('and the dialog says why', card._pending && card._pending.error === 'partner_short');

  card._pending = { kind: 'partner_pick', slot: two, query: 'DOE' };
  click(card, { 'data-action': 'partner-search' });
  await new Promise((r) => setTimeout(r, 0));
  const sent = ws.filter((m) => m.type === 'tenup/partner/search');
  ok('a real search reaches the integration', sent.length === 1 && sent[0].query === 'DOE');
  ok('and carries the entry it belongs to', sent[0].entry_id === 'entry-1');
  ok('both homonyms come back', card._pending.results && card._pending.results.length === 2);
  const list = card._markup(NOW);
  contains('each one is offered by name', list, 'John DOE');
  contains('the father is there too', list, 'Eric DOE');
  contains('the button carries the exact key, not the display name', list, 'data-choice="John DOE (111111111)"');

  click(card, { 'data-action': 'partner-pick', 'data-choice': 'John DOE (111111111)' });
  await new Promise((r) => setTimeout(r, 0));
  const booked = hass.calls.filter((c) => c.service === 'book');
  ok('booking is sent once', booked.length === 1);
  ok('it names the partner by his exact key', booked[0].data.partner === 'John DOE (111111111)');
  ok('on the right court and slot', booked[0].data.court_id === '21099' && booked[0].data.start === '2026-09-11T10:00:00+02:00');
}
{
  const one = slot('21100', '2026-09-11T10:00:00+02:00', '2026-09-11T11:00:00+02:00', 'free', { required_players: 1 });
  const hass = makeHass('fr');
  hass.callWS = async () => ({ ...DATA, days: [{ date: '2026-09-11', slots: [one] }] });
  const card = await makeCard({ days: 1 }, hass);
  click(card, { 'data-action': 'book', 'data-court': '21100', 'data-start': '2026-09-11T10:00:00+02:00' });
  click(card, { 'data-action': 'confirm' });
  await new Promise((r) => setTimeout(r, 0));
  const booked = hass.calls.filter((c) => c.service === 'book');
  ok('a single-player booking is still sent', booked.length === 1);
  ok('and carries no partner at all', !('partner' in booked[0].data));
}

// -- remembering a partner, and colouring from a stored booking key -----------
ok('a stored booking key still colours the grid', H.matchFriend('J. DOE', ['John DOE (111111111)']) === 'John DOE (111111111)');
ok('it colours a two-player booking too', H.matchFriend('J. DOE E. DOE', ['John DOE (111111111)']) === 'John DOE (111111111)');
// A key names ONE person: his son must stay uncoloured, while a bare surname still covers the family.
ok('a key does not colour the son', H.matchFriend('E. DOE', ['John DOE (111111111)']) === null);
ok('a bare surname still covers the family', H.matchFriend('E. DOE', ['DOE']) === 'DOE');
ok('a plain surname keeps working', H.matchFriend('J. DOE', ['DOE']) === 'DOE');
ok('the old abbreviated form keeps working', H.matchFriend('J. DOE', ['J. DOE']) === 'J. DOE');
ok('an unrelated key does not colour', H.matchFriend('J. DOE', ['Richard ROE (1234)']) === null);

{
  const two = slot('21099', '2026-09-11T10:00:00+02:00', '2026-09-11T11:00:00+02:00', 'free', { required_players: 2 });
  const ws = [];
  // 'DOE' est stocke sans identifiant: il colore la grille mais ne peut pas
  // servir a reserver (John ou Eric ?), donc pas d'acces rapide pour lui.
  const state = { friends: ['John DOE (111111111)', 'DOE'] };
  const hass = makeHass('fr');
  hass.callWS = async (msg) => {
    ws.push(msg);
    if (msg.type === 'tenup/partner/search') {
      return { results: [
        { choice: 'John DOE (111111111)', name: 'John DOE' },
        { choice: 'Eric DOE (222222222)', name: 'Eric DOE' },
      ] };
    }
    if (msg.type === 'tenup/friends/set') { state.friends = msg.friends; return { friends: msg.friends }; }
    return { ...DATA, days: [{ date: '2026-09-11', slots: [two] }], friends: state.friends };
  };
  const card = await makeCard({ days: 1 }, hass);

  click(card, { 'data-action': 'book2', 'data-court': '21099', 'data-start': '2026-09-11T10:00:00+02:00' });
  const dlg = card._markup(NOW);
  contains('a known partner is offered without searching', dlg, 'data-action="partner-pick" data-choice="John DOE (111111111)"');
  contains('and shown the way the grid writes it, not as the raw key', dlg, '>J. DOE<');
  ok('a friend stored without an identifier is not offered for booking',
     (dlg.match(/data-action="partner-pick"/g) || []).length === 1);

  card._pending = { kind: 'partner_pick', slot: two, query: 'DOE' };
  click(card, { 'data-action': 'partner-search' });
  await new Promise((r) => setTimeout(r, 0));
  const list = card._markup(NOW);
  contains('an unknown partner can be remembered', list, 'data-action="partner-remember" data-choice="Eric DOE (222222222)"');
  ok('one already stored is not offered again', !list.includes('data-action="partner-remember" data-choice="John DOE (111111111)"'));

  const bookedBefore = hass.calls.filter((c) => c.service === 'book').length;
  click(card, { 'data-action': 'partner-remember', 'data-choice': 'Eric DOE (222222222)', 'data-name': 'Eric DOE' });
  await new Promise((r) => setTimeout(r, 0));
  const sent = ws.filter((m) => m.type === 'tenup/friends/set');
  ok('remembering sends the full booking key', sent.length === 1 && sent[0].friends.includes('Eric DOE (222222222)'));
  ok('it keeps the partner already stored', sent[0].friends.includes('John DOE (111111111)'));
  ok('and keeps a bare surname, which covers the whole family', sent[0].friends.includes('DOE'));
  // Remembering someone must never book with them.
  ok('remembering does NOT book', hass.calls.filter((c) => c.service === 'book').length === bookedBefore);
}

// -- remembering replaces the shorter entries for that same person ------------
{
  const two = slot('21099', '2026-09-11T10:00:00+02:00', '2026-09-11T11:00:00+02:00', 'free', { required_players: 2 });
  const ws = [];
  // "J. DOE" is John; "DOE" stands for the family and must survive.
  const state = { friends: ['J. DOE', 'DOE', 'Richard ROE (1234)'] };
  const hass = makeHass('fr');
  hass.callWS = async (msg) => {
    ws.push(msg);
    if (msg.type === 'tenup/partner/search') return { results: [{ choice: 'John DOE (111111111)', name: 'John DOE' }] };
    if (msg.type === 'tenup/friends/set') { state.friends = msg.friends; return { friends: msg.friends }; }
    return { ...DATA, days: [{ date: '2026-09-11', slots: [two] }], friends: state.friends };
  };
  const card = await makeCard({ days: 1 }, hass);
  card._pending = { kind: 'partner_pick', slot: two, query: 'Do' };
  click(card, { 'data-action': 'partner-search' });
  await new Promise((r) => setTimeout(r, 0));
  click(card, { 'data-action': 'partner-remember', 'data-choice': 'John DOE (111111111)', 'data-name': 'John DOE' });
  await new Promise((r) => setTimeout(r, 0));
  const out = ws.filter((m) => m.type === 'tenup/friends/set').pop().friends;
  ok('the abbreviated entry for the same person is replaced', !out.includes('J. DOE'));
  ok('the booking key is there', out.includes('John DOE (111111111)'));
  ok('the family surname is untouched', out.includes('DOE'));
  ok('another member is untouched', out.includes('Richard ROE (1234)'));
  ok('one entry per person', out.length === 3);
}

// ---------------------------------------------------------------------------
// shipped with the integration: a second copy must not fight the first
// ---------------------------------------------------------------------------
{
  const CARD_PATH = join(HERE, '..', '..', 'custom_components', 'tenup', 'ha-tenup-card.js');
  ok('the bundle sits where the integration serves it from', existsSync(CARD_PATH));

  // Someone upgrading still has the standalone card's Lovelace resource until
  // the integration removes it, so this file is loaded twice in one page.
  let threw = null;
  let loaded;
  try {
    loaded = await loadCardTwice(CARD_PATH);
  } catch (err) {
    threw = err;
  }
  ok('loading it twice does not throw', threw === null);
  if (loaded) {
    ok('the first copy keeps the element', loaded.registry.get('ha-tenup-card') === loaded.first.get('ha-tenup-card'));
    ok('the first copy keeps the editor', loaded.registry.get('ha-tenup-card-editor') === loaded.first.get('ha-tenup-card-editor'));
    const mine = (globalThis.window.customCards || []).filter((c) => c.type === 'ha-tenup-card');
    ok('the card picker lists it once', mine.length === 1);
    ok('the picker points at the integration', mine[0].documentationURL.endsWith('/ha-tenup-resa'));
  }
}

report();
