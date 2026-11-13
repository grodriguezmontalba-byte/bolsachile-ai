"use strict";
(() => {
  const WATCH_RADAR = ["SQM-B","FALABELLA","COPEC","CHILE","BSANTANDER","CENCOSUD","ENELCHILE","CMPC","CAP","ANDINA-B"];
  const escapeRadar = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));
  const formatMoneyRadar = value => Number(value).toLocaleString("es-CL", {style:"currency",currency:"CLP",maximumFractionDigits:0});
  async function getRadarJSON(path) {
    const response = await fetch(path + "?t=" + Date.now(), {cache:"no-store"});
    if (!response.ok) throw new Error("HTTP " + response.status);
    return response.json();
  }
  function portfolioHost() {
    // Prefer the existing standalone portfolio section. Do not create duplicates.
    const standalone = document.getElementById("autoPortfolio") || document.getElementById("portfolioStatus") || document.getElementById("remotePortfolioBody") || document.getElementById("remotePortfolio");
    if (standalone) return standalone;
    const analysis = document.getElementById("analysis");
    const radarList = document.getElementById("radarList");
    if (!analysis || !radarList) return null;
    const card = document.createElement("div");
    card.className = "card";
    card.id = "remotePortfolio";
    card.innerHTML = '<h2>Cartera automática virtual</h2><div id="remotePortfolioBody" class="muted">Consultando cartera…</div>';
    const radarCard = radarList.closest(".card");
    if (radarCard) radarCard.insertAdjacentElement("afterend", card);
    else analysis.prepend(card);
    return document.getElementById("remotePortfolioBody");
  }
  async function loadPortfolioRadar() {
    const root = portfolioHost();
    if (!root) return;
    root.textContent = "Consultando cartera…";
    try {
      const p = await getRadarJSON("./data/portfolio.json");
      if (p.mode !== "virtual" || !Number.isFinite(Number(p.equity_clp)) || !Number.isFinite(Number(p.cash))) throw new Error("Formato de cartera no válido");
      const positions = Array.isArray(p.positions) ? p.positions : [];
      const trades = Array.isArray(p.trades) ? p.trades : [];
      const pct = Number(p.return_pct);
      root.innerHTML = `<div class="grid" style="margin:12px 0"><div><div class="muted">Patrimonio virtual</div><div class="value">${formatMoneyRadar(p.equity_clp)}</div></div><div><div class="muted">Rentabilidad</div><div class="value ${pct > 0 ? 'positive' : pct < 0 ? 'negative' : ''}">${Number.isFinite(pct) ? pct.toLocaleString('es-CL',{minimumFractionDigits:2,maximumFractionDigits:2}) + ' %' : 'No disponible'}</div></div><div><div class="muted">Efectivo</div><div class="value">${formatMoneyRadar(p.cash)}</div></div><div><div class="muted">Posiciones / operaciones</div><div class="value">${positions.length} / ${trades.length}</div></div></div><div class="muted">Última actualización: ${escapeRadar(p.updated_at || 'sin fecha')} · Datos simulados, no operaciones reales.</div><h2 style="margin-top:18px">Posiciones abiertas</h2><div class="list">${positions.length ? positions.map(x => `<div class="item"><strong>${escapeRadar(x.symbol || x.ticker || 'Acción')}</strong><small>${escapeRadar(JSON.stringify(x))}</small></div>`).join('') : '<div class="muted">Sin posiciones abiertas.</div>'}</div><h2 style="margin-top:18px">Últimas operaciones virtuales</h2><div class="list">${trades.length ? trades.slice(-10).reverse().map(x => `<div class="item"><strong>${escapeRadar(x.symbol || x.ticker || 'Operación')}</strong><small>${escapeRadar(JSON.stringify(x))}</small></div>`).join('') : '<div class="muted">Todavía no hay operaciones.</div>'}</div>`;
    } catch (err) {
      root.innerHTML = `<span class="negative">No se pudo consultar la cartera: ${escapeRadar(err.message)}</span> <button class="secondary" id="retryPortfolioRadar" type="button">Reintentar</button>`;
      document.getElementById("retryPortfolioRadar")?.addEventListener("click", loadPortfolioRadar);
    }
  }
  async function loadMarketRadar() {
    const root = document.getElementById("radarList"), status = document.getElementById("radarStatus");
    if (!root || !status) return;
    status.textContent = "Consultando datos publicados…";
    try {
      const obj = await getRadarJSON("./data/market.json");
      const rows = new Map((obj.actions || []).map(x => [x.symbol,x]));
      status.textContent = obj.updated_at ? "Último informe: " + obj.updated_at + " UTC · Fuente: " + (obj.source || "no indicada") : "Sin fecha de actualización.";
      root.innerHTML = WATCH_RADAR.map(symbol => {
        const a = rows.get(symbol), ok = a && a.status === "ok", label = ok ? (a.signal || "Sin señal") : "Pendiente de datos";
        return `<div class="item" style="display:block"><div style="display:flex;justify-content:space-between;gap:8px"><strong>${escapeRadar(symbol)}</strong><span>${escapeRadar(label)}</span></div><small>${ok ? `Cierre: ${formatMoneyRadar(a.close)} · Fecha: ${escapeRadar(a.date)} · Casos fuera de muestra: ${Number(a.samples) || 0} · Positivos: ${a.hit_rate == null ? "No estimable" : (100 * a.hit_rate).toFixed(1) + " %"}` : escapeRadar(a?.reason || "Aún sin cotizaciones verificadas")}</small></div>`;
      }).join("");
    } catch (err) {
      status.textContent = "No se pudo consultar el radar: " + err.message;
      root.innerHTML = "";
    }
  }
  document.getElementById("refreshRadar")?.addEventListener("click", () => {loadMarketRadar();loadPortfolioRadar();});
  document.getElementById("refreshPortfolio")?.addEventListener("click", loadPortfolioRadar);
  loadMarketRadar();
  loadPortfolioRadar();
})();
