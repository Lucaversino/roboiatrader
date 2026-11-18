# Configuração na Vercel — Trader IA PRO

## Passo a passo para configurar as variáveis de ambiente

### 1. Acesse seu projeto na Vercel
- Faça login em [vercel.com](https://vercel.com)
- Clique no projeto `trader-ia-pro`

### 2. Adicione as variáveis de ambiente
Vá em **Settings** → **Environment Variables** e adicione:

| Variável | Valor | Descrição |
|----------|-------|-----------|
| `ADMIN_USER` | `admin` (ou seu usuário) | Usuário para login no painel |
| `ADMIN_PASSWORD` | `sua_senha_forte` | Senha para login no painel |
| `BACKEND_URL` | `https://seu-backend.railway.app` | URL do backend no Railway |
| `BACKEND_TOKEN` | `token_igual_ao_backend` | Token de autenticação do backend |
| `BINANCE_API_KEY` | `tlvbG3fZ...` | Sua API Key da Binance |
| `BINANCE_SECRET_KEY` | `sua_secret_key` | Sua Secret Key da Binance |

### 3. Selecione os ambientes
Marque **Production**, **Preview** e **Development** para cada variável.

### 4. Refaça o deploy
Após salvar as variáveis, vá em **Deployments** e clique nos três pontos do último deploy → **Redeploy**.

---

## ⚠️ Segurança Importante

Sua chave API da Binance está configurada como **"Irrestrito (Menos Seguro)"** e com permissão de **Leitura** apenas. Isso é seguro para o modo paper trading atual.

Quando for operar com dinheiro real:
1. Volte à página de API da Binance
2. Em "Restrições de acesso por IP", adicione **apenas o IP do servidor Vercel**
3. Nunca habilite "Habilitar Saques" em chaves de API usadas por bots
4. Considere criar uma subconta dedicada apenas para trading automatizado

---

## Verificação

Após o redeploy, acesse seu domínio Vercel e verifique:
- O gráfico deve mostrar candles reais da Binance
- No painel "Diagnóstico OpenAI", o status da API Binance deve aparecer como conectado
- Os dados de preço devem atualizar a cada 5 segundos