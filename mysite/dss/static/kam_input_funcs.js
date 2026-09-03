// ─────────────────────────────────────────────────────────────────────────────
// Configuration — predefined names and default values
// ─────────────────────────────────────────────────────────────────────────────

const COUNTRIES = ['DE', 'US', 'FR', 'NL', 'BE', 'PL', 'IT', 'UK'];
const QUALITY_OPTIONS = ['low', 'medium', 'high'];

// ─────────────────────────────────────────────────────────────────────────────
// HTML builder helpers
// ─────────────────────────────────────────────────────────────────────────────

const inputCls = `w-full rounded-md border border-slate-700 bg-slate-800 px-3 py-2
                  text-sm text-slate-100 placeholder-slate-500
                  focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500`;

function labelWrap(label, unit, inner) {
  return `
    <div>
      <label class="block text-xs font-semibold uppercase tracking-wider
                    text-slate-400 mb-1">
        ${label}${unit ? ` <span class="normal-case font-normal text-slate-500">(${unit})</span>` : ''}
      </label>
      ${inner}
    </div>`;
}

function numInput(field, value, {min = 0, step = 'any', placeholder = ''} = {}) {
  return `<input type="number" data-field="${field}" value="${value ?? ''}"
                 min="${min}" step="${step}" placeholder="${placeholder}"
                 class="${inputCls}">`;
}

function selectInput(field, options, selected) {
  const opts = options.map(o =>
    `<option value="${o}" ${o === selected ? 'selected' : ''}>${o}</option>`
  ).join('');
  return `<select data-field="${field}" class="${inputCls}">${opts}</select>`;
}

function sectionHeader(title, hint = '') {
  return `
    <div class="flex items-baseline gap-3 mb-3 mt-8 first:mt-0">
      <h3 class="text-sm font-semibold text-slate-200 whitespace-nowrap">${title}</h3>
      <span class="h-px flex-1 bg-slate-800"></span>
    </div>
    ${hint ? `<p class="text-xs text-slate-500 mb-3">${hint}</p>` : ''}`;
}

function grid2(...fields) {
  return `<div class="grid grid-cols-2 gap-3">${fields.join('')}</div>`;
}

function grid3(...fields) {
  return `<div class="grid grid-cols-3 gap-3">${fields.join('')}</div>`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Panel builder
// ─────────────────────────────────────────────────────────────────────────────

function createPanel(idx) {

  const panel = document.createElement('div');
  panel.className = 'tab-panel';
  panel.dataset.panel = idx;

  panel.innerHTML = `

    ${sectionHeader('General')}
    ${grid3(
      labelWrap('Experiment ID', '', numInput('experimentId', idx+1, {min: 1, step: 1})),
      labelWrap('Country', '', selectInput('country', COUNTRIES)),
      labelWrap('Recyclability', '', selectInput('recyclability', QUALITY_OPTIONS, 'medium')),
    )}
    ${grid3(
      labelWrap('Maintenance costs', '€', numInput('maintenanceCosts', {placeholder: '0.00'})),
      labelWrap('Cycle time', 's', numInput('cycleTime', 1, {min: 1, step: 1})),
      labelWrap('Scrap rate', '0–1', numInput('scrapRate', 0, {min: 0, max: 1, step: 0.01})),
    )}

    ${sectionHeader('Process')}
    ${grid2(
      labelWrap('Weld length', 'mm', numInput('weldLength', 1)),
      labelWrap('Weld speed', 'mm/min', numInput('weldSpeed', 1)),
    )}
    ${grid2(
      labelWrap('Laser power', 'kW', numInput('laserPower', 1)),
      labelWrap('Station power', 'kW', numInput('stationPower', 1)),
    )}

    ${sectionHeader('Material', 'Predefined material — enter quantity used')}
    ${labelWrap('Stainless steel', 'kg', numInput('materialWeight', 1))}

    ${sectionHeader('Consumables', 'Predefined names — enter quantity used')}
    ${grid3(
      labelWrap('Nitrogen', 'm³/h', numInput('nitrogen', 0)),
      labelWrap('Argon', 'm³/h', numInput('argon', 0)),
      labelWrap('Aluminium (filler wire)', 'kg/h', numInput('aluminium', 0, {step: 0.001})),
    )}

    ${sectionHeader('Quality parameters', 'Targets: Porosity → min · Tensile strength → max · Weld depth → 3.5')}
    ${grid3(
      labelWrap('Porosity', '',         numInput('porosity', 0.0, {step: 0.01})),
      labelWrap('Tensile strength', '', numInput('tensile', 0.0, {step: 0.01})),
      labelWrap('Weld depth', 'mm',     numInput('weldDepth', 0.0, {step: 0.1})),
    )}

    ${sectionHeader('Productivity', 'Targets: Automation → max · Specialisation → min · Monitoring → min · Lead time → min · Saturation → max')}

    ${grid2(
      labelWrap('Automation level', '', selectInput('automation', QUALITY_OPTIONS, 'medium')),
      labelWrap('Specialisation level', '', selectInput('specialisation', QUALITY_OPTIONS, 'low')),
    )}
    ${grid3(
      labelWrap('Monitoring', 'min until issue detection', numInput('monitoring', {step: 1})),
      labelWrap('Lead time', 'hours', numInput('leadTime', 1, {step: 1})),
      labelWrap('Saturation', '0–1', numInput('saturation', {max: 1, step: 0.01})),
    )}
  `;

  return panel;
}

// ─────────────────────────────────────────────────────────────────────────────
// Tab management
// ─────────────────────────────────────────────────────────────────────────────

let expCount  = 0;
let activeTab = 0;

const tabBar    = document.getElementById('tab-bar');
const addTabBtn = document.getElementById('add-tab-btn');
const panels    = document.getElementById('tab-panels');

function updateCountLabel() {
  const n = expCount;
  document.getElementById('exp-count-label').textContent =
    `${n} experiment${n === 1 ? '' : 's'}`;
}

function showTab(idx) {
  activeTab = idx;
  tabBar.querySelectorAll('.tab-btn').forEach(btn => {
    const active = parseInt(btn.dataset.tab) === idx;
    btn.className = `tab-btn mb-[-1px] flex-none flex items-center gap-1.5 px-4 py-2 text-sm
      font-medium border-b-2 transition ${
        active
          ? 'border-indigo-500 text-indigo-400'
          : 'border-transparent text-slate-500 hover:text-slate-300'
      }`;
  });
  panels.querySelectorAll('.tab-panel').forEach(p => {
    p.style.display = parseInt(p.dataset.panel) === idx ? 'block' : 'none';
  });
}

function addExperiment() {
  const idx = expCount;
  expCount++;

  // Tab button
  const tab = document.createElement('button');
  tab.type = 'button';
  tab.dataset.tab = idx;
  tab.innerHTML = `
    <span>Exp ${idx + 1}</span>
    ${idx >= 2 ? `<span class="remove-tab text-slate-600 hover:text-red-400 leading-none"
                        data-tab="${idx}">×</span>` : ''}
  `;
  tab.addEventListener('click', (e) => {
    if (e.target.classList.contains('remove-tab')) return;
    showTab(idx);
  });
  addTabBtn.insertAdjacentElement('beforebegin', tab);

  // Remove handler on the × span
  const removeSpan = tab.querySelector('.remove-tab');
  if (removeSpan) {
    removeSpan.addEventListener('click', () => removeExperiment(idx));
  }

  // Panel
  const panel = createPanel(idx);
  panels.appendChild(panel);

  showTab(idx);
  updateCountLabel();
}

function removeExperiment(idx) {
  if (expCount <= 2) return;

  // Remove tab button
  tabBar.querySelector(`[data-tab="${idx}"]`)?.closest('button')?.remove();

  // Remove panel
  panels.querySelector(`[data-panel="${idx}"]`)?.remove();

  expCount--;
  updateCountLabel();

  // Show a remaining tab
  const remaining = panels.querySelector('.tab-panel');
  if (remaining) showTab(parseInt(remaining.dataset.panel));
}

addTabBtn.addEventListener('click', addExperiment);

// ─────────────────────────────────────────────────────────────────────────────
// Payload builder
// ─────────────────────────────────────────────────────────────────────────────

function buildPayload() {
  return Array.from(panels.querySelectorAll('.tab-panel')).map(panel => {
    const g  = (f) => panel.querySelector(`[data-field="${f}"]`)?.value ?? '';
    const gf = (f) => parseFloat(g(f)) || 0;
    const gi = (f) => parseInt(g(f))   || 0;
    const gl = (f) => ({ low: 0, medium: 0.5, high: 1 }[g(f)] ?? 0);

    return {
      experimentId:          gi('experimentId'),
      weldLength:            gf('weldLength'),
      weldSpeed:             gf('weldSpeed'),
      country:               g('country'),
      laserPowerkW:          gf('laserPower'),
      weldingStationPowerkW: gf('stationPower'),
      materials: [{ name: 'Stainless steel', weight: gf('materialWeight') }],
      maintenanceCosts:      gf('maintenanceCosts'),
      cycleTime:             gf('cycleTime'),
      scrapRate:             gf('scrapRate'),
      recyclability:         gl('recyclability'),
      consumables: [
        { name: 'Nitrogen',                flowRate: gf('nitrogen'),  unit: 'm3/h'},
        { name: 'Argon',                   flowRate: gf('argon'),     unit: 'm3/h'},
        { name: 'Aluminium (filler wire)', flowRate: gf('aluminium'), unit: 'kg/h'},
      ],
      qualityParameters: [
        { name: 'Porosity',         value: gf('porosity'),  target: 'min'},
        { name: 'Tensile strength', value: gf('tensile'),   target: 'max'},
        { name: 'Weld depth',       value: gf('weldDepth'), target: 3.5},
      ],
      productivity: [
        { name: 'Process automation level', value: gl('automation'), target: 'max' },
        { name: 'Operator specialisation level', value: gl('specialisation'), target: 'min' },
        { name: 'Process monitoring', value: gi('monitoring'), target: 'min' },
        { name: 'Production lead time', value: gi('leadTime'), target: 'min' },
        { name: 'Machine saturation', value: gf('saturation'), target: 'max' },
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
  const dot  = document.getElementById('response-status-dot');
  const lbl  = document.getElementById('response-status-label');
  const link = document.getElementById('response-link');

  btn.disabled = true;
  btn.textContent = 'Submitting…';
  pane.classList.remove('hidden');
  body.textContent = '';
  dot.className  = 'h-2.5 w-2.5 rounded-full bg-slate-500 animate-pulse';
  lbl.textContent = 'Sending request…';
  link.classList.add('hidden');

  const csrf = document.querySelector('[name=csrfmiddlewaretoken]')?.value ?? '';

  try {
    const payload = buildPayload();
    const resp    = await fetch('/dss/welding-stations/', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
      body:    JSON.stringify(payload),
    });

    const data = await resp.json();
    const ok   = resp.ok;

    dot.className   = `h-2.5 w-2.5 rounded-full ${ok ? 'bg-emerald-500' : 'bg-red-500'}`;
    lbl.textContent = `${resp.status} ${resp.statusText}`;
    lbl.className   = `text-sm font-semibold ${ok ? 'text-emerald-400' : 'text-red-400'}`;
    body.textContent = JSON.stringify(data, null, 2);

    if (ok && data.session_id) {
      link.href = `/dss/${data.session_id}/step/0/`;
      link.classList.remove('hidden');
    }
  } catch (err) {
    dot.className   = 'h-2.5 w-2.5 rounded-full bg-red-500';
    lbl.textContent = 'Network error';
    lbl.className   = 'text-sm font-semibold text-red-400';
    body.textContent = String(err);
  } finally {
    btn.disabled    = false;
    btn.innerHTML   = `
      <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none"
           viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z"/>
      </svg>
      Submit to API`;
  }
});

// ─────────────────────────────────────────────────────────────────────────────
// Initialise with two experiments
// ─────────────────────────────────────────────────────────────────────────────
addExperiment();
addExperiment();
