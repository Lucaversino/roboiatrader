import asyncio, os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
import secrets
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import engine

ROOT=Path(__file__).parent
worker=None
async def loop():
    while True:
        try:
            if engine.state()['settings']['enabled']:
                await asyncio.to_thread(engine.step)
        except Exception as exc:
            # Explicitly log failures; never replace with invented market data.
            print('DATA/ENGINE ERROR:',repr(exc),flush=True)
        await asyncio.sleep(60)

@asynccontextmanager
async def lifespan(app):
    if os.getenv("DEPLOYMENT_MODE") == "production" and not os.getenv("BACKEND_TOKEN"):
        raise RuntimeError("BACKEND_TOKEN obrigatório em produção")
    engine.init_db()
    # Fail-safe on restart: operator must explicitly re-enable the engine.
    engine.set_enabled(False)
    global worker
    worker=asyncio.create_task(loop())
    yield
    worker.cancel()
    try: await worker
    except asyncio.CancelledError: pass

app=FastAPI(title='Trader IA PRO / Paper Only', lifespan=lifespan)
@app.middleware('http')
async def protect(request: Request, call_next):
    if request.url.path == '/health':
        return await call_next(request)
    expected=os.getenv('BACKEND_TOKEN','')
    if os.getenv('DEPLOYMENT_MODE') == 'production' and not expected:
        return JSONResponse({'detail':'Backend sem token configurado'},status_code=503)
    if expected and not secrets.compare_digest(request.headers.get('authorization',''), 'Bearer '+expected):
        return JSONResponse({'detail':'Acesso negado'},status_code=401)
    return await call_next(request)

app.mount('/static',StaticFiles(directory=ROOT/'static'),name='static')
class Toggle(BaseModel):
    enabled:bool
class Patch(BaseModel):
    symbol:str|None=None
    ai_enabled:bool|None=None
    allocation_pct:float|None=None
    risk_pct:float|None=None
    daily_loss_pct:float|None=None
    max_drawdown_pct:float|None=None
    max_trades_day:int|None=None
    cooldown_minutes:float|None=None
    stop_pct:float|None=None
    take_pct:float|None=None
    fee_pct:float|None=None

@app.get('/')
def home():return FileResponse(ROOT/'static'/'index.html')
@app.get('/api/status')
def status():return engine.state()
@app.post('/api/engine')
def toggle(body:Toggle):
    try:engine.set_enabled(body.enabled);return {'ok':True,'enabled':body.enabled}
    except ValueError as e:raise HTTPException(400,str(e))
@app.post('/api/settings')
def settings(body:Patch):
    try:return engine.update_settings(body.model_dump(exclude_none=True))
    except ValueError as e:raise HTTPException(400,str(e))
@app.post('/api/step')
async def step():
    try:return await asyncio.to_thread(engine.step)
    except Exception as e:raise HTTPException(503,f'Dados indisponíveis: {type(e).__name__}: {e}')
@app.post('/api/reset')
def reset():
    try:engine.reset();return {'ok':True}
    except ValueError as e:raise HTTPException(400,str(e))
@app.get('/api/candles')
async def market():
    try:
        symbol=engine.state()['settings']['symbol']
        return {'symbol':symbol,'candles':await asyncio.to_thread(engine.candles,symbol,100)}
    except Exception as e:raise HTTPException(503,f'Mercado indisponível: {e}')
@app.get('/health')
def health():return {'ok':True,'order_execution':'DISABLED','mode':'paper'}
