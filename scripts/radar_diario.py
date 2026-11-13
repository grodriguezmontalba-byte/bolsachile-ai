#!/usr/bin/env python3
"""BolsaChile AI: radar diario experimental, solo lectura, sin órdenes."""
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data' / 'market.json'
WATCH = {
    'SQM-B': ['SQM-B.SN'], 'FALABELLA': ['FALABELLA.SN'],
    'COPEC': ['COPEC.SN'], 'CHILE': ['CHILE.SN'],
    'BSANTANDER': ['BSANTANDER.SN'], 'CENCOSUD': ['CENCOSUD.SN'],
    'ENELCHILE': ['ENELCHILE.SN'], 'CMPC': ['CMPC.SN'],
    'CAP': ['CAP.SN'], 'ANDINA-B': ['ANDINA-B.SN'],
}
HORIZON = 20  # ~4 semanas, dentro del rango objetivo de 1-8 semanas
MIN_HISTORY = 180
MIN_TEST_SAMPLES = 10


def history(ticker):
    data = yf.download(ticker, period='5y', interval='1d', auto_adjust=True,
                       progress=False, threads=False)
    if data is None or data.empty:
        raise ValueError('Sin cotizaciones en la fuente')
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    if 'Close' not in data:
        raise ValueError('La fuente no entregó precios de cierre')
    close = pd.to_numeric(data['Close'], errors='coerce').dropna()
    close = close[(close > 0) & np.isfinite(close)]
    close = close[~close.index.duplicated(keep='last')].sort_index()
    if len(close) < MIN_HISTORY:
        raise ValueError(f'Historial insuficiente: {len(close)} sesiones')
    return close


def analyze(symbol, ticker):
    close = history(ticker)
    ma20 = close.rolling(20, min_periods=20).mean()
    ma60 = close.rolling(60, min_periods=60).mean()
    # Señal observable al cierre: tendencia positiva y cruce alcista reciente.
    bullish = (close > ma20) & (ma20 > ma60)
    crossed = (ma20 > ma60) & (ma20.shift(1) <= ma60.shift(1))
    entry = bullish & (crossed | ((~bullish.shift(1).fillna(False)) & bullish))
    # Reservamos cronológicamente el 70 % inicial para diseño y el 30 % final
    # para evaluación. El algoritmo de señal se fija de antemano.
    test_start = max(60, int(len(close) * 0.70))
    # Las operaciones evaluadas no se solapan: se elige la primera señal
    # posterior a la salida anterior, evitando contar períodos repetidos.
    candidates = np.flatnonzero(entry.to_numpy())
    selected = []
    next_allowed = test_start
    for i in candidates:
        if i >= next_allowed and i + HORIZON < len(close):
            selected.append(int(i))
            next_allowed = i + HORIZON + 1
    # Compra teórica al cierre de la señal; sin comisiones ni deslizamiento.
    # No se usa para ejecutar órdenes ni representa un backtest operable.
    returns = [(float(close.iloc[i + HORIZON]) / float(close.iloc[i]) - 1.0)
               for i in selected]
    samples = len(returns)
    hit_rate = sum(r > 0 for r in returns) / samples if samples >= MIN_TEST_SAMPLES else None
    last = float(close.iloc[-1])
    if bool(bullish.iloc[-1]):
        signal = 'Tendencia alcista; observar'
    elif last < float(ma60.iloc[-1]):
        signal = 'Tendencia débil; esperar'
    else:
        signal = 'Sin señal de entrada'
    return {
        'symbol': symbol, 'status': 'ok', 'date': close.index[-1].strftime('%Y-%m-%d'),
        'close': round(last, 4), 'signal': signal, 'samples': samples,
        'hit_rate': round(hit_rate, 4) if hit_rate is not None else None,
        'horizon_sessions': HORIZON,
        'median_return': round(float(np.median(returns)), 5) if returns else None,
        'data_ticker': ticker,
        'note': 'Datos ajustados según proveedor; resultados sin comisiones ni spread.'
    }


def main():
    actions = []
    for symbol, tickers in WATCH.items():
        errors = []
        for ticker in tickers:
            try:
                item = analyze(symbol, ticker)
                actions.append(item)
                print(f'{symbol}: OK ({item["samples"]} muestras)')
                break
            except Exception as exc:
                errors.append(f'{ticker}: {type(exc).__name__}: {str(exc)[:180]}')
        else:
            actions.append({'symbol': symbol, 'status': 'unavailable',
                            'reason': '; '.join(errors)[:300]})
            print(f'{symbol}: NO DISPONIBLE')
    payload = {
        'updated_at': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
        'source': 'Yahoo Finance vía yfinance (fuente no oficial)',
        'mode': 'virtual', 'initial_capital_clp': 50000,
        'method': 'Tendencia MA20/MA60; evaluación cronológica exploratoria, 20 sesiones',
        'disclaimer': 'No son probabilidades predictivas. Sin ejecución real, comisiones ni spread.',
        'actions': actions,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(f'Escrito {OUT} | disponibles: {sum(a["status"] == "ok" for a in actions)}/10')


if __name__ == '__main__':
    main()
