#!/usr/bin/env python3
"""BolsaChile AI V1.2. Simulador diario, nunca envía órdenes reales."""
import json, os, math
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import yfinance as yf

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'; DATA.mkdir(exist_ok=True)
SYMBOLS=['SQM-B','FALABELLA','COPEC','CHILE','BSANTANDER','CENCOSUD','ENELCHILE','CMPC','CAP','ANDINA-B']
HORIZONS=(5,10,20,40)
CAPITAL=50000.0
# Supuestos configurables, NO tarifas reales de una corredora.
FEE=0.003; SPREAD=0.002; COST=2*FEE+SPREAD
MIN_CASES=12
MAX_POSITION_FRACTION=0.30

def finite(x):
    try:
        x=float(x)
        return round(x,6) if math.isfinite(x) else None
    except (TypeError,ValueError):return None

def prices(symbol):
    df=yf.download(symbol+'.SN',period='10y',interval='1d',auto_adjust=True,progress=False,threads=False)
    if df is None or df.empty: raise ValueError('Sin historial')
    if isinstance(df.columns,pd.MultiIndex):df.columns=df.columns.get_level_values(0)
    close=pd.to_numeric(df['Close'],errors='coerce')
    volume=pd.to_numeric(df['Volume'],errors='coerce') if 'Volume' in df else pd.Series(index=close.index,dtype=float)
    out=pd.DataFrame({'close':close,'volume':volume}).replace([np.inf,-np.inf],np.nan).dropna(subset=['close'])
    out=out[out.close>0];out=out[~out.index.duplicated(keep='last')].sort_index()
    if len(out)<400:raise ValueError('Menos de 400 sesiones')
    return out

def signals(df):
    c=df.close
    ma20=c.rolling(20).mean();ma60=c.rolling(60).mean()
    # Solo información disponible al cierre de cada sesión.
    bullish=(c>ma20)&(ma20>ma60)
    entry=bullish & (~bullish.shift(1).fillna(False))
    return bullish.fillna(False),entry.fillna(False)

def evaluate(df,entry,h):
    # Tramo de prueba final 40%; se evita reutilizar señales solapadas.
    start=max(100,int(len(df)*0.60)); last_exit=start-1; returns=[]; benchmark=[]
    c=df.close.to_numpy();e=entry.to_numpy()
    for i in range(start,len(df)-h-1):
        if not e[i] or i<=last_exit:continue
        # Señal conocida al cierre i, compra en cierre i+1 (aproximación).
        buy=c[i+1];sell=c[i+1+h]
        r=sell/buy-1-COST
        returns.append(float(r));benchmark.append(float(c[i+1+h]/c[i+1]-1))
        last_exit=i+1+h
    n=len(returns)
    if not n:return {'samples':0,'hit_rate':None,'median_return':None,'mean_return':None,'worst_return':None,'benchmark_return':None,'eligible':False}
    arr=np.asarray(returns)
    return {'samples':n,'hit_rate':finite(np.mean(arr>0)) if n>=MIN_CASES else None,
            'median_return':finite(np.median(arr)),'mean_return':finite(np.mean(arr)),
            'worst_return':finite(np.min(arr)),'benchmark_return':finite(np.mean(benchmark)),
            'eligible':bool(n>=MIN_CASES and np.mean(arr)>0.012 and np.mean(arr>0)>=0.58 and np.min(arr)>-0.20)}

def analyze(symbol):
    df=prices(symbol);bull,entry=signals(df);latest=df.index[-1].strftime('%Y-%m-%d')
    tests={str(h):evaluate(df,entry,h) for h in HORIZONS}
    # Se exige señal de entrada reciente; no se compra solo por tendencia.
    recent=bool(entry.iloc[-2:].any())
    viable=[h for h in HORIZONS if tests[str(h)]['eligible']]
    selected=sorted(viable,key=lambda h:(tests[str(h)]['mean_return'] or -999),reverse=True)[0] if viable else None
    eligible=bool(recent and selected is not None)
    return {'symbol':symbol,'status':'ok','date':latest,'close':finite(df.close.iloc[-1]),
            'signal':'Candidato virtual (pendiente de cartera)' if eligible else ('Tendencia alcista; observar' if bool(bull.iloc[-1]) else 'Esperar / sin entrada'),
            'samples':tests['20']['samples'],'hit_rate':tests['20']['hit_rate'],
            'horizon_sessions':20,'median_return':tests['20']['median_return'],
            'horizons':tests,'selected_horizon':selected,'entry_candidate':eligible,
            'data_ticker':symbol+'.SN','note':'Cierres ajustados según Yahoo; ejecución hipotética al cierre siguiente, sin datos intradía.'}

def read_portfolio():
    p=DATA/'portfolio.json'
    if p.exists():
        try:
            v=json.loads(p.read_text(encoding='utf8'))
            if v.get('mode')=='virtual' and isinstance(v.get('cash'),(float,int)) and isinstance(v.get('positions'),list) and isinstance(v.get('trades'),list):return v
        except (ValueError,KeyError):pass
    return {'mode':'virtual','initial_capital_clp':CAPITAL,'cash':CAPITAL,'positions':[],'trades':[],'last_processed_date':None}

def simulate(portfolio,actions):
    # Solo una decisión por fecha de cierre. Persistencia en GitHub, no en el navegador.
    valid={a['symbol']:a for a in actions if a['status']=='ok'}
    dates=[a['date'] for a in valid.values()]
    if not dates:return portfolio
    current=max(dates)
    if portfolio.get('last_processed_date')==current:return portfolio
    # No procesar cotizaciones atrasadas como si fueran del día.
    for pos in list(portfolio['positions']):
        a=valid.get(pos['symbol'])
        if not a or a['date']!=current:continue
        # Solo cerrar si venció el horizonte por sesiones observadas (contado en cada actualización válida).
        if pos.get('last_mark_date')!=current:
            pos['elapsed_sessions']=int(pos.get('elapsed_sessions',0))+1
            pos['last_mark_date']=current
        pos['last_price']=a['close']
        if pos['elapsed_sessions']>=pos['horizon_sessions']:
            gross=pos['shares']*a['close'];net=gross*(1-FEE-SPREAD/2)
            portfolio['cash']+=net
            portfolio['trades'].append({'date':current,'symbol':pos['symbol'],'side':'SELL','shares':pos['shares'],'price':a['close'],'cash_change':finite(net),'note':'Salida por horizonte virtual'})
            portfolio['positions'].remove(pos)
    # Restricción: como máximo una posición; capital pequeño, sin fracciones.
    if not portfolio['positions']:
        candidates=[a for a in valid.values() if a['date']==current and a.get('entry_candidate')]
        candidates.sort(key=lambda a:a['horizons'][str(a['selected_horizon'])]['mean_return'],reverse=True)
        for a in candidates:
            price=a['close']*(1+SPREAD/2)
            max_spend=min(portfolio['cash']*MAX_POSITION_FRACTION,portfolio['cash'])
            shares=int(max_spend/(price*(1+FEE)))
            if shares<1:continue
            spend=shares*price*(1+FEE)
            portfolio['cash']-=spend
            portfolio['positions'].append({'symbol':a['symbol'],'shares':shares,'entry_price':finite(price),'last_price':a['close'],'entry_date':current,'last_mark_date':current,'elapsed_sessions':0,'horizon_sessions':a['selected_horizon']})
            portfolio['trades'].append({'date':current,'symbol':a['symbol'],'side':'BUY','shares':shares,'price':finite(price),'cash_change':finite(-spend),'note':'Entrada virtual, señal validada exploratoriamente'})
            break
    portfolio['last_processed_date']=current
    portfolio['cash']=round(portfolio['cash'],4)
    value=portfolio['cash']+sum(p['shares']*p['last_price'] for p in portfolio['positions'])
    portfolio['equity_clp']=finite(value)
    portfolio['return_pct']=finite(100*(value/CAPITAL-1))
    portfolio['updated_at']=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    return portfolio

def main():
    actions=[]
    for symbol in SYMBOLS:
        try:
            a=analyze(symbol);print(symbol,'OK',a['date'])
        except Exception as exc:
            a={'symbol':symbol,'status':'unavailable','reason':str(exc)[:180]};print(symbol,'UNAVAILABLE',str(exc)[:100])
        actions.append(a)
    payload={'updated_at':datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
             'source':'Yahoo Finance vía yfinance (no oficial)','mode':'virtual','initial_capital_clp':CAPITAL,
             'method':'MA20/MA60, prueba cronológica 40%, 5/10/20/40 sesiones; costos supuestos',
             'assumed_fee_per_side':FEE,'assumed_spread_roundtrip':SPREAD,
             'disclaimer':'Resultados exploratorios, no probabilidades predictivas ni órdenes reales. Datos sin verificación secundaria.',
             'actions':actions}
    (DATA/'market.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')
    portfolio=simulate(read_portfolio(),actions)
    (DATA/'portfolio.json').write_text(json.dumps(portfolio,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')
    print('Disponibles:',sum(a['status']=='ok' for a in actions),'| Operaciones acumuladas:',len(portfolio['trades']))
if __name__=='__main__':main()
