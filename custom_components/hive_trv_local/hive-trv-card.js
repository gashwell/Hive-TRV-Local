/**
 * hive-trv-card — Standalone Hive/Danfoss TRV card
 * For individual Z2M TRV climate entities.
 * Install via Hive TRV Local (auto-registered) or manually.
 *
 * Config:
 *   type: custom:hive-trv-card
 *   entity: climate.living_room_trv
 *   name: Living Room                             # optional
 *   battery_entity: sensor.trv_battery            # optional
 *   demand_entity: sensor.trv_pi_heating_demand   # optional
 *   orientation_entity: select.trv_mounting_orientation  # optional
 */
const CARD_VERSION = "2.0.0";

const STYLES = `
  :host{display:block}
  *{box-sizing:border-box}
  .card{background:var(--card-background-color,#fff);border-radius:14px;overflow:hidden;box-shadow:var(--ha-card-box-shadow,0 2px 8px rgba(0,0,0,.1));font-family:var(--primary-font-family,sans-serif)}
  .hdr{padding:16px 18px 14px;transition:background .3s}
  .hdr-top{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:14px}
  .name{font-size:12px;color:rgba(255,255,255,.75);margin-bottom:3px}
  .status{display:flex;align-items:center;gap:6px;font-size:13px;color:rgba(255,255,255,.9)}
  .cur-temp .lbl{font-size:11px;color:rgba(255,255,255,.7);text-align:right}
  .cur-temp .val{font-size:30px;font-weight:500;color:#fff;line-height:1;text-align:right}
  .tgt-row{display:flex;align-items:center;justify-content:center;gap:20px;border-top:.5px solid rgba(255,255,255,.2);padding-top:14px}
  .adj{width:42px;height:42px;border-radius:50%;background:rgba(255,255,255,.2);border:none;color:#fff;font-size:24px;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:background .15s}
  .adj:hover{background:rgba(255,255,255,.35)}
  .tgt .lbl{font-size:11px;color:rgba(255,255,255,.7);text-align:center}
  .tgt .val{font-size:38px;font-weight:500;color:#fff;line-height:1;text-align:center;min-width:96px}
  .modes{display:flex;gap:6px;padding:10px 14px;border-bottom:1px solid var(--divider-color,#eee)}
  .mbtn{flex:1;padding:8px 3px;border-radius:8px;border:1px solid var(--divider-color,#eee);font-size:11px;cursor:pointer;background:transparent;color:var(--secondary-text-color,#888);text-align:center;transition:all .15s}
  .mbtn .mi{font-size:15px;display:block;margin-bottom:2px}
  .mbtn.on{background:var(--secondary-background-color,#f5f5f5);color:var(--primary-text-color,#333);font-weight:500}
  .panel{padding:12px 14px;background:var(--secondary-background-color,#f5f5f5);border-bottom:1px solid var(--divider-color,#eee)}
  .prow{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}
  .ptitle{font-size:13px;font-weight:500;color:var(--primary-text-color,#333)}
  .countdown{font-size:12px;color:#f97316;font-weight:600}
  .srow{display:flex;gap:10px;align-items:center;margin-bottom:8px}
  .slbl{font-size:12px;color:var(--secondary-text-color,#888);min-width:70px}
  .srow input[type=range]{flex:1;accent-color:#f97316}
  .sval{font-size:13px;font-weight:500;min-width:44px;text-align:right;color:var(--primary-text-color,#333)}
  .pbtn{width:100%;padding:8px;border-radius:8px;border:1px solid var(--divider-color,#eee);background:transparent;color:var(--secondary-text-color,#888);font-size:13px;cursor:pointer;margin-top:6px}
  .slot{display:flex;justify-content:space-between;align-items:center;padding:6px 8px;border-radius:6px;margin-bottom:4px;font-size:13px;border:1px solid var(--divider-color,#eee)}
  .slot.cur{background:rgba(249,115,22,.1);border-color:#f97316}
  .now{font-size:10px;background:rgba(249,115,22,.15);color:#f97316;padding:1px 5px;border-radius:4px;margin-left:4px;font-weight:600}
  .stats{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;padding:10px 14px}
  .stat{background:var(--secondary-background-color,#f5f5f5);border-radius:8px;padding:8px 10px}
  .slabel{font-size:11px;color:var(--secondary-text-color,#888);margin-bottom:4px}
  .brow{display:flex;align-items:center;gap:4px}
  .btrack{flex:1;height:5px;background:var(--divider-color,#ddd);border-radius:3px;overflow:hidden}
  .bfill{height:100%;border-radius:3px;transition:width .4s}
  .sigbars{display:flex;align-items:flex-end;gap:2px;height:16px;margin-top:2px}
  .sigbar{width:3px;border-radius:1px}
  .divl{height:1px;background:var(--divider-color,#eee)}
  .sect{padding:10px 14px}
  .stitle{font-size:11px;color:var(--secondary-text-color,#888);margin-bottom:7px}
  .orient{display:flex;gap:6px}
  .obtn{flex:1;padding:7px 4px;border-radius:8px;border:1px solid var(--divider-color,#eee);background:transparent;color:var(--secondary-text-color,#888);font-size:11px;cursor:pointer;text-align:center;transition:all .15s}
  .obtn.on{border-color:#f97316;color:#f97316;background:rgba(249,115,22,.08);font-weight:500}
  .ohint{font-size:10px;color:var(--secondary-text-color);margin-top:5px}
  .actions{display:flex;gap:8px;padding:10px 14px;flex-wrap:wrap}
  .abtn{flex:1;min-width:110px;padding:8px;border-radius:8px;border:1px solid var(--divider-color,#eee);background:transparent;color:var(--secondary-text-color,#888);font-size:12px;cursor:pointer;transition:all .15s}
  .abtn.warn{border-color:#ef4444;color:#ef4444;background:rgba(239,68,68,.06)}
`;

const COLORS = { manual:"#f97316", boost:"#dc2626", schedule:"#7c3aed", idle:"#3b82f6", off:"#6b7280" };

class HiveTRVCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode:"open" });
    this._boostInterval = null;
    this._boostSecs = 0;
    this._localMode = null;
    this._localTarget = null;
    this._windowOpen = false;
  }

  static getConfigElement() { return document.createElement("hive-trv-card-editor"); }

  static getStubConfig(hass) {
    const trv = Object.keys(hass.states).find(e => {
      const s = hass.states[e];
      return e.startsWith("climate.") && (s?.attributes?.pi_heating_demand !== undefined || s?.attributes?.battery !== undefined);
    });
    return { entity: trv || "climate.living_room_trv" };
  }

  set hass(hass) { this._hass = hass; this._render(); }

  setConfig(cfg) {
    if (!cfg.entity) throw new Error("entity is required");
    this._cfg = cfg;
  }

  getCardSize() { return 5; }

  _st() { return this._hass?.states[this._cfg.entity] || null; }
  _a(k) { return this._st()?.attributes[k] ?? null; }
  _mode() { return this._localMode || this._st()?.state || "off"; }
  _target() { return this._localTarget ?? this._a("temperature") ?? 20; }
  _curTemp() { return this._a("current_temperature") ?? "—"; }

  _orient() {
    if (this._cfg.orientation_entity)
      return this._hass.states[this._cfg.orientation_entity]?.state || "auto";
    return this._a("thermostat_orientation") || "auto";
  }

  _render() {
    const sh = this.shadowRoot;
    if (!sh.querySelector("style")) {
      const s = document.createElement("style"); s.textContent = STYLES; sh.appendChild(s);
      sh.appendChild(document.createElement("div"));
    }

    const mode     = this._mode();
    const target   = parseFloat(this._target()).toFixed(1);
    const curT     = parseFloat(this._curTemp() || 0).toFixed(1);
    const name     = this._cfg.name || this._a("friendly_name") || this._cfg.entity;
    const isHeat   = this._a("hvac_action") === "heating";
    const orient   = this._orient();

    const battery  = this._cfg.battery_entity
                     ? parseInt(this._hass.states[this._cfg.battery_entity]?.state || 0)
                     : (this._a("battery") ?? null);
    const demand   = this._cfg.demand_entity
                     ? parseInt(this._hass.states[this._cfg.demand_entity]?.state || 0)
                     : (this._a("pi_heating_demand") || 0);

    const color    = mode==="boost"?"#dc2626":mode==="off"?"#6b7280":mode==="schedule"?"#7c3aed":isHeat?"#f97316":"#3b82f6";
    const sIcon    = mode==="boost"?"🚀":mode==="off"?"⏻":mode==="schedule"?"📅":isHeat?"🔥":"💧";
    const sTxt     = mode==="boost"?"Boosting":mode==="off"?"Off":mode==="schedule"?"Schedule":isHeat?"Heating":"Idle";
    const battBar  = battery ?? 0;
    const battCol  = battBar > 30 ? "#22c55e" : battBar > 15 ? "#f97316" : "#ef4444";

    const schedSlots = this._a("schedule") || [];
    const curIdx     = this._a("schedule_current_slot") || 0;
    const schedHtml  = schedSlots.length
      ? schedSlots.map((s,i) => `<div class="slot ${i===curIdx?"cur":""}">
          <span style="color:var(--primary-text-color)">${s.time}</span>
          <span style="font-weight:${i===curIdx?500:400};color:var(--primary-text-color)">
            ${parseFloat(s.temperature).toFixed(1)} °C
            ${i===curIdx?'<span class="now">now</span>':""}
          </span>
        </div>`).join("")
      : `<div style="font-size:12px;color:var(--secondary-text-color);text-align:center;padding:8px 0">No schedule configured.</div>`;

    const boostCd = this._boostSecs > 0
      ? `${Math.floor(this._boostSecs/60)}:${String(this._boostSecs%60).padStart(2,"0")} remaining`
      : this._a("boost_remaining_minutes") != null ? `${this._a("boost_remaining_minutes")} min remaining` : "";

    sh.children[1].innerHTML = `
      <div class="card">
        <div class="hdr" style="background:${color}">
          <div class="hdr-top">
            <div>
              <div class="name">${name}</div>
              <div class="status"><span>${sIcon}</span><span>${sTxt}</span></div>
            </div>
            <div class="cur-temp">
              <div class="lbl">Current</div>
              <div class="val">${curT}°</div>
            </div>
          </div>
          <div class="tgt-row">
            <button class="adj" id="minus">−</button>
            <div class="tgt"><div class="lbl">Target</div><div class="val" id="tval">${target}°</div></div>
            <button class="adj" id="plus">+</button>
          </div>
        </div>

        <div class="modes">
          ${[{m:"manual",i:"🌡",l:"Manual"},{m:"schedule",i:"📅",l:"Schedule"},{m:"boost",i:"🚀",l:"Boost"},{m:"off",i:"⏻",l:"Off"}]
            .map(({m,i,l}) => `<button class="mbtn${mode===m?" on":""}" data-mode="${m}"><span class="mi">${i}</span>${l}</button>`).join("")}
        </div>

        ${mode==="boost" ? `
        <div class="panel">
          <div class="prow"><span class="ptitle">Boost</span><span class="countdown" id="bcd">${boostCd}</span></div>
          <div class="srow"><span class="slbl">Temperature</span>
            <input type="range" min="5" max="32" step="0.5" value="${this._a("boost_temperature")||22}" id="btemp" oninput="this.getRootNode().getElementById('btv').textContent=parseFloat(this.value).toFixed(1)+'°'">
            <span class="sval" id="btv">${parseFloat(this._a("boost_temperature")||22).toFixed(1)}°</span></div>
          <div class="srow"><span class="slbl">Duration</span>
            <input type="range" min="5" max="120" step="5" value="${this._a("boost_duration")||30}" id="bdur" oninput="this.getRootNode().getElementById('bdv').textContent=this.value+' min'">
            <span class="sval" id="bdv">${this._a("boost_duration")||30} min</span></div>
          <button class="pbtn" id="endboost">End boost</button>
        </div>` : mode==="schedule" ? `
        <div class="panel">
          <div class="prow"><span class="ptitle">Schedule</span></div>
          ${schedHtml}
          <button class="pbtn" id="skip">Skip to next slot →</button>
        </div>` : ""}

        <div class="stats">
          ${battery!=null ? `<div class="stat"><div class="slabel">Battery</div>
            <div class="brow"><div class="btrack"><div class="bfill" style="width:${battBar}%;background:${battCol}"></div></div>
            <span style="font-size:11px;font-weight:500;min-width:28px;color:var(--primary-text-color)">${battBar}%</span></div></div>` : ""}
          <div class="stat"><div class="slabel">Demand</div>
            <div class="brow"><div class="btrack"><div class="bfill" style="width:${demand}%;background:#f97316"></div></div>
            <span style="font-size:11px;font-weight:500;min-width:28px;color:var(--primary-text-color)">${demand}%</span></div></div>
          <div class="stat"><div class="slabel">Signal</div>
            <div class="sigbars">${[5,8,12,16].map((h,i)=>`<div class="sigbar" style="height:${h}px;background:${i<3?"#22c55e":"var(--divider-color,#ddd)"}"></div>`).join("")}</div>
          </div>
        </div>

        <div class="divl"></div>
        <div class="sect">
          <div class="stitle">Valve mounting orientation</div>
          <div class="orient">
            ${[{v:"auto",l:"Auto"},{v:"horizontal",l:"Horizontal"},{v:"vertical",l:"Vertical"}]
              .map(o=>`<button class="obtn${orient===o.v?" on":""}" data-orient="${o.v}">${o.l}</button>`).join("")}
          </div>
          <div class="ohint">Set to match your radiator pipe direction for accurate valve control.</div>
        </div>

        <div class="divl"></div>
        <div class="actions">
          <button class="abtn${this._windowOpen?" warn":""}" id="winbtn">
            🪟 ${this._windowOpen?"Window open":"Window closed"}
          </button>
          ${mode!=="off" ? `<button class="abtn" id="frostbtn">❄ Frost protect</button>` : ""}
        </div>
      </div>`;

    this._bind();
  }

  _bind() {
    const sh  = this.shadowRoot;
    const eid = this._cfg.entity;
    const svc = (s,d) => this._hass.callService("climate",s,{entity_id:eid,...d});
    const htl = (s,d) => this._hass.callService("hive_trv_local",s,{entity_id:eid,...d})
                          .catch(()=>this._hass.callService("hive_local_trv",s,{entity_id:eid,...d}).catch(()=>{}));

    sh.getElementById("minus")?.addEventListener("click",()=>{
      this._localTarget=Math.max(5,parseFloat(this._target())-0.5);
      sh.getElementById("tval").textContent=this._localTarget.toFixed(1)+"°";
      svc("set_temperature",{temperature:this._localTarget});
    });
    sh.getElementById("plus")?.addEventListener("click",()=>{
      this._localTarget=Math.min(32,parseFloat(this._target())+0.5);
      sh.getElementById("tval").textContent=this._localTarget.toFixed(1)+"°";
      svc("set_temperature",{temperature:this._localTarget});
    });

    sh.querySelectorAll(".mbtn").forEach(b=>b.addEventListener("click",()=>{
      const m=b.dataset.mode; this._localMode=m;
      if(m==="off") svc("set_hvac_mode",{hvac_mode:"off"});
      else if(m==="boost"){
        const bt=parseFloat(sh.getElementById("btemp")?.value||22);
        const bd=parseInt(sh.getElementById("bdur")?.value||30);
        htl("boost",{temperature:bt,duration_minutes:bd});
        this._startTimer(bd*60);
      } else { svc("set_hvac_mode",{hvac_mode:"heat"}); svc("set_preset_mode",{preset_mode:m}); }
      this._render();
    }));

    sh.getElementById("endboost")?.addEventListener("click",()=>{
      htl("end_boost",{});
      this._localMode="manual";
      if(this._boostInterval) clearInterval(this._boostInterval);
      this._render();
    });
    sh.getElementById("skip")?.addEventListener("click",()=>htl("advance_schedule",{}));

    sh.querySelectorAll(".obtn").forEach(b=>b.addEventListener("click",()=>{
      const o=b.dataset.orient;
      if(this._cfg.orientation_entity)
        this._hass.callService("select","select_option",{entity_id:this._cfg.orientation_entity,option:o});
      else {
        const fname=this._a("friendly_name")||eid;
        this._hass.callService("mqtt","publish",{topic:`zigbee2mqtt/${fname}/set`,payload:JSON.stringify({thermostat_orientation:o})}).catch(()=>{});
      }
    }));

    sh.getElementById("winbtn")?.addEventListener("click",()=>{
      this._windowOpen=!this._windowOpen;
      const fname=this._a("friendly_name")||eid;
      this._hass.callService("mqtt","publish",{topic:`zigbee2mqtt/${fname}/set`,payload:JSON.stringify({window_open_external:this._windowOpen})}).catch(()=>{});
      this._render();
    });

    sh.getElementById("frostbtn")?.addEventListener("click",()=>svc("set_temperature",{temperature:7}));
  }

  _startTimer(s){
    if(this._boostInterval) clearInterval(this._boostInterval);
    this._boostSecs=s;
    this._boostInterval=setInterval(()=>{
      this._boostSecs=Math.max(0,this._boostSecs-1);
      const cd=this.shadowRoot.getElementById("bcd");
      if(cd) cd.textContent=`${Math.floor(this._boostSecs/60)}:${String(this._boostSecs%60).padStart(2,"0")} remaining`;
      if(this._boostSecs===0){clearInterval(this._boostInterval);this._localMode="manual";this._render();}
    },1000);
  }

  disconnectedCallback(){ if(this._boostInterval) clearInterval(this._boostInterval); }
}

customElements.define("hive-trv-card",HiveTRVCard);
window.customCards=window.customCards||[];
window.customCards.push({
  type:"hive-trv-card",
  name:"Hive TRV Card",
  description:`v${CARD_VERSION} — Individual Hive/Danfoss TRV card`,
  preview:true,
  documentationURL:"https://github.com/gashwell/Hive-TRV-Local-v2",
  getEntitySuggestion:(hass,entityId)=>{
    if(!entityId.startsWith("climate.")) return null;
    const s=hass.states[entityId];
    if(!s) return null;
    const a=s.attributes;
    // Must be an individual TRV (has pi_heating_demand or battery) and NOT a group
    const isTRV=(a.pi_heating_demand!==undefined||a.battery!==undefined);
    const isGroup=Array.isArray(a.members);
    if(!isTRV||isGroup) return null;
    const slug=entityId.replace("climate.","");
    const cfg={type:"custom:hive-trv-card",entity:entityId};
    if(hass.states[`sensor.${slug}_battery`]) cfg.battery_entity=`sensor.${slug}_battery`;
    if(hass.states[`sensor.${slug}_pi_heating_demand`]) cfg.demand_entity=`sensor.${slug}_pi_heating_demand`;
    else if(hass.states[`sensor.${slug}_heating_demand`]) cfg.demand_entity=`sensor.${slug}_heating_demand`;
    if(hass.states[`select.${slug}_mounting_orientation`]) cfg.orientation_entity=`select.${slug}_mounting_orientation`;
    else if(hass.states[`select.${slug}_thermostat_orientation`]) cfg.orientation_entity=`select.${slug}_thermostat_orientation`;
    return {config:cfg};
  },
});
console.info(`%c HIVE-TRV-CARD %c v${CARD_VERSION} `,"color:#f97316;font-weight:700;background:#000;padding:2px 4px","background:#f97316;color:#fff;padding:2px 4px");

