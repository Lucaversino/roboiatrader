// Proxy para contornar CORS da Binance na Vercel
// Retorna candles + volumes separados para o Lightweight Charts
export default async function handler(req, res) {
  const { symbol = 'BTCUSDT', interval = '15m', limit = '300' } = req.query;

  try {
    // Validação básica dos parâmetros
    if (!symbol || !interval) {
      return res.status(400).json({ error: 'Parâmetros symbol e interval são obrigatórios' });
    }

    const url = `https://api.binance.com/api/v3/klines?symbol=${encodeURIComponent(symbol)}&interval=${encodeURIComponent(interval)}&limit=${Math.min(parseInt(limit) || 300, 1000)}`;

    const headers = {
      'User-Agent': 'TraderIAPro/1.0',
      'Accept': 'application/json',
    };

    // Adiciona API Key apenas se estiver configurada e não for string vazia
    if (process.env.BINANCE_API_KEY && process.env.BINANCE_API_KEY.trim() !== '') {
      headers['X-MBX-APIKEY'] = process.env.BINANCE_API_KEY.trim();
    }

    const response = await fetch(url, {
      headers,
      method: 'GET',
    });

    if (!response.ok) {
      const errorText = await response.text().catch(() => 'Unknown error');
      console.error(`Binance API error: ${response.status} - ${errorText}`);
      return res.status(response.status).json({
        error: `Binance API error: ${response.status}`,
        details: errorText.substring(0, 200)
      });
    }

    const data = await response.json();

    // Valida se a resposta é um array válido
    if (!Array.isArray(data) || data.length === 0) {
      console.error('Resposta inválida da Binance:', data);
      return res.status(500).json({ error: 'Resposta inválida da API Binance' });
    }

    // Binance format: [openTime, open, high, low, close, volume, ...]
    const candles = [];
    const volumes = [];

    for (const d of data) {
      if (!Array.isArray(d) || d.length < 6) {
        continue; // Pula entradas malformadas
      }

      const time = Math.floor(Number(d[0]) / 1000);
      const open = parseFloat(d[1]);
      const high = parseFloat(d[2]);
      const low = parseFloat(d[3]);
      const close = parseFloat(d[4]);
      const volume = parseFloat(d[5]);

      // Valida se os valores são números válidos
      if (isNaN(time) || isNaN(open) || isNaN(high) || isNaN(low) || isNaN(close)) {
        continue;
      }

      candles.push({ time, open, high, low, close });
      volumes.push(isNaN(volume) ? 0 : volume);
    }

    if (candles.length === 0) {
      return res.status(500).json({ error: 'Nenhum dado válido retornado pela Binance' });
    }

    res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate');
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.status(200).json({ candles, volumes });
  } catch (error) {
    console.error('Erro no proxy de candles:', error);
    res.status(500).json({
      error: error.message || 'Erro interno do servidor',
      stack: process.env.NODE_ENV === 'development' ? error.stack : undefined
    });
  }
}