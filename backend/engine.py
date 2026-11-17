"""Paper-only trading engine. There is deliberately no exchange order API."""
import json, os, sqlite3, threading, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
import httpx

DB_PATH = os.environ.get('TRADER_DB', str(Path(__file__).parent / 'trader.db'))
ALLOWED_SYMBOLS = ('BTCUSDT', 'ETHUSDT', 'SOLUSDT')
DB_LOCK = threading.RLock()
DEFAULTS = {'symbol':'BTCUSDT','enabled':False,'ai_enabled':False,'allocation_pct':10.0,'risk_pct':1.0,'daily_loss_pct':3.0,'max_drawdown_pct':10.0,'max_trades_day':10,'cooldown_minutes':15,'stop_pct':2.0,'take_pct':4.0,'fee_pct':0.1}


def connect():
    db = sqlite3.connect(DB_PATH, timeout=20, check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA busy_timeout=20000')
    return db


def now(): return datetime.now(timezone.utc).isoformat()
def today(): return datetime.now(timezone.utc).strftime('%Y-%m-%d')


def init_db():
    with DB_LOCK, connect() as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.executescript('''
        CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY CHECK(id=1), data TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS account (id INTEGER PRIMARY KEY CHECK(id=1), cash REAL NOT NULL, qty REAL NOT NULL, entry REAL NOT NULL, high_water REAL NOT NULL, realized REAL NOT NULL, last_candle INTEGER NOT NULL DEFAULT 0, last_trade_at TEXT, halted INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS trades (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, symbol TEXT NOT NULL, side TEXT NOT NULL, price REAL NOT NULL, qty REAL NOT NULL, notional REAL NOT NULL, fee REAL NOT NULL, pnl REAL, reason TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS decisions (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, symbol TEXT NOT NULL, candle_ts INTEGER, price REAL, signal TEXT NOT NULL, reason TEXT NOT NULL, ai_reason TEXT);
        CREATE TABLE IF NOT EXISTS snapshots (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, equity REAL NOT NULL, price REAL NOT NULL);
        ''')
        db.execute('INSERT OR IGNORE INTO settings VALUES(1,?)', (json.dumps(DEFAULTS),))
        db.execute('INSERT OR IGNORE INTO account (id,cash,qty,entry,high_water,realized) VALUES (1,10000,0,0,10000,0)')


def get_settings(db): return json.loads(db.execute('SELECT data FROM settings WHERE id=1').fetchone()['data'])
def get_account(db): return dict(db.execute('SELECT * FROM account WHERE id=1').fetchone())

def candles(symbol='BTCUSDT', limit=120):
    if symbol not in ALLOWED_SYMBOLS: raise ValueError('Par não autorizado')
    url='https://data-api.binance.vision/api/v3/klines'
    with httpx.Client(timeout=12, headers={'User-Agent':'TraderIAPro-Paper/1.0'}) as client:
        resp=client.get(url, params={'symbol':symbol,'interval':'15m','limit':limit})
        resp.raise_for_status()
        data=resp.json()
    if not isinstance(data,list) or len(data)<55: raise ValueError('Candles insuficientes')
    current_ms=int(time.time()*1000)
    # Never use an open/unclosed candle.
    valid=[{'t':int(c[0]),'close':float(c[4]),'high':float(c[2]),'low':float(c[3]),'volume':float(c[5])} for c in data if int(c[6])<current_ms]
    if len(valid)<52 or valid[-1]['close']<=0: raise ValueError('Dados inválidos ou insuficientes')
    if current_ms-valid[-1]['t']>45*60*1000: raise ValueError('Dados de mercado desatualizados')
    return valid


def rsi(values, period=14):
    if len(values)<period+1:return 50.0
    changes=[values[i]-values[i-1] for i in range(len(values)-period,len(values))]
    gain=sum(max(x,0) for x in changes)/period
    loss=sum(max(-x,0) for x in changes)/period
    if loss==0:return 100.0 if gain else 50.0
    return 100-100/(1+gain/loss)


def signal(rows, holding=False, entry=0, stop_pct=2, take_pct=4):
    close=[x['close'] for x in rows]
    price=close[-1]
    sma20=sum(close[-20:])/20
    sma50=sum(close[-50:])/50
    prev20=sum(close[-21:-1])/20
    prev50=sum(close[-51:-1])/50
    strength=rsi(close)
    details={'sma20':round(sma20,4),'sma50':round(sma50,4),'rsi':round(strength,2)}
    if holding:
        if price <= entry*(1-stop_pct/100): return 'SELL','Stop-loss',details
        if price >= entry*(1+take_pct/100): return 'SELL','Take-profit',details
        if sma20<sma50 and prev20>=prev50: return 'SELL','Cruzamento de baixa',details
        return 'HOLD','Posição mantida',details
    if prev20<=prev50 and sma20>sma50 and 45<=strength<=70:
        return 'BUY','Cruzamento de alta SMA20/SMA50 e RSI aprovado',details
    return 'HOLD','Sem entrada: estratégia não confirmou cruzamento',details


def ai_veto(symbol, price, indicators, strategy_reason):
    """AI can only approve or veto a strategy BUY. Fail closed if unavailable."""
    key=os.getenv('OPENAI_API_KEY','')
    if not key:return False,'OPENAI_API_KEY ausente: entrada bloqueada'
    try:
        from openai import OpenAI
        client=OpenAI(api_key=key, timeout=12, max_retries=0)
        prompt={'symbol':symbol,'price':price,'indicators':indicators,'strategy_reason':strategy_reason}
        result=client.responses.create(model=os.getenv('OPENAI_MODEL','gpt-4.1-mini'), instructions='Você é um FILTRO CONSERVADOR para PAPER TRADING, não um executor. Use apenas os dados fornecidos, sem inventar notícias. Responda somente JSON válido no formato {"approve":boolean,"reason":string}. Se dados insuficientes ou dúvida, approve=false.', input=json.dumps(prompt), max_output_tokens=150)
        data=json.loads(result.output_text)
        return (data.get('approve') is True, str(data.get('reason',''))[:250])
    except Exception as exc:
        return False,'Falha na avaliação da IA; ordem bloqueada: '+type(exc).__name__


def state():
    with DB_LOCK, connect() as db:
        s=get_settings(db); a=get_account(db)
        ds=[dict(row) for row in db.execute('SELECT * FROM decisions ORDER BY id DESC LIMIT 25')]
        trades=[dict(row) for row in db.execute('SELECT * FROM trades ORDER BY id DESC LIMIT 50')]
        curve=[dict(row) for row in db.execute('SELECT * FROM snapshots ORDER BY id DESC LIMIT 100')][::-1]
        last= db.execute('SELECT price FROM snapshots ORDER BY id DESC LIMIT 1').fetchone()
        price=last['price'] if last else None
        equity=a['cash']+a['qty']*price if price else a['cash']
        return {'settings':s,'account':a,'equity':round(equity,2),'price':price,'decisions':ds,'trades':trades,'curve':curve,'mode':'PAPER_ONLY','ai_configured':bool(os.getenv('OPENAI_API_KEY'))}


def update_settings(patch):
    allowed={'symbol','ai_enabled','allocation_pct','risk_pct','daily_loss_pct','max_drawdown_pct','max_trades_day','cooldown_minutes','stop_pct','take_pct','fee_pct'}
    if any(k not in allowed for k in patch): raise ValueError('Configuração não permitida')
    with DB_LOCK, connect() as db:
        s=get_settings(db); a=get_account(db)
        if 'symbol' in patch and patch['symbol']!=s['symbol'] and a['qty']>0: raise ValueError('Feche a posição virtual antes de mudar o par')
        for k,v in patch.items():
            if k=='symbol':
                if v not in ALLOWED_SYMBOLS:raise ValueError('Par inválido')
            elif k=='ai_enabled':
                if not isinstance(v,bool):raise ValueError('Valor inválido')
            elif k=='max_trades_day':
                if type(v)!=int or not 1<=v<=20:raise ValueError('Limite inválido')
            else:
                if type(v) not in (int,float) or not 0<float(v)<=({'allocation_pct':20,'risk_pct':2,'daily_loss_pct':5,'max_drawdown_pct':20,'cooldown_minutes':240,'stop_pct':5,'take_pct':15,'fee_pct':1}[k]):raise ValueError('Valor fora dos limites')
            s[k]=v
        db.execute('UPDATE settings SET data=? WHERE id=1',(json.dumps(s),))
        return s


def set_enabled(value):
    with DB_LOCK, connect() as db:
        a=get_account(db)
        if value and a['halted']:raise ValueError('Circuit breaker ativo. Reinicie a simulação para continuar.')
        s=get_settings(db);s['enabled']=bool(value)
        db.execute('UPDATE settings SET data=? WHERE id=1',(json.dumps(s),))


def step(rows=None):
    # Public candles are fetched before DB lock, so status remains available while network waits.
    with DB_LOCK, connect() as db:s=get_settings(db)
    rows = rows if rows is not None else candles(s['symbol'])
    candle=rows[-1]['t']; price=rows[-1]['close']
    with DB_LOCK, connect() as db:
        db.execute('BEGIN IMMEDIATE')
        s=get_settings(db);a=get_account(db)
        # Ensure symbol unchanged mid-fetch
        if candle<=a['last_candle']:
            db.rollback();return {'status':'skipped','reason':'Candle já processado'}
        if not s['enabled']:
            db.rollback();return {'status':'skipped','reason':'Robô pausado'}
        action,reason,ind=signal(rows,a['qty']>0,a['entry'],s['stop_pct'],s['take_pct'])
        equity=a['cash']+a['qty']*price
        high=max(a['high_water'],equity)
        day= today()
        daily_pnl=db.execute('SELECT COALESCE(SUM(pnl),0) FROM trades WHERE ts >= ? AND side="SELL"',(day,)).fetchone()[0]
        count=db.execute('SELECT COUNT(*) FROM trades WHERE ts >= ?',(day,)).fetchone()[0]
        ai_reason=None
        if daily_pnl <= -(10000*s['daily_loss_pct']/100) or equity <= high*(1-s['max_drawdown_pct']/100):
            a['halted']=1
            if a['qty']>0:action='SELL'; reason='Circuit breaker: liquidar posição virtual'
            else:action='HOLD';reason='Circuit breaker: negociação bloqueada'
        if action=='BUY':
            if count>=s['max_trades_day'] or a['halted']:
                action='HOLD';reason='Limite de operações atingido'
            elif a['last_trade_at'] and (datetime.now(timezone.utc)-datetime.fromisoformat(a['last_trade_at'])).total_seconds() < s['cooldown_minutes']*60:
                action='HOLD';reason='Cooldown entre ordens'
            elif s['ai_enabled']:
                ok,ai_reason=ai_veto(s['symbol'],price,ind,reason)
                if not ok:action='HOLD';reason='Entrada vetada pela IA'
        fee_rate=s['fee_pct']/100
        if action=='BUY':
            # Conservative position sizing: min(allocation cap, loss-at-stop risk budget).
            budget=min(a['cash']*s['allocation_pct']/100, equity*s['risk_pct']/s['stop_pct'])
            budget=min(budget,a['cash']/(1+fee_rate))
            qty=budget/price
            if budget<10:
                action='HOLD';reason='Ordem inferior a US$ 10'
            else:
                fee=budget*fee_rate;a['cash']-=budget+fee;a['qty']=qty;a['entry']=(budget+fee)/qty;a['last_trade_at']=now()
                db.execute('INSERT INTO trades(ts,symbol,side,price,qty,notional,fee,pnl,reason) VALUES (?,?,?,?,?,?,?,?,?)',(a['last_trade_at'],s['symbol'],'BUY',price,qty,budget,fee,None,reason))
        elif action=='SELL' and a['qty']>0:
            qty=a['qty'];notional=qty*price;fee=notional*fee_rate
            pnl=(notional-fee)-(qty*a['entry']);a['cash']+=notional-fee;a['realized']+=pnl;a['qty']=0;a['entry']=0;a['last_trade_at']=now()
            db.execute('INSERT INTO trades(ts,symbol,side,price,qty,notional,fee,pnl,reason) VALUES (?,?,?,?,?,?,?,?,?)',(a['last_trade_at'],s['symbol'],'SELL',price,qty,notional,fee,pnl,reason))
        a['last_candle']=candle;a['high_water']=high
        db.execute('UPDATE account SET cash=?,qty=?,entry=?,high_water=?,realized=?,last_candle=?,last_trade_at=?,halted=? WHERE id=1',(a['cash'],a['qty'],a['entry'],a['high_water'],a['realized'],candle,a['last_trade_at'],a['halted']))
        db.execute('INSERT INTO decisions(ts,symbol,candle_ts,price,signal,reason,ai_reason) VALUES(?,?,?,?,?,?,?)',(now(),s['symbol'],candle,price,action,reason,ai_reason))
        db.execute('INSERT INTO snapshots(ts,equity,price) VALUES(?,?,?)',(now(),a['cash']+a['qty']*price,price))
        return {'status':'processed','signal':action,'reason':reason,'price':price,'indicators':ind,'ai_reason':ai_reason}


def reset():
    with DB_LOCK, connect() as db:
        s=get_settings(db)
        if s['enabled']:raise ValueError('Pause o robô antes de reiniciar')
        db.execute('DELETE FROM trades');db.execute('DELETE FROM decisions');db.execute('DELETE FROM snapshots')
        db.execute('UPDATE account SET cash=10000,qty=0,entry=0,high_water=10000,realized=0,last_candle=0,last_trade_at=NULL,halted=0 WHERE id=1')
