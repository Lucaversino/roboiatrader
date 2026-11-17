# Trader IA PRO — Web App V1.1 (paper only)

**Arquitetura:** Vercel (Next.js, painel e proxy autenticado) -> Railway (FastAPI, loop 24/7) -> SQLite em volume persistente, Binance pública e OpenAI opcional. **Não contém endpoints de ordens reais.**

## Preparar GitHub
1. Crie repositório **privado** chamado `trader-ia-pro`.
2. Na pasta deste pacote, rode:
   ```bash
   git init
   git add .
   git commit -m "Trader IA PRO web app paper trading"
   git branch -M main
   git remote add origin https://github.com/SEU-USUARIO/trader-ia-pro.git
   git push -u origin main
   ```
3. Nunca faça commit de `.env`, chaves, tokens, banco SQLite ou arquivos `.vercel`.

## Railway — primeiro o backend
1. Crie um projeto Railway com GitHub e selecione o mesmo repositório.
2. **Root Directory** = `backend` (a pasta contém Dockerfile).
3. Adicione volume persistente montado em `/data` (não use filesystem efêmero).
4. Em Variables configure `DEPLOYMENT_MODE=production`, `TRADER_DB=/data/trader.db`, `BACKEND_TOKEN=<valor aleatório longo>`. Para usar IA, configure também `OPENAI_API_KEY` apenas no backend.
5. Gere domínio HTTPS público no Railway e confira `/health` (informa `mode: paper`). O backend protege as demais rotas por Bearer token.
6. Execute somente **uma réplica** do backend; múltiplas réplicas criariam múltiplos motores e possíveis disputas. O robô inicia DESLIGADO após reinício e precisa ser religado no painel.

## Vercel — depois o frontend
1. Import Project > GitHub > repositório `trader-ia-pro`.
2. **Root Directory** = `frontend` e Framework Preset = `Next.js`.
3. Em Environment Variables (Production) configure:
   - `ADMIN_USER` = seu usuário administrativo
   - `ADMIN_PASSWORD` = uma senha forte exclusiva
   - `BACKEND_URL` = URL HTTPS do Railway (sem barra final)
   - `BACKEND_TOKEN` = mesmo valor definido no Railway
4. Deploy. No primeiro acesso, o navegador pedirá usuário e senha (HTTP Basic sobre HTTPS).
5. O botão de iniciar ativa o loop AUTOMÁTICO **apenas de operações simuladas**, no backend persistente.

## Segurança e limites
- Esta V1 tem **um único operador**. Basic Auth é um acesso simples, não substitui login com MFA e auditoria para produção financeira.
- SQLite é adequado apenas a esse teste de instância única; a migração para PostgreSQL/Supabase exige reimplementar a camada de persistência, o SQL incluído na V1 original é apenas uma referência.
- Stop-loss e take-profit são verificados no fechamento do candle; não são ordens de proteção na corretora. Com movimentos bruscos podem ocorrer perdas superiores ao limite simulado.
- Não há backtest confiável nem garantia de resultado. Custos de Railway, Vercel e OpenAI dependem dos planos e consumo.
- **Sem dinheiro real:** o backend não recebe chaves de exchange e não implementa envio de ordens.

## Rodar local
Backend: `cd backend && pip install -r requirements.txt && uvicorn app:app --reload` (variáveis de produção não são necessárias para execução local sem token).
Frontend: `cd frontend && npm install && npm run dev`. O frontend precisa das variáveis `ADMIN_USER`, `ADMIN_PASSWORD`, `BACKEND_URL` (HTTPS) e `BACKEND_TOKEN` para operar conectado remotamente.

## Verificações
- `GET /health` no Railway: resposta 200 e `paper`.
- Login no domínio Vercel: janela de credenciais.
- `GET /api/status` no site após login: dados do motor (sem acesso direto a tokens).
- Testar `Iniciar` / `Parar`, e conferir eventos em logs, com **modo PAPER_ONLY**.
