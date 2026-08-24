/**
 * hive-local-dashboard-card
 * Full-page dashboard for the Hive Local integration.
 *
 * One card, one entity needed. Reads all hive_local state automatically.
 * Tabs: Overview · Rooms · TRVs · Settings
 *
 * Usage:
 *   type: custom:hive-local-dashboard-card
 */

const DASH_VERSION = '1.0.0';

const ICONS = {
  flame:    `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 12c0-3 2.5-6 2.5-9C14.5 1.5 13 0 12 0c0 2-4 5-4 9s1.8 6 4 6z"/><path d="M12 12c0-3-2.5-6-2.5-9"/><path d="M5 21a7 7 0 0 1 14 0"/></svg>`,
  idle:     `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 8v4l3 3"/></svg>`,
  trv:      `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 14.76V3.5a2.5 2.5 0 0 0-5 0v11.26a4.5 4.5 0 1 0 5 0z"/></svg>`,
  room:     `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>`,
  settings: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>`,
  battery:  `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="7" width="18" height="10" rx="2"/><line x1="22" y1="11" x2="22" y2="13"/></svg>`,
  frost:    `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="2" x2="12" y2="22"/><path d="M17 7l-5 5-5-5"/><path d="M17 17l-5-5-5 5"/><path d="M2 12l5-3 5 3 5-3 5 3"/><path d="M2 12l5 3 5-3 5 3 5-3"/></svg>`,
  boost:    `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>`,
  schedule: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>`,
  warn:     `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`,
  chev:     `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>`,
};

function icon(key, size = 14) {
  return `<span style="display:inline-flex;align-items:center;width:${size}px;height:${size}px;flex-shrink:0">${ICONS[key]}</span>`;
}

const CSS = `
  :host{display:block;font-family:var(--paper-font-body1_-_font-family,system-ui,sans-serif)}
  *{box-sizing:border-box;margin:0;padding:0}
  .dash{background:var(--ha-card-background,#fff);border-radius:12px;overflow:hidden;
    border:0.5px solid var(--divider-color,#e0e0e0)}

  /* tab bar */
  .tabs{display:flex;border-bottom:1px solid var(--divider-color,#e0e0e0)}
  .tab{flex:1;padding:12px 8px;border:none;background:transparent;cursor:pointer;
    font-size:11px;font-weight:500;color:var(--secondary-text-color,#727272);
    font-family:inherit;display:flex;flex-direction:column;align-items:center;gap:4px;
    text-transform:uppercase;letter-spacing:.04em;border-bottom:2px solid transparent;
    transition:color .15s,border-color .15s;margin-bottom:-1px}
  .tab svg{width:16px;height:16px;stroke:currentColor;fill:none;stroke-width:2;
    stroke-linecap:round;stroke-linejoin:round}
  .tab.active{color:#e8632a;border-bottom-color:#e8632a}
  .tab:hover:not(.active){color:var(--primary-text-color,#212121)}

  /* body */
  .body{padding:16px}

  /* boiler hero */
  .hero{border-radius:10px;padding:14px 16px;margin-bottom:16px;
    display:flex;align-items:center;gap:14px;border:0.5px solid}
  .hero-on{background:#fff7f0;border-color:#e8632a}
  .hero-off{background:var(--secondary-background-color,#f5f5f5);
    border-color:var(--divider-color,#e0e0e0)}
  .hero-icon{width:40px;height:40px;border-radius:10px;display:flex;
    align-items:center;justify-content:center;flex-shrink:0}
  .hero-on .hero-icon{background:#fde8d8;color:#e8632a}
  .hero-off .hero-icon{background:var(--divider-color,#e0e0e0);color:var(--secondary-text-color,#9ca3af)}
  .hero-icon svg{width:20px;height:20px;stroke:currentColor;fill:none;stroke-width:2;
    stroke-linecap:round;stroke-linejoin:round}
  .hero-body{flex:1}
  .hero-label{font-size:11px;color:var(--secondary-text-color,#727272);margin-bottom:2px}
  .hero-state{font-size:20px;font-weight:500}
  .hero-on .hero-state{color:#e8632a}
  .hero-off .hero-state{color:var(--secondary-text-color,#727272)}
  .hero-dot{width:10px;height:10px;border-radius:50%;flex-shrink:0}
  .hero-on .hero-dot{background:#e8632a;animation:pulse 1.5s ease-in-out infinite}
  .hero-off .hero-dot{background:var(--divider-color,#e0e0e0)}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:.35}}

  /* stat grid */
  .stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(90px,1fr));gap:8px;margin-bottom:16px}
  .stat{background:var(--secondary-background-color,#f5f5f5);border-radius:8px;padding:10px 12px}
  .stat-lbl{font-size:10px;color:var(--secondary-text-color,#727272);
    text-transform:uppercase;letter-spacing:.04em;margin-bottom:4px}
  .stat-val{font-size:18px;font-weight:500;color:var(--primary-text-color,#212121)}
  .stat-sub{font-size:11px;color:var(--secondary-text-color,#727272);margin-top:1px}

  /* section */
  .section{margin-bottom:16px}
  .sec-hdr{font-size:10px;font-weight:500;color:var(--secondary-text-color,#727272);
    text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px}

  /* card list */
  .list{border:0.5px solid var(--divider-color,#e0e0e0);border-radius:10px;overflow:hidden}
  .item{display:flex;align-items:center;gap:10px;padding:10px 14px;
    border-bottom:0.5px solid var(--divider-color,#e0e0e0);cursor:pointer}
  .item:last-child{border-bottom:none}
  .item:hover{background:var(--secondary-background-color,#fafafa)}
  .item-icon{width:28px;height:28px;border-radius:7px;display:flex;
    align-items:center;justify-content:center;flex-shrink:0}
  .item-icon svg{width:13px;height:13px;stroke:currentColor;fill:none;stroke-width:2;
    stroke-linecap:round;stroke-linejoin:round}
  .icon-room{background:#f0fdf4;color:#16a34a}
  .icon-trv{background:#fff7f0;color:#e8632a}
  .icon-set{background:#f5f3ff;color:#7c3aed}
  .item-body{flex:1;min-width:0}
  .item-name{font-size:13px;font-weight:500;color:var(--primary-text-color,#212121);
    white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .item-meta{font-size:11px;color:var(--secondary-text-color,#727272);margin-top:1px;
    white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .item-temp{font-size:14px;font-weight:500;color:var(--primary-text-color,#212121);
    flex-shrink:0;min-width:36px;text-align:right}
  .item-chev{color:var(--secondary-text-color,#ccc);flex-shrink:0}
  .item-chev svg{width:13px;height:13px;stroke:currentColor;fill:none;stroke-width:2;
    stroke-linecap:round;stroke-linejoin:round}

  /* badges */
  .badge{display:inline-flex;align-items:center;gap:3px;font-size:10px;font-weight:500;
    padding:1px 6px;border-radius:10px;flex-shrink:0}
  .badge-heat{background:#fef3ee;color:#c2410c}
  .badge-idle{background:var(--secondary-background-color,#f5f5f5);color:var(--secondary-text-color,#6b7280)}
  .badge-off{background:var(--secondary-background-color,#f5f5f5);color:var(--secondary-text-color,#9ca3af)}
  .badge-boost{background:#fef2f2;color:#b91c1c}
  .badge-solo{background:#fefce8;color:#a16207}
  .badge-sched{background:#eff6ff;color:#1d4ed8}

  /* heat bar */
  .bar{height:3px;border-radius:2px;background:var(--divider-color,#e0e0e0);margin-top:3px;overflow:hidden}
  .bar-fill{height:100%;border-radius:2px;background:#e8632a}

  /* warning */
  .warn{display:flex;align-items:flex-start;gap:8px;font-size:12px;color:#92400e;
    background:#fffbeb;border:0.5px solid #fcd34d;border-radius:8px;
    padding:8px 12px;margin-bottom:12px;line-height:1.4}
  .warn svg{flex-shrink:0;width:14px;height:14px;stroke:#b45309;fill:none;
    stroke-width:2;stroke-linecap:round;stroke-linejoin:round;margin-top:1px}

  /* TRV grid */
  .trv-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:8px}
  .trv-card{background:var(--secondary-background-color,#f9f9f9);border-radius:10px;
    padding:12px;border:0.5px solid var(--divider-color,#e0e0e0);cursor:pointer}
  .trv-card:hover{background:var(--secondary-background-color,#f5f5f5)}
  .trv-top{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px}
  .trv-name{font-size:12px;font-weight:500;color:var(--primary-text-color,#212121);
    line-height:1.3;max-width:90px}
  .trv-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0;margin-top:3px}
  .trv-temp{font-size:22px;font-weight:500;color:var(--primary-text-color,#212121);margin-bottom:4px}
  .trv-target{font-size:11px;color:var(--secondary-text-color,#727272);margin-bottom:6px}
  .trv-bat{display:flex;align-items:center;gap:4px;font-size:10px;
    color:var(--secondary-text-color,#727272)}
  .trv-bat svg{width:11px;height:11px;stroke:currentColor;fill:none;stroke-width:2;
    stroke-linecap:round;stroke-linejoin:round}

  /* settings list */
  .set-item{display:flex;align-items:center;gap:10px;padding:11px 14px;
    border-bottom:0.5px solid var(--divider-color,#e0e0e0);cursor:pointer}
  .set-item:last-child{border-bottom:none}
  .set-item:hover{background:var(--secondary-background-color,#fafafa)}
  .set-lbl{flex:1;font-size:13px;color:var(--primary-text-color,#212121)}
  .set-val{font-size:12px;color:var(--secondary-text-color,#727272)}

  /* empty */
  .empty{padding:24px;text-align:center;font-size:13px;color:var(--secondary-text-color,#727272)}
`;

class HiveLocalDashboardCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({mode:'open'});
    this._hass   = null;
    this._config = null;
    this._tab    = 'overview';
    this._init();
  }

  _init() {
    const style = document.createElement('style');
    style.textContent = CSS;
    const root = document.createElement('div');
    root.className = 'dash';
    root.innerHTML = `
      <div class="tabs" id="tabs"></div>
      <div class="body" id="body"></div>`;
    this.shadowRoot.append(style, root);
  }

  setConfig(config) { this._config = config || {}; }
  getCardSize() { return 10; }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _render() {
    if (!this._hass) return;
    this._renderTabs();
    this._renderBody();
  }

  _renderTabs() {
    const tabs = this.shadowRoot.getElementById('tabs');
    const defs = [
      {id:'overview', label:'Overview', icon:'flame'},
      {id:'rooms',    label:'Rooms',    icon:'room'},
      {id:'trvs',     label:'TRVs',     icon:'trv'},
      {id:'settings', label:'Settings', icon:'settings'},
    ];
    tabs.innerHTML = defs.map(t => `
      <button class="tab${this._tab===t.id?' active':''}" data-tab="${t.id}">
        ${ICONS[t.icon]}${t.label}
      </button>`).join('');
    tabs.querySelectorAll('.tab').forEach(btn => {
      btn.addEventListener('click', () => {
        this._tab = btn.dataset.tab;
        this._render();
      });
    });
  }

  _renderBody() {
    const body = this.shadowRoot.getElementById('body');
    body.innerHTML = this[`_tab_${this._tab}`]();
    body.querySelectorAll('[data-entity]').forEach(el => {
      el.addEventListener('click', () => {
        this.dispatchEvent(new CustomEvent('hass-more-info',
          {bubbles:true, composed:true, detail:{entityId: el.dataset.entity}}));
      });
    });
    body.querySelectorAll('[data-configure]').forEach(el => {
      el.addEventListener('click', () => this._openConfigure());
    });
  }

  _openConfigure() {
    const evt = new CustomEvent('hass-more-info',
      {bubbles:true, composed:true, detail:{entityId:'hive_local'}});
    this.dispatchEvent(evt);
  }

  // ── Data helpers ─────────────────────────────────────────────────────────────

  _states() { return this._hass.states; }

  _boilerSensor() {
    return Object.values(this._states()).find(s =>
      s.entity_id.startsWith('binary_sensor.') &&
      s.attributes.device_class === 'heat' &&
      (s.attributes.friendly_name||'').toLowerCase().includes('heating')
    ) || null;
  }

  _rooms() {
    return Object.values(this._states()).filter(s =>
      s.entity_id.startsWith('climate.') &&
      Array.isArray(s.attributes.member_detail) &&
      s.attributes.member_detail.length > 0
    ).sort((a,b) => (a.attributes.friendly_name||'').localeCompare(b.attributes.friendly_name||''));
  }

  _trvs() {
    return Object.values(this._states()).filter(s =>
      s.entity_id.startsWith('climate.') &&
      !Array.isArray(s.attributes.member_detail) &&
      s.attributes.battery !== undefined
    ).sort((a,b) => (a.attributes.friendly_name||'').localeCompare(b.attributes.friendly_name||''));
  }

  _groupedTrvNames() {
    const names = new Set();
    this._rooms().forEach(r => (r.attributes.member_detail||[]).forEach(m => names.add(m.name)));
    return names;
  }

  _standaloneTrvs() {
    const grouped = this._groupedTrvNames();
    return this._trvs().filter(s =>
      !grouped.has(s.attributes.friendly_name||'')
    );
  }

  _roomHeating() { return this._rooms().filter(r => r.attributes.heat_required); }

  _heatingTrvCount() {
    return this._trvs().filter(s => s.attributes.hvac_action === 'heating').length;
  }

  _avgTemp() {
    const temps = this._trvs().map(s => s.attributes.current_temperature).filter(t => t!=null);
    if (!temps.length) return null;
    return (temps.reduce((a,b)=>a+b,0)/temps.length).toFixed(1);
  }

  _lowBat() {
    return this._trvs().filter(s => (s.attributes.battery||100) < 25);
  }

  // ── Tabs ─────────────────────────────────────────────────────────────────────

  _tab_overview() {
    const boiler  = this._boilerSensor();
    const on      = boiler ? boiler.state === 'on' : null;
    const rooms   = this._rooms();
    const trvs    = this._trvs();
    const lowBat  = this._lowBat();
    const heating = this._roomHeating();

    let html = '';

    // Warnings
    if (lowBat.length) {
      html += `<div class="warn">${ICONS.warn}<span>${lowBat.length} TRV${lowBat.length>1?'s':''} with low battery: ${lowBat.map(s=>s.attributes.friendly_name||s.entity_id).join(', ')}</span></div>`;
    }

    // Boiler hero
    if (on !== null) {
      const sub = on
        ? `${heating.length} room${heating.length!==1?'s':''} demanding heat`
        : 'No heat demand';
      html += `
        <div class="hero hero-${on?'on':'off'}" data-entity="${boiler.entity_id}">
          <div class="hero-icon">${on ? ICONS.flame : ICONS.idle}</div>
          <div class="hero-body">
            <div class="hero-label">Boiler</div>
            <div class="hero-state">${on ? 'Heating' : 'Idle'}</div>
            <div style="font-size:11px;color:var(--secondary-text-color,#727272);margin-top:2px">${sub}</div>
          </div>
          <div class="hero-dot"></div>
        </div>`;
    }

    // Stat grid
    const avg = this._avgTemp();
    html += `<div class="stats">
      <div class="stat">
        <div class="stat-lbl">Rooms</div>
        <div class="stat-val">${rooms.length}</div>
        <div class="stat-sub">${heating.length} heating</div>
      </div>
      <div class="stat">
        <div class="stat-lbl">TRVs</div>
        <div class="stat-val">${trvs.length}</div>
        <div class="stat-sub">${this._heatingTrvCount()} heating</div>
      </div>
      ${avg !== null ? `<div class="stat">
        <div class="stat-lbl">Avg temp</div>
        <div class="stat-val">${avg}°</div>
        <div class="stat-sub">across all TRVs</div>
      </div>` : ''}
      <div class="stat">
        <div class="stat-lbl">Low battery</div>
        <div class="stat-val" style="color:${lowBat.length?'#e53935':'inherit'}">${lowBat.length}</div>
        <div class="stat-sub">TRV${lowBat.length!==1?'s':''}</div>
      </div>
    </div>`;

    // Active rooms
    if (heating.length) {
      html += `<div class="section">
        <div class="sec-hdr">Heating now</div>
        <div class="list">`;
      heating.forEach(r => {
        const attrs = r.attributes;
        const cur   = attrs.current_temperature;
        const tgt   = attrs.temperature;
        const count = (attrs.member_detail||[]).length;
        html += `<div class="item" data-entity="${r.entity_id}">
          <div class="item-icon icon-room">${ICONS.room}</div>
          <div class="item-body">
            <div class="item-name">${attrs.friendly_name||r.entity_id}</div>
            <div class="item-meta">${count} TRV${count!==1?'s':''} · target ${tgt?parseFloat(tgt).toFixed(1)+'°':'—'}</div>
          </div>
          ${cur!=null?`<div class="item-temp">${parseFloat(cur).toFixed(1)}°</div>`:''}
          <div class="item-chev">${ICONS.chev}</div>
        </div>`;
      });
      html += `</div></div>`;
    }

    // Standalone TRVs heating
    const soloHeating = this._standaloneTrvs().filter(s => s.attributes.hvac_action==='heating');
    if (soloHeating.length) {
      html += `<div class="section">
        <div class="sec-hdr">Standalone TRVs heating</div>
        <div class="list">`;
      soloHeating.forEach(s => {
        const attrs = s.attributes;
        const cur   = attrs.current_temperature;
        html += `<div class="item" data-entity="${s.entity_id}">
          <div class="item-icon icon-trv">${ICONS.trv}</div>
          <div class="item-body">
            <div class="item-name">${attrs.friendly_name||s.entity_id}</div>
            <div class="item-meta">batt ${Math.round(attrs.battery||0)}% · demand ${Math.round(attrs.pi_heating_demand||0)}%</div>
          </div>
          ${cur!=null?`<div class="item-temp">${parseFloat(cur).toFixed(1)}°</div>`:''}
          <div class="item-chev">${ICONS.chev}</div>
        </div>`;
      });
      html += `</div></div>`;
    }

    if (!rooms.length && !trvs.length) {
      html += `<div class="empty">No devices registered yet.<br>Configure → Devices to add TRVs.</div>`;
    }

    return html;
  }

  _tab_rooms() {
    const rooms = this._rooms();
    if (!rooms.length) return `<div class="empty">No rooms yet.<br><button data-configure style="margin-top:8px;padding:6px 12px;border-radius:6px;border:0.5px solid var(--divider-color,#e0e0e0);background:transparent;cursor:pointer;font-family:inherit;font-size:12px">Configure → Rooms</button></div>`;

    let html = `<div class="list">`;
    rooms.forEach(r => {
      const attrs   = r.attributes;
      const cur     = attrs.current_temperature;
      const tgt     = attrs.temperature;
      const heating = attrs.heat_required;
      const mode    = attrs.mode || 'manual';
      const boost   = mode === 'boost';
      const members = attrs.member_detail || [];
      const sched   = mode === 'schedule' || mode === 'schedule_with_preheat';

      const stateBadge = boost
        ? `<span class="badge badge-boost">${ICONS.boost} Boost</span>`
        : heating
          ? `<span class="badge badge-heat">${ICONS.flame} Heating</span>`
          : r.state === 'off'
            ? `<span class="badge badge-off">Off</span>`
            : sched
              ? `<span class="badge badge-sched">${ICONS.schedule} Schedule</span>`
              : `<span class="badge badge-idle">Idle</span>`;

      const memberTemps = members.map(m =>
        m.temperature!=null ? `${m.name}: ${parseFloat(m.temperature).toFixed(1)}°` : null
      ).filter(Boolean).join(' · ');

      html += `<div class="item" data-entity="${r.entity_id}">
        <div class="item-icon icon-room">${ICONS.room}</div>
        <div class="item-body">
          <div class="item-name" style="display:flex;align-items:center;gap:6px">
            ${attrs.friendly_name||r.entity_id}
            ${stateBadge}
          </div>
          <div class="item-meta">${members.length} TRV${members.length!==1?'s':''} · target ${tgt?parseFloat(tgt).toFixed(1)+'°':'—'}</div>
          ${memberTemps?`<div class="item-meta" style="margin-top:1px">${memberTemps}</div>`:''}
        </div>
        ${cur!=null?`<div class="item-temp">${parseFloat(cur).toFixed(1)}°</div>`:''}
        <div class="item-chev">${ICONS.chev}</div>
      </div>`;
    });
    html += `</div>`;
    return html;
  }

  _tab_trvs() {
    const allTrvs    = this._trvs();
    const grouped    = this._groupedTrvNames();
    const standalone = this._standaloneTrvs();
    const rooms      = this._rooms();

    if (!allTrvs.length) return `<div class="empty">No TRVs registered yet.</div>`;

    let html = '';

    // Grouped TRVs — show per-room
    if (rooms.length) {
      html += `<div class="section"><div class="sec-hdr">In rooms</div><div class="trv-grid">`;
      rooms.forEach(room => {
        (room.attributes.member_detail||[]).forEach(m => {
          const trv = allTrvs.find(s => (s.attributes.friendly_name||'') === m.name);
          const heating = trv ? trv.attributes.hvac_action === 'heating' : m.pi_heating_demand > 0;
          const cur     = m.temperature;
          const tgt     = room.attributes.temperature;
          const bat     = trv ? trv.attributes.battery : null;
          const demand  = m.pi_heating_demand || 0;
          const eid     = trv ? trv.entity_id : '';

          html += `<div class="trv-card" ${eid?`data-entity="${eid}"`:''}">
            <div class="trv-top">
              <div class="trv-name">${m.name}</div>
              <div class="trv-dot" style="background:${heating?'#e8632a':'#c8c8c8'}"></div>
            </div>
            <div class="trv-temp">${cur!=null?parseFloat(cur).toFixed(1)+'°':'—'}</div>
            <div class="trv-target">target ${tgt?parseFloat(tgt).toFixed(1)+'°':'—'}</div>
            ${demand>0?`<div class="bar"><div class="bar-fill" style="width:${Math.min(demand,100)}%"></div></div>`:''}
            ${bat!=null?`<div class="trv-bat">${ICONS.battery} ${Math.round(bat)}%</div>`:''}
          </div>`;
        });
      });
      html += `</div></div>`;
    }

    // Standalone TRVs
    if (standalone.length) {
      html += `<div class="section"><div class="sec-hdr">Standalone</div><div class="trv-grid">`;
      standalone.forEach(s => {
        const attrs   = s.attributes;
        const heating = attrs.hvac_action === 'heating';
        const cur     = attrs.current_temperature;
        const tgt     = attrs.temperature;
        const bat     = attrs.battery;
        const demand  = attrs.pi_heating_demand || 0;

        html += `<div class="trv-card" data-entity="${s.entity_id}">
          <div class="trv-top">
            <div class="trv-name">${attrs.friendly_name||s.entity_id}</div>
            <div class="trv-dot" style="background:${heating?'#e8632a':'#c8c8c8'}"></div>
          </div>
          <div class="trv-temp">${cur!=null?parseFloat(cur).toFixed(1)+'°':'—'}</div>
          <div class="trv-target">target ${tgt?parseFloat(tgt).toFixed(1)+'°':'—'}</div>
          ${demand>0?`<div class="bar"><div class="bar-fill" style="width:${Math.min(demand,100)}%"></div></div>`:''}
          ${bat!=null?`<div class="trv-bat">${ICONS.battery} ${Math.round(bat)}%</div>`:''}
          <div style="margin-top:4px"><span class="badge badge-solo">standalone</span></div>
        </div>`;
      });
      html += `</div></div>`;
    }

    return html;
  }

  _tab_settings() {
    const items = [
      {icon:'room',     label:'Rooms',               sub:'Create and manage heating zones',          action:'configure'},
      {icon:'trv',      label:'Devices',              sub:'Add or remove TRVs',                       action:'configure'},
      {icon:'flame',    label:'On-demand heating',    sub:'Select rooms that trigger the ZBMINIR2',   action:'configure'},
      {icon:'frost',    label:'Settings',             sub:'Heat demand switch, Z2M topic, frost',     action:'configure'},
    ];
    let html = `<div class="list">`;
    items.forEach(item => {
      html += `<div class="set-item" data-configure>
        <div class="item-icon icon-set">${ICONS[item.icon]||ICONS.settings}</div>
        <div class="item-body">
          <div class="item-name">${item.label}</div>
          <div class="item-meta">${item.sub}</div>
        </div>
        <div class="item-chev">${ICONS.chev}</div>
      </div>`;
    });
    html += `</div>`;
    html += `<div style="margin-top:12px;font-size:11px;color:var(--secondary-text-color,#9ca3af);text-align:center">Hive Local v${DASH_VERSION}</div>`;
    return html;
  }
}

customElements.define('hive-local-dashboard-card', HiveLocalDashboardCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type:        'hive-local-dashboard-card',
  name:        'Hive Local — Dashboard',
  description: 'Full dashboard: overview, rooms, TRVs, and settings in one card',
  preview:     false,
  documentationURL: 'https://github.com/gashwell/Hive-TRV-Local',
});
