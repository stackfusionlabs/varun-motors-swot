#!/usr/bin/env node
/*
 * Drishti offline test harness.
 *
 * Runs the deterministic router (the <script id="drishti-bot"> block inside
 * index.html) against the real dashboard_data.js, in Node, with the browser
 * APIs stubbed out. Lets us validate answers — especially RTO/market — without
 * a browser. STT, TTS read-aloud and the MiniLM semantic fallback are
 * browser-only and are NOT exercised here.
 *
 * Usage:
 *   node drishti_harness.js                 # run the built-in suite (incl. RTO)
 *   node drishti_harness.js "maruti share in vizag" "biggest market"   # ad-hoc
 *
 * pulse is proxied as sentiment_score-5 (the real effectiveScore needs the
 * dashboard's time-range machinery); RTO/market/people/counts don't use pulse.
 */
const fs = require('fs');
const path = require('path');
const ROOT = __dirname;

let src = fs.readFileSync(path.join(ROOT, 'dashboard_data.js'), 'utf8').replace('const DASHBOARD_DATA', 'globalThis.DASHBOARD_DATA');
eval(src);

const answers = [];
const makeEl = (id) => ({
  _id: id, style: {}, classList: { add() {}, remove() {}, contains() { return false; }, toggle() {} },
  addEventListener() {}, querySelector() { return makeEl('q'); }, querySelectorAll() { return []; },
  appendChild() {}, setAttribute() {}, getBoundingClientRect() { return { top: 0, bottom: 0, left: 0, right: 0 }; },
  get textContent() { return this._t || ''; }, set textContent(v) { this._t = v; if (this._id === 'drishti-answer') answers.push(v); },
  value: '', innerHTML: '', focus() {}, options: [],
});
globalThis.document = { getElementById: (id) => makeEl(id), querySelector: () => makeEl('qs'), querySelectorAll: () => [], addEventListener() {}, createElement: () => makeEl('c') };
globalThis.window = { speechSynthesis: { getVoices: () => [], speak() {}, cancel() {} }, addEventListener() {}, localStorage: { getItem: () => null, setItem() {} } };
globalThis.localStorage = window.localStorage;
globalThis.navigator = { mediaDevices: { getUserMedia: () => Promise.reject(new Error('no mic')) } };
globalThis.speechSynthesis = window.speechSynthesis;
globalThis.SpeechSynthesisUtterance = function (t) { this.text = t; };
globalThis.requestAnimationFrame = (cb) => cb();
globalThis.performance = { now: () => 0 };
globalThis.L = { latLngBounds: (pts) => ({ pts }) };
globalThis.map = { flyTo() {}, flyToBounds() {}, closePopup() {}, getZoom: () => 10, panBy() {}, getContainer: () => ({ getBoundingClientRect: () => ({ top: 0, bottom: 600, left: 0, right: 800 }) }) };
globalThis.dealerMarkers = (DASHBOARD_DATA.dealers || []).map(d => ({ marker: { openPopup() {}, getPopup: () => null }, data: d }));
globalThis.rtoMarkers = (DASHBOARD_DATA.rtos || []).map(r => ({ marker: { openPopup() {} }, data: r }));
globalThis.popupViewState = {};
globalThis.getRange = () => ({ from: '2020-01', to: '2030-01' });
globalThis.effectiveScore = (d) => ({ score: d.sentiment_score != null ? (d.sentiment_score - 5) : null });
globalThis.fmtScore5 = (s) => (s >= 0 ? '+' : '') + s.toFixed(1);
globalThis.DIV_LABEL = { arena: 'Arena', nexa: 'Nexa', commercial: 'Commercial', service: 'Service', true_value: 'True Value' };

const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
const m = html.match(/<script id="drishti-bot">([\s\S]*?)<\/script>/);
if (!m) { console.error('Could not find drishti-bot script in index.html'); process.exit(1); }
let script = m[1];
const idx = script.lastIndexOf('})();');
script = script.slice(0, idx) + '\n; globalThis.__T = { handleUtterance };\n' + script.slice(idx);
try { eval(script); } catch (e) { console.error('EVAL ERROR:', e.message); process.exit(1); }

function ask(q) {
  answers.length = 0;
  try { __T.handleUtterance(q); } catch (e) { answers.push('THREW: ' + e.message); }
  return answers.join(' || ') || '(no synchronous answer — likely the browser-only semantic fallback)';
}
function run(list) { for (const q of list) { console.log('Q: ' + q); console.log('   -> ' + ask(q) + '\n'); } }

const SUITE = [
  // --- RTO / market ---
  'how many cars are registered in Vizag',
  'and in vizag',
  'in 2025',
  'maruti market share in Visakhapatnam',
  'maruti share in Hyderabad',
  'maruti share in Vijayawada since 2020',
  'registrations between 2020 and 2023 in Vizag',
  'walk me through Gajuwaka RTO',
  'what is the biggest market',
  'smallest market',
  'where is maruti share highest',
  'where is maruti share lowest',
  'is Vizag growing',
  'maruti share in Andhra Pradesh',
  'cars registered this year',
  // --- outlets / people / compare ---
  'best in Vizag', 'three best in Vijayawada', 'compare Gajuwaka and Bheemili',
  'compare staff at MVP Colony and Thagarapuvalasa',
  'who is the best salesperson in Gajuwaka', 'tell me about Harish',
  'how is staff in Gajuwaka', 'top complaints in MVP Colony',
  'how many outlets', 'how many Arena in Andhra Pradesh',
];

const args = process.argv.slice(2);
run(args.length ? args : SUITE);
