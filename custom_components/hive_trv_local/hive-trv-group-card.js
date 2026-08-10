/**
 * hive-trv-group-card — Hive TRV Local room group card
 * For Hive TRV Local v2/v3 room group climate entities.
 *
 * Config:
 *   type: custom:hive-trv-group-card
 *   entity: climate.living_room            # room group entity
 *   name: Living Room                      # optional
 */
const GROUP_CARD_VERSION = "2.0.0";

const GSTYLES = `
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
  .divl{height:1px;background:var(--divider-color,#eee)}
  .sect{padding:10px 14px}
  .stitle{font-size:11px;color:var(--secondary-text-color,#888);margin-bottom:7px}
  .member{display:flex;justify-content:space-between;align-items:center;padding:6px 10px;background:var(--secondary-background-color,#f5f5f5);border-radius:8px;margin-bottom:4px}
  .mname{font-size:12px;color:var(--secondary-text-color,#888)}
  .mtemp{font-size:13px;font-weight:500;color:var(--primary-text-color,#333)}
  .demand-row{display:flex;align-items:center;gap:8px;padding:10px 14px;border-bottom:1px solid var(--divider-color,#eee)}
  .dlbl{font-size:12px;color:var(--secondary-text-color,#888);min-width:80px}
  .dtrack{flex:1;height:6px;background:var(--divider-color,#ddd);border-radius:3px;overflow:hidden}
  .dfill{height:100%;border-radius:3px;background:#f97316;transition:width .4s}
  .dval{font-size:12px;font-weight:500;min-width:32px;color:var(--primary-text-color,#333)}
  .heat-badge{font-size:11px;padding:2px 8px;border-radius:6px;font-weight:500}
  .actions{display:flex;gap:8px;padding:10px 14px}
  .abtn{flex:1;padding:8px;border-radius:8px;border:1px solid var(--divider-color,#eee);background:transparent;color:var(--secondary-text-color,#888);font-size:12px;cursor:pointer}
`;

class HiveTRVGroupCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode:"open" });
    this._boostInterval = null;
    this._boostSecs = 0;
    this._localMode = null;
    this._localTarget = null;
  }

  static getConfigElement() { return document.createElement("hive-trv-group-card-editor"); }

  static getStubConfig(hass) {
    const group = Object.keys(hass.states).find(e => {
      const s = hass.states[e];
      return e.startsWith("climate.") && Array.isArray(s?.attributes?.members);
    });
    return { entity: group || "climate.living_room" };
  }

  set hass(hass) { this._hass = hass; this._render(); }

  setConfig(cfg) {
    if (!cfg.entity) throw new Error("entity is required");
    this._cfg = cfg;
  }

  getCardSize() { return 6; }

  _st() { return this._hass?.states[this._cfg.entity] || null; }
  _a(k) { return this._st()?.attributes[k] ?? null; }
  _mode() { return this._localMode || this._st()?.state || "off"; }
  _target() { return this._localTarget ?? this._a("temperature") ?? 20; }

  _render() {
    const sh = this.shadowRoot;
    if (!sh.querySelector("style")) {
      const s = document.createElement("style"); s.textContent = GSTYLES; sh.appendChild(s);
      sh.appendChild(document.createElement("div"));
    }

    const mode    = this._mode();
    const target  = parseFloat(this._target()).toFixed(1);
    const curT    = this._a("current_temperature");
    const name    = this._cfg.name || this._a("friendly_name") || this._cfg.entity;
    const isHeat  = this._a("heat_required") === true || this._a("hvac_action") === "heating";
    const demand  = this._a("pi_heating_demand") || 0;
    const members = this._a("members") || [];
    const mTemps  = this._a("member_temperatures") || {};
    const mCount  = this._a("member_count") || members.length;

    const color   = mode==="boost"?"#dc2626":mode==="off"?"#6b7280":mode==="schedule"?"#7c3aed":isHeat?"#f97316":"#3b82f6";
    const sIcon   = mode==="boost"?"🚀":mode==="off"?"⏻":mode==="schedule"?"📅":isHeat?"🔥":"💧";
    const sTxt    = mode==="boost"?"Boosting":mode==="off"?"Off":mode==="schedule"?"Schedule":isHeat?"Heating":"Idle";
    const curDisp = curT != null ? parseFloat(curT).toFixed(1)+"°" : "—";

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
      : `<div style="font-size:12px;color:var(--secondary-text-color);text-align:center;padding:8px 0">No schedule. Use Configure → Set a heating schedule.</div>`;

    const boostCd = this._boostSecs > 0
      ? `${Math.floor(this._boostSecs/60)}:${String(this._boostSecs%60).padStart(2,"0")} remaining`
      : this._a("boost_remaining_minutes") != null ? `${this._a("boost_remaining_minutes")} min remaining` : "";

    // Member rows — use member_temperatures attribute if available
    const memberHtml = members.map(eid => {
      const temp = mTemps[eid];
      const mState = this._hass.states[eid];
      const mName  = mState?.attributes?.friendly_name || eid.split(".")[1].replace(/_/g," ");
      const tempStr = temp != null ? parseFloat(temp).toFixed(1)+" °C" : "—";
      const heating = mState?.attributes?.hvac_action === "heating";
      return `<div class="member">
        <span class="mname">${mName}</span>
        <div style="display:flex;align-items:center;gap:6px">
          ${heating ? `<span style="font-size:10px;color:#f97316">🔥</span>` : ""}
          <span class="mtemp">${tempStr}</span>
        </div>
      </div>`;
    }).join("") || `<div style="font-size:12px;color:var(--secondary-text-color);padding:4px 0">No members configured.</div>`;

    sh.children[1].innerHTML = `
      <div class="card">
        <div class="hdr" style="background:${color}">
          <div class="hdr-top">
            <div>
              <div class="name">${name} <span style="font-size:10px;opacity:.75">(${mCount} TRV${mCount!==1?"s":""})</span></div>
              <div class="status"><span>${sIcon}</span><span>${sTxt}</span></div>
            </div>
            <div class="cur-temp">
              <div class="lbl">Avg current</div>
              <div class="val">${curDisp}</div>
            </div>
          </div>
          <div class="tgt-row">
            <button class="adj" id="minus">−</button>
            <div class="tgt"><div class="lbl">Group target</div><div class="val" id="tval">${target}°</div></div>
            <button class="adj" id="plus">+</button>
          </div>
        </div>

        <div class="modes">
          ${[{m:"manual",i:"🌡",l:"Manual"},{m:"schedule",i:"📅",l:"Schedule"},{m:"boost",i:"🚀",l:"Boost"},{m:"off",i:"⏻",l:"Off"}]
            .map(({m,i,l}) => `<button class="mbtn${mode===m?" on":""}" data-mode="${m}"><span class="mi">${i}</span>${l}</button>`).join("")}
        </div>

        ${mode==="boost" ? `
        <div class="panel">
          <div class="prow"><span class="ptitle">Group boost</span><span class="countdown" id="bcd">${boostCd}</span></div>
          <div class="srow"><span class="slbl">Temperature</span>
            <input type="range" min="5" max="32" step="0.5" value="${this._a("boost_temperature")||22}" id="btemp" oninput="this.getRootNode().getElementById('btv').textContent=parseFloat(this.value).toFixed(1)+'°'">
            <span class="sval" id="btv">${parseFloat(this._a("boost_temperature")||22).toFixed(1)}°</span></div>
          <div class="srow"><span class="slbl">Duration</span>
            <input type="range" min="5" max="120" step="5" value="${this._a("boost_duration")||30}" id="bdur" oninput="this.getRootNode().getElementById('bdv').textContent=this.value+' min'">
            <span class="sval" id="bdv">${this._a("boost_duration")||30} min</span></div>
          <button class="pbtn" id="endboost">End group boost</button>
        </div>` : mode==="schedule" ? `
        <div class="panel">
          <div class="prow"><span class="ptitle">Group schedule</span></div>
          ${schedHtml}
          <button class="pbtn" id="skip">Skip to next slot →</button>
        </div>` : ""}

        <div class="demand-row">
          <span class="dlbl">Heating demand</span>
          <div class="dtrack"><div class="dfill" style="width:${demand}%"></div></div>
          <span class="dval">${demand}%</span>
          <span class="heat-badge" style="background:${isHeat?"rgba(249,115,22,.1)":"var(--secondary-background-color)"};color:${isHeat?"#f97316":"var(--secondary-text-color)"}">
            ${isHeat?"Heating":"Idle"}
          </span>
        </div>

        <div class="divl"></div>
        <div class="sect">
          <div class="stitle">Member temperatures</div>
          ${memberHtml}
        </div>

        <div class="divl"></div>
        <div class="actions">
          <button class="abtn" id="frostbtn">❄ Frost protect all</button>
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
      htl("end_boost",{}); this._localMode="manual";
      if(this._boostInterval) clearInterval(this._boostInterval);
      this._render();
    });
    sh.getElementById("skip")?.addEventListener("click",()=>htl("advance_schedule",{}));
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

customElements.define("hive-trv-group-card",HiveTRVGroupCard);
window.customCards=window.customCards||[];
window.customCards.push({
  type:"hive-trv-group-card",
  name:"Hive TRV Group Card",
  description:`v${GROUP_CARD_VERSION} — Hive TRV Local room group card`,
  preview:true,
  documentationURL:"https://github.com/gashwell/Hive-TRV-Local-v2",
  getEntitySuggestion:(hass,entityId)=>{
    if(!entityId.startsWith("climate.")) return null;
    const s=hass.states[entityId];
    if(!s) return null;
    // Must be a Hive TRV Local room group (has members array attribute)
    if(!Array.isArray(s.attributes.members)) return null;
    return {config:{type:"custom:hive-trv-group-card",entity:entityId}};
  },
});
console.info(`%c HIVE-TRV-GROUP-CARD %c v${GROUP_CARD_VERSION} `,"color:#7c3aed;font-weight:700;background:#000;padding:2px 4px","background:#7c3aed;color:#fff;padding:2px 4px");

