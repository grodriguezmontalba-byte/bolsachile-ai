"use strict";
const WATCH=["SQM-B","FALABELLA","COPEC","CHILE","BSANTANDER","CENCOSUD","ENELCHILE","CMPC","CAP","ANDINA-B"];
const safe=t=>String(t??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));
async function radar(){const root=document.getElementById("radarList"),status=document.getElementById("radarStatus");if(!root)return;
status.textContent="Consultando datos publicados…";let obj=null;try{const r=await fetch("./data/market.json?t="+Date.now(),{cache:"no-store"});if(r.ok)obj=await r.json()}catch(e){}
const rows=new Map((obj?.actions||[]).map(x=>[x.symbol,x]));status.textContent=obj?.updated_at?"Último informe: "+obj.updated_at+" UTC · Fuente: "+(obj.source||"no indicada"):"No hay informe automático publicado todavía.";
root.innerHTML=WATCH.map(symbol=>{const a=rows.get(symbol);const ok=a&&a.status==="ok";const label=ok?(a.signal||"Sin señal"):"Pendiente de datos";return `<div class="item" style="display:block"><div style="display:flex;justify-content:space-between;gap:8px"><strong>${safe(symbol)}</strong><span>${safe(label)}</span></div><small>${ok?`Cierre: $${Number(a.close).toLocaleString("es-CL")} · Fecha: ${safe(a.date)} · Casos fuera de muestra: ${Number(a.samples)||0} · Positivos: ${a.hit_rate==null?"No estimable":(100*a.hit_rate).toFixed(1)+" %"}`:safe(a?.reason||"Aún sin cotizaciones verificadas")}</small></div>`}).join("");}
document.getElementById("refreshRadar")?.addEventListener("click",radar);radar();
