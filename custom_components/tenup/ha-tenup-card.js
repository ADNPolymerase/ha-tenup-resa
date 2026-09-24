const CARD_VERSION = "1.1.0";

console.info(
  "%c HA-TENUP-CARD %c v" + CARD_VERSION + " ",
  "color:white;background:#1b1464;font-weight:700;",
  "color:#1b1464;background:white;font-weight:700;"
);

// ---------------------------------------------------------------------------
// i18n
// NOTE: this file is intentionally pure ASCII -- every non-ASCII character
// is written as a \uXXXX escape so the card renders correctly no matter
// which charset the resource is served with.
// ---------------------------------------------------------------------------

const T = {
  en: {
    book: "Book", cancel: "Cancel", you: "You", free: "Free", busy: "Booked", past: "Past",
    confirm_book: "Book {court} on {date}, {start} to {end}?",
    confirm_cancel: "Cancel your reservation on {court}, {date} at {start}?",
    yes_book: "Book", yes_cancel: "Cancel the reservation", back: "Back",
    booked: "Reservation confirmed", cancelled: "Reservation cancelled",
    refused: "Ten'Up refused: {message}", failed: "Ten'Up could not be reached: {message}",
    loading: "Loading the planning\u2026",
    no_data: "No planning yet. Is the Ten'Up integration configured?",
    updated: "Updated", refresh: "Refresh", today: "Today", tomorrow: "Tomorrow",
    free_count: "{n} free", working: "Please wait\u2026", open_site: "Open on Ten\u2019Up", two_players: "2 players", two_players_hint: "2 players, pick a partner",
    partner_title: "Who are you playing with on {court}, {start} to {end}?",
    partner_ph: "Surname, at least 3 letters", partner_search: "Search", partner_searching: "Searching\u2026",
    partner_none: "No club member found", partner_short: "Type at least 3 letters",
    partner_hint: "Only a club member can be added at no cost.",
    partner_known: "Your usual partners", partner_remember: "Remember",
    partner_remembered: "{name} added to your friends",
    cancelling: "Cancelling", booking: "Booking", in_progress: "waiting for Ten\u2019Up\u2026",
    friend_add: "Follow this player?", friend_del: "Stop following {name}?",
    yes_friend_add: "Add to friends", yes_friend_del: "Remove",
    friend_added: "{name} added to your friends", friend_removed: "{name} removed from your friends",
    friend_short: "Too short to be safe: at least 3 characters", friends: "Friends",
    friends_manage: "Friends followed", friends_none: "Nobody followed yet.",
    friend_new: "Surname", add: "Add", close: "Close",
    friends_hint: "Their bookings show in purple. You can also tap a booking on the grid.",
    friend_pick: "Follow a player", friend_all: "Every {name}",
    friend_pick_hint: "With the initial, only this player. The surname alone follows everyone who has it, family and namesakes included.",
    // editor
    name: "Title", entry_id: "Club (Ten'Up entry)", entry_auto: "First configured club",
    days: "Days shown (1 to 7)", start_hour: "First hour shown", end_hour: "Last hour shown",
    courts: "Courts shown (empty = all)", show_names: "Show who booked the busy slots",
    confirm: "Ask for confirmation before booking or cancelling", compact: "Compact cells",
    language: "Language", language_auto: "Follow Home Assistant",
  },
  fr: {
    book: "R\u00e9server", cancel: "Annuler", you: "Vous", free: "Libre", busy: "Occup\u00e9", past: "Pass\u00e9",
    confirm_book: "R\u00e9server {court} le {date} de {start} \u00e0 {end} ?",
    confirm_cancel: "Annuler votre r\u00e9servation sur {court}, {date} \u00e0 {start} ?",
    yes_book: "R\u00e9server", yes_cancel: "Annuler la r\u00e9servation", back: "Retour",
    booked: "R\u00e9servation confirm\u00e9e", cancelled: "R\u00e9servation annul\u00e9e",
    refused: "Ten'Up a refus\u00e9 : {message}", failed: "Ten'Up injoignable : {message}",
    loading: "Chargement du planning\u2026",
    no_data: "Pas encore de planning. L'int\u00e9gration Ten'Up est-elle configur\u00e9e ?",
    updated: "Mis \u00e0 jour", refresh: "Actualiser", today: "Aujourd'hui", tomorrow: "Demain",
    free_count: "{n} libre(s)", working: "Veuillez patienter\u2026", open_site: "Ouvrir sur Ten\u2019Up", two_players: "2 joueurs", two_players_hint: "2 joueurs, choisir un partenaire",
    partner_title: "Avec qui jouez-vous sur {court}, de {start} \u00e0 {end} ?",
    partner_ph: "Nom, au moins 3 lettres", partner_search: "Chercher", partner_searching: "Recherche\u2026",
    partner_none: "Aucun adh\u00e9rent trouv\u00e9", partner_short: "Tapez au moins 3 lettres",
    partner_hint: "Seul un adh\u00e9rent du club peut \u00eatre ajout\u00e9 sans frais.",
    partner_known: "Vos partenaires habituels", partner_remember: "Retenir",
    partner_remembered: "{name} ajout\u00e9 \u00e0 vos amis",
    cancelling: "Annulation", booking: "R\u00e9servation", in_progress: "en cours\u2026",
    friend_add: "Suivre ce joueur ?", friend_del: "Ne plus suivre {name} ?",
    yes_friend_add: "Ajouter aux amis", yes_friend_del: "Retirer",
    friend_added: "{name} ajout\u00e9 \u00e0 vos amis", friend_removed: "{name} retir\u00e9 de vos amis",
    friend_short: "Trop court pour \u00eatre s\u00fbr : 3 caract\u00e8res minimum", friends: "Amis",
    friends_manage: "Amis suivis", friends_none: "Personne pour l\u2019instant.",
    friend_new: "Nom de famille", add: "Ajouter", close: "Fermer",
    friends_hint: "Leurs r\u00e9servations apparaissent en violet. Vous pouvez aussi cliquer une r\u00e9servation sur la grille.",
    friend_pick: "Suivre un joueur", friend_all: "Tous les {name}",
    friend_pick_hint: "Avec l\u2019initiale : ce joueur seulement. Le nom seul suit tous ceux qui le portent, famille et homonymes compris.",
    name: "Titre", entry_id: "Club (entr\u00e9e Ten'Up)", entry_auto: "Premier club configur\u00e9",
    days: "Jours affich\u00e9s (1 \u00e0 7)", start_hour: "Premi\u00e8re heure affich\u00e9e", end_hour: "Derni\u00e8re heure affich\u00e9e",
    courts: "Courts affich\u00e9s (vide = tous)", show_names: "Afficher qui a r\u00e9serv\u00e9 les cr\u00e9neaux occup\u00e9s",
    confirm: "Demander confirmation avant de r\u00e9server ou d'annuler", compact: "Cellules compactes",
    language: "Langue", language_auto: "Suivre Home Assistant",
  },
};

function langOf(hass, config) {
  const wanted = config && config.language && config.language !== "auto" ? config.language : (hass && hass.language) || "en";
  const short = String(wanted).slice(0, 2).toLowerCase();
  return T[short] ? short : "en";
}

function t(hass, config, key, vars) {
  const l = langOf(hass, config);
  let s = (T[l] && T[l][key]) || T.en[key] || key;
  if (vars) for (const k of Object.keys(vars)) s = s.split("{" + k + "}").join(String(vars[k]));
  return s;
}

function esc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

// ---------------------------------------------------------------------------
// Pure helpers (also used by the tests)
// ---------------------------------------------------------------------------

/** Minutes since local midnight of an ISO date string. */
function minutesOf(iso) {
  const d = new Date(iso);
  return d.getHours() * 60 + d.getMinutes();
}

function hhmm(iso) {
  const m = minutesOf(iso);
  return String(Math.floor(m / 60)).padStart(2, "0") + ":" + String(m % 60).padStart(2, "0");
}

/** "past" when the slot is over, otherwise the state Ten'Up gave. */
function slotState(slot, now) {
  const end = new Date(slot.end).getTime();
  // A booking of ours that is over stays ours on the grid, but there is nothing left
  // to cancel: Ten'Up can still print the link, the card must not offer it.
  if (end <= now) return slot.state === "mine" ? "mine_past" : "past";
  return slot.state;
}

/**
 * The time axis of one day: first minute, last minute and the row step
 * (30 minutes as soon as one slot is not aligned on the hour).
 */
function fold(value) {
  return String(value === undefined || value === null ? "" : value)
    .normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
}

/** The friend this booking belongs to, or null. Whole words, accents ignored. */
// A friend may now be stored as the booking key, "John DOE (111111111)".
// The grid only ever writes the initial ("J. DOE"), so colour on the
// surname: the full name would never match, and the id even less.
const FRIEND_KEY = /^(.+?)\s*\((\d+)\)\s*$/;
function friendNeedle(friend) {
  const text = String(friend === undefined || friend === null ? "" : friend).trim();
  const keyed = FRIEND_KEY.exec(text);
  if (!keyed) return text;
  const words = keyed[1].trim().split(/\s+/);
  if (words.length < 2) return words[0] || text;
  // Ten'Up writes "J. DOE" in the grid. Match that person rather than the
  // surname alone, which would also colour his son's bookings.
  return words[0].charAt(0).toUpperCase() + ". " + words.slice(1).join(" ");
}

/**
 * Does a stored friend designate the same person as this booking key?
 * "J. DOE" and "John DOE" do; a bare "DOE" does not, since it
 * stands for the whole family and dropping it would lose Eric's colour.
 */
function samePerson(friend, choice) {
  const stored = fold(String(friend === undefined || friend === null ? "" : friend).trim());
  const key = String(choice === undefined || choice === null ? "" : choice).trim();
  if (!stored || !key) return false;
  const keyed = FRIEND_KEY.exec(key);
  if (stored === fold(key)) return true;
  if (!keyed) return false;
  return stored === fold(friendNeedle(key)) || stored === fold(keyed[1].trim());
}

/** The booking key of a stored friend, or null when it holds only a name. */
function friendKey(friend) {
  const text = String(friend === undefined || friend === null ? "" : friend).trim();
  return FRIEND_KEY.test(text) ? text : null;
}

function matchFriend(label, friends) {
  if (!label || !friends || !friends.length) return null;
  const hay = fold(label);
  for (const friend of friends) {
    const needle = fold(friendNeedle(friend)).trim();
    if (needle.length < 3) continue;
    const body = needle.replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/\s+/g, "[^a-z0-9]+");
    if (new RegExp("(^|[^a-z0-9])" + body + "($|[^a-z0-9])").test(hay)) return friend;
  }
  return null;
}

// A player as Ten'Up writes them: an initial ("J", "J.P", "J-P"), a dot, a surname.
const PLAYER_HEAD = /^[A-Z\u00c0-\u00dd](?:[.-]?[A-Z\u00c0-\u00dd])*\.\s*/;
const PLAYER_SPLIT = /\s(?=[A-Z\u00c0-\u00dd](?:[.-]?[A-Z\u00c0-\u00dd])*\.\s)/;

/**
 * The players of a booking: "J. KING M. MOORE" gives ["J. KING", "M. MOORE"].
 * A club lesson ("EDT sam 10h30 Alex") is not a list of players: [].
 */
function labelPlayers(label) {
  const text = String(label === undefined || label === null ? "" : label).replace(/\s+/g, " ").trim();
  if (!text) return [];
  const parts = text.split(PLAYER_SPLIT);
  return parts.every((p) => PLAYER_HEAD.test(p) && p.replace(PLAYER_HEAD, "").trim()) ? parts : [];
}

/** One player, split into what can be followed: just them, or their whole surname. */
function playerParts(player) {
  const text = String(player === undefined || player === null ? "" : player).trim();
  const head = text.match(PLAYER_HEAD);
  if (!head) return null;
  const surname = text.slice(head[0].length).trim();
  const initial = head[0].replace(/\.\s*$/, "");
  return surname ? { initial, surname, exact: initial + ". " + surname } : null;
}

/** Ten'Up writes "C. BLACKWELL": drop the initial, keep what identifies. */
function friendGuess(label) {
  const players = labelPlayers(label);
  if (players.length) return playerParts(players[0]).surname;
  return String(label === undefined || label === null ? "" : label).trim();
}

function buildAxis(slots, startHour, endHour) {
  let start = Infinity, end = -Infinity, step = 60;
  for (const s of slots) {
    const a = minutesOf(s.start);
    const b = a + Math.max(1, Math.round((new Date(s.end) - new Date(s.start)) / 60000));
    if (a < start) start = a;
    if (b > end) end = b;
    if (a % 60 !== 0 || (b - a) % 60 !== 0) step = 30;
  }
  if (!isFinite(start)) { start = 8 * 60; end = 22 * 60; }
  if (Number.isFinite(startHour)) start = Math.max(start, startHour * 60);
  if (Number.isFinite(endHour)) end = Math.min(end, endHour * 60);
  if (end <= start) end = start + 60;
  start = Math.floor(start / step) * step;
  end = Math.ceil(end / step) * step;
  return { start, end, step, rows: (end - start) / step };
}

function dayLabel(hass, config, dateIso) {
  const d = new Date(dateIso + "T12:00:00");
  const today = new Date(); today.setHours(12, 0, 0, 0);
  const diff = Math.round((d - today) / 86400000);
  const l = langOf(hass, config);
  const short = d.toLocaleDateString(l === "fr" ? "fr-FR" : "en-GB", { weekday: "short", day: "2-digit", month: "2-digit" });
  if (diff === 0) return t(hass, config, "today") + " " + short.replace(/^[^\d]*/, "");
  if (diff === 1) return t(hass, config, "tomorrow") + " " + short.replace(/^[^\d]*/, "");
  return short;
}

function longDate(hass, config, iso) {
  const l = langOf(hass, config);
  return new Date(iso).toLocaleDateString(l === "fr" ? "fr-FR" : "en-GB", { weekday: "long", day: "numeric", month: "long" });
}

function sortedJson(value) {
  if (Array.isArray(value)) return "[" + value.map(sortedJson).join(",") + "]";
  if (value && typeof value === "object") {
    return "{" + Object.keys(value).sort().map((k) => JSON.stringify(k) + ":" + sortedJson(value[k])).join(",") + "}";
  }
  return JSON.stringify(value);
}

const STYLE = `
  :host { display: block; }
  .wrap { padding: 12px 12px 8px; }
  .head { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; margin-bottom: 8px; }
  .head .title { font-size: 1.1em; font-weight: 600; }
  .head .sub { font-size: 0.8em; color: var(--secondary-text-color); display: flex; align-items: center; gap: 6px; }
  .head button.icon, .head a.icon { background: none; border: 0; cursor: pointer; color: var(--secondary-text-color); padding: 2px; line-height: 0; text-decoration: none; }
  .head button.icon ha-icon, .head a.icon ha-icon { --mdc-icon-size: 18px; }
  .tabs { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 10px; }
  .tab { border: 1px solid var(--divider-color); background: var(--card-background-color); color: var(--primary-text-color);
         border-radius: 16px; padding: 4px 12px; font-size: 0.85em; cursor: pointer; }
  .tab.active { background: var(--primary-color); color: var(--text-primary-color, #fff); border-color: var(--primary-color); }
  .tab .n { opacity: 0.7; margin-left: 4px; font-size: 0.9em; }
  .scroll { overflow-x: auto; }
  .grid { display: grid; gap: 2px; min-width: 100%; }
  .court { grid-row: 1; font-weight: 600; font-size: 0.8em; text-align: center; padding: 4px 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .time { grid-column: 1; font-size: 0.72em; color: var(--secondary-text-color); text-align: right; padding-right: 6px; line-height: 1; margin-top: -0.5em; }
  .cell { border-radius: 6px; font-size: 0.82em; display: flex; flex-direction: column; align-items: center; justify-content: center;
          text-align: center; padding: 2px 4px; overflow: hidden; line-height: 1.15; min-height: 0; }
  .cell span:first-child { font-weight: 600; letter-spacing: 0.01em; }
  .cell.free { background: #3d8a44; color: #f2fbf2; cursor: pointer; border: 1px solid #66bb6a; }
  .cell.free:hover { background: #4aa352; }
  .cell.free .hint { display: none; font-size: 0.85em; opacity: 0.9; font-weight: 400; }
  .cell.free:hover .hint { display: block; }
  .cell.free.two-players { background: #b08800; border: 1px solid #ffd54f; color: #fffaeb; cursor: pointer; text-decoration: none; }
  .cell.free.two-players:hover { background: #cba000; }
  .cell .badge2 { font-size: 0.68em; opacity: 0.9; white-space: nowrap; font-weight: 400; }
  .cell.busy { background: #a43434; color: #fdf1f1; border: 1px solid #ef7878; }
  .cell.busy { cursor: pointer; }
  .cell.busy:hover { background: #b93c3c; }
  .cell.friend { background: #6a3fa0; color: #f5eefc; border: 1px solid #b28ddb; cursor: pointer; }
  .cell.friend:hover { background: #7d4bbb; }
  .icon .badge { font-size: 0.62em; font-weight: 700; margin-left: 2px; vertical-align: super; opacity: 0.85; }
  .dialog .flist { display: flex; flex-wrap: wrap; gap: 6px; margin: 10px 0 4px; }
  .dialog .chip { display: inline-flex; align-items: center; gap: 6px; background: #6a3fa0; color: #f5eefc;
                  border: 1px solid #b28ddb; border-radius: 14px; padding: 3px 6px 3px 10px; font-size: 0.85em; cursor: pointer; }
  .dialog .chip:hover { background: #7d4bbb; }
  .dialog .chip .x { font-weight: 700; opacity: 0.85; }
  .dialog .plist { margin: 4px 0 2px; min-width: 260px; }
  .dialog .prow { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 8px 0; }
  .dialog .prow + .prow { border-top: 1px solid var(--divider-color); }
  .dialog .pname { font-weight: 600; white-space: nowrap; }
  .dialog .pacts { display: flex; flex-wrap: wrap; gap: 6px; justify-content: flex-end; }
  .dialog button.pick { padding: 5px 10px; font-size: 0.85em; }
  .dialog .pall { display: flex; flex-wrap: wrap; gap: 6px; justify-content: flex-end; padding-top: 10px; border-top: 1px solid var(--divider-color); }
  .dialog .hint { font-size: 0.82em; color: var(--secondary-text-color); margin-top: 8px; }
  .dialog .row { display: flex; gap: 8px; margin-top: 10px; }
  .dialog .row .fname { margin-top: 0; }
  .dialog .fname { width: 100%; box-sizing: border-box; margin-top: 10px; padding: 7px 9px;
                   border-radius: 6px; border: 1px solid var(--divider-color);
                   background: var(--card-background-color); color: var(--primary-text-color); font-size: 1em; }
  .cell.past { background: rgba(127, 127, 127, 0.14); color: var(--disabled-text-color); border: 1px solid var(--divider-color); }
  .cell.mine { background: #1565c0; color: #fff; cursor: pointer; border: 1px solid #64b5f6; }
  .cell.pending { background: #4a4a57; color: #f1f1f5; border: 1px solid #7b7b8b; cursor: progress;
                  animation: tenup-pulse 1.1s ease-in-out infinite; }
  .cell.pending .prog { font-size: 0.68em; font-weight: 400; line-height: 1.05; white-space: normal; }
  @keyframes tenup-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.58; } }
  .cell.mine .x { font-size: 0.85em; opacity: 0.9; font-weight: 400; }
  .cell.mine-past { background: #0d3c73; color: #c9dbf2; border: 1px solid #1f5391; cursor: default; }
  .cell.mine-past .x { font-size: 0.85em; opacity: 0.85; font-weight: 400; }
  .cell .lbl { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%; font-weight: 500; }
  .compact .cell { font-size: 0.7em; padding: 1px 2px; }
  .overlay { position: absolute; inset: 0; background: rgba(0,0,0,0.45); display: flex; align-items: center; justify-content: center; z-index: 2; border-radius: var(--ha-card-border-radius, 12px); }
  .dialog { background: var(--card-background-color); color: var(--primary-text-color); border-radius: 10px; padding: 16px 18px; max-width: 90%; box-shadow: 0 6px 24px rgba(0,0,0,0.35); }
  .dialog .msg { margin-bottom: 14px; }
  .dialog .btns { display: flex; gap: 8px; justify-content: flex-end; }
  .dialog button { border: 0; border-radius: 6px; padding: 8px 14px; cursor: pointer; font-weight: 600; }
  .dialog button.primary { background: var(--primary-color); color: var(--text-primary-color, #fff); }
  .dialog button.secondary { background: var(--secondary-background-color); color: var(--primary-text-color); }
  .dialog button.danger { background: var(--error-color, #db4437); color: #fff; }
  .toast { margin-top: 8px; padding: 8px 10px; border-radius: 6px; font-size: 0.85em; }
  .toast.ok { background: #2e7d32; color: #f2fbf2; }
  .toast.err { background: #b3261e; color: #fdecea; }
  .toast a { color: inherit; font-weight: 600; }
  .empty { color: var(--secondary-text-color); font-style: italic; padding: 12px 0; }
  ha-card { position: relative; overflow: hidden; }
`;

// ---------------------------------------------------------------------------
// Card
// ---------------------------------------------------------------------------

class TenupCard extends HTMLElement {
  static getStubConfig() {
    return { days: 3, confirm: true, show_names: true };
  }

  static getConfigElement() {
    return document.createElement("ha-tenup-card-editor");
  }

  constructor() {
    super();
    this._config = null;
    this._hass = null;
    this._data = null;
    this._day = 0;
    this._lastFetch = 0;
    this._fetching = false;
    this._pending = null;   // {kind: "book"|"cancel", slot}
    this._toast = null;     // {kind: "ok"|"err", text}
    this._busy = false;
    this._built = false;
    this._lastHtml = null;
    this._inflight = null;  // {kind, court_id, start} while Ten'Up is answering
  }

  setConfig(config) {
    if (!config || typeof config !== "object") throw new Error("Invalid configuration");
    const days = Number(config.days);
    if (config.days !== undefined && (!Number.isFinite(days) || days < 1 || days > 14)) {
      throw new Error("days must be between 1 and 14");
    }
    this._config = config;
    this._day = 0;
    this._render();
  }

  set hass(hass) {
    const prev = this._hass;
    this._hass = hass;
    if (!this._built) this._build();
    if (hass && (!this._data || Date.now() - this._lastFetch > 60000)) this._fetch();
    // Home Assistant assigns a fresh hass on every state change in the whole
    // instance, many times per second. Re-rendering here replaced the cell the
    // pointer was pressing, so the browser never completed the click and the
    // confirmation dialog did not open. Only render when something we show can
    // actually have changed; _fetch and the user actions render on their own.
    if (!prev || !hass || prev.language !== hass.language) this._render();
  }

  getCardSize() {
    return 10;
  }

  // ------------------------------------------------------------------ data
  async _fetch(force) {
    if (!this._hass || this._fetching) return;
    if (!force && this._lastFetch && Date.now() - this._lastFetch < 5000) return;
    this._fetching = true;
    try {
      const msg = { type: "tenup/planning" };
      if (this._config && this._config.entry_id) msg.entry_id = this._config.entry_id;
      this._data = await this._hass.callWS(msg);
      this._lastFetch = Date.now();
      this._error = null;
    } catch (err) {
      this._error = (err && err.message) || String(err);
      this._lastFetch = Date.now();
    } finally {
      this._fetching = false;
      this._render();
    }
  }

  _friends() {
    return (this._data && Array.isArray(this._data.friends)) ? this._data.friends : [];
  }

  _days() {
    if (!this._data || !this._data.days) return [];
    const n = Math.max(1, Math.min(14, Number(this._config.days) || 3));
    return this._data.days.slice(0, n);
  }

  _courts() {
    if (!this._data) return [];
    let courts = this._data.courts || [];
    const wanted = this._config.courts;
    if (Array.isArray(wanted) && wanted.length) {
      const ids = wanted.map(String);
      courts = courts.filter((c) => ids.includes(String(c.id)));
    }
    return courts;
  }

  _findSlot(courtId, start) {
    for (const day of this._data ? this._data.days || [] : []) {
      for (const s of day.slots) if (String(s.court_id) === String(courtId) && s.start === start) return s;
    }
    return null;
  }

  // --------------------------------------------------------------- actions
  _onClick(ev) {
    const el = ev.target && ev.target.closest ? ev.target.closest("[data-action]") : null;
    if (!el) return;
    ev.stopPropagation();
    const action = el.getAttribute("data-action");
    if (action === "day") { this._day = Number(el.getAttribute("data-index")) || 0; this._render(); return; }
    if (action === "refresh") { this._fetch(true); return; }
    if (action === "dismiss") { this._pending = null; this._render(); return; }
    if (action === "confirm") {
      const pending = this._pending;
      if (pending && (pending.kind === "friend_add" || pending.kind === "friend_del")) {
        this._saveFriend(pending);
        return;
      }
      this._runPending();
      return;
    }
    if (action === "friend-manage" || action === "friends") {
      this._toast = null;
      this._pending = { kind: "friends" };
      this._render();
      return;
    }
    if (action === "friend-push") {
      const name = this._friendInput("");
      if (name.length < 3) { this._pending = { kind: "friends", error: "friend_short" }; this._render(); return; }
      const next = this._friends().filter((f) => fold(f) !== fold(name)).concat([name]);
      this._pending = { kind: "friends" };
      this._persistFriends(next, "friend_added", name);
      return;
    }
    if (action === "friend-drop") {
      const name = el.getAttribute("data-friend");
      const next = this._friends().filter((f) => fold(f) !== fold(name));
      this._pending = { kind: "friends" };
      this._persistFriends(next, "friend_removed", name);
      return;
    }
    if (action === "friend-open") {
      this._toast = null;
      this._pending = { kind: "friend_pick", label: el.getAttribute("data-label") };
      this._render();
      return;
    }
    if (action === "friend-pick" || action === "friend-unpick") {
      const name = el.getAttribute("data-friend");
      const label = this._pending && this._pending.label;
      const rest = this._friends().filter((f) => fold(f) !== fold(name));
      // Stay open: a booking can hold two players worth following.
      this._pending = { kind: "friend_pick", label };
      if (action === "friend-pick") this._persistFriends(rest.concat([name]), "friend_added", name);
      else this._persistFriends(rest, "friend_removed", name);
      return;
    }
    if (action === "friend-add") {
      this._toast = null;
      this._pending = { kind: "friend_add", name: friendGuess(el.getAttribute("data-label")) };
      this._render();
      return;
    }
    if (action === "friend-del") {
      this._toast = null;
      this._pending = { kind: "friend_del", name: el.getAttribute("data-friend") };
      this._render();
      return;
    }
    if (action === "partner-search") { this._searchPartner(); return; }
    if (action === "partner-remember") {
      // Stay in the dialog: remembering someone is not booking with them.
      const choice = el.getAttribute("data-choice");
      const name = el.getAttribute("data-name") || choice;
      // Replace the shorter entries for this person: one line does both jobs.
      const rest = this._friends().filter((f) => !samePerson(f, choice));
      this._persistFriends(rest.concat([choice]), "partner_remembered", name);
      return;
    }
    if (action === "partner-pick") {
      const cur = this._pending;
      if (!cur || !cur.slot) return;
      // Picking a name in the list IS the confirmation: it names a real person.
      this._pending = { kind: "book", slot: cur.slot, partner: el.getAttribute("data-choice") };
      this._runPending();
      return;
    }
    const slot = this._findSlot(el.getAttribute("data-court"), el.getAttribute("data-start"));
    if (!slot) return;
    if (action === "book2") {
      this._toast = null;
      this._pending = { kind: "partner_pick", slot, query: "" };
      this._render();
      return;
    }
    if (action === "book") this._request("book", slot);
    if (action === "cancel") this._request("cancel", slot);
  }

  _request(kind, slot) {
    this._toast = null;
    if (this._config.confirm === false) { this._pending = { kind, slot }; this._runPending(); return; }
    this._pending = { kind, slot };
    this._render();
  }

  async _runPending() {
    const pending = this._pending;
    if (!pending || this._busy) return;
    this._busy = true;
    // Close the dialog at once so the cell itself can show the work in progress
    // for as long as Ten'Up takes to answer.
    this._pending = null;
    this._inflight = { kind: pending.kind, court_id: String(pending.slot.court_id), start: pending.slot.start };
    this._render();
    try {
      if (pending.kind === "book") await this._book(pending.slot, pending.partner);
      else await this._cancel(pending.slot);
      this._toast = { kind: "ok", text: t(this._hass, this._config, pending.kind === "book" ? "booked" : "cancelled") };
      await this._fetch(true);
    } catch (err) {
      const message = (err && (err.message || err.error)) || String(err);
      const refused = /Ten'Up/.test(message);
      this._toast = { kind: "err", text: t(this._hass, this._config, refused ? "refused" : "failed", { message: message.replace(/^Ten'Up:\s*/, "") }) };
    } finally {
      this._busy = false;
      this._inflight = null;
      this._render();
    }
  }

  _serviceData(extra) {
    const data = { ...extra };
    if (this._config.entry_id) data.entry_id = this._config.entry_id;
    else if (this._data && this._data.entry_id) data.entry_id = this._data.entry_id;
    return data;
  }

  _book(slot, partner) {
    const data = { court_id: String(slot.court_id), start: slot.start };
    if (partner) data.partner = partner;
    return this._hass.callService("tenup", "book", this._serviceData(data));
  }

  /** The typed search term, falling back to what the dialog already held. */
  _partnerInput(fallback) {
    const el = this._card && this._card.querySelector ? this._card.querySelector("#tenup-partner") : null;
    const value = el && typeof el.value === "string" ? el.value : fallback;
    return String(value || "").trim();
  }

  /** Ask the integration, which runs the very search the site's own field runs. */
  async _searchPartner() {
    const cur = this._pending;
    if (!cur || cur.kind !== "partner_pick") return;
    const query = this._partnerInput(cur.query || "");
    if (query.length < 3) {
      this._pending = { kind: "partner_pick", slot: cur.slot, query, error: "partner_short" };
      this._render();
      return;
    }
    this._pending = { kind: "partner_pick", slot: cur.slot, query, searching: true };
    this._render();
    const msg = { type: "tenup/partner/search", query };
    if (this._config.entry_id) msg.entry_id = this._config.entry_id;
    else if (this._data && this._data.entry_id) msg.entry_id = this._data.entry_id;
    try {
      const res = await this._hass.callWS(msg);
      const now = this._pending;
      if (!now || now.kind !== "partner_pick") return;
      this._pending = { kind: "partner_pick", slot: now.slot, query, results: (res && res.results) || [] };
    } catch (err) {
      const message = (err && (err.message || err.error)) || String(err);
      this._pending = { kind: "partner_pick", slot: cur.slot, query, errorText: message };
    }
    this._render();
  }

  _cancel(slot) {
    const data = slot.reservation_id
      ? { reservation_id: String(slot.reservation_id) }
      : { court_id: String(slot.court_id), start: slot.start };
    return this._hass.callService("tenup", "cancel", this._serviceData(data));
  }

  // ---------------------------------------------------------------- render
  _build() {
    this._built = true;
    const root = this.attachShadow({ mode: "open" });
    const style = document.createElement("style");
    style.textContent = STYLE;
    root.appendChild(style);
    this._card = document.createElement("ha-card");
    root.appendChild(this._card);
    this._card.addEventListener("click", (ev) => this._onClick(ev));
  }

  _render() {
    if (!this._built || !this._config) return;
    const html = this._markup(Date.now());
    if (html === this._lastHtml) return;
    this._lastHtml = html;
    this._card.innerHTML = html;
  }

  _markup(now) {
    const hass = this._hass, cfg = this._config;
    const cls = "wrap" + (cfg.compact ? " compact" : "");
    const title = cfg.name || (this._data && this._data.club_name) || "Ten'Up";
    let head = `<div class="head"><div class="title">${esc(title)}</div><div class="sub">`;
    if (this._data && this._data.fetched_at) {
      head += `<span>${esc(t(hass, cfg, "updated"))} ${esc(hhmm(this._data.fetched_at))}</span>`;
    }
    const siteUrl = this._siteUrl();
    if (siteUrl) {
      head += `<a class="icon" href="${esc(siteUrl)}" target="_blank" rel="noopener noreferrer" title="${esc(t(hass, cfg, "open_site"))}"><ha-icon icon="mdi:open-in-new"></ha-icon></a>`;
    }
    head += `<button class="icon" data-action="friends" title="${esc(t(hass, cfg, "friends_manage"))}"><ha-icon icon="mdi:account-heart"></ha-icon>${this._friends().length ? `<span class="badge">${this._friends().length}</span>` : ""}</button>`;
    head += `<button class="icon" data-action="refresh" title="${esc(t(hass, cfg, "refresh"))}"><ha-icon icon="mdi:refresh"></ha-icon></button></div></div>`;

    let body;
    if (!this._data) {
      body = `<div class="empty">${esc(this._error ? this._error : t(hass, cfg, this._hass ? "loading" : "no_data"))}</div>`;
    } else {
      const days = this._days();
      if (!days.length) body = `<div class="empty">${esc(t(hass, cfg, "no_data"))}</div>`;
      else {
        if (this._day >= days.length) this._day = 0;
        body = this._tabs(days, now) + this._grid(days[this._day], now);
      }
    }
    let extra = "";
    if (this._toast) {
      const site = this._toast.kind === "err" ? this._siteUrl() : null;
      const link = site ? ` <a href="${esc(site)}" target="_blank" rel="noopener noreferrer">${esc(t(hass, cfg, "open_site"))}</a>` : "";
      extra += `<div class="toast ${this._toast.kind}">${esc(this._toast.text)}${link}</div>`;
    }
    if (this._pending) extra += this._dialog(this._pending);
    return `<div class="${cls}">${head}${body}${extra}</div>`;
  }

  _siteUrlForDate(dateOrIso) {
    const code = this._data && this._data.club_code;
    if (!code) return null;
    const ymd = dateOrIso ? "/" + String(dateOrIso).slice(0, 10).replace(/-/g, "") : "";
    return `https://tenup.fft.fr/club/${encodeURIComponent(code)}/reservations${ymd}`;
  }

  _siteUrl() {
    const days = this._days();
    const day = days[this._day] || days[0];
    return this._siteUrlForDate(day && day.date);
  }

  _tabs(days, now) {
    const hass = this._hass, cfg = this._config;
    const courts = new Set(this._courts().map((c) => String(c.id)));
    return `<div class="tabs">` + days.map((day, i) => {
      const free = day.slots.filter((s) => courts.has(String(s.court_id)) && slotState(s, now) === "free").length;
      return `<button class="tab${i === this._day ? " active" : ""}" data-action="day" data-index="${i}">${esc(dayLabel(hass, cfg, day.date))}<span class="n">${free}</span></button>`;
    }).join("") + `</div>`;
  }

  _axis(ids) {
    const cfg = this._config;
    const all = [];
    for (const d of this._days()) {
      for (const s of d.slots) { if (ids.has(String(s.court_id))) all.push(s); }
    }
    return buildAxis(all, cfg.start_hour !== undefined ? Number(cfg.start_hour) : undefined, cfg.end_hour !== undefined ? Number(cfg.end_hour) : undefined);
  }

  _grid(day, now) {
    const hass = this._hass, cfg = this._config;
    const courts = this._courts();
    const ids = new Set(courts.map((c) => String(c.id)));
    const slots = day.slots.filter((s) => ids.has(String(s.court_id)));
    if (!courts.length || !slots.length) return `<div class="empty">${esc(t(hass, cfg, "no_data"))}</div>`;
    const axis = this._axis(ids);
    const rowH = cfg.compact ? (axis.step === 30 ? 16 : 26) : (axis.step === 30 ? 22 : 36);
    const cols = `48px repeat(${courts.length}, minmax(${cfg.compact ? 54 : 68}px, 1fr))`;
    let html = `<div class="scroll"><div class="grid" style="grid-template-columns:${cols};grid-template-rows:auto repeat(${axis.rows}, ${rowH}px)">`;
    courts.forEach((c, i) => { html += `<div class="court" style="grid-column:${i + 2}" title="${esc(c.name)}">${esc(c.name)}</div>`; });
    for (let m = axis.start; m <= axis.end; m += 60) {
      const r = (m - axis.start) / axis.step + 2;
      if (r > axis.rows + 1) break;
      html += `<div class="time" style="grid-row:${r}">${String(m / 60).padStart(2, "0")}:00</div>`;
    }
    for (const s of slots) {
      const col = courts.findIndex((c) => String(c.id) === String(s.court_id)) + 2;
      const a = minutesOf(s.start), dur = Math.round((new Date(s.end) - new Date(s.start)) / 60000);
      const r1 = (a - axis.start) / axis.step + 2, r2 = r1 + Math.max(1, Math.round(dur / axis.step));
      if (a + dur <= axis.start || a >= axis.end) continue;
      const state = slotState(s, now);
      let inner = "", action = "", href = "", cls = state;
      const flight = this._inflight;
      if (flight && flight.court_id === String(s.court_id) && flight.start === s.start) {
        const what = t(hass, cfg, flight.kind === "book" ? "booking" : "cancelling");
        const wait = t(hass, cfg, "in_progress");
        cls = "pending";
        inner = `<span>${esc(what)}</span><span class="prog">${esc(wait)}</span>`;
        const pos0 = `grid-column:${col};grid-row:${Math.max(2, r1)} / ${Math.min(axis.rows + 2, r2)}`;
        html += `<div class="cell ${cls}" style="${pos0}" title="${esc(what + " " + wait)}">${inner}</div>`;
        continue;
      }
      if (state === "free" && s.required_players > 1) {
        // Bookable from the grid now that the integration can add a partner.
        // The link to the site moved into the dialog, as a way out.
        cls = "free two-players";
        inner = `<span>${esc(hhmm(s.start))}</span><span class="badge2">${esc(t(hass, cfg, "two_players"))}</span>`;
        action = ` data-action="book2" data-court="${esc(s.court_id)}" data-start="${esc(s.start)}" title="${esc(t(hass, cfg, "two_players_hint"))}"`;
      } else if (state === "free") {
        inner = `<span>${esc(hhmm(s.start))}</span><span class="hint">${esc(t(hass, cfg, "book"))}</span>`;
        action = ` data-action="book" data-court="${esc(s.court_id)}" data-start="${esc(s.start)}" title="${esc(t(hass, cfg, "book"))} ${esc(hhmm(s.start))}"`;
      } else if (state === "mine") {
        inner = `<span>${esc(t(hass, cfg, "you"))}</span><span class="x">${esc(hhmm(s.start))} \u2715</span>`;
        action = ` data-action="cancel" data-court="${esc(s.court_id)}" data-start="${esc(s.start)}" title="${esc(t(hass, cfg, "cancel"))}"`;
      } else if (state === "mine_past") {
        cls = "mine-past";
        inner = `<span>${esc(t(hass, cfg, "you"))}</span><span class="x">${esc(hhmm(s.start))}</span>`;
      } else if (state === "past") {
        inner = `<span>${esc(hhmm(s.start))}</span>`;
      } else {
        inner = `<span class="lbl">${esc(cfg.show_names === false ? t(hass, cfg, "busy") : (s.label || t(hass, cfg, "busy")))}</span>`;
        const friend = matchFriend(s.label, this._friends());
        // With the names hidden, the label must not come back through an
        // attribute; the friend colours still work, only adding is off.
        const named = !!s.label && cfg.show_names !== false;
        // "J. KING M. MOORE" is two people, each followable on their own: players
        // get a dialog listing them. A club lesson keeps the free field.
        const players = named ? labelPlayers(s.label) : [];
        if (friend) cls = "busy friend";
        const title = friend ? t(hass, cfg, "friend_del", { name: friend }) : t(hass, cfg, "friend_add");
        if (players.length) {
          action = ` data-action="friend-open" data-label="${esc(s.label)}" title="${esc(title)}"`;
        } else if (friend) {
          action = ` data-action="friend-del" data-friend="${esc(friend)}" title="${esc(title)}"`;
        } else if (named) {
          action = ` data-action="friend-add" data-label="${esc(s.label)}" title="${esc(title)}"`;
        }
      }
      const pos = `grid-column:${col};grid-row:${Math.max(2, r1)} / ${Math.min(axis.rows + 2, r2)}`;
      if (href) {
        html += `<a class="cell ${cls}" style="${pos}" href="${esc(href)}" target="_blank" rel="noopener noreferrer" title="${esc(t(hass, cfg, "two_players_hint"))}">${inner}</a>`;
      } else {
        html += `<div class="cell ${cls}" style="${pos}"${action}>${inner}</div>`;
      }
    }
    return html + `</div></div>`;
  }

  _friendsDialog(pending) {
    const hass = this._hass, cfg = this._config;
    const friends = this._friends();
    const chips = friends.length
      ? `<div class="flist">` + friends.map((f) =>
          `<button class="chip" data-action="friend-drop" data-friend="${esc(f)}" title="${esc(t(hass, cfg, "yes_friend_del"))}">${esc(f)}<span class="x">\u2715</span></button>`
        ).join("") + `</div>`
      : `<div class="hint">${esc(t(hass, cfg, "friends_none"))}</div>`;
    const err = pending.error ? `<div class="msg">${esc(t(hass, cfg, pending.error))}</div>` : "";
    return `<div class="overlay"><div class="dialog">` +
      `<div class="msg">${esc(t(hass, cfg, "friends_manage"))}</div>${chips}${err}` +
      `<div class="row"><input class="fname" id="tenup-friend" type="text" spellcheck="false" placeholder="${esc(t(hass, cfg, "friend_new"))}">` +
      `<button class="primary" data-action="friend-push">${esc(t(hass, cfg, "add"))}</button></div>` +
      `<div class="hint">${esc(t(hass, cfg, "friends_hint"))}</div>` +
      `<div class="btns"><button class="secondary" data-action="dismiss">${esc(t(hass, cfg, "close"))}</button></div></div></div>`;
  }

  /** One row per player to follow them alone; their whole surname under the list. */
  _friendPickDialog(pending) {
    const hass = this._hass, cfg = this._config;
    const friends = this._friends();
    const players = labelPlayers(pending.label);
    const rows = players.map((player) => {
      const p = playerParts(player);
      const followed = matchFriend(player, friends);
      const acts = followed
        ? `<button class="chip" data-action="friend-unpick" data-friend="${esc(followed)}" title="${esc(t(hass, cfg, "yes_friend_del"))}">${esc(followed)}<span class="x">\u2715</span></button>`
        : `<button class="secondary pick" data-action="friend-pick" data-friend="${esc(p.exact)}">${esc(p.exact)}</button>`;
      return `<div class="prow"><span class="pname">${esc(player)}</span><span class="pacts">${acts}</span></div>`;
    }).join("");
    // A whole surname is about the name, not about one of the two players: offer it
    // once per surname, under the list. Not when that surname is already followed,
    // and not under three letters, where a bare surname would also paint club
    // lessons (the integration refuses it anyway).
    const seen = new Set();
    const all = [];
    for (const player of players) {
      const p = playerParts(player);
      const key = fold(p.surname).trim();
      if (seen.has(key)) continue;
      seen.add(key);
      if (p.surname.length < 3) continue;
      if (friends.some((f) => fold(f).trim() === key)) continue;
      all.push(`<button class="secondary pick" data-action="friend-pick" data-friend="${esc(p.surname)}">${esc(t(hass, cfg, "friend_all", { name: p.surname }))}</button>`);
    }
    const allRow = all.length ? `<div class="pall">${all.join("")}</div>` : "";
    return `<div class="overlay"><div class="dialog">` +
      `<div class="msg">${esc(t(hass, cfg, "friend_pick"))}</div><div class="plist">${rows}</div>${allRow}` +
      `<div class="hint">${esc(t(hass, cfg, "friend_pick_hint"))}</div>` +
      `<div class="btns"><button class="secondary" data-action="dismiss">${esc(t(hass, cfg, "close"))}</button></div></div></div>`;
  }

  /** Send a list to the integration and keep the colours in step. */
  async _persistFriends(next, toastKey, name) {
    const hass = this._hass, cfg = this._config;
    try {
      const msg = { type: "tenup/friends/set", friends: next };
      if (cfg.entry_id) msg.entry_id = cfg.entry_id;
      const res = await hass.callWS(msg);
      // The list only drives the colours, never the slots: no refetch needed.
      if (this._data && res && Array.isArray(res.friends)) this._data.friends = res.friends;
      if (toastKey) this._toast = { kind: "ok", text: t(hass, cfg, toastKey, { name }) };
    } catch (err) {
      const message = (err && (err.message || err.error)) || String(err);
      this._toast = { kind: "err", text: t(hass, cfg, "failed", { message }) };
    }
    this._render();
  }

  _partnerDialog(pending) {
    const hass = this._hass, cfg = this._config, s = pending.slot;
    const vars = { court: s.court_name, start: hhmm(s.start), end: hhmm(s.end) };
    // Friends already stored WITH their key can be booked without searching.
    const known = this._friends().filter((f) => friendKey(f));
    const quick = known.length
      ? `<div class="hint">${esc(t(hass, cfg, "partner_known"))}</div><div class="pall">` +
        known.map((f) =>
          `<button class="secondary pick" data-action="partner-pick" data-choice="${esc(f)}">` +
          `${esc(friendNeedle(f))}</button>`).join("") + `</div>`
      : "";
    let list = "";
    if (pending.searching) {
      list = `<div class="hint">${esc(t(hass, cfg, "partner_searching"))}</div>`;
    } else if (Array.isArray(pending.results)) {
      list = pending.results.length
        ? `<div class="plist">` + pending.results.map((r) =>
            `<div class="prow"><span class="pname">${esc(r.name)}</span><span class="pacts">` +
            `<button class="secondary pick" data-action="partner-pick" data-choice="${esc(r.choice)}">${esc(t(hass, cfg, "yes_book"))}</button>` +
            (this._friends().some((f) => f === r.choice)
              ? ""
              : `<button class="secondary" data-action="partner-remember" data-choice="${esc(r.choice)}" data-name="${esc(r.name)}">${esc(t(hass, cfg, "partner_remember"))}</button>`) +
            `</span></div>`).join("") + `</div>`
        : `<div class="hint">${esc(t(hass, cfg, "partner_none"))}</div>`;
    }
    const err = pending.errorText
      ? `<div class="msg">${esc(pending.errorText)}</div>`
      : (pending.error ? `<div class="msg">${esc(t(hass, cfg, pending.error))}</div>` : "");
    return `<div class="overlay"><div class="dialog">` +
      `<div class="msg">${esc(t(hass, cfg, "partner_title", vars))}</div>` + quick +
      `<input class="fname" id="tenup-partner" type="text" value="${esc(pending.query || "")}" placeholder="${esc(t(hass, cfg, "partner_ph"))}" spellcheck="false">` +
      `<div class="btns"><button class="primary" data-action="partner-search">${esc(t(hass, cfg, "partner_search"))}</button></div>` +
      err + list +
      `<div class="hint">${esc(t(hass, cfg, "partner_hint"))}</div>` +
      `<div class="btns">` +
      `<a class="secondary" href="${esc(this._siteUrlForDate(s.start))}" target="_blank" rel="noopener noreferrer">${esc(t(hass, cfg, "open_site"))}</a>` +
      `<button class="secondary" data-action="dismiss">${esc(t(hass, cfg, "back"))}</button></div></div></div>`;
  }

  _friendDialog(pending) {
    const hass = this._hass, cfg = this._config;
    const add = pending.kind === "friend_add";
    const msg = add ? t(hass, cfg, "friend_add") : t(hass, cfg, "friend_del", { name: pending.name });
    // Editable on purpose: a label can hold two players, or be a club lesson.
    const field = add
      ? `<input class="fname" id="tenup-friend" type="text" value="${esc(pending.name)}" spellcheck="false">`
      : "";
    const err = pending.error ? `<div class="msg">${esc(t(hass, cfg, pending.error))}</div>` : "";
    const yes = add
      ? `<button class="primary" data-action="confirm">${esc(t(hass, cfg, "yes_friend_add"))}</button>`
      : `<button class="danger" data-action="confirm">${esc(t(hass, cfg, "yes_friend_del"))}</button>`;
    return `<div class="overlay"><div class="dialog"><div class="msg">${esc(msg)}</div>${field}${err}` +
           `<div class="btns"><button class="secondary" data-action="dismiss">${esc(t(hass, cfg, "back"))}</button>${yes}</div></div></div>`;
  }

  /** The name as edited in the dialog, falling back to what we suggested. */
  _friendInput(fallback) {
    const el = this._card && this._card.querySelector ? this._card.querySelector("#tenup-friend") : null;
    const value = el && typeof el.value === "string" ? el.value : "";
    return value.trim() || fallback;
  }

  async _saveFriend(pending) {
    const hass = this._hass, cfg = this._config;
    const add = pending.kind === "friend_add";
    const name = (add ? this._friendInput(pending.name) : pending.name).trim();
    if (add && name.length < 3) {
      this._pending = { ...pending, name, error: "friend_short" };
      this._render();
      return;
    }
    const current = this._friends();
    const next = add
      ? current.filter((f) => fold(f) !== fold(name)).concat([name])
      : current.filter((f) => fold(f) !== fold(name));
    this._pending = null;
    this._render();
    await this._persistFriends(next, add ? "friend_added" : "friend_removed", name);
  }

  _dialog(pending) {
    if (pending.kind === "friends") return this._friendsDialog(pending);
    if (pending.kind === "partner_pick") return this._partnerDialog(pending);
    if (pending.kind === "friend_pick") return this._friendPickDialog(pending);
    if (pending.kind === "friend_add" || pending.kind === "friend_del") return this._friendDialog(pending);
    const hass = this._hass, cfg = this._config, s = pending.slot;
    const vars = { court: s.court_name, date: longDate(hass, cfg, s.start), start: hhmm(s.start), end: hhmm(s.end) };
    const msg = t(hass, cfg, pending.kind === "book" ? "confirm_book" : "confirm_cancel", vars);
    const yes = pending.kind === "book"
      ? `<button class="primary" data-action="confirm">${esc(t(hass, cfg, "yes_book"))}</button>`
      : `<button class="danger" data-action="confirm">${esc(t(hass, cfg, "yes_cancel"))}</button>`;
    const busy = this._busy ? `<div class="msg">${esc(t(hass, cfg, "working"))}</div>` : "";
    return `<div class="overlay"><div class="dialog"><div class="msg">${esc(msg)}</div>${busy}<div class="btns"><button class="secondary" data-action="dismiss">${esc(t(hass, cfg, "back"))}</button>${this._busy ? "" : yes}</div></div></div>`;
  }
}

// ---------------------------------------------------------------------------
// Editor
// ---------------------------------------------------------------------------

class TenupCardEditor extends HTMLElement {
  constructor() {
    super();
    this._config = {};
    this._hass = null;
    this._entries = null;
    this._courts = null;
    this._form = null;
    this._lastEmitted = null;
  }

  setConfig(config) {
    // HA echoes our own config-changed back through setConfig; do not rebuild for that.
    const same = this._lastEmitted !== null && sortedJson(config) === this._lastEmitted;
    this._config = { ...config };
    if (!same) this._refresh();
  }

  set hass(hass) {
    this._hass = hass;
    if (this._form) this._form.hass = hass;
    if (hass && this._entries === null) this._loadEntries();
    if (hass && this._courts === null) this._loadCourts();
  }

  async _loadEntries() {
    this._entries = [];
    try {
      const entries = await this._hass.callWS({ type: "config_entries/get", domain: "tenup" });
      this._entries = (entries || []).map((e) => ({ value: e.entry_id, label: e.title }));
    } catch (err) { /* not admin or no entry: keep the free text */ }
    this._refresh();
  }

  async _loadCourts() {
    this._courts = [];
    try {
      const msg = { type: "tenup/planning" };
      if (this._config.entry_id) msg.entry_id = this._config.entry_id;
      const data = await this._hass.callWS(msg);
      this._courts = (data.courts || []).map((c) => ({ value: String(c.id), label: c.name }));
    } catch (err) { /* integration not loaded yet */ }
    this._refresh();
  }

  _schema() {
    const hass = this._hass, cfg = this._config;
    const entryOptions = [{ value: "", label: t(hass, cfg, "entry_auto") }, ...(this._entries || [])];
    const schema = [
      { name: "name", selector: { text: {} } },
      { name: "entry_id", selector: { select: { mode: "dropdown", options: entryOptions } } },
      { name: "days", selector: { number: { min: 1, max: 7, mode: "box" } } },
      { name: "start_hour", selector: { number: { min: 0, max: 23, mode: "box" } } },
      { name: "end_hour", selector: { number: { min: 1, max: 24, mode: "box" } } },
    ];
    if (this._courts && this._courts.length) {
      schema.push({ name: "courts", selector: { select: { multiple: true, mode: "list", options: this._courts } } });
    }
    schema.push(
      { name: "show_names", selector: { boolean: {} } },
      { name: "confirm", selector: { boolean: {} } },
      { name: "compact", selector: { boolean: {} } },
      { name: "language", selector: { select: { mode: "dropdown", options: [
        { value: "auto", label: t(hass, cfg, "language_auto") }, { value: "en", label: "English" }, { value: "fr", label: "Fran\u00e7ais" },
      ] } } },
    );
    return schema;
  }

  _formData() {
    const c = this._config;
    return {
      name: c.name || "", entry_id: c.entry_id || "", days: c.days !== undefined ? c.days : 3,
      start_hour: c.start_hour, end_hour: c.end_hour, courts: c.courts || [],
      show_names: c.show_names !== false, confirm: c.confirm !== false, compact: !!c.compact,
      language: c.language || "auto",
    };
  }

  _refresh() {
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.computeLabel = (s) => t(this._hass, this._config, s.name);
      this._form.addEventListener("value-changed", (ev) => this._onChange(ev.detail && ev.detail.value));
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.schema = this._schema();
    this._form.data = this._formData();
  }

  _onChange(value) {
    if (!value) return;
    const config = { ...this._config };
    const set = (key, v, drop) => { if (drop) delete config[key]; else config[key] = v; };
    set("name", value.name, !value.name);
    set("entry_id", value.entry_id, !value.entry_id);
    set("days", Number(value.days), !Number.isFinite(Number(value.days)) || Number(value.days) === 3);
    set("start_hour", Number(value.start_hour), value.start_hour === undefined || value.start_hour === null || value.start_hour === "");
    set("end_hour", Number(value.end_hour), value.end_hour === undefined || value.end_hour === null || value.end_hour === "");
    set("courts", value.courts, !Array.isArray(value.courts) || !value.courts.length);
    set("show_names", false, value.show_names !== false);
    set("confirm", false, value.confirm !== false);
    set("compact", true, !value.compact);
    set("language", value.language, !value.language || value.language === "auto");
    this._config = config;
    this._lastEmitted = sortedJson(config);
    this.dispatchEvent(new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true }));
  }
}

// The card ships with the integration, which serves it and keeps a single
// Lovelace resource pointing at it. A leftover resource for the standalone
// card would load a second copy of this file, and defining a custom element
// twice throws: guard, so the first copy loaded simply wins.
const ELEMENTS = [
  ["ha-tenup-card", TenupCard],
  ["ha-tenup-card-editor", TenupCardEditor],
];
for (const [name, cls] of ELEMENTS) {
  if (!customElements.get(name)) customElements.define(name, cls);
}

window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === "ha-tenup-card")) {
  window.customCards.push({
    type: "ha-tenup-card",
    name: "Ten'Up Card",
    description: "Free courts of your tennis club on Ten'Up, book and cancel from the dashboard.",
    preview: false,
    documentationURL: "https://github.com/ADNPolymerase/ha-tenup-resa",
  });
}

// Exposed for the tests.
TenupCard._helpers = { minutesOf, hhmm, slotState, buildAxis, dayLabel, sortedJson, t, langOf, fold, matchFriend, friendGuess, labelPlayers, playerParts };
