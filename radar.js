
"use strict";

(() => {
  const WATCH = [
    "SQM-B", "FALABELLA", "COPEC", "CHILE",
    "BSANTANDER", "CENCOSUD", "ENELCHILE",
    "CMPC", "CAP", "ANDINA-B"
  ];

  const safe = value =>
    String(value ?? "").replace(/[&<>"']/g, c => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;"
    }[c]));

  const moneyRadar = value =>
    Number(value).toLocaleString("es-CL", {
      style: "currency",
      currency: "CLP",
      maximumFractionDigits: 0
    });

  async function getJSON(path) {
    const separator = path.includes("?") ? "&" : "?";
    const response = await fetch(
      path + separator + "t=" + Date.now(),
      { cache: "no-store" }
    );

    if (!response.ok) {
      throw new Error("HTTP " + response.status);
    }

    return response.json();
  }

  // Crear una sola cartera automática.
  function portfolioHost() {
    const analysis = document.getElementById("analysis");
    if (!analysis) return null;

    let card = document.getElementById(
      "bolsaPortfolioCard"
    );

    if (!card) {
      card = document.createElement("div");
      card.id = "bolsaPortfolioCard";
      card.className = "card";

      card.innerHTML = `
        <h2>Cartera automática virtual V1.2</h2>
        <div id="bolsaPortfolioBody" class="muted">
          Consultando cartera...
        </div>
        <div class="actions">
          <button
            id="bolsaRefreshPortfolio"
            class="secondary"
            type="button">
            Actualizar cartera
          </button>
        </div>
      `;

      const radarList = document.getElementById(
        "radarList"
      );

      const radarCard = radarList?.closest(".card");

      if (radarCard) {
        radarCard.insertAdjacentElement(
          "afterend",
          card
        );
      } else {
        analysis.prepend(card);
      }

      document.getElementById(
        "bolsaRefreshPortfolio"
      )?.addEventListener("click", loadPortfolio);
    }

    // Ocultar tarjetas antiguas duplicadas.
    const oldIds = [
      "autoPortfolio",
      "portfolioStatus",
      "remotePortfolio",
      "remotePortfolioBody"
    ];

    oldIds.forEach(id => {
      const element = document.getElementById(id);
      if (!element) return;

      const oldCard = element.closest(".card");

      if (oldCard && oldCard !== card) {
        oldCard.style.display = "none";
      } else if (!card.contains(element)) {
        element.style.display = "none";
      }
    });

    return document.getElementById(
      "bolsaPortfolioBody"
    );
  }

  // Consultar cartera virtual remota.
  async function loadPortfolio() {
    const root = portfolioHost();
    if (!root) return;

    root.textContent = "Consultando cartera...";

    try {
      const p = await getJSON(
        "./data/portfolio.json"
      );

      if (
        p.mode !== "virtual" ||
        !Number.isFinite(Number(p.equity_clp)) ||
        !Number.isFinite(Number(p.cash))
      ) {
        throw new Error(
          "Formato de cartera no válido"
        );
      }

      const positions = Array.isArray(p.positions)
        ? p.positions
        : [];

      const trades = Array.isArray(p.trades)
        ? p.trades
        : [];

      const pct = Number(p.return_pct);

      const pctText = Number.isFinite(pct)
        ? pct.toLocaleString("es-CL", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
          }) + " %"
        : "No disponible";

      const pctClass = pct > 0
        ? "positive"
        : pct < 0
          ? "negative"
          : "";

      root.innerHTML = `
        <div class="grid" style="margin:12px 0">
          <div>
            <div class="muted">
              Patrimonio virtual
            </div>
            <div class="value">
              ${moneyRadar(p.equity_clp)}
            </div>
          </div>

          <div>
            <div class="muted">
              Rentabilidad
            </div>
            <div class="value ${pctClass}">
              ${pctText}
            </div>
          </div>

          <div>
            <div class="muted">
              Efectivo disponible
            </div>
            <div class="value">
              ${moneyRadar(p.cash)}
            </div>
          </div>

          <div>
            <div class="muted">
              Posiciones / operaciones
            </div>
            <div class="value">
              ${positions.length} / ${trades.length}
            </div>
          </div>
        </div>

        <div class="muted">
          Última actualización:
          ${safe(p.updated_at || "Sin fecha")}
        </div>

        <h2 style="margin-top:18px">
          Posiciones abiertas
        </h2>

        <div class="list">
          ${
            positions.length
              ? positions.map(x => `
                  <div class="item">
                    <strong>
                      ${safe(x.symbol || x.ticker || "Acción")}
                    </strong>
                    <small>
                      ${safe(JSON.stringify(x))}
                    </small>
                  </div>
                `).join("")
              : '<div class="muted">Sin posiciones abiertas.</div>'
          }
        </div>

        <h2 style="margin-top:18px">
          Operaciones virtuales
        </h2>

        <div class="list">
          ${
            trades.length
              ? trades.slice(-10).reverse().map(x => `
                  <div class="item">
                    <strong>
                      ${safe(x.symbol || x.ticker || "Operación")}
                    </strong>
                    <small>
                      ${safe(JSON.stringify(x))}
                    </small>
                  </div>
                `).join("")
              : '<div class="muted">Todavía no hay operaciones.</div>'
          }
        </div>

        <p class="muted">
          Simulación educativa.
          No se realizan operaciones reales.
        </p>
      `;

    } catch (error) {
      root.innerHTML = `
        <div class="negative">
          No se pudo consultar la cartera:
          ${safe(error.message)}
        </div>
        <p class="muted">
          Comprueba que portfolio.json
          esté publicado en GitHub Pages.
        </p>
      `;
    }
  }

  // Radar automático de diez acciones.
  async function loadRadar() {
    const root = document.getElementById(
      "radarList"
    );

    const status = document.getElementById(
      "radarStatus"
    );

    if (!root || !status) return;

    status.textContent =
      "Consultando datos publicados...";

    try {
      const obj = await getJSON(
        "./data/market.json"
      );

      const rows = new Map(
        (obj.actions || []).map(
          action => [action.symbol, action]
        )
      );

      status.textContent = obj.updated_at
        ? "Último informe: " +
          obj.updated_at +
          " UTC · Fuente: " +
          (obj.source || "No indicada")
        : "Sin fecha de actualización";

      root.innerHTML = WATCH.map(symbol => {
        const action = rows.get(symbol);

        const ok = action &&
          action.status === "ok";

        const signal = ok
          ? action.signal || "Sin señal"
          : "Pendiente de datos";

        const hitRate = action?.hit_rate == null
          ? "No estimable"
          : (
              Number(action.hit_rate) * 100
            ).toFixed(1) + " %";

        const details = ok
          ? `
            Cierre: ${moneyRadar(action.close)}
            · Fecha: ${safe(action.date)}
            · Casos históricos:
            ${Number(action.samples) || 0}
            · Positivos: ${hitRate}
          `
          : safe(
              action?.reason ||
              "Sin cotizaciones verificadas"
            );

        return `
          <div class="item" style="display:block">
            <div style="
              display:flex;
              justify-content:space-between;
              gap:8px;
            ">
              <strong>${safe(symbol)}</strong>
              <span>${safe(signal)}</span>
            </div>
            <small>${details}</small>
          </div>
        `;
      }).join("");

    } catch (error) {
      status.textContent =
        "Error al consultar radar: " +
        error.message;

      root.innerHTML = "";
    }
  }

  function refreshAll() {
    loadRadar();
    loadPortfolio();
  }

  document.getElementById(
    "refreshRadar"
  )?.addEventListener("click", refreshAll);

  document.getElementById(
    "refreshPortfolio"
  )?.addEventListener("click", loadPortfolio);

  // Iniciar consultas.
  refreshAll();

  // Actualizar al volver a la aplicación.
  document.addEventListener(
    "visibilitychange",
    () => {
      if (!document.hidden) refreshAll();
    }
  );
})();
