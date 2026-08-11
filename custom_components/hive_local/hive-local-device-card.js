/**
 * hive-local-device-card
 * Lovelace card for an individual Hive Local v5 TRV or receiver entity.
 *
 * Config:
 *   type: custom:hive-local-device-card
 *   entity: climate.living_room_trv   (required)
 *   battery_entity: sensor.living_room_trv_battery   (optional)
 *   demand_entity:  sensor.living_room_trv_demand     (optional)
 */

const DEVICE_CARD_VERSION = '5.0.0';

const DTPL = document.createElement('template');
DTPL.innerHTML = `
<style>
  :host{display:block}
  *{box-sizing:border-box;margin:0;padding:0}
  .card{background:var(--ha-card-background,var(--card-background-color,#fff));
    border-radius:12px;overflow:hidden;
    box-shadow:var(--ha-card-box-shadow,0 2px 8px rgba(0,0,0,.1));
    font-family:var(--paper-font-body1_-_font-family,sans-serif)}
  .header{padding:16px 18px 14px;background:#2563eb;transition:background .3s}
  .hdr-top{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:12px}
  .dev-name{font-size:13px;color:rgba(255,255,255,.8);margin-bottom:2px}
  .dev-status{font-size:12px;color:rgba(255,255,255,.65)}
  .cur-temp{text-align:right}
  .cur-temp .lbl{font-size:11px;color:rgba(255,255,255,.7)}
  .cur-temp .val{font-size:30px;font-weight:500;color:#fff;line-height:1}
  .target-row{display:flex;align-items:center;justify-content:center;gap:16px;
    border-top:0.5px solid rgba(255,255,255,.2);padding-top:12px}
  .tbtn{width:36px;height:36px;border-radius:50%;
    background:rgba(255,255,255,.18);border:none;color:#fff;
    font-size:20px;cursor:pointer;display:flex;align-items:center;justify-content:center}
  .tbtn:hover{background:rgba(255,255,255,.28)}
  .tdisp{text-align:center}
  .tdisp .lbl{font-size:11px;color:rgba(255,255,255,.7)}
  .tdisp .val{font-size:30px;font-weight:500;color:#fff;line-height:1;min-width:80px}
  .stats{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:1px;
    background:var(--divider-color,#e0e0e0);border-top:1px solid var(--divider-color,#e0e0e0)}
  .stat{padding:10px 12px;background:var(--ha-card-background,#fff)}
  .stat .lbl{font-size:10px;color:var(--secondary-text-color,#727272);margin-bottom:4px}
  .stat .val{font-size:13px;font-weight:500;color:var(--primary-text-color,#212121)}
  .bar{height:4px;border-radius:2px;background:var(--divider-color,#e0e0e0);margin-top:4px;overflow:hidden}
  .bar-fill{height:100%;border-radius:2px;transition:width .5s}
  .actions{display:flex;gap:8px;padding:10px 14px;border-top:1px solid var(--divider-color,#e0e0e0)}
  .abtn{flex:1;padding:8px;border-radius:8px;
    border:0.5px solid var(--divider-color,#e0e0e0);
    background:transparent;color:var(--secondary-text-color,#727272);
    font-size:12px;cursor:pointer;font-family:inherit;
    display:flex;align-items:center;justify-content:center;gap:5px}
  .abtn:hover{border-color:var(--primary-color,#03a9f4);color:var(--primary-color,#03a9f4)}
  .abtn.active{border-color:#dc2626;color:#dc2626}
  .unavail{padding:32px;text-align:center;color:var(--secondary-text-color,#727272);font-size:13px}
  .demand-list{border-top:1px solid var(--divider-color,#e0e0e0);padding:8px 14px}
  .demand-title{font-size:10px;color:var(--secondary-text-color,#727272);text-transform:uppercase;letter-spacing:.04em;margin-bottom:6px}
  .demand-row{display:flex;align-items:center;gap:8px;padding:3px 0;font-size:12px;color:var(--primary-text-color,#212121)}
  .demand-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
</style>
<div class="card">
  <div class="header" id="hdr">
    <div class="hdr-top">
      <div>
        <div class="dev-name" id="devName">Device</div>
        <div class="dev-status" id="devStatus">—</div>
      </div>
      <div class="cur-temp">
        <div class="lbl">Current</div>
        <div class="val" id="curTemp">—</div>
      </div>
    </div>
    <div class="target-row">
      <button class="tbtn" id="tMinus">−</button>
      <div class="tdisp"><div class="lbl">Target</div><div class="val" id="tVal">—</div></div>
      <button class="tbtn" id="tPlus">+</button>
    </div>
  </div>
  <div class="stats" id="stats"></div>
  <div class="demand-list" id="demandList" style="display:none"></div>
  <div class="actions">
    <button class="abtn" id="boostBtn">⚡ Boost</button>
    <button class="abtn" id="onoffBtn">⏻ Turn off</button>
  </div>
</div>`;

class HiveLocalDeviceCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({mode:'open'});
    this.shadowRoot.appendChild(DTPL.content.cloneNode(true));
    this._hass   = null;
    this._config = null;
    this._target = 20.0;
  }

  setConfig(config) {
    if (!config.entity) throw new Error('hive-local-device-card: entity required');
    this._config = config;
    this._bindStatic();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() { return 4; }

  getGridOptions() { return {columns:4, rows:5}; }

  _bindStatic() {
    this.shadowRoot.getElementById('tMinus').addEventListener('click', () => {
      this._target = Math.max(5, this._target - 0.5);
      this.shadowRoot.getElementById('tVal').textContent = this._target.toFixed(1) + '°';
      this._call('climate','set_temperature',{temperature:this._target});
    });
    this.shadowRoot.getElementById('tPlus').addEventListener('click', () => {
      this._target = Math.min(32, this._target + 0.5);
      this.shadowRoot.getElementById('tVal').textContent = this._target.toFixed(1) + '°';
      this._call('climate','set_temperature',{temperature:this._target});
    });
    this.shadowRoot.getElementById('boostBtn').addEventListener('click', () => {
      const state = this._getState();
      if (!state) return;
      const boosting = (state.attributes?.boost_remaining_minutes > 0);
      if (boosting) {
        this._call('hive_local','device_end_boost',{});
      } else {
        this._call('hive_local','device_boost',{});
      }
    });
    this.shadowRoot.getElementById('onoffBtn').addEventListener('click', () => {
      const state = this._getState();
      if (!state) return;
      if (state.state === 'off') {
        this._call('climate','turn_on',{});
      } else {
        this._call('climate','turn_off',{});
      }
    });
  }

  _render() {
    if (!this._hass || !this._config) return;
    const state = this._getState();
    if (!state) return;

    const attrs   = state.attributes || {};
    const heating = attrs.hvac_action === 'heating';
    const off     = state.state === 'off';
    const col     = off ? '#6b7280' : (heating ? '#e8632a' : '#2563eb');

    this.shadowRoot.getElementById('hdr').style.background = col;
    this.shadowRoot.getElementById('devName').textContent =
      this._config.name || attrs.friendly_name || this._config.entity;

    const statusMap = {heating:'Heating',idle:'Idle',off:'Off'};
    this.shadowRoot.getElementById('devStatus').textContent =
      statusMap[attrs.hvac_action] || state.state;

    const cur = attrs.current_temperature;
    this.shadowRoot.getElementById('curTemp').textContent =
      cur != null ? parseFloat(cur).toFixed(1) + '°' : '—';

    this._target = parseFloat(attrs.temperature || 20);
    this.shadowRoot.getElementById('tVal').textContent = this._target.toFixed(1) + '°';

    // Stats
    const batEid    = this._config.battery_entity;
    const demandEid = this._config.demand_entity;
    const bat    = batEid    ? this._hass.states[batEid]?.state    : attrs.battery;
    const demand = demandEid ? this._hass.states[demandEid]?.state : attrs.pi_heating_demand;
    const boostRem = attrs.boost_remaining_minutes;

    const heatRequired   = attrs.heat_required === true;
    const receiverName   = attrs.receiver_name || null;
    const heatDemandActive = attrs.heat_demand_active === true;
    const demandedBy     = attrs.demanded_by || [];
    const isReceiver     = attrs.running_state !== undefined
                        && attrs.battery === undefined
                        && attrs.pi_heating_demand === undefined;

    const stats = this.shadowRoot.getElementById('stats');

    let statItems;
    if (isReceiver) {
      // Receiver card — show what's triggering it
      statItems = [
        {
          lbl: 'Status',
          val: off ? 'Off' : (heating ? 'Heating' : 'Idle'),
          bar: null,
          col: heating ? '#e8632a' : off ? '#9ca3af' : '#2563eb',
        },
        {
          lbl: 'Heat source',
          val: heatDemandActive
            ? 'On-demand'
            : heating
              ? 'Schedule / manual'
              : 'Idle',
          bar: null,
          col: heatDemandActive ? '#e8632a' : heating ? '#2563eb' : '#9ca3af',
        },
        {
          lbl: 'Zones demanding',
          val: `${demandedBy.length} zone${demandedBy.length !== 1 ? 's' : ''}`,
          bar: null,
          col: demandedBy.length > 0 ? '#e8632a' : '#9ca3af',
        },
        boostRem > 0 ? {
          lbl: 'Boost remaining',
          val: `${boostRem} min`,
          bar: null,
          col: '#dc2626',
        } : null,
      ].filter(Boolean);
    } else {
      // TRV card — show battery, demand, mode, on-demand link
      statItems = [
        bat != null ? {
          lbl:'Battery',
          val: `${Math.round(bat)}%`,
          bar: Math.round(bat),
          col: parseInt(bat) < 20 ? '#e53935' : '#22c55e',
        } : null,
        demand != null ? {
          lbl:'Heating demand',
          val: `${Math.round(demand)}%`,
          bar: Math.round(demand),
          col: '#e8632a',
        } : null,
        boostRem > 0 ? {
          lbl:'Boost remaining',
          val: `${boostRem} min`,
          bar: null,
          col: '#dc2626',
        } : {
          lbl:'Mode',
          val: off ? 'Off' : (heating ? 'Heating' : 'Idle'),
          bar: null,
          col: col,
        },
        {
          lbl: 'On-demand heating',
          val: receiverName
            ? (heatRequired ? `Firing → ${receiverName}` : `Ready → ${receiverName}`)
            : 'Not configured',
          bar: null,
          col: heatRequired ? '#e8632a'
            : receiverName ? '#2563eb'
            : '#9ca3af',
        },
      ].filter(Boolean);
    }

    stats.innerHTML = statItems.map(s => `
      <div class="stat">
        <div class="lbl">${s.lbl}</div>
        <div class="val" style="color:${s.col};font-size:12px">${s.val}</div>
        ${s.bar != null
          ? `<div class="bar"><div class="bar-fill" style="width:${Math.min(s.bar,100)}%;background:${s.col}"></div></div>`
          : ''}
      </div>`).join('');

    // Demand list — show individual TRVs/rooms calling for heat on receiver card
    const demandList = this.shadowRoot.getElementById('demandList');
    if (demandList) {
      if (isReceiver && demandedBy.length > 0) {
        demandList.style.display = '';
        demandList.innerHTML = `
          <div class="demand-title">Demanding heat</div>
          ${demandedBy.map(name => `
            <div class="demand-row">
              <div class="demand-dot" style="background:#e8632a"></div>
              ${name}
            </div>`).join('')}`;
      } else if (isReceiver && heating && !heatDemandActive) {
        demandList.style.display = '';
        demandList.innerHTML = `
          <div class="demand-title">Demanding heat</div>
          <div class="demand-row">
            <div class="demand-dot" style="background:#6b7280"></div>
            Running from own schedule or manual
          </div>`;
      } else {
        demandList.style.display = 'none';
      }
    }

    // Boost button
    const boostBtn = this.shadowRoot.getElementById('boostBtn');
    const boosting = boostRem > 0;
    boostBtn.textContent = boosting ? '⏹ End boost' : '⚡ Boost';
    boostBtn.classList.toggle('active', boosting);

    // On/off button
    const onoffBtn = this.shadowRoot.getElementById('onoffBtn');
    onoffBtn.textContent = off ? '▶ Turn on' : '⏻ Turn off';
  }

  _getState() { return this._hass?.states[this._config?.entity]; }

  _call(domain, service, extra = {}) {
    if (!this._hass) return;
    this._hass.callService(domain, service, {entity_id:this._config.entity, ...extra});
  }
}

customElements.define('hive-local-device-card', HiveLocalDeviceCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type:             'hive-local-device-card',
  name:             'Hive Local Device Card',
  description:      `v${DEVICE_CARD_VERSION} — Individual Hive TRV or receiver`,
  preview:          true,
  documentationURL: 'https://github.com/gashwell/Hive-TRV-Local',
  getEntitySuggestion: (hass, entityId) => {
    if (!entityId.startsWith('climate.')) return null;
    const state = hass.states[entityId];
    if (!state) return null;
    const attrs = state.attributes || {};
    if (Array.isArray(attrs.member_detail)) return null; // room card handles those
    if (attrs.pi_heating_demand === undefined && attrs.battery === undefined) return null;
    return {config:{type:'custom:hive-local-device-card', entity:entityId}};
  },
});
