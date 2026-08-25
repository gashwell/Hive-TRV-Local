/**
 * trv-schedule-card
 * Lovelace custom card for scheduling Hive TRVs via Zigbee2MQTT
 * Uses HA WebSocket API natively — no token or CORS issues
 *
 * Usage:
 *   type: custom:trv-schedule-card
 */

const DAYS = ['monday','tuesday','wednesday','thursday','friday','saturday','sunday'];
const DAY_LABELS = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
const MAX_SLOTS = 6;

const ROOMS = [
  { key:'living',       label:'Living Room',   trvs:['Hive TRV TV','Hive TRV Bay','Hive TRV Dining'] },
  { key:'bedroom',      label:'Bedroom',       trvs:['Hive TRV Bedroom'] },
  { key:'kitchen',      label:'Kitchen',       trvs:['Hive TRV Kitchen'] },
  { key:'office',       label:'Office',        trvs:['Hive TRV Office'] },
  { key:'hallway',      label:'Hallway',       trvs:['Hive TRV Hallway'] },
  { key:'entrance',     label:'Entrance',      trvs:['Hive TRV Entrance'] },
  { key:'guestroom',    label:'Guest Room',    trvs:['Hive TRV Guestroom'] },
  { key:'conservatory', label:'Conservatory',  trvs:['Hive TRV Conservatory'] },
  { key:'garage',       label:'Garage',        trvs:['Hive TRV Garage'] },
];

const CSS = `
  :host { display: block; }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  .card { padding: 16px; font-family: var(--paper-font-body1_-_font-family, system-ui, sans-serif); }
  h2 { font-size: 14px; font-weight: 500; color: var(--primary-text-color); margin-bottom: 16px;
       display: flex; align-items: center; gap: 8px; }
  .row { display: flex; gap: 10px; align-items: center; margin-bottom: 12px; flex-wrap: wrap; }
  .row label { font-size: 12px; color: var(--secondary-text-color); min-width: 44px; }
  select { font-size: 13px; background: var(--card-background-color,#fff);
    color: var(--primary-text-color); border: 1px solid var(--divider-color);
    border-radius: 6px; padding: 6px 10px; font-family: inherit; flex: 1; min-width: 140px; }
  .tabs { display: flex; gap: 4px; margin-bottom: 12px; flex-wrap: wrap; }
  .tab { padding: 5px 11px; font-size: 12px; border: 1px solid var(--divider-color);
    border-radius: 6px; background: transparent; color: var(--secondary-text-color);
    cursor: pointer; font-family: inherit; transition: all .15s; white-space: nowrap; }
  .tab.active { background: var(--primary-color,#1a73e8); color: #fff;
    border-color: var(--primary-color,#1a73e8); }
  .slots { display: flex; flex-direction: column; gap: 6px; margin-bottom: 12px; }
  .slot { display: flex; align-items: center; gap: 8px;
    background: var(--secondary-background-color,#f5f5f5);
    border: 1px solid var(--divider-color); border-radius: 6px; padding: 7px 10px; }
  .slot-num { font-size: 11px; color: var(--secondary-text-color); min-width: 14px; }
  .slot input[type=time] { font-size: 13px; border: 1px solid var(--divider-color);
    border-radius: 4px; padding: 4px 6px; background: var(--card-background-color,#fff);
    color: var(--primary-text-color); font-family: inherit; width: 106px; }
  .slot input[type=number] { font-size: 13px; border: 1px solid var(--divider-color);
    border-radius: 4px; padding: 4px 6px; background: var(--card-background-color,#fff);
    color: var(--primary-text-color); font-family: inherit; width: 64px; }
  .slot-lbl { font-size: 12px; color: var(--secondary-text-color); }
  .rm-btn { background: none; border: none; color: var(--error-color,#c0392b);
    cursor: pointer; font-size: 18px; line-height: 1; padding: 0 2px; }
  .no-slots { font-size: 13px; color: var(--secondary-text-color); padding: 8px 0; }
  .btn-row { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 14px; }
  .btn { padding: 6px 14px; font-size: 13px; border: 1px solid var(--divider-color);
    border-radius: 6px; background: transparent; color: var(--primary-text-color);
    cursor: pointer; font-family: inherit; transition: background .15s; }
  .btn:hover { background: var(--secondary-background-color); }
  .btn-primary { background: var(--primary-color,#1a73e8); color: #fff;
    border-color: var(--primary-color,#1a73e8); }
  .btn-primary:hover { opacity: .9; }
  .btn-success { background: #34a853; color: #fff; border-color: #34a853; }
  .btn-success:hover { opacity: .9; }
  .btn-sm { padding: 4px 10px; font-size: 12px; }
  .panel { background: var(--secondary-background-color,#f9f9f9);
    border: 1px solid var(--divider-color); border-radius: 8px;
    padding: 12px; margin-bottom: 10px; }
  .panel h3 { font-size: 13px; font-weight: 500; color: var(--primary-text-color); margin-bottom: 8px; }
  .checks { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 8px; }
  .chk { display: flex; align-items: center; gap: 4px; font-size: 13px;
    color: var(--secondary-text-color); cursor: pointer; }
  .chk input { width: 14px; height: 14px; cursor: pointer; }
  .pact { display: flex; gap: 6px; flex-wrap: wrap; }
  .msg { font-size: 12px; margin-top: 6px; min-height: 18px; }
  .msg.ok { color: #34a853; }
  .msg.err { color: var(--error-color,#c0392b); }
  .msg.info { color: var(--primary-color,#1a73e8); }
  .sec-hdr { font-size: 11px; font-weight: 500; color: var(--secondary-text-color);
    text-transform: uppercase; letter-spacing: .05em; margin: 14px 0 8px; }
  .write-row { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-bottom: 6px; }
`;

class TrvScheduleCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._hass = null;
    this._currentDay = 0;
    this._schedules = {};
    ROOMS.forEach(r => {
      this._schedules[r.key] = {};
      DAYS.forEach(d => { this._schedules[r.key][d] = []; });
    });
    this._build();
  }

  _build() {
    const style = document.createElement('style');
    style.textContent = CSS;

    const root = document.createElement('div');
    root.className = 'card';
    root.innerHTML = `
      <h2>📅 TRV Schedule Editor</h2>
      <div class="row">
        <label>Room</label>
        <select id="roomSel"></select>
      </div>
      <div class="tabs" id="dayTabs"></div>
      <div class="slots" id="slotList"></div>
      <div class="btn-row">
        <button class="btn" id="addSlot">+ Add slot</button>
      </div>
      <div class="sec-hdr">Copy options</div>
      <div class="panel">
        <h3>Copy this day to other days</h3>
        <div class="checks" id="copyDays"></div>
        <div class="pact">
          <button class="btn btn-sm" id="selAllDays">Select all</button>
          <button class="btn btn-primary btn-sm" id="copyDaysBtn">Copy to days</button>
        </div>
        <div class="msg" id="copyDaysMsg"></div>
      </div>
      <div class="panel">
        <h3>Copy full week to other rooms</h3>
        <div class="checks" id="copyRooms"></div>
        <div class="pact">
          <button class="btn btn-sm" id="selAllRooms">Select all</button>
          <button class="btn btn-primary btn-sm" id="copyRoomsBtn">Copy to rooms</button>
        </div>
        <div class="msg" id="copyRoomsMsg"></div>
      </div>
      <div class="write-row">
        <button class="btn" id="loadBtn">↓ Load from TRV</button>
        <button class="btn btn-success" id="writeBtn">✓ Write to TRVs</button>
        <button class="btn" id="clearBtn">Clear room</button>
      </div>
      <div class="msg" id="writeMsg"></div>
    `;

    // Populate room select
    const roomSel = root.querySelector('#roomSel');
    ROOMS.forEach(r => {
      const o = document.createElement('option');
      o.value = r.key;
      o.textContent = r.label;
      roomSel.appendChild(o);
    });

    this.shadowRoot.append(style, root);
    this._root = root;
    this._bindEvents();
    this._render();
  }

  set hass(hass) { this._hass = hass; }
  setConfig(config) { this._config = config || {}; }
  getCardSize() { return 10; }

  _room() {
    return ROOMS.find(r => r.key === this._root.querySelector('#roomSel').value);
  }

  _bindEvents() {
    const r = this._root;
    r.querySelector('#roomSel').addEventListener('change', () => {
      this._currentDay = 0; this._render();
    });
    r.querySelector('#addSlot').addEventListener('click', () => {
      const rk = this._room().key;
      const slots = this._schedules[rk][DAYS[this._currentDay]];
      if (slots.length >= MAX_SLOTS) return;
      const last = slots.length ? slots[slots.length - 1].time : '06:00';
      const [h, m] = last.split(':').map(Number);
      const nh = String(Math.min(h + 2, 23)).padStart(2, '0');
      slots.push({ time: `${nh}:${String(m).padStart(2, '0')}`, temp: 20 });
      this._render();
    });
    r.querySelector('#selAllDays').addEventListener('click', () => {
      r.querySelectorAll('#copyDays input').forEach(c => c.checked = true);
    });
    r.querySelector('#selAllRooms').addEventListener('click', () => {
      r.querySelectorAll('#copyRooms input').forEach(c => c.checked = true);
    });
    r.querySelector('#copyDaysBtn').addEventListener('click', () => {
      const src = DAYS[this._currentDay], rk = this._room().key;
      const targets = [...r.querySelectorAll('#copyDays input:checked')].map(c => c.value);
      if (!targets.length) { this._msg('copyDaysMsg','err','Select at least one day.'); return; }
      targets.forEach(t => { this._schedules[rk][t] = this._schedules[rk][src].map(s => ({...s})); });
      this._render();
      this._msg('copyDaysMsg','ok',`Copied to ${targets.map(t => DAY_LABELS[DAYS.indexOf(t)]).join(', ')}.`);
    });
    r.querySelector('#copyRoomsBtn').addEventListener('click', () => {
      const sk = this._room().key;
      const targets = [...r.querySelectorAll('#copyRooms input:checked')].map(c => c.value);
      if (!targets.length) { this._msg('copyRoomsMsg','err','Select at least one room.'); return; }
      targets.forEach(rk => {
        DAYS.forEach(d => { this._schedules[rk][d] = this._schedules[sk][d].map(s => ({...s})); });
      });
      this._msg('copyRoomsMsg','ok',
        `Week copied to ${targets.map(t => ROOMS.find(r=>r.key===t).label).join(', ')}.`);
    });
    r.querySelector('#clearBtn').addEventListener('click', () => {
      const rk = this._room().key;
      DAYS.forEach(d => { this._schedules[rk][d] = []; });
      this._render();
    });
    r.querySelector('#loadBtn').addEventListener('click', () => this._load());
    r.querySelector('#writeBtn').addEventListener('click', () => this._write());
  }

  _render() {
    this._renderTabs();
    this._renderSlots();
    this._renderCopyDays();
    this._renderCopyRooms();
    this._root.querySelector('#copyDaysMsg').textContent = '';
    this._root.querySelector('#copyRoomsMsg').textContent = '';
  }

  _renderTabs() {
    const room = this._room(), r = this._root;
    r.querySelector('#dayTabs').innerHTML = DAYS.map((d, i) => {
      const n = this._schedules[room.key][d].length;
      return `<button class="tab${i===this._currentDay?' active':''}" data-i="${i}">${DAY_LABELS[i]}${n?` (${n})`:''}</button>`;
    }).join('');
    r.querySelectorAll('.tab').forEach(b => {
      b.addEventListener('click', () => { this._currentDay = +b.dataset.i; this._render(); });
    });
  }

  _renderSlots() {
    const room = this._room(), r = this._root;
    const list = r.querySelector('#slotList');
    const slots = this._schedules[room.key][DAYS[this._currentDay]];
    if (!slots.length) {
      list.innerHTML = '<div class="no-slots">No slots — tap + Add slot below.</div>';
      return;
    }
    list.innerHTML = slots.map((s, i) => `
      <div class="slot">
        <span class="slot-num">${i+1}</span>
        <input type="time" value="${s.time}" data-i="${i}" data-f="time" />
        <span class="slot-lbl">→</span>
        <input type="number" value="${s.temp}" min="1" max="32" step="0.5" data-i="${i}" data-f="temp" />
        <span class="slot-lbl">°C</span>
        <button class="rm-btn" data-i="${i}">×</button>
      </div>`).join('');
    list.querySelectorAll('input').forEach(inp => {
      inp.addEventListener('change', () => {
        const i = +inp.dataset.i, f = inp.dataset.f;
        const rk = this._room().key, d = DAYS[this._currentDay];
        if (f === 'time') this._schedules[rk][d][i].time = inp.value;
        if (f === 'temp') this._schedules[rk][d][i].temp = parseFloat(inp.value) || 20;
        this._renderTabs();
      });
    });
    list.querySelectorAll('.rm-btn').forEach(b => {
      b.addEventListener('click', () => {
        this._schedules[this._room().key][DAYS[this._currentDay]].splice(+b.dataset.i, 1);
        this._render();
      });
    });
  }

  _renderCopyDays() {
    this._root.querySelector('#copyDays').innerHTML = DAYS.map((d, i) => i === this._currentDay ? '' :
      `<label class="chk"><input type="checkbox" value="${d}" />${DAY_LABELS[i]}</label>`
    ).join('');
  }

  _renderCopyRooms() {
    const room = this._room();
    this._root.querySelector('#copyRooms').innerHTML = ROOMS
      .filter(r => r.key !== room.key)
      .map(r => `<label class="chk"><input type="checkbox" value="${r.key}" />${r.label}</label>`)
      .join('');
  }

  _msg(id, type, text) {
    const el = this._root.querySelector('#' + id);
    el.className = 'msg ' + type;
    el.textContent = text;
  }

  async _mqttPublish(topic, payload) {
    return this._hass.callService('mqtt', 'publish', {
      topic,
      payload: typeof payload === 'string' ? payload : JSON.stringify(payload),
    });
  }

  async _load() {
    if (!this._hass) return;
    const room = this._room();
    const trv = room.trvs[0];
    this._msg('writeMsg', 'info', `Loading schedule from ${trv}...`);
    try {
      await this._mqttPublish(`zigbee2mqtt/${trv}/get`, { weekly_schedule: '' });
      await new Promise(res => setTimeout(res, 2000));
      const entityId = 'climate.' + trv.toLowerCase().replace(/ /g, '_');
      const state = this._hass.states[entityId];
      const ws = state?.attributes?.weekly_schedule;
      if (ws) {
        DAYS.forEach(d => {
          if (ws[d]?.length) {
            this._schedules[room.key][d] = ws[d].map(t => ({
              time: t.transitionTime || '06:00',
              temp: t.heatSetpoint || 20,
            }));
          }
        });
        this._msg('writeMsg', 'ok', 'Schedule loaded from device.');
      } else {
        this._msg('writeMsg', 'info', 'No schedule found on device — starting fresh.');
      }
      this._render();
    } catch(e) {
      this._msg('writeMsg', 'err', 'Load failed: ' + e.message);
    }
  }

  async _write() {
    if (!this._hass) return;
    const room = this._room();
    let written = 0, errors = [];
    this._msg('writeMsg', 'info', 'Writing schedule...');

    for (const trv of room.trvs) {
      for (const day of DAYS) {
        const slots = [...this._schedules[room.key][day]]
          .sort((a, b) => a.time.localeCompare(b.time));
        if (!slots.length) continue;
        try {
          await this._mqttPublish(`zigbee2mqtt/${trv}/set`, {
            weekly_schedule: {
              [day]: slots.map(s => ({
                transitionTime: s.time,
                heatSetpoint: parseFloat(s.temp),
              }))
            }
          });
          written++;
          await new Promise(res => setTimeout(res, 300));
        } catch(e) {
          errors.push(`${trv}/${day}: ${e.message}`);
        }
      }
      try {
        await this._mqttPublish(`zigbee2mqtt/${trv}/set`, {
          programming_operation_mode: 'schedule'
        });
      } catch(e) {
        errors.push(`${trv} mode: ${e.message}`);
      }
    }

    if (errors.length) {
      this._msg('writeMsg', 'err', 'Errors: ' + errors.join('; '));
    } else {
      this._msg('writeMsg', 'ok',
        `Written ${written} day(s) to ${room.trvs.length} TRV(s). Mode set to Schedule.`);
    }
  }
}

customElements.define('trv-schedule-card', TrvScheduleCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: 'trv-schedule-card',
  name: 'TRV Schedule Card',
  description: 'Schedule editor for Hive TRVs via Zigbee2MQTT',
  preview: false,
  documentationURL: 'https://github.com/gashwell/Hive-TRV-Local',
});
