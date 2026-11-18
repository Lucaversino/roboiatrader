// Proxy com fallback: tenta Binance Global primeiro, depois CoinGecko se bloqueado (erro 451)
export default async function handler(req, res) {
 const { symbol = 'BTCUSDT', interval = '15m', limit = '300' } = req.query;

 // Mapeamento de símbolos para CoinGecko IDs
 const coingeckoMap = {
 'BTCUSDT': 'bitcoin',
 'ETHUSDT': 'ethereum',
 'SOLUSDT': 'solana',
 'BNBUSDT': 'binancecoin',
 'ADAUSDT': 'cardano',
 'XRPUSDT': 'ripple'
 };

 // Mapeamento de intervalos para dias (CoinGecko usa dias, não candles)
 const intervalToDays = {
 '1m': 1, '3m': 1, '5m': 1, '15m': 1, '30m': 2,
 '1h': 3, '4h': 7, '1d': 30, '1w': 90
 };

 const headers = {
 'User-Agent': 'TraderIAPro/1.0',
 'Accept': 'application/json',
 };

 if (process.env.BINANCE_API_KEY && process.env.BINANCE_API_KEY.trim() !== '') {
 headers['X-MBX-APIKEY'] = process.env.BINANCE_API_KEY.trim();
 }

 // Tenta Binance Global (data-api.binance.vision é menos restrito que api.binance.com)
 const binanceEndpoints = [
 `https://data-api.binance.vision/api/v3/klines?symbol=${encodeURIComponent(symbol)}&interval=${encodeURIComponent(interval)}&limit=${Math.min(parseInt(limit) || 300, 1000)}`,
 `https://api.binance.com/api/v3/klines?symbol=${encodeURIComponent(symbol)}&interval=${encodeURIComponent(interval)}&limit=${Math.min(parseInt(limit) || 300, 1000)}`
 ];

 for (const url of binanceEndpoints) {
 try {
 const response = await fetch(url, { headers, method: 'GET' });

 if (!response.ok) {
 const status = response.status;
 // Se for 451 (bloqueio geográfico) ou 403, tenta próximo endpoint
 if (status === 451 || status === 403) {
 console.warn(`Binance blocked (${status}) on ${url}, trying next...`);
 continue;
 }
 const errorText = await response.text().catch(() => '');
 console.error(`Binance API error: ${status} - ${errorText}`);
 continue;
 }

 const data = await response.json();

 if (!Array.isArray(data) || data.length === 0) {
 console.warn('Resposta vazia da Binance, tentando próximo...');
 continue;
 }

 const candles = [];
 const volumes = [];

 for (const d of data) {
 if (!Array.isArray(d) || d.length < 6) continue;
 const time = Math.floor(Number(d[0]) / 1000);
 const open = parseFloat(d[1]);
 const high = parseFloat(d[2]);
 const low = parseFloat(d[3]);
 const close = parseFloat(d[4]);
 const volume = parseFloat(d[5]);
 if (isNaN(time) || isNaN(open)) continue;
 candles.push({ time, open, high, low, close });
 volumes.push(isNaN(volume) ? 0 : volume);
 }

 if (candles.length > 0) {
 res.setHeader('Cache-Control', 'no-cache');
 res.setHeader('X-Data-Source', 'binance');
 return res.status(200).json({ candles, volumes, source: 'binance' });
 }
 } catch (e) {
 console.warn(`Erro ao acessar ${url}: ${e.message}`);
 continue;
 }
 }

 // Fallback: CoinGecko (sem bloqueio geográfico)
 const cgId = coingeckoMap[symbol];
 if (cgId) {
 try {
 const days = intervalToDays[interval] || 7;
 const cgUrl = `https://api.coingecko.com/api/v3/coins/${cgId}/market_chart?vs_currency=usd&days=${days}`;
 const cgResponse = await fetch(cgUrl, { headers: { 'Accept': 'application/json' } });

 if (cgResponse.ok) {
 const cgData = await cgResponse.json();
 const prices = cgData.prices || [];

 if (prices.length > 0) {
 // Converter dados do CoinGecko para formato OHLC aproximado
 const candles = [];
 const volumes = [];
 const bucketSize = Math.max(1, Math.floor(prices.length / 300));

 for (let i = 0; i < prices.length; i += bucketSize) {
 const bucket = prices.slice(i, i + bucketSize);
 if (bucket.length === 0) continue;

 const time = Math.floor(bucket[0][0] / 1000);
 const values = bucket.map(p => p[1]);
 const open = values[0];
 const close = values[values.length - 1];
 const high = Math.max(...values);
 const low = Math.min(...values);

 candles.push({ time, open, high, low, close });
 volumes.push(0); // CoinGecko não fornece volume por candle neste endpoint
 }

 if (candles.length > 0) {
 res.setHeader('Cache-Control', 'no-cache');
 res.setHeader('X-Data-Source', 'coingecko');
 return res.status(200).json({ candles, volumes, source: 'coingecko' });
 }
 }
 }
 } catch (e) {
 console.error(`CoinGecko fallback failed: ${e.message}`);
 }
 }

 // Se tudo falhar
 res.status(502).json({
 error: 'Todos os provedores de dados indisponíveis',
 details: 'Binance bloqueou o acesso (erro 451) e CoinGecko não respondeu. Verifique sua conexão ou tente novamente em alguns minutos.'
 });
}