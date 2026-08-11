/**
 * hive-local-room-card
 * Lovelace card for a Hive Local v5 room climate entity.
 *
 * Config:
 *   type: custom:hive-local-room-card
 *   entity: climate.living_room   (required — must be a hive_local room entity)
 *   name: Living Room             (optional — overrides entity name)
 *
 * Reads from entity state attributes:
 *   mode, schedule, current_schedule_slot, member_detail,
 *   heat_required, boost_remaining_minutes, boost_ends,
 *   outdoor_temperature, frost_protection_active
 *
 * Calls HA services:
 *   climate.set_temperature         — manual temp change
 *   climate.set_preset_mode         — schedule / manual / boost / off
 *   climate.turn_on / turn_off
 *   hive_local.room_boost
 *   hive_local.room_end_boost
 *   hive_local.room_set_schedule
 */

const CARD_VERSION = '5.0.0';
const DOMAIN       = 'hive_local';

const DAYS     = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
const MODE_COL = {
  schedule: '#e8632a',
  manual:   '#2563eb',
  boost:    '#dc2626',
  off:      '#6b7280',
};

const TPL = document.createElement('template');
TPL.innerHTML = `
<style>
  :host{display:block}
  *{box-sizing:border-box;margin:0;padding:0}
  .card{background:var(--ha-card-background,var(--card-background-color,#fff));
    border-radius:12px;overflow:hidden;
    box-shadow:var(--ha-card-box-shadow,0 2px 8px rgba(0,0,0,.1));
    font-family:var(--paper-font-body1_-_font-family,sans-serif)}
  .header{padding:16px 18px 14px;transition:background .3s}
  .hdr-top{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:12px}
  .room-name{font-size:13px;color:rgba(255,255,255,.8);margin-bottom:2px}
  .room-status{font-size:12px;color:rgba(255,255,255,.65);display:flex;align-items:center;gap:5px}
  .cur-temp{text-align:right}
  .cur-temp .lbl{font-size:11px;color:rgba(255,255,255,.7)}
  .cur-temp .val{font-size:30px;font-weight:500;color:#fff;line-height:1}
  .target-row{display:flex;align-items:center;justify-content:center;gap:16px;
    border-top:0.5px solid rgba(255,255,255,.2);padding-top:12px}
  .tbtn{width:38px;height:38px;border-radius:50%;
    background:rgba(255,255,255,.18);border:none;color:#fff;
    font-size:22px;cursor:pointer;display:flex;align-items:center;justify-content:center;line-height:1}
  .tbtn:hover{background:rgba(255,255,255,.28)}
  .tdisp{text-align:center}
  .tdisp .lbl{font-size:11px;color:rgba(255,255,255,.7)}
  .tdisp .val{font-size:32px;font-weight:500;color:#fff;line-height:1;min-width:88px}
  .modes{display:flex;border-bottom:1px solid var(--divider-color,#e0e0e0)}
  .mbtn{flex:1;padding:9px 2px;border:none;
    background:transparent;color:var(--secondary-text-color,#727272);
    font-size:10px;cursor:pointer;
    font-family:inherit;display:flex;flex-direction:column;align-items:center;gap:3px;
    border-right:0.5px solid var(--divider-color,#e0e0e0)}
  .mbtn:last-child{border-right:none}
  .mbtn.active{background:var(--secondary-background-color,#f5f5f5);
    color:var(--primary-text-color,#212121);font-weight:500}
  .mbtn svg{width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
  .members{padding:10px 14px;border-bottom:1px solid var(--divider-color,#e0e0e0);
    background:var(--secondary-background-color,#fafafa)}
  .mtitle{font-size:11px;color:var(--secondary-text-color,#727272);margin-bottom:6px}
  .member{display:flex;justify-content:space-between;align-items:center;padding:3px 0}
  .mname{font-size:12px;color:var(--secondary-text-color,#727272)}
  .mright{display:flex;align-items:center;gap:6px}
  .mtemp{font-size:13px;font-weight:500;color:var(--primary-text-color,#212121)}
  .hdot{width:7px;height:7px;border-radius:50%}
  .sched{padding:12px 14px}
  .sched-hdr{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}
  .sched-title{font-size:13px;font-weight:500;color:var(--primary-text-color,#212121)}
  .add-btn{font-size:12px;color:var(--primary-color,#03a9f4);
    background:none;border:none;cursor:pointer;font-family:inherit;
    display:flex;align-items:center;gap:3px}
  .day-tabs{display:flex;gap:3px;margin-bottom:10px;flex-wrap:wrap}
  .dtab{padding:3px 7px;border-radius:6px;
    border:0.5px solid var(--divider-color,#e0e0e0);
    font-size:10px;cursor:pointer;
    background:transparent;color:var(--secondary-text-color,#727272);font-family:inherit}
  .dtab.active{background:rgba(3,169,244,.1);
    border-color:var(--primary-color,#03a9f4);
    color:var(--primary-color,#03a9f4);font-weight:500}
  .slots{display:flex;flex-direction:column;gap:4px}
  .slot{display:flex;align-items:center;gap:8px;padding:6px 10px;
    border-radius:8px;border:0.5px solid var(--divider-color,#e0e0e0);cursor:pointer}
  .slot:hover{border-color:var(--primary-color,#03a9f4)}
  .slot.current{background:rgba(232,99,42,.08);border-color:#e8632a}
  .slot.current .stime{color:#e8632a}
  .stime{font-size:13px;font-weight:500;color:var(--primary-text-color,#212121);min-width:44px}
  .stemp{font-size:13px;color:var(--primary-text-color,#212121);flex:1}
  .sdesc{font-size:11px;color:var(--secondary-text-color,#727272)}
  .snow{font-size:10px;padding:1px 6px;border-radius:4px;
    background:rgba(232,99,42,.15);color:#e8632a;font-weight:500}
  .sdel{background:none;border:none;cursor:pointer;
    color:var(--secondary-text-color,#727272);padding:2px;font-size:14px;line-height:1}
  .sdel:hover{color:#e53935}
  .edit-form{display:flex;flex-direction:column;gap:6px;padding:10px;
    border-radius:8px;border:0.5px solid var(--primary-color,#03a9f4);
    background:rgba(3,169,244,.04)}
  .dp-row{display:flex;gap:3px}
  .dp{width:28px;height:28px;border-radius:50%;
    border:0.5px solid var(--divider-color,#e0e0e0);
    font-size:10px;cursor:pointer;background:transparent;
    color:var(--secondary-text-color,#727272);font-family:inherit;
    display:flex;align-items:center;justify-content:center}
  .dp.on{background:var(--primary-color,#03a9f4);border-color:var(--primary-color,#03a9f4);color:#fff}
  .form-row{display:flex;gap:6px;align-items:center;flex-wrap:wrap}
  .form-row input{padding:5px 8px;border-radius:6px;
    border:0.5px solid var(--divider-color,#e0e0e0);
    background:var(--card-background-color,#fff);
    color:var(--primary-text-color,#212121);font-size:12px;font-family:inherit}
  .form-row input[type=time]{width:90px}
  .form-row input[type=number]{width:66px}
  .form-row .save{padding:5px 12px;border-radius:6px;
    border:none;background:var(--primary-color,#03a9f4);
    color:#fff;font-size:12px;cursor:pointer;font-family:inherit}
  .form-row .cancel{padding:5px 10px;border-radius:6px;
    border:0.5px solid var(--divider-color,#e0e0e0);
    background:none;color:var(--secondary-text-color,#727272);
    font-size:12px;cursor:pointer;font-family:inherit}
  .empty{font-size:12px;color:var(--secondary-text-color,#727272);
    text-align:center;padding:16px 0}
  .boost-panel{padding:10px 14px;border-top:1px solid var(--divider-color,#e0e0e0)}
  .boost-row{display:flex;gap:8px}
  .bbtn{flex:1;padding:8px;border-radius:8px;
    border:0.5px solid var(--divider-color,#e0e0e0);
    background:transparent;color:var(--secondary-text-color,#727272);
    font-size:12px;cursor:pointer;font-family:inherit;
    display:flex;align-items:center;justify-content:center;gap:5px}
  .bbtn:hover{border-color:var(--primary-color,#03a9f4);color:var(--primary-color,#03a9f4)}
  .bbtn.boosting{border-color:#dc2626;color:#dc2626}
  .bbtn svg{width:14px;height:14px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
  .boost-timer{font-size:11px;color:#dc2626;text-align:center;padding:4px 0 0}
  .frost-bar{display:flex;align-items:center;gap:8px;padding:8px 14px;
    background:rgba(33,150,243,.06);border-top:1px solid var(--divider-color,#e0e0e0);
    font-size:12px;color:var(--secondary-text-color,#727272)}
</style>
<div class="card">
  <div class="header" id="hdr">
    <div class="hdr-top">
      <div>
        <div class="room-name" id="roomName">Room</div>
        <div class="room-status" id="roomStatus">—</div>
      </div>
      <div class="cur-temp">
        <div class="lbl">Average</div>
        <div class="val" id="curTemp">—</div>
      </div>
    </div>
    <div class="target-row">
      <button class="tbtn" id="tMinus">−</button>
      <div class="tdisp"><div class="lbl">Target</div><div class="val" id="tVal">—</div></div>
      <button class="tbtn" id="tPlus">+</button>
    </div>
  </div>
  <div class="modes" id="modes"></div>
  <div class="members" id="membersSection" style="display:none">
    <div class="mtitle">Members</div>
    <div id="memberList"></div>
  </div>
  <div class="sched" id="schedSection" style="display:none">
    <div class="sched-hdr">
      <span class="sched-title">Weekly schedule</span>
      <button class="add-btn" id="addBtn">+ Add slot</button>
    </div>
    <div class="day-tabs" id="dayTabs"></div>
    <div class="slots" id="slotList"></div>
  </div>
  <div class="boost-panel">
    <div class="boost-row">
      <button class="bbtn" id="boostBtn">
        <svg viewBox="0 0 24 24"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
        Boost
      </button>
      <button class="bbtn" id="offBtn">
        <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
        Frost protect
      </button>
    </div>
    <div class="boost-timer" id="boostTimer" style="display:none"></div>
  </div>
  <div class="frost-bar" id="frostBar" style="display:none">
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="2" x2="12" y2="22"/><path d="M17 7l-5 5-5-5"/><path d="M17 17l-5-5-5 5"/><path d="M2 12l5-3 5 3 5-3 5 3"/><path d="M2 12l5 3 5-3 5 3 5-3"/></svg>
    <span id="frostText"></span>
  </div>
</div>`;

class HiveLocalRoomCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({mode:'open'});
    this.shadowRoot.appendChild(TPL.content.cloneNode(true));
    this._hass     = null;
    this._config   = null;
    this._schedule = [];
    this._target   = 20.0;
    this._filterDay= 'all';
    this._editIdx  = null;
    this._adding   = false;
    this._modesBuilt = false;
  }

  setConfig(config) {
    if (!config.entity) throw new Error('hive-local-room-card: entity required');
    this._config = config;
    this._buildModes();
    this._buildDayTabs();
    this._bindStatic();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() { return 6; }

  getGridOptions() { return {columns:6, rows:7}; }

  static getConfigForm() {
    return {
      schema: [
        {name:'entity',   selector:{entity:{domain:'climate',integration:'hive_local'}}},
        {name:'name',     selector:{text:{}}},
      ],
    };
  }

  // ── Build static structure ────────────────────────────────────────────────

  _buildModes() {
    const icons = {
      schedule: `<svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>`,
      manual:   `<svg viewBox="0 0 24 24"><path d="M14 14.76V3.5a2.5 2.5 0 0 0-5 0v11.26a4.5 4.5 0 1 0 5 0z"/></svg>`,
      boost:    `<svg viewBox="0 0 24 24"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>`,
      off:      `<svg viewBox="0 0 24 24"><path d="M18.36 6.64a9 9 0 1 1-12.73 0"/><line x1="12" y1="2" x2="12" y2="12"/></svg>`,
    };
    const labels = {schedule:'Schedule',manual:'Manual',boost:'Boost',off:'Off'};
    const modes  = document.createDocumentFragment();
    Object.entries(labels).forEach(([mode,label]) => {
      const btn = document.createElement('button');
      btn.className   = 'mbtn';
      btn.dataset.mode= mode;
      btn.innerHTML   = icons[mode] + label;
      btn.addEventListener('click', () => this._setMode(mode));
      modes.appendChild(btn);
    });
    this.shadowRoot.getElementById('modes').appendChild(modes);
  }

  _buildDayTabs() {
    const tabs = document.createDocumentFragment();
    [['all','All'],['0','Mon'],['1','Tue'],['2','Wed'],['3','Thu'],
     ['4','Fri'],['5','Sat'],['6','Sun']].forEach(([val,label]) => {
      const btn = document.createElement('button');
      btn.className    = 'dtab' + (val==='all'?' active':'');
      btn.dataset.filter= val;
      btn.textContent  = label;
      btn.addEventListener('click', () => {
        this.shadowRoot.querySelectorAll('.dtab').forEach(t=>t.classList.remove('active'));
        btn.classList.add('active');
        this._filterDay = val;
        this._editIdx   = null;
        this._adding    = false;
        this._renderSlots();
      });
      tabs.appendChild(btn);
    });
    this.shadowRoot.getElementById('dayTabs').appendChild(tabs);
  }

  _bindStatic() {
    this.shadowRoot.getElementById('tMinus').addEventListener('click', () => {
      this._target = Math.max(5, this._target - 0.5);
      this.shadowRoot.getElementById('tVal').textContent = this._target.toFixed(1) + '°';
      this._callService('climate','set_temperature',{temperature:this._target});
    });
    this.shadowRoot.getElementById('tPlus').addEventListener('click', () => {
      this._target = Math.min(32, this._target + 0.5);
      this.shadowRoot.getElementById('tVal').textContent = this._target.toFixed(1) + '°';
      this._callService('climate','set_temperature',{temperature:this._target});
    });
    this.shadowRoot.getElementById('addBtn').addEventListener('click', () => {
      this._adding  = true;
      this._editIdx = null;
      this._renderSlots();
    });
    this.shadowRoot.getElementById('boostBtn').addEventListener('click', () => {
      const state = this._getState();
      if (!state) return;
      const attrs = state.attributes || {};
      if (attrs.mode === 'boost') {
        this._callService(DOMAIN,'room_end_boost',{});
      } else {
        this._callService(DOMAIN,'room_boost',{duration_minutes:30});
      }
    });
    this.shadowRoot.getElementById('offBtn').addEventListener('click', () => {
      const state = this._getState();
      if (!state) return;
      if (state.state === 'off') {
        this._callService('climate','turn_on',{});
      } else {
        this._callService('climate','turn_off',{});
      }
    });
  }

  // ── Render ────────────────────────────────────────────────────────────────

  _render() {
    if (!this._hass || !this._config) return;
    const state = this._getState();
    if (!state) { this.shadowRoot.getElementById('roomName').textContent = this._config.entity; return; }

    const attrs  = state.attributes || {};
    const mode   = attrs.mode       || 'manual';
    const hscol  = MODE_COL[mode]   || '#e8632a';

    this._schedule = attrs.schedule || [];
    this._target   = parseFloat(attrs.temperature || 20);

    // Header
    this.shadowRoot.getElementById('hdr').style.background = hscol;
    this.shadowRoot.getElementById('roomName').textContent =
      this._config.name || attrs.friendly_name || state.entity_id;

    const statusMap = {schedule:'On schedule',manual:'Manual',boost:'Boosting',off:'Off'};
    this.shadowRoot.getElementById('roomStatus').textContent = statusMap[mode] || mode;

    const cur = attrs.current_temperature;
    this.shadowRoot.getElementById('curTemp').textContent =
      cur != null ? parseFloat(cur).toFixed(1) + '°' : '—';
    this.shadowRoot.getElementById('tVal').textContent =
      this._target.toFixed(1) + '°';

    // Mode buttons
    this.shadowRoot.querySelectorAll('.mbtn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.mode === mode);
    });

    // Members
    const members = attrs.member_detail || [];
    const mSec = this.shadowRoot.getElementById('membersSection');
    const mList = this.shadowRoot.getElementById('memberList');
    if (members.length) {
      mSec.style.display = '';
      mList.innerHTML = members.map(m => {
        const temp   = m.temperature != null ? parseFloat(m.temperature).toFixed(1)+'°' : '—';
        const dotCol = m.heating ? '#e8632a' : 'var(--divider-color,#e0e0e0)';
        const bat    = m.battery != null ? ` · ${m.battery}%` : '';
        return `<div class="member">
          <span class="mname">${m.name}${bat}</span>
          <div class="mright">
            <div class="hdot" style="background:${dotCol}"></div>
            <span class="mtemp">${temp}</span>
          </div>
        </div>`;
      }).join('');
    } else {
      mSec.style.display = 'none';
    }

    // Schedule panel — only visible in schedule mode
    this.shadowRoot.getElementById('schedSection').style.display =
      mode === 'schedule' ? '' : 'none';

    if (mode === 'schedule') this._renderSlots();

    // Boost panel
    const isBoosting  = mode === 'boost';
    const boostBtn    = this.shadowRoot.getElementById('boostBtn');
    const boostTimer  = this.shadowRoot.getElementById('boostTimer');
    boostBtn.classList.toggle('boosting', isBoosting);
    boostBtn.innerHTML = isBoosting
      ? `<svg viewBox="0 0 24 24" style="width:14px;height:14px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>End boost`
      : `<svg viewBox="0 0 24 24" style="width:14px;height:14px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>Boost`;

    if (isBoosting && attrs.boost_remaining_minutes) {
      boostTimer.style.display = '';
      boostTimer.textContent   = `${attrs.boost_remaining_minutes} min remaining`;
    } else {
      boostTimer.style.display = 'none';
    }

    const offBtn = this.shadowRoot.getElementById('offBtn');
    if (state.state === 'off') {
      offBtn.innerHTML = `<svg viewBox="0 0 24 24" style="width:14px;height:14px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round"><polyline points="23 7 13.5 15.5 8.5 10.5 1 17"/><polyline points="17 7 23 7 23 13"/></svg>Turn on`;
    } else {
      offBtn.innerHTML = `<svg viewBox="0 0 24 24" style="width:14px;height:14px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round"><circle cx="12" cy="12" r="10"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/></svg>Turn off`;
    }

    // Frost bar
    const frostBar  = this.shadowRoot.getElementById('frostBar');
    const frostText = this.shadowRoot.getElementById('frostText');
    if (attrs.frost_protection_active) {
      frostBar.style.display = '';
      const outdoor = attrs.outdoor_temperature;
      frostText.textContent = outdoor != null
        ? `Frost protection active — outdoor ${parseFloat(outdoor).toFixed(1)}°C`
        : 'Frost protection active';
    } else if (attrs.outdoor_temperature != null) {
      frostBar.style.display = '';
      frostText.textContent = `Outdoor: ${parseFloat(attrs.outdoor_temperature).toFixed(1)}°C`;
    } else {
      frostBar.style.display = 'none';
    }
  }

  _renderSlots() {
    const list     = document.createDocumentFragment();
    const activeSlot = this._getState()?.attributes?.current_schedule_slot;

    // Build new-slot form at top
    if (this._adding) {
      list.appendChild(this._buildEditForm(null, {
        days:[0,1,2,3,4], time:'07:00', temperature:21.0
      }));
    }

    // Filter and sort
    const filtered = this._schedule
      .map((s,i) => ({s,i}))
      .filter(({s}) => this._filterDay==='all' || s.days.includes(parseInt(this._filterDay)))
      .sort((a,b) => a.s.time.localeCompare(b.s.time));

    if (!filtered.length && !this._adding) {
      const emp = document.createElement('div');
      emp.className   = 'empty';
      emp.textContent = 'No slots for this day — add one above.';
      list.appendChild(emp);
    }

    filtered.forEach(({s,i}) => {
      if (this._editIdx === i) {
        list.appendChild(this._buildEditForm(i, s));
      } else {
        const isCur = activeSlot && activeSlot.time === s.time &&
          JSON.stringify([...s.days].sort()) === JSON.stringify([...(activeSlot.days||[])].sort());

        const el = document.createElement('div');
        el.className = 'slot' + (isCur?' current':'');
        el.innerHTML = `
          <span class="stime">${s.time}</span>
          <span class="stemp">${parseFloat(s.temperature).toFixed(1)}°C
            <span class="sdesc">${this._dayLabel(s.days)}</span>
          </span>
          ${isCur ? '<span class="snow">now</span>' : ''}
          <button class="sdel" title="Delete slot">✕</button>`;
        el.querySelector('.sdel').addEventListener('click', e => {
          e.stopPropagation();
          const updated = this._schedule.filter((_,idx)=>idx!==i);
          this._saveSchedule(updated);
        });
        el.addEventListener('click', () => {
          this._editIdx = i;
          this._adding  = false;
          this._renderSlots();
        });
        list.appendChild(el);
      }
    });

    const container = this.shadowRoot.getElementById('slotList');
    container.innerHTML = '';
    container.appendChild(list);
  }

  _buildEditForm(idx, slot) {
    const wrap = document.createElement('div');
    wrap.className = 'edit-form';

    const dpRow = document.createElement('div');
    dpRow.className = 'dp-row';
    DAYS.forEach((d,i) => {
      const btn = document.createElement('button');
      btn.className   = 'dp' + (slot.days.includes(i)?' on':'');
      btn.textContent = d[0];
      btn.title       = d;
      btn.addEventListener('click', () => btn.classList.toggle('on'));
      dpRow.appendChild(btn);
    });

    const formRow = document.createElement('div');
    formRow.className = 'form-row';

    const tInput = document.createElement('input');
    tInput.type  = 'time';
    tInput.value = slot.time;

    const tempInput = document.createElement('input');
    tempInput.type  = 'number';
    tempInput.value = parseFloat(slot.temperature).toFixed(1);
    tempInput.min   = '5';
    tempInput.max   = '32';
    tempInput.step  = '0.5';

    const degSpan = document.createElement('span');
    degSpan.textContent = '°C';
    degSpan.style.fontSize = '12px';
    degSpan.style.color = 'var(--secondary-text-color,#727272)';

    const saveBtn = document.createElement('button');
    saveBtn.className   = 'save';
    saveBtn.textContent = 'Save';
    saveBtn.addEventListener('click', () => {
      const days = [...dpRow.querySelectorAll('.dp.on')].map(b => DAYS.indexOf(b.title));
      const time = tInput.value;
      const temp = parseFloat(tempInput.value);
      if (!time || isNaN(temp) || !days.length) return;
      let updated = [...this._schedule];
      if (idx !== null) {
        updated[idx] = {days, time, temperature:temp};
      } else {
        updated.push({days, time, temperature:temp});
      }
      this._saveSchedule(updated);
    });

    const cancelBtn = document.createElement('button');
    cancelBtn.className   = 'cancel';
    cancelBtn.textContent = 'Cancel';
    cancelBtn.addEventListener('click', () => {
      this._editIdx = null;
      this._adding  = false;
      this._renderSlots();
    });

    formRow.appendChild(tInput);
    formRow.appendChild(tempInput);
    formRow.appendChild(degSpan);
    formRow.appendChild(saveBtn);
    formRow.appendChild(cancelBtn);
    wrap.appendChild(dpRow);
    wrap.appendChild(formRow);
    return wrap;
  }

  // ── Helpers ───────────────────────────────────────────────────────────────

  _getState() {
    return this._hass?.states[this._config?.entity];
  }

  _dayLabel(days) {
    if (!days || !days.length) return '';
    if (days.length === 7) return 'Every day';
    const sorted = [...days].sort((a,b)=>a-b);
    if (JSON.stringify(sorted)===JSON.stringify([0,1,2,3,4])) return 'Mon–Fri';
    if (JSON.stringify(sorted)===JSON.stringify([5,6]))        return 'Sat–Sun';
    return sorted.map(d=>DAYS[d]).join(', ');
  }

  _setMode(mode) {
    if (mode === 'off') {
      this._callService('climate','turn_off',{});
    } else {
      this._callService('climate','set_preset_mode',{preset_mode:mode});
    }
  }

  _saveSchedule(schedule) {
    this._schedule = schedule;
    this._editIdx  = null;
    this._adding   = false;
    this._callService(DOMAIN,'room_set_schedule',{schedule});
    this._renderSlots();
  }

  _callService(domain, service, extra = {}) {
    if (!this._hass) return;
    const data = {entity_id: this._config.entity, ...extra};
    this._hass.callService(domain, service, data);
  }
}

customElements.define('hive-local-room-card', HiveLocalRoomCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type:             'hive-local-room-card',
  name:             'Hive Local Room Card',
  description:      `v${CARD_VERSION} — Hive Local v5 room with built-in scheduler`,
  preview:          true,
  documentationURL: 'https://github.com/gashwell/Hive-TRV-Local',
  getEntitySuggestion: (hass, entityId) => {
    if (!entityId.startsWith('climate.')) return null;
    const state = hass.states[entityId];
    if (!state) return null;
    const attrs = state.attributes || {};
    if (!Array.isArray(attrs.member_detail)) return null;
    return {config:{type:'custom:hive-local-room-card', entity:entityId}};
  },
});
