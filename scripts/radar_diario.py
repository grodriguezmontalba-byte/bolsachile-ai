            continue
        pos['last_price'] = a['close']
        pos['last_mark_date'] = price_date
        if symbol in histories and pos.get('entry_date'):
            pos['elapsed_sessions'] = session_count(histories[symbol], pos['entry_date'], price_date)
        if (not already_processed and price_date == current and
            int(pos.get('elapsed_sessions', 0)) >= int(pos.get('horizon_sessions', 20))):
            gross = float(pos['shares']) * float(a['close'])
            net = gross * (1 - SPREAD / 2) * (1 - FEE)
            portfolio['cash'] += net
            portfolio['trades'].append({'date': current, 'symbol': symbol, 'side': 'SELL',
                'shares': pos['shares'], 'price': a['close'], 'cash_change': finite(net),
                'note': 'Salida virtual por horizonte; cierre disponible'})
            portfolio['positions'].remove(pos)
            diagnostics.append(f'{symbol}: venta virtual por horizonte')

    # Las señales se almacenan y solo se ejecutan en una fecha posterior.
    pending = portfolio.get('pending_entry')
    if not already_processed and not portfolio['positions'] and isinstance(pending, dict):
        symbol = pending.get('symbol')
        a = valid.get(symbol)
        signal_date = pending.get('signal_date', '')
        if a and a['date'] > signal_date and a['date'] == current:
            price = float(a['close']) * (1 + SPREAD / 2)
            spend_limit = float(portfolio['cash']) * MAX_POSITION_FRACTION
            shares = int(spend_limit / (price * (1 + FEE)))
            if shares >= 1:
                spend = shares * price * (1 + FEE)
                portfolio['cash'] -= spend
                portfolio['positions'].append({
                    'symbol': symbol, 'shares': shares, 'entry_price': finite(price),
                    'last_price': a['close'], 'entry_date': current,
                    'last_mark_date': current, 'elapsed_sessions': 0,
                    'horizon_sessions': int(pending['horizon_sessions'])})
                portfolio['trades'].append({'date': current, 'symbol': symbol, 'side': 'BUY',
                    'shares': shares, 'price': finite(price), 'cash_change': finite(-spend),
                    'note': 'Compra virtual al cierre disponible posterior a señal'})
                diagnostics.append(f'{symbol}: compra virtual de {shares} acción(es)')
            else:
                diagnostics.append(f'{symbol}: sin compra; límite de gasto insuficiente para una acción')
            portfolio.pop('pending_entry', None)
        elif a and a['date'] == signal_date:
            diagnostics.append(f'{symbol}: señal pendiente de la siguiente sesión')
        elif a is None:
            diagnostics.append(f'{symbol}: señal pendiente; sin cotización actual')

    if not already_processed and not portfolio['positions'] and not portfolio.get('pending_entry'):
        candidates = [a for a in valid.values()
                      if a['date'] == current and a.get('entry_candidate')]
        candidates.sort(key=lambda a: a['horizons'][str(a['selected_horizon'])]['mean_return'],
                        reverse=True)
        for a in candidates:
            if float(a['close']) * (1 + SPREAD / 2) * (1 + FEE) > float(portfolio['cash']) * MAX_POSITION_FRACTION:
                diagnostics.append(f"{a['symbol']}: señal descartada; acción excede el 30 % del efectivo")
                continue
            portfolio['pending_entry'] = {'symbol': a['symbol'],
                'signal_date': current, 'horizon_sessions': a['selected_horizon']}
            diagnostics.append(f"{a['symbol']}: señal registrada para próxima sesión")
            break
        if not candidates:
            diagnostics.append('Sin señales de entrada que cumplan todos los filtros')

    if not already_processed:
        portfolio['last_processed_date'] = current
    portfolio['cash'] = round(float(portfolio['cash']), 4)
    equity = portfolio['cash'] + sum(float(p['shares']) * float(p['last_price'])
                                     for p in portfolio['positions'])
    initial = float(portfolio.get('initial_capital_clp', CAPITAL))
    portfolio['equity_clp'] = finite(equity)
    portfolio['return_pct'] = finite(100 * (equity / initial - 1)) if initial > 0 else None
    portfolio['updated_at'] = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    portfolio['diagnostics'] = diagnostics
    return portfolio


def main():
    actions, histories = [], {}
    for symbol in SYMBOLS:
        try:
            df = prices(symbol)
            histories[symbol] = df
            action = analyze(symbol, df)
            print(symbol, 'OK', action['date'], '|', action['entry_reason'])
        except Exception as exc:
            action = {'symbol': symbol, 'status': 'unavailable', 'reason': str(exc)[:180]}
            print(symbol, 'UNAVAILABLE', str(exc)[:100])
        actions.append(action)
    portfolio = simulate(read_portfolio(), actions, histories)
    payload = {'updated_at': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
        'source': 'Yahoo Finance vía yfinance (no oficial)', 'mode': 'virtual',
        'initial_capital_clp': CAPITAL,
        'method': 'MA20/MA60, prueba cronológica 40%, horizontes 5/10/20/40 sesiones',
        'assumed_fee_per_side': FEE, 'assumed_spread_roundtrip': SPREAD,
        'disclaimer': 'Simulación educativa; resultados exploratorios, no probabilidades predictivas.',
        'actions': actions}
    (DATA / 'market.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2,
        allow_nan=False) + '\n', encoding='utf-8')
    (DATA / 'portfolio.json').write_text(json.dumps(portfolio, ensure_ascii=False, indent=2,
        allow_nan=False) + '\n', encoding='utf-8')
    print('Disponibles:', sum(a['status'] == 'ok' for a in actions),
          '| Operaciones acumuladas:', len(portfolio['trades']))
    print('Diagnóstico:', ' | '.join(portfolio.get('diagnostics', [])))


if __name__ == '__main__':
    main()
