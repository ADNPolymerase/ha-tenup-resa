/**
 * Minimal browser stub for testing a Home Assistant Lovelace card in Node,
 * with no dependency and no build step.
 *
 * It does NOT implement the DOM. Nodes only remember the HTML string assigned
 * to them, which is enough to assert on what a card actually renders for a
 * given hass state — the part that silently goes wrong.
 *
 * What it can check:
 *   - the markup produced by _render() for a given config + hass state
 *   - the numbers shown in it (the reason this file exists)
 *   - that an editor dispatches config-changed with a real detail.config
 *
 * What it cannot check: layout, CSS, anything visual, and event handlers —
 * getElementById/querySelector return inert stubs, so wiring runs without
 * throwing but cannot be triggered. Visual verification stays manual.
 */
import { readFileSync } from 'node:fs';

// ── DOM stubs ────────────────────────────────────────────────────────────────

class FakeNode {
  constructor(tag = 'div') {
    this.tagName   = String(tag).toUpperCase();
    this.children  = [];
    this.style     = {};
    this.attributes= {};
    this._html     = '';
  }
  set innerHTML(v) { this._html = String(v); this.children = []; }
  get innerHTML()  { return this._html; }
  appendChild(c)   { this.children.push(c); return c; }
  removeChild(c)   { this.children = this.children.filter(x => x !== c); return c; }
  setAttribute(k, v) { this.attributes[k] = v; }
  getAttribute(k)  { return this.attributes[k]; }
  addEventListener() {}
  removeEventListener() {}
  dispatchEvent()  { return true; }
  getElementById() { return null; }
  querySelector()  { return new FakeNode(); }
  querySelectorAll() { return []; }
  /** Full markup of this node and everything appended under it. */
  get markup() { return this._html + this.children.map(c => c.markup).join(''); }
}

class FakeElement extends FakeNode {
  constructor() { super(); this.events = []; }
  attachShadow() { return (this.shadowRoot = new FakeNode()); }
  // Captured so tests can assert on config-changed & friends.
  dispatchEvent(ev) { this.events.push(ev); return true; }
}

/**
 * Installs the globals a card module expects, then imports it.
 * Returns the custom-element registry it populated.
 */
function installGlobals(registry, strict) {
  globalThis.HTMLElement    = FakeElement;
  globalThis.customElements = {
    define: (n, c) => {
      // The real registry throws on a duplicate name. The permissive stub is
      // kept for the ordinary tests, which reload the card constantly.
      if (strict && registry.has(n)) throw new Error(`'${n}' has already been defined`);
      registry.set(n, c);
    },
    get: n => registry.get(n),
  };
  globalThis.document = { createElement: tag => new FakeNode(tag) };
  globalThis.window   = globalThis;
  // node ships a read-only navigator that already has .language — leave it be.
}

/**
 * Installs the globals a card module expects, then imports it.
 * Returns the custom-element registry it populated.
 */
export async function loadCard(modulePath) {
  const registry = new Map();
  installGlobals(registry, false);
  await import(modulePath);
  return registry;
}

/**
 * Loads the card twice into the same registry, the way a leftover Lovelace
 * resource for the standalone card would alongside the bundled one. define()
 * throws on a duplicate here, exactly as the real registry does, so an
 * unguarded registration fails instead of passing silently.
 *
 * The source is compiled twice rather than imported twice: the bundle is a
 * plain .js with no export, so node loads it as CommonJS and a second import
 * of the same file returns the cached copy without running it again, whatever
 * query string is tacked on. Each compile gets its own scope, which is what
 * two module resources give it in a browser.
 */
export async function loadCardTwice(modulePath) {
  const registry = new Map();
  installGlobals(registry, true);
  globalThis.window.customCards = [];
  const run = new Function(readFileSync(modulePath, 'utf8'));
  run();
  const first = new Map(registry);
  run();
  return { registry, first };
}

/** Rendered markup of an element, shadow DOM or light DOM alike. */
export function markup(el) {
  return el.shadowRoot ? el.shadowRoot.markup : el.markup;
}

// ── Frozen clock ─────────────────────────────────────────────────────────────

let _now = null;
/** Pins Date.now() so time-dependent rendering is reproducible. */
export function freezeClock(iso) {
  _now = new Date(iso).getTime();
  Date.now = () => _now;
  return _now;
}
export function now() { return _now ?? Date.now(); }

// ── Assertions ───────────────────────────────────────────────────────────────

let failures = 0, total = 0;

export function check(label, got, want) {
  total++;
  const ok = Object.is(got, want);
  if (!ok) failures++;
  console.log(`${ok ? '✅' : '❌'} ${label}`);
  if (!ok) console.log(`     attendu: ${want}\n     obtenu : ${got}`);
}

export function contains(label, haystack, needle) {
  check(label, String(haystack).includes(needle), true);
}

/** Prints the tally and exits non-zero on any failure — the CI signal. */
export function report() {
  console.log(failures
    ? `\n❌ ${failures} échec(s) sur ${total} assertions`
    : `\n✅ ${total}/${total} assertions OK`);
  process.exit(failures ? 1 : 0);
}
