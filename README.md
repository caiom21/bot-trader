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
