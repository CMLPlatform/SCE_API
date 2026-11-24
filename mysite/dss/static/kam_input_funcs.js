// Test page for POST /dss/welding-stations/ (KAM comparison).
// Builds one tab per welding station and sends them as the platform would.

// ─────────────────────────────────────────────────────────────────────────────
// Options and example values
// Material and consumable names must exist in init_data/material_data.csv;
// country codes follow init_data/country_data.csv (Eurostat: UK, EL).
// ─────────────────────────────────────────────────────────────────────────────

const COUNTRIES = ['DE', 'UK', 'IT', 'FR', 'NL', 'BE', 'PL', 'ES', 'AT', 'SE'];
const QUALITY_OPTIONS = ['low', 'medium', 'high'];
const MATERIALS = [
  'Aluminium sheet', 'Aluminium alloy, wrought', 'Aluminium alloy, cast', 'Aluminium, virgin',
  'AISI 316 steel plate', 'Chromium steel sheets', 'Chromium steel pipe',
  'Steel sheets', 'Steel, low-alloyed', 'Steel, low-alloyed, hot rolled',
];

// Same values as dss/examples/kam_welding_stations.json (synthetic).
const EXAMPLES = [
  { experimentId: 1, country: 'UK', recyclability: 'high', maintenanceCosts: 18000, cycleTime: 75, scrapRate: 0.03,
    weldLength: 2400, weldSpeed: 120, laserPower: 4.5, stationPower: 14, material: 'Aluminium sheet', materialWeight: 1.85,
    nitrogen: 0, argon: 1.2, filler: 0.33, porosity: 2.0, tensile: 180, weldDepth: 1.5,
    automation: 'high', specialisation: 'medium', monitoring: 5, leadTime: 12, saturation: 0.72 },
  { experimentId: 2, country: 'DE', recyclability: 'high', maintenanceCosts: 15000, cycleTime: 68, scrapRate: 0.02,
    weldLength: 2400, weldSpeed: 120, laserPower: 4.5, stationPower: 12, material: 'Aluminium sheet', materialWeight: 1.85,
    nitrogen: 0, argon: 1.2, filler: 0.33, porosity: 1.6, tensile: 184, weldDepth: 1.5,
    automation: 'high', specialisation: 'high', monitoring: 2, leadTime: 10, saturation: 0.81 },
  { experimentId: 3, country: 'IT', recyclability: 'medium', maintenanceCosts: 12000, cycleTime: 90, scrapRate: 0.04,
    weldLength: 2400, weldSpeed: 100, laserPower: 4.0, stationPower: 12, material: 'Aluminium sheet', materialWeight: 1.85,
    nitrogen: 0, argon: 1.0, filler: 0.30, porosity: 2.4, tensile: 178, weldDepth: 1.4,
    automation: 'medium', specialisation: 'medium', monitoring: 15, leadTime: 14, saturation: 0.64 },
];

// ─────────────────────────────────────────────────────────────────────────────
// HTML helpers (Bootstrap)
// ─────────────────────────────────────────────────────────────────────────────

function field(id, label, unit, inner) {
  return `
    <div class="col-sm-4">
      <label class="form-label" for="${id}">${label}${unit ? ` <span class="text-secondary fw-normal">(${unit})</span>` : ''}</label>
      ${inner}
    </div>`;
}

function numInput(id, name, value, {min = 0, max = '', step = 'any'} = {}) {
  return `<input type="number" class="form-control" id="${id}" data-field="${name}" value="${value ?? ''}" min="${min}" ${max !== '' ? `max="${max}"` : ''} step="${step}">`;
}

function selectInput(id, name, options, selected) {
  const opts = options.map(o => `<option value="${o}"${o === selected ? ' selected' : ''}>${o}</option>`).join('');
  return `<select class="form-select" id="${id}" data-field="${name}">${opts}</select>`;
}

function section(title, hint = '') {
  return `
    <h2 class="section-title mt-4 mb-1">${title}</h2>
    ${hint ? `<p class="text-secondary small mb-2">${hint}</p>` : ''}`;
}

// ─────────────────────────────────────────────────────────────────────────────
// One panel per station
// ─────────────────────────────────────────────────────────────────────────────

function createPanel(idx, v) {
  const id = (name) => `s${idx}-${name}`;
  const num = (name, label, unit, opts) => field(id(name), label, unit, numInput(id(name), name, v[name], opts));
  const sel = (name, label, unit, options) => field(id(name), label, unit, selectInput(id(name), name, options, v[name]));

  const panel = document.createElement('div');
  panel.className = 'tab-panel';
  panel.dataset.panel = idx;
  panel.setAttribute('role', 'tabpanel');
  panel.innerHTML = `
    ${section('General')}
    <div class="row g-3">
      ${num('experimentId', 'Station ID', '', {min: 1, step: 1})}
      ${sel('country', 'Country', '', COUNTRIES)}
      ${sel('recyclability', 'Recyclability', '', QUALITY_OPTIONS)}
      ${num('maintenanceCosts', 'Maintenance costs', '€/year', {step: 100})}
      ${num('cycleTime', 'Cycle time', 's', {min: 0.1, step: 1})}
      ${num('scrapRate', 'Scrap rate', '0–0.99', {max: 0.99, step: 0.01})}
    </div>

    ${section('Process')}
    <div class="row g-3">
      ${num('weldLength', 'Weld length', 'mm', {step: 1})}
      ${num('weldSpeed', 'Weld speed', 'mm/s', {step: 1})}
      ${num('laserPower', 'Laser power', 'kW', {step: 0.1})}
      ${num('stationPower', 'Station power, excl. laser', 'kW', {step: 0.1})}
    </div>

    ${section('Material', 'Main material of the product, per product.')}
    <div class="row g-3">
      ${sel('material', 'Material', '', MATERIALS)}
      ${num('materialWeight', 'Weight', 'kg', {step: 0.01})}
    </div>

    ${section('Consumables', 'Flow rates during welding. Leave 0 for consumables that are not used.')}
    <div class="row g-3">
      ${num('nitrogen', 'Nitrogen', 'm³/h', {step: 0.1})}
      ${num('argon', 'Argon', 'm³/h', {step: 0.1})}
      ${num('filler', 'Aluminium filler wire', 'kg/h', {step: 0.01})}
    </div>

    ${section('Quality parameters', 'Targets: porosity → lowest, tensile strength → highest, weld depth → 1.5 mm.')}
    <div class="row g-3">
      ${num('porosity', 'Porosity', '%', {step: 0.1})}
      ${num('tensile', 'Tensile strength', 'MPa', {step: 1})}
      ${num('weldDepth', 'Weld depth', 'mm', {step: 0.1})}
    </div>

    ${section('Productivity', 'Targets: automation → highest; specialisation, monitoring time, lead time and saturation → lowest.')}
    <div class="row g-3">
      ${sel('automation', 'Automation level', '', QUALITY_OPTIONS)}
      ${sel('specialisation', 'Operator specialisation', '', QUALITY_OPTIONS)}
      ${num('monitoring', 'Time to detect an issue', 'min', {step: 1})}
      ${num('leadTime', 'Lead time', 'days', {step: 1})}
      ${num('saturation', 'Machine saturation', '0–1', {max: 1, step: 0.01})}
    </div>
  `;
  return panel;
}

// ─────────────────────────────────────────────────────────────────────────────
// Tabs
// ─────────────────────────────────────────────────────────────────────────────

let nextIdx = 0;
const tabBar = document.getElementById('tab-bar');
const panels = document.getElementById('tab-panels');

function stationCount() {
  return panels.querySelectorAll('.tab-panel').length;
}

function updateCountLabel() {
  const n = stationCount();
  document.getElementById('exp-count-label').textContent = `${n} station${n === 1 ? '' : 's'} (at least 2)`;
  // Stations can be removed only while more than 2 remain
  tabBar.querySelectorAll('.remove-tab').forEach(btn => btn.classList.toggle('d-none', n <= 2));
}

function showTab(idx) {
  tabBar.querySelectorAll('.tab-btn').forEach(btn => {
    const active = parseInt(btn.dataset.tab) === idx;
    btn.classList.toggle('active', active);
    btn.setAttribute('aria-selected', active);
  });
  panels.querySelectorAll('.tab-panel').forEach(p => {
    p.hidden = parseInt(p.dataset.panel) !== idx;
  });
}

function addStation(values) {
  const idx = nextIdx++;
  const v = values ?? { ...EXAMPLES[EXAMPLES.length - 1], experimentId: idx + 1 };

  const item = document.createElement('li');
  item.className = 'nav-item d-flex align-items-center';
  item.setAttribute('role', 'presentation');
  item.innerHTML = `
    <button type="button" class="nav-link tab-btn" role="tab" data-tab="${idx}">Station ${v.experimentId}</button>
    <button type="button" class="btn btn-sm btn-link link-danger btn-icon remove-tab" data-tab="${idx}" aria-label="Remove station ${v.experimentId}"><i class="bi bi-x-lg" aria-hidden="true"></i></button>`;
  item.querySelector('.tab-btn').addEventListener('click', () => showTab(idx));
  item.querySelector('.remove-tab').addEventListener('click', () => removeStation(idx));
  tabBar.appendChild(item);

  panels.appendChild(createPanel(idx, v));
  showTab(idx);
  updateCountLabel();
}

function removeStation(idx) {
  if (stationCount() <= 2) return;
  tabBar.querySelector(`.tab-btn[data-tab="${idx}"]`)?.closest('li')?.remove();
  panels.querySelector(`[data-panel="${idx}"]`)?.remove();
  updateCountLabel();
  const first = panels.querySelector('.tab-panel');
  if (first) showTab(parseInt(first.dataset.panel));
}

document.getElementById('add-tab-btn').addEventListener('click', () => addStation());

// ─────────────────────────────────────────────────────────────────────────────
// Request body, in the format of the platform
// ─────────────────────────────────────────────────────────────────────────────

function buildPayload() {
  return Array.from(panels.querySelectorAll('.tab-panel')).map(panel => {
    const g  = (f) => panel.querySelector(`[data-field="${f}"]`)?.value ?? '';
    const gf = (f) => parseFloat(g(f)) || 0;
    const gi = (f) => parseInt(g(f)) || 0;

    const consumables = [
      { name: 'Nitrogen', flowRate: gf('nitrogen'), unit: 'm3/h' },
      { name: 'Argon', flowRate: gf('argon'), unit: 'm3/h' },
      { name: 'Aluminium filler wire', flowRate: gf('filler'), unit: 'kg/h' },
    ].filter(c => c.flowRate > 0);

    return {
      experimentId: gi('experimentId'),
      weldLength: gf('weldLength'),
      weldSpeed: gf('weldSpeed'),
      country: g('country'),
      laserPowerkW: gf('laserPower'),
      weldingStationPowerkW: gf('stationPower'),
      consumables,
      qualityParameters: [
        { name: 'Porosity', value: gf('porosity'), target: 'min' },
        { name: 'Tensile strength', value: gf('tensile'), target: 'max' },
        { name: 'Weld depth', value: gf('weldDepth'), target: 1.5 },
      ],
      maintenanceCosts: gf('maintenanceCosts'),
      cycleTime: gf('cycleTime'),
      scrapRate: gf('scrapRate'),
      recyclability: g('recyclability'),
      materials: [{ name: g('material'), weight: gf('materialWeight') }],
      productivity: [
        { name: 'Process automation level', value: g('automation'), target: 'max' },
        { name: 'Operator specialisation level', value: g('specialisation'), target: 'min' },
        { name: 'Process monitoring', value: gf('monitoring'), target: 'min' },
        { name: 'Production lead time', value: gf('leadTime'), target: 'min' },
        { name: 'Machine saturation', value: gf('saturation'), target: 'min' },
      ],
    };
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Submit
// ─────────────────────────────────────────────────────────────────────────────

document.getElementById('submit-btn').addEventListener('click', async () => {
  const btn  = document.getElementById('submit-btn');
  const pane = document.getElementById('response-panel');
  const body = document.getElementById('response-body');
  const lbl  = document.getElementById('response-status-label');
  const link = document.getElementById('response-link');
  const label = btn.innerHTML;

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-border spinner-border-sm" aria-hidden="true"></span>Submitting…';
  pane.classList.remove('d-none');
  body.textContent = '';
  lbl.className = 'badge rounded-pill text-bg-light';
  lbl.textContent = 'Sending…';
  link.classList.add('d-none');

  const csrf = document.querySelector('[name=csrfmiddlewaretoken]')?.value ?? '';
  try {
    const resp = await fetch('/dss/welding-stations/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
      body: JSON.stringify(buildPayload()),
    });
    const text = await resp.text();
    let data;
    try { data = JSON.parse(text); } catch { data = text.slice(0, 2000); }

    lbl.className = `badge rounded-pill ${resp.ok ? 'text-bg-success' : 'text-bg-danger'}`;
    lbl.textContent = `${resp.status} ${resp.statusText}`;
    body.textContent = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
    if (resp.ok && data.session_id) {
      link.href = `/dss/${data.session_id}/step/0/`;
      link.classList.remove('d-none');
    }
  } catch (err) {
    lbl.className = 'badge rounded-pill text-bg-danger';
    lbl.textContent = 'Network error';
    body.textContent = String(err);
  } finally {
    btn.disabled = false;
    btn.innerHTML = label;
  }
});

// Start with the three example stations
EXAMPLES.forEach(v => addStation(v));
showTab(0);
