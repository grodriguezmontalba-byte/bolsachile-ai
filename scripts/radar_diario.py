
#!/usr/bin/env python3
"""BolsaChile AI V1.3: radar y cartera exclusivamente virtual."""

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DATA.mkdir(parents=True, exist_ok=True)

SYMBOLS = [
    "SQM-B", "FALABELLA", "COPEC", "CHILE", "BSANTANDER",
    "CENCOSUD", "ENELCHILE", "CMPC", "CAP", "ANDINA-B"
]

HORIZONS = (5, 10, 20, 40)
CAPITAL = 50000.0
FEE = 0.003
SPREAD = 0.002
COST = 2 * FEE + SPREAD
MIN_CASES = 12
MAX_POSITION_FRACTION = 0.30


def finite(value):
    try:
        value = float(value)
        return round(value, 6) if math.isfinite(value) else None
    except (ValueError, TypeError):
        return None


def prices(symbol):
    df = yf.download(
        symbol + ".SN",
        period="10y",
        interval="1d",
        auto_adjust=True,
        progress=False,
        threads=False
    )

    if df is None or df.empty:
        raise ValueError("Sin historial")

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    close = pd.to_numeric(df["Close"], errors="coerce")

    volume = (
        pd.to_numeric(df["Volume"], errors="coerce")
        if "Volume" in df
        else pd.Series(index=close.index, dtype=float)
    )

    out = pd.DataFrame({
        "close": close,
        "volume": volume
    })

    out = out.replace(
        [np.inf, -np.inf], np.nan
    ).dropna(subset=["close"])

    out = out[out.close > 0]
    out = out[
        ~out.index.duplicated(keep="last")
    ].sort_index()

    if len(out) < 400:
        raise ValueError("Menos de 400 sesiones")

    return out


def signals(df):
    c = df.close

    ma20 = c.rolling(20).mean()
    ma60 = c.rolling(60).mean()

    bullish = (c > ma20) & (ma20 > ma60)

    entry = bullish & (
        ~bullish.shift(1).fillna(False).astype(bool)
    )

    return bullish.fillna(False), entry.fillna(False)


def evaluate(df, entry, h):
    start = max(100, int(len(df) * 0.60))
    last_exit = start - 1

    returns = []
    benchmark = []

    c = df.close.to_numpy()
    e = entry.to_numpy()

    for i in range(start, len(df) - h - 1):
        if not e[i] or i <= last_exit:
            continue

        buy = c[i + 1]
        sell = c[i + 1 + h]

        gross = (
            sell * (1 - SPREAD / 2) * (1 - FEE)
        ) / (
            buy * (1 + SPREAD / 2) * (1 + FEE)
        ) - 1

        returns.append(float(gross))
        benchmark.append(float(sell / buy - 1))

        last_exit = i + 1 + h

    n = len(returns)

    if not n:
        return {
            "samples": 0,
            "hit_rate": None,
            "median_return": None,
            "mean_return": None,
            "worst_return": None,
            "benchmark_return": None,
            "eligible": False
        }

    arr = np.asarray(returns)

    return {
        "samples": n,
        "hit_rate": (
            finite(np.mean(arr > 0))
            if n >= MIN_CASES else None
        ),
        "median_return": finite(np.median(arr)),
        "mean_return": finite(np.mean(arr)),
        "worst_return": finite(np.min(arr)),
        "benchmark_return": finite(np.mean(benchmark)),
        "eligible": bool(
            n >= MIN_CASES
            and np.mean(arr) > 0.012
            and np.mean(arr > 0) >= 0.58
            and np.min(arr) > -0.20
        )
    }


def analyze(symbol, df):
    bull, entry = signals(df)

    tests = {
        str(h): evaluate(df, entry, h)
        for h in HORIZONS
    }

    viable = [
        h for h in HORIZONS
        if tests[str(h)]["eligible"]
    ]

    selected = (
        max(
            viable,
            key=lambda h: tests[str(h)]["mean_return"]
        )
        if viable else None
    )

    recent = bool(entry.iloc[-1])
    candidate = bool(recent and selected is not None)

    reasons = []

    if not recent:
        reasons.append(
            "No hay cruce alcista nuevo en el último cierre"
        )

    if selected is None:
        reasons.append(
            "Ningún horizonte supera los filtros históricos"
        )

    if candidate:
        reasons.append(
            "Señal validada; posible compra virtual "
            "en la siguiente sesión disponible"
        )

    latest = df.index[-1].strftime("%Y-%m-%d")

    return {
        "symbol": symbol,
        "status": "ok",
        "date": latest,
        "close": finite(df.close.iloc[-1]),
        "signal": (
            "Candidato virtual (próxima sesión)"
            if candidate
            else (
                "Tendencia alcista; observar"
                if bool(bull.iloc[-1])
                else "Esperar / sin entrada"
            )
        ),
        "samples": tests["20"]["samples"],
        "hit_rate": tests["20"]["hit_rate"],
        "horizon_sessions": 20,
        "median_return": tests["20"]["median_return"],
        "horizons": tests,
        "selected_horizon": selected,
        "entry_candidate": candidate,
        "entry_reason": "; ".join(reasons),
        "data_ticker": symbol + ".SN",
        "note": (
            "Datos ajustados de Yahoo; ejecución virtual "
            "aproximada al cierre de la sesión siguiente."
        )
    }


def read_portfolio():
    path = DATA / "portfolio.json"

    if path.exists():
        value = json.loads(
            path.read_text(encoding="utf-8")
        )

        if (
            value.get("mode") != "virtual"
            or not isinstance(
                value.get("cash"), (float, int)
            )
            or not isinstance(
                value.get("positions"), list
            )
            or not isinstance(
                value.get("trades"), list
            )
        ):
            raise ValueError(
                "Cartera existente inválida: "
                "se detiene para no sobrescribirla"
            )

        return value

    return {
        "mode": "virtual",
        "initial_capital_clp": CAPITAL,
        "cash": CAPITAL,
        "positions": [],
        "trades": [],
        "last_processed_date": None
    }


def session_count(df, start, end):
    dates = pd.to_datetime(df.index).normalize()

    return int((
        (dates > pd.Timestamp(start))
        & (dates <= pd.Timestamp(end))
    ).sum())


def simulate(portfolio, actions, histories):
    valid = {
        a["symbol"]: a
        for a in actions
        if a["status"] == "ok"
    }

    dates = [a["date"] for a in valid.values()]

    if not dates:
        portfolio["diagnostics"] = [
            "No hay cotizaciones disponibles; "
            "cartera conservada"
        ]
        return portfolio

    current = max(dates)
    diagnostics = []

    already_processed = (
        portfolio.get("last_processed_date") == current
    )

    if already_processed:
        diagnostics.append(
            "Sesión ya procesada; no se repiten operaciones"
        )

    for pos in list(portfolio["positions"]):
        symbol = pos.get("symbol")
        a = valid.get(symbol)

        if not a:
            diagnostics.append(
                f"{symbol}: cotización no disponible; "
                "valoración anterior conservada"
            )
            continue

        price_date = a["date"]

        if price_date < str(
            pos.get(
                "last_mark_date",
                pos.get("entry_date", price_date)
            )
        ):
            continue

        pos["last_price"] = a["close"]
        pos["last_mark_date"] = price_date

        if symbol in histories and pos.get("entry_date"):
            pos["elapsed_sessions"] = session_count(
                histories[symbol],
                pos["entry_date"],
                price_date
            )

        if (
            not already_processed
            and price_date == current
            and int(pos.get("elapsed_sessions", 0))
                >= int(pos.get("horizon_sessions", 20))
        ):
            gross = (
                float(pos["shares"])
                * float(a["close"])
            )

            net = gross * (
                1 - SPREAD / 2
            ) * (1 - FEE)

            portfolio["cash"] += net

            portfolio["trades"].append({
                "date": current,
                "symbol": symbol,
                "side": "SELL",
                "shares": pos["shares"],
                "price": a["close"],
                "cash_change": finite(net),
                "note": (
                    "Salida virtual por horizonte; "
                    "cierre disponible"
                )
            })

            portfolio["positions"].remove(pos)

            diagnostics.append(
                f"{symbol}: venta virtual por horizonte"
            )

    pending = portfolio.get("pending_entry")

    if (
        not already_processed
        and not portfolio["positions"]
        and isinstance(pending, dict)
    ):
        symbol = pending.get("symbol")
        a = valid.get(symbol)
        signal_date = pending.get("signal_date", "")

        if (
            a
            and a["date"] > signal_date
            and a["date"] == current
        ):
            price = float(a["close"]) * (
                1 + SPREAD / 2
            )

            spend_limit = (
                float(portfolio["cash"])
                * MAX_POSITION_FRACTION
            )

            shares = int(
                spend_limit / (price * (1 + FEE))
            )

            if shares >= 1:
                spend = shares * price * (1 + FEE)

                portfolio["cash"] -= spend

                portfolio["positions"].append({
                    "symbol": symbol,
                    "shares": shares,
                    "entry_price": finite(price),
                    "last_price": a["close"],
                    "entry_date": current,
                    "last_mark_date": current,
                    "elapsed_sessions": 0,
                    "horizon_sessions": int(
                        pending["horizon_sessions"]
                    )
                })

                portfolio["trades"].append({
                    "date": current,
                    "symbol": symbol,
                    "side": "BUY",
                    "shares": shares,
                    "price": finite(price),
                    "cash_change": finite(-spend),
                    "note": (
                        "Compra virtual al cierre disponible "
                        "posterior a señal"
                    )
                })

                diagnostics.append(
                    f"{symbol}: compra virtual "
                    f"de {shares} acción(es)"
                )

            else:
                diagnostics.append(
                    f"{symbol}: sin compra; límite de "
                    "gasto insuficiente para una acción"
                )

            portfolio.pop("pending_entry", None)

        elif a and a["date"] == signal_date:
            diagnostics.append(
                f"{symbol}: señal pendiente "
                "de la siguiente sesión"
            )

        elif a is None:
            diagnostics.append(
                f"{symbol}: señal pendiente; "
                "sin cotización actual"
            )

    if (
        not already_processed
        and not portfolio["positions"]
        and not portfolio.get("pending_entry")
    ):
        candidates = [
            a for a in valid.values()
            if a["date"] == current
            and a.get("entry_candidate")
        ]

        candidates.sort(
            key=lambda a: a["horizons"][
                str(a["selected_horizon"])
            ]["mean_return"],
            reverse=True
        )

        for a in candidates:
            unit_cost = (
                float(a["close"])
                * (1 + SPREAD / 2)
                * (1 + FEE)
            )

            limit = (
                float(portfolio["cash"])
                * MAX_POSITION_FRACTION
            )

            if unit_cost > limit:
                diagnostics.append(
                    f"{a['symbol']}: señal descartada; "
                    "acción excede el 30 % del efectivo"
                )
                continue

            portfolio["pending_entry"] = {
                "symbol": a["symbol"],
                "signal_date": current,
                "horizon_sessions": a["selected_horizon"]
            }

            diagnostics.append(
                f"{a['symbol']}: señal registrada "
                "para próxima sesión"
            )

            break

        if not candidates:
            diagnostics.append(
                "Sin señales de entrada que cumplan "
                "todos los filtros"
            )

    if not already_processed:
        portfolio["last_processed_date"] = current

    portfolio["cash"] = round(
        float(portfolio["cash"]), 4
    )

    equity = portfolio["cash"] + sum(
        float(p["shares"]) * float(p["last_price"])
        for p in portfolio["positions"]
    )

    initial = float(
        portfolio.get("initial_capital_clp", CAPITAL)
    )

    portfolio["equity_clp"] = finite(equity)

    portfolio["return_pct"] = (
        finite(100 * (equity / initial - 1))
        if initial > 0 else None
    )

    portfolio["updated_at"] = (
        datetime.now(timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )
    )

    portfolio["diagnostics"] = diagnostics

    return portfolio


def main():
    actions = []
    histories = {}

    for symbol in SYMBOLS:
        try:
            df = prices(symbol)
            histories[symbol] = df

            action = analyze(symbol, df)

            print(
                symbol,
                "OK",
                action["date"],
                "|",
                action["entry_reason"]
            )

        except Exception as exc:
            action = {
                "symbol": symbol,
                "status": "unavailable",
                "reason": str(exc)[:180]
            }

            print(
                symbol,
                "UNAVAILABLE",
                str(exc)[:100]
            )

        actions.append(action)

    portfolio = simulate(
        read_portfolio(), actions, histories
    )

    payload = {
        "updated_at": (
            datetime.now(timezone.utc).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        ),
        "source": (
            "Yahoo Finance vía yfinance (no oficial)"
        ),
        "mode": "virtual",
        "initial_capital_clp": CAPITAL,
        "method": (
            "MA20/MA60, prueba cronológica 40%, "
            "horizontes 5/10/20/40 sesiones"
        ),
        "assumed_fee_per_side": FEE,
        "assumed_spread_roundtrip": SPREAD,
        "disclaimer": (
            "Simulación educativa; resultados "
            "exploratorios, no probabilidades predictivas."
        ),
        "actions": actions
    }

    (DATA / "market.json").write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            allow_nan=False
        ) + "\n",
        encoding="utf-8"
    )

    (DATA / "portfolio.json").write_text(
        json.dumps(
            portfolio,
            ensure_ascii=False,
            indent=2,
            allow_nan=False
        ) + "\n",
        encoding="utf-8"
    )

    print(
        "Disponibles:",
        sum(
            a["status"] == "ok"
            for a in actions
        ),
        "| Operaciones acumuladas:",
        len(portfolio["trades"])
    )

    print(
        "Diagnóstico:",
        " | ".join(
            portfolio.get("diagnostics", [])
        )
    )


if __name__ == "__main__":
    main()
