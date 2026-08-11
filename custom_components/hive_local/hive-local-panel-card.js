/**
 * hive-local-panel-card
 * System overview panel for Hive Local v5.
 *
 * Shows: warning banner · rooms · standalone TRVs · receivers · settings
 * All sections are live — update with HA state changes.
 *
 * Config:
 *   type: custom:hive-local-panel-card
 *   (no entity required — reads all hive_local entities automatically)
 */

const PANEL_VERSION = '5.0.0';
const DOMAIN        = 'hive_local';

const TPL = document.createElement('template');
TPL.innerHTML = `
<style>
  :host{display:block;font-family:var(--paper-font-body1_-_font-family,sans-serif)}
  *{box-sizing:border-box;margin:0;padding:0}
  .panel{padding:0 0 24px}
  .warning{font-size:12px;color:#92400e;background:#fffbeb;
    border:0.5px solid #fcd34d;border-radius:8px;
    padding:8px 12px;margin-bottom:12px;
    display:flex;align-items:center;gap:8px;line-height:1.4}
  .warning svg{flex-shrink:0;width:14px;height:14px;stroke:#b45309;fill:none;
    stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
  .section{margin-bottom:20px}
  .section-hdr{display:flex;justify-content:space-between;align-items:center;
    margin-bottom:8px;padding:0 2px}
  .section-title{font-size:11px;font-weight:500;
    color:var(--secondary-text-color,#727272);
    text-transform:uppercase;letter-spacing:.05em}
  .section-action{font-size:12px;color:var(--primary-color,#03a9f4);
    cursor:pointer;background:none;border:none;font-family:inherit;padding:0}
  .card{background:var(--ha-card-background,var(--card-background-color,#fff));
    border:0.5px solid var(--divider-color,#e0e0e0);border-radius:12px;overflow:hidden}
  .row{display:flex;align-items:center;gap:10px;padding:11px 14px;
    border-bottom:0.5px solid var(--divider-color,#e0e0e0);cursor:pointer}
  .row:last-child{border-bottom:none}
  .row:hover{background:var(--secondary-background-color,#fafafa)}
  .dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
  .icon{width:30px;height:30px;border-radius:8px;
    display:flex;align-items:center;justify-content:center;flex-shrink:0}
  .icon svg{width:15px;height:15px;stroke:currentColor;fill:none;
    stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
  .icon-trv{background:#fff7f0;color:#e8632a}
  .icon-recv{background:#eff6ff;color:#2563eb}
  .icon-room{background:#f0fdf4;color:#16a34a}
  .icon-set{background:#f5f3ff;color:#7c3aed}
  .row-body{flex:1;min-width:0}
  .row-top{display:flex;align-items:center;gap:6px;margin-bottom:2px}
  .row-name{font-size:13px;font-weight:500;
    color:var(--primary-text-color,#212121);
    white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .row-meta{font-size:11px;color:var(--secondary-text-color,#727272);
    white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .temp{font-size:14px;font-weight:500;
    color:var(--primary-text-color,#212121);
    min-width:40px;text-align:right;flex-shrink:0}
  .badge{font-size:10px;padding:1px 6px;border-radius:10px;
    font-weight:500;white-space:nowrap;flex-shrink:0}
  .badge-heat{background:#fef3ee;color:#c2410c}
  .badge-idle{background:#f5f5f5;color:#737373}
  .badge-off{background:#f5f5f5;color:#737373}
  .badge-boost{background:#fef2f2;color:#b91c1c}
  .badge-room{background:#dcfce7;color:#15803d}
  .badge-recv{background:#eff6ff;color:#1d4ed8}
  .badge-solo{background:#fefce8;color:#a16207}
  .chev{color:var(--secondary-text-color,#ccc);margin-left:2px;flex-shrink:0}
  .chev svg{width:14px;height:14px;stroke:currentColor;fill:none;
    stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
  .empty{font-size:12px;color:var(--secondary-text-color,#727272);
    padding:14px 16px;text-align:center}
</style>
<div class="panel" id="panel"></div>`;

const ICONS = {
  trv:     `<svg viewBox="0 0 24 24"><path d="M14 14.76V3.5a2.5 2.5 0 0 0-5 0v11.26a4.5 4.5 0 1 0 5 0z"/></svg>`,
  recv:    `<svg viewBox="0 0 24 24"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>`,
  room:    `<svg viewBox="0 0 24 24"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>`,
  settings:`<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>`,
  frost:   `<svg viewBox="0 0 24 24"><line x1="12" y1="2" x2="12" y2="22"/><path d="M17 7l-5 5-5-5"/><path d="M17 17l-5-5-5 5"/><path d="M2 12l5-3 5 3 5-3 5 3"/><path d="M2 12l5 3 5-3 5 3 5-3"/></svg>`,
  z2m:     `<svg viewBox="0 0 24 24"><circle cx="12" cy="5" r="2"/><circle cx="5" cy="19" r="2"/><circle cx="19" cy="19" r="2"/><path d="M12 7v4M5 17l5-6M19 17l-5-6"/></svg>`,
  add:     `<svg viewBox="0 0 24 24"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>`,
  chev:    `<svg viewBox="0 0 24 24"><polyline points="9 18 15 12 9 6"/></svg>`,
  warn:    `<svg viewBox="0 0 24 24"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`,
};

function chev() {
  return `<span class="chev">${ICONS.chev}</span>`;
}

function badge(text, cls) {
  return `<span class="badge badge-${cls}">${text}</span>`;
}

class HiveLocalPanelCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({mode:'open'});
    this.shadowRoot.appendChild(TPL.content.cloneNode(true));
    this._hass   = null;
    this._config = null;
  }

  setConfig(config) {
    this._config = config || {};
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() { return 8; }

  _render() {
    if (!this._hass) return;

    // ── Gather all hive_local entities from HA states ──────────────────────
    const states = this._hass.states;

    // Room climate entities — have member_detail attribute
    const rooms = Object.values(states).filter(s =>
      s.entity_id.startsWith('climate.') &&
      Array.isArray(s.attributes.member_detail) &&
      s.attributes.member_detail.length > 0
    );

    // Individual TRV entities — NOT room entities (no member_detail), have pi_heating_demand or battery
    const trvEntities = Object.values(states).filter(s =>
      s.entity_id.startsWith('climate.') &&
      !Array.isArray(s.attributes.member_detail) &&
      (s.attributes.pi_heating_demand !== undefined || s.attributes.battery !== undefined)
    );

    // Receiver entities — have running_state and no member_detail and no battery
    const recvEntities = Object.values(states).filter(s =>
      s.entity_id.startsWith('climate.') &&
      !Array.isArray(s.attributes.member_detail) &&
      s.attributes.running_state !== undefined &&
      s.attributes.battery === undefined &&
      s.attributes.pi_heating_demand === undefined
    );

    // Build set of TRVs that are in rooms (hidden) — detect via member_detail names
    const groupedNames = new Set();
    rooms.forEach(r => {
      (r.attributes.member_detail || []).forEach(m => groupedNames.add(m.name));
    });

    // Standalone = TRVs not in any room
    const standalone = trvEntities.filter(s => {
      const name = s.attributes.friendly_name || '';
      return !groupedNames.has(name);
    });

    // Receivers with no room linked — detect by checking room attributes
    const linkedReceiverEntities = new Set();
    rooms.forEach(r => {
      const recvName = (r.attributes.receiver_name || '');
      if (recvName) linkedReceiverEntities.add(recvName);
    });

    // Warnings
    const warnings = [];
    if (recvEntities.length > 0 && rooms.length === 0) {
      warnings.push('No rooms configured — create a room and link your receiver to enable on-demand heating.');
    }
    recvEntities.forEach(r => {
      const name = r.attributes.friendly_name || r.entity_id;
      const linked = rooms.some(room =>
        (room.attributes.receiver_name || '') === name
      );
      if (!linked) {
        warnings.push(`${name} is not linked to any room — edit a room to assign it.`);
      }
    });

    // ── Build HTML ─────────────────────────────────────────────────────────
    let html = '<div class="panel" id="panel">';

    // Warning banners
    warnings.forEach(w => {
      html += `<div class="warning">${ICONS.warn}<span>${w}</span></div>`;
    });

    // ── Rooms ──────────────────────────────────────────────────────────────
    html += `<div class="section">
      <div class="section-hdr">
        <span class="section-title">Rooms</span>
      </div>
      <div class="card">`;

    if (!rooms.length) {
      html += `<div class="empty">No rooms yet. Configure → Rooms → Create a room.</div>`;
    } else {
      rooms.forEach(r => {
        const attrs   = r.attributes;
        const mode    = attrs.mode || 'manual';
        const cur     = attrs.current_temperature;
        const target  = attrs.temperature;
        const heating = attrs.heat_required;
        const members = attrs.member_detail || [];
        const recv    = attrs.receiver_name || '';
        const boost   = mode === 'boost';

        const statusBadge = boost
          ? badge('boosting', 'boost')
          : heating
            ? badge('heating', 'heat')
            : r.state === 'off'
              ? badge('off', 'off')
              : badge('idle', 'idle');
        const recvBadgeRoom = recv
          ? badge(recv, 'recv')
          : `<span class="badge" style="background:#fff7ed;color:#c2410c;font-size:10px;padding:1px 6px;border-radius:10px;font-weight:500">link receiver</span>`;

        const meta = [
          `${members.length} TRV${members.length !== 1 ? 's' : ''}`,
          cur != null ? `avg ${parseFloat(cur).toFixed(1)}°` : null,
          target != null ? `target ${parseFloat(target).toFixed(1)}°` : null,
          recv ? `→ ${recv}` : 'no receiver linked',
        ].filter(Boolean).join(' · ');

        const memberTemps = members
          .map(m => m.temperature != null ? `${m.name}: ${parseFloat(m.temperature).toFixed(1)}°` : null)
          .filter(Boolean).join(', ');

        html += `<div class="row" data-navigate="${r.entity_id}">
          <div class="icon icon-room">${ICONS.room}</div>
          <div class="row-body">
            <div class="row-top">
              <span class="row-name">${attrs.friendly_name || r.entity_id}</span>
              ${statusBadge}
              ${recvBadgeRoom}
            </div>
            <div class="row-meta">${meta}</div>
            ${memberTemps ? `<div class="row-meta" style="margin-top:1px">${memberTemps}</div>` : ''}
          </div>
          ${cur != null ? `<span class="temp">${parseFloat(cur).toFixed(1)}°</span>` : ''}
          ${chev()}
        </div>`;
      });
    }
    html += `</div></div>`;

    // ── Standalone TRVs ────────────────────────────────────────────────────
    if (standalone.length) {
      html += `<div class="section">
        <div class="section-hdr">
          <span class="section-title">Standalone TRVs</span>
          <span class="section-title" style="color:#b45309">not in any room</span>
        </div>
        <div class="card">`;

      standalone.forEach(s => {
        const attrs      = s.attributes;
        const heating    = attrs.hvac_action === 'heating';
        const cur        = attrs.current_temperature;
        const bat        = attrs.battery;
        const demand     = attrs.pi_heating_demand;
        const recvLinked = attrs.receiver_name || null;

        const meta = [
          heating ? 'heating' : (s.state === 'off' ? 'off' : 'idle'),
          cur    != null ? `${parseFloat(cur).toFixed(1)}°` : null,
          bat    != null ? `batt ${Math.round(bat)}%` : null,
          demand != null ? `demand ${Math.round(demand)}%` : null,
          recvLinked ? `→ ${recvLinked}` : 'no receiver linked',
        ].filter(Boolean).join(' · ');

        const recvBadgeTrv = recvLinked
          ? badge(recvLinked, 'recv')
          : `<span class="badge" style="background:#fff7ed;color:#c2410c;font-size:10px;padding:1px 6px;border-radius:10px;font-weight:500">link receiver</span>`;

        html += `<div class="row" data-navigate="${s.entity_id}">
          <div class="dot" style="background:${heating ? '#e8632a' : '#c8c8c8'}"></div>
          <div class="icon icon-trv">${ICONS.trv}</div>
          <div class="row-body">
            <div class="row-top">
              <span class="row-name">${attrs.friendly_name || s.entity_id}</span>
              ${badge('ungrouped', 'solo')}
              ${recvBadgeTrv}
            </div>
            <div class="row-meta">${meta}</div>
          </div>
          ${cur != null ? `<span class="temp">${parseFloat(cur).toFixed(1)}°</span>` : ''}
          ${chev()}
        </div>`;
      });

      html += `</div></div>`;
    }

    // ── Receivers ──────────────────────────────────────────────────────────
    if (recvEntities.length) {
      html += `<div class="section">
        <div class="section-hdr">
          <span class="section-title">Receivers</span>
        </div>
        <div class="card">`;

      recvEntities.forEach(r => {
        const attrs   = r.attributes;
        const heating = attrs.hvac_action === 'heating' || attrs.running_state === 'heat';
        const model   = attrs.model || '';
        const cur     = attrs.current_temperature;

        // Find which room is demanding this receiver
        const demandingRoom = rooms.find(room =>
          room.attributes.receiver_name === (attrs.friendly_name || '') &&
          room.attributes.heat_required
        );

        const meta = [
          heating ? 'heating' : 'idle',
          cur != null ? `${parseFloat(cur).toFixed(1)}°` : null,
          demandingRoom
            ? `${demandingRoom.attributes.friendly_name || ''} demanding`
            : null,
        ].filter(Boolean).join(' · ');

        html += `<div class="row" data-navigate="${r.entity_id}">
          <div class="dot" style="background:${heating ? '#e8632a' : '#c8c8c8'}"></div>
          <div class="icon icon-recv">${ICONS.recv}</div>
          <div class="row-body">
            <div class="row-top">
              <span class="row-name">${attrs.friendly_name || r.entity_id}</span>
              ${model ? badge(model, 'recv') : ''}
            </div>
            <div class="row-meta">${meta}</div>
          </div>
          ${chev()}
        </div>`;
      });

      html += `</div></div>`;
    }

    // ── Settings ───────────────────────────────────────────────────────────
    html += `<div class="section">
      <div class="section-hdr">
        <span class="section-title">Settings</span>
      </div>
      <div class="card">
        <div class="row" data-action="settings">
          <div class="icon icon-set">${ICONS.frost}</div>
          <div class="row-body">
            <div class="row-name">Boiler and frost protection</div>
            <div class="row-meta">Configure receiver, Open-Meteo frost threshold</div>
          </div>
          ${chev()}
        </div>
        <div class="row" data-action="settings">
          <div class="icon icon-set">${ICONS.z2m}</div>
          <div class="row-body">
            <div class="row-name">Z2M and discovery</div>
            <div class="row-meta">Base topic, diagnostic logging</div>
          </div>
          ${chev()}
        </div>
        <div class="row" data-action="manage_devices">
          <div class="icon icon-set">${ICONS.add}</div>
          <div class="row-body">
            <div class="row-name">Add a TRV or receiver</div>
            <div class="row-meta">Manual add if auto-discovery missed a device</div>
          </div>
          ${chev()}
        </div>
        <div class="row" data-action="link_receiver">
          <div class="icon icon-recv">${ICONS.recv}</div>
          <div class="row-body">
            <div class="row-name">Link TRV or room to receiver</div>
            <div class="row-meta">Configure on-demand heating for any TRV or room</div>
          </div>
          ${chev()}
        </div>
      </div>
    </div>`;

    html += '</div>';

    this.shadowRoot.getElementById('panel').outerHTML = html;

    // ── Bind click navigation ──────────────────────────────────────────────
    this.shadowRoot.querySelectorAll('[data-navigate]').forEach(el => {
      el.addEventListener('click', () => {
        const eid = el.dataset.navigate;
        this._hass.callService('lovelace', 'navigate', {path: `/lovelace`});
        this._fireNavigate(eid);
      });
    });

    this.shadowRoot.querySelectorAll('[data-action]').forEach(el => {
      el.addEventListener('click', () => {
        this._openConfig();
      });
    });
  }

  _fireNavigate(entityId) {
    const event = new CustomEvent('hass-more-info', {
      bubbles: true, composed: true,
      detail: {entityId},
    });
    this.dispatchEvent(event);
  }

  _openConfig() {
    const event = new CustomEvent('hass-more-info', {
      bubbles: true, composed: true,
      detail: {entityId: `hive_local`},
    });
    this.dispatchEvent(event);
  }
}

customElements.define('hive-local-panel-card', HiveLocalPanelCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type:        'hive-local-panel-card',
  name:        'Hive Local — System overview',
  description: `v${PANEL_VERSION} — Rooms, TRVs, receivers, settings in one card`,
  preview:     false,
  documentationURL: 'https://github.com/gashwell/Hive-TRV-Local',
});
