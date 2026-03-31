## 🎯 O que é?

Uma estratégia automatizada de trading de criptomoedas para o framework **Freqtrade**, baseada no conceito de **Opening Range Breakout (ORB)** combinado com múltiplos filtros de confirmação.

O bot identifica o range de preço formado na **primeira hora do dia (00:00 UTC)**, aguarda o rompimento dessa faixa e entra na operação **somente quando todos os indicadores de tendência, volume e momentum confirmam a direção**.

---

## 📊 Evolução da Estratégia

Esta é a **quinta iteração** de um processo de refinamento baseado em dados reais de backtest:

| Versão | Timeframe | Trades | Taxa de Acerto | Resultado | Problema |
|--------|-----------|--------|----------------|-----------|----------|
| v001   | 5m        | 392    | 5.9%           | **-3.08%** | Ruído excessivo |
| v002   | 5m + Janela | 67   | 11.9%          | **-0.55%** | Poucos sinais lucrativos |
| v003   | 5m        | ~200   | ~10%           | **~-1.5%** | DI Cross muito restritivo |
| v004   | 5m + EWO  | 0      | N/A            | **0.00%**  | EWO rígido demais (0 trades) |
| **v005** | **15m** | **~80** | **~21%+**     | **Em teste** | ✅ Versão atual |

### Lições aprendidas com dados:
- **5 minutos é ruído**: Indicadores como ADX e MACD não são confiáveis nesse intervalo
- **15 minutos é o sweet spot**: Taxa de acerto salta de 5.9% para ~21%
- **Janela horária funciona**: Limitar trades para 00:00-04:00 UTC estanca perdas
- **EWO precisa de flexibilidade**: Threshold de 3.1 = zero trades. Threshold de 1.0 = oportunidades reais

---

## 🧠 Lógica da Estratégia

### Condições de ENTRADA (Compra)

Todas as condições **obrigatórias** devem ser verdadeiras (AND):

✅ Janela horária: 00:00 - 04:00 UTC
✅ ADX > 20 (mercado em tendência)
✅ +DI > -DI (pressão compradora dominante)
✅ OBV > SMA(OBV, 20) (fluxo de dinheiro positivo)
✅ MACD > Linha de Sinal
✅ RSI < 70 (não sobrecomprado)
✅ Preço > EMA 200 (tendência de longo prazo)
✅ Volume > 1.2x a média de 20 períodos
✅ Range Width > 0.1% (evita ranges muito estreitos)

text


Pelo menos **uma** condição híbrida deve ser verdadeira (OR):
🔀 Rompimento do Opening Range (Close > OR High)
OU
🔀 Elliott Wave Oscillator > 1.0 (momentum acelerando)

text


### Condições de SAÍDA (Venda)
🔴 Take Profit: 1.5x o risco (RR 1.5:1)
🔴 Stop Loss: 2x ATR abaixo da entrada (máximo 5%)
🔴 Saída por tempo: 4h com lucro / 8h máximo
🔴 Exit por tendência: ADX < 20 + DI bearish + OBV bearish

text


### Fluxo Visual
text

                ┌─────────────────────┐
                │   00:00 UTC         │
                │   Formação do       │
                │   Opening Range     │
                │   (1ª hora do dia)  │
                └─────────┬───────────┘
                          │
                ┌─────────▼───────────┐
                │   01:00 - 04:00 UTC │
                │   Aguarda           │
                │   Rompimento        │
                └─────────┬───────────┘
                          │
             ┌────────────▼────────────┐
             │  FILTROS DE CONFIRMAÇÃO │
             │                         │
             │  ADX > 20?      ✅/❌   │
             │  +DI > -DI?     ✅/❌   │
             │  OBV bullish?   ✅/❌   │
             │  MACD > Signal? ✅/❌   │
             │  RSI < 70?      ✅/❌   │
             │  EMA200 ok?     ✅/❌   │
             │  Volume ok?     ✅/❌   │
             └────────────┬────────────┘
                          │
                 Todos ✅? │
                          │
             ┌────────────▼────────────┐
             │     ENTRADA (COMPRA)    │
             │                         │
             │  Stop: -2x ATR          │
             │  Take Profit: +3x ATR   │
             │  (RR 1.5:1)             │
             └─────────────────────────┘
text


---

## 🛠️ Indicadores Técnicos Utilizados

| Indicador | Período | Função |
|-----------|---------|--------|
| **ADX** | 14 | Força da tendência (> 20 = tendência ativa) |
| **+DI / -DI** | 14 | Direção da tendência |
| **MACD** | 12/26/9 | Momentum e direção |
| **RSI** | 14 | Sobrecompra/sobrevenda |
| **ATR** | 14 | Volatilidade (base para stop/TP) |
| **OBV** | - | Fluxo de volume acumulado |
| **OBV SMA** | 20 | Média do OBV para confirmação |
| **EMA** | 200 | Tendência de longo prazo |
| **EMA** | 21 | Tendência de curto prazo |
| **EWO** | 5/35 | Elliott Wave Oscillator |

---

## ⚡ Instalação

### Pré-requisitos

- [Docker](https://docs.docker.com/get-docker/) e [Docker Compose](https://docs.docker.com/compose/install/)
- Ou: Python 3.10+ com Freqtrade instalado localmente

### 1. Clone o repositório

```bash
git clone https://github.com/seu-usuario/orb-strategy-v005.git
cd orb-strategy-v005
2. Copie a estratégia para o Freqtrade
Bash

cp ORB_Strategy_v005.py ~/freqtrade/user_data/strategies/
cp config.json ~/freqtrade/user_data/
3. Baixe os dados históricos
Bash

# Via Docker
docker compose run --rm freqtrade download-data \
  --config user_data/config.json \
  --timeframe 15m \
  --timerange 20250101-20250331

# Via instalação local
freqtrade download-data \
  --config user_data/config.json \
  --timeframe 15m \
  --timerange 20250101-20250331
🧪 Backtest
Bash

# Backtest padrão (1 mês)
docker compose run --rm freqtrade backtesting \
  --strategy ORB_Strategy_v005 \
  --config user_data/config.json \
  --timeframe 15m \
  --timerange 20250301-20250331

# Backtest estendido (3 meses)
docker compose run --rm freqtrade backtesting \
  --strategy ORB_Strategy_v005 \
  --config user_data/config.json \
  --timeframe 15m \
  --timerange 20250101-20250331

# Backtest comparativo em 1h (wildcard)
docker compose run --rm freqtrade backtesting \
  --strategy ORB_Strategy_v005 \
  --config user_data/config.json \
  --timeframe 1h \
  --timerange 20250101-20250331
📄 Paper Trading (Dry Run)
Bash

docker compose run --rm freqtrade trade \
  --strategy ORB_Strategy_v005 \
  --config user_data/config.json \
  --dry-run
⚠️ Rode em paper trading por no mínimo 7 dias antes de usar dinheiro real.
Meta: taxa de acerto > 25% e lucro médio por trade positivo.

⚙️ Configuração (config.json)
JSON

{
    "max_open_trades": 3,
    "stake_currency": "USDT",
    "stake_amount": "unlimited",
    "tradable_balance_ratio": 0.99,
    "dry_run": true,
    "dry_run_wallet": 1000,
    "trading_mode": "spot",
    "timeframe": "15m",
    "exchange": {
        "name": "binance",
        "key": "",
        "secret": "",
        "pair_whitelist": [
            "BTC/USDT",
            "ETH/USDT",
            "SOL/USDT",
            "BNB/USDT",
            "XRP/USDT"
        ]
    },
    "pairlists": [
        {
            "method": "StaticPairList"
        }
    ],
    "telegram": {
        "enabled": false,
        "token": "",
        "chat_id": ""
    }
}
Parâmetros Ajustáveis na Estratégia
Parâmetro	Padrão	Descrição
adx_threshold	20	Força mínima de tendência
volume_multiplier	1.2	Multiplicador do volume médio
obv_sma_period	20	Período da SMA do OBV
trade_hour_start	0	Início da janela (UTC)
trade_hour_end	4	Fim da janela (UTC)
ewo_threshold	1.0	Threshold do Elliott Wave Oscillator
atr_multiplier	2.0	Multiplicador do ATR para stop
risk_reward_ratio	1.5	Relação risco/recompensa
📁 Estrutura do Projeto
text

orb-strategy-v005/
│
├── ORB_Strategy_v005.py      # Estratégia principal
├── config.json                # Configuração do Freqtrade
├── README.md                  # Este arquivo
├── LICENSE                    # Licença MIT
│
├── docs/
│   ├── backtest_results/      # Resultados dos backtests
│   ├── evolution.md           # Histórico v001 → v005
│   └── indicators.md          # Explicação dos indicadores
│
└── backtests/
    ├── v001_5m_results.txt
    ├── v002_5m_window.txt
    ├── v003_5m_hybrid.txt
    ├── v004_5m_ewo.txt
    └── v005_15m_final.txt
🗺️ Roadmap
 v001 — ORB básico em 5m
 v002 — Adição de janela horária
 v003 — Filtros ADX + DI + OBV
 v004 — Elliott Wave Oscillator
 v005 — Migração para 15m + EWO híbrido
 v006 — Backtests em 1h (âncora de capital)
 v007 — Hyperopt para otimização automática
 v008 — Multi-timeframe (15m entrada + 1h confirmação)
 Deploy em VPS (DigitalOcean/AWS)
 Integração com Telegram para alertas
📚 Referências
Freqtrade Documentation
Opening Range Breakout — Investopedia
ADX Indicator — StockCharts
Elliott Wave Oscillator
On-Balance Volume (OBV)
⚠️ Disclaimer
Este projeto é apenas para fins educacionais e de pesquisa.

Trading de criptomoedas envolve risco significativo de perda financeira.
Resultados de backtests não garantem performance futura.
Nunca invista mais do que pode perder.

O autor não se responsabiliza por quaisquer perdas financeiras
decorrentes do uso desta estratégia. Faça sua própria pesquisa (DYOR).

📝 Licença
Este projeto está licenciado sob a MIT License.

🤝 Contribuição
Contribuições são bem-vindas! Abra uma issue ou envie um pull request.

Fork o projeto
Crie sua branch (git checkout -b feature/melhoria)
Commit suas mudanças (git commit -m 'Adiciona filtro X')
Push para a branch (git push origin feature/melhoria)
Abra um Pull Request
<div align="center">
Feito com ☕ e dados de backtest

Se este projeto te ajudou, deixe uma ⭐ no repositório!

</div> ```
