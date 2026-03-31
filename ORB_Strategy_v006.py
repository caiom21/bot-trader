from pandas import DataFrame
from functools import reduce
import talib.abstract as ta
import talib
import numpy as np
from freqtrade.strategy import IStrategy
from datetime import datetime


class ORB_Strategy_v006(IStrategy):
    """
    Estratégia Híbrida v005: ORB + ADX + OBV + MACD + EWO (Opcional)

    LÓGICA DE ENTRADA (COMPRA):
    ─────────────────────────────────────────────────────────
    Condições OBRIGATÓRIAS (todas AND):
      - Janela horária: 00:00 - 04:00 UTC
      - ADX > 20
      - +DI > -DI (tendência de alta ativa)
      - OBV > SMA(OBV, 20)
      - MACD > Sinal
      - RSI < 70
      - Preço > EMA200
      - Volume > 1.2x média

    Condição HÍBRIDA (pelo menos UMA — OR):
      - Rompimento do Opening Range (close > OR High)
      - EWO > 1.0 (momentum Elliott acelerando)

    SAÍDA:
    ─────────────────────────────────────────────────────────
      - Stop Loss: 2x ATR abaixo da entrada (máx 5%)
      - Take Profit: 1.5x o risco (RR 1.5:1)
      - Exit por tendência: ADX < 20 + DI- > DI+ + OBV bearish
    """

    # ══════════════════════════════════════════════════════
    # CONFIGURAÇÕES PRINCIPAIS
    # ══════════════════════════════════════════════════════
    timeframe = '15m'
    startup_candle_count = 200
    process_only_new_candles = True

    # Stop base de segurança (sobrescrito pelo custom_stoploss)
    stoploss = -0.05

    # ROI desativado — take profit via custom_exit
    minimal_roi = {"0": 100}

    # Trailing stop desativado — RR fixo
    trailing_stop = False

    # Limite de operações simultâneas
    max_open_trades = 3  # NOVO: proteção de capital

    # ══════════════════════════════════════════════════════
    # PARÂMETROS DA ESTRATÉGIA (fácil ajuste)
    # ══════════════════════════════════════════════════════
    # Tendência
    adx_threshold = 20          
    # Volume
    volume_multiplier = 1.2     
    obv_sma_period = 20         
    # Janela de operação (UTC)
    trade_hour_start = 0        
    trade_hour_end = 4         
    ewo_fast = 5
    ewo_slow = 35
    ewo_threshold = 1.0         
    # Risco
    atr_multiplier = 2.0        
    risk_reward_ratio = 1.5     
    # Opening Range
    or_window_hours = 1        

    # ══════════════════════════════════════════════════════
    # INDICADORES
    # ══════════════════════════════════════════════════════
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        # ── 1. MACD ──
        macd = ta.MACD(dataframe, fastperiod=12, slowperiod=26, signalperiod=9)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        dataframe['macdhist'] = macd['macdhist']

        # ── 2. RSI ──
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)

        # ── 3. ATR (Stop & TP dinâmicos) ──
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)

        # ── 4. ADX + DI+ + DI- ──
        dataframe['adx'] = talib.ADX(
            dataframe['high'], dataframe['low'], dataframe['close'], timeperiod=14
        )
        dataframe['plus_di'] = talib.PLUS_DI(
            dataframe['high'], dataframe['low'], dataframe['close'], timeperiod=14
        )
        dataframe['minus_di'] = talib.MINUS_DI(
            dataframe['high'], dataframe['low'], dataframe['close'], timeperiod=14
        )

        # MUDANÇA: Em vez de exigir cruzamento exato (evento raro),
        # verificamos se +DI está ACIMA de -DI (estado contínuo)
        dataframe['di_bullish'] = dataframe['plus_di'] > dataframe['minus_di']
        dataframe['di_bearish'] = dataframe['plus_di'] < dataframe['minus_di']

        # Mantemos o cruzamento para o sinal de saída
        dataframe['di_cross_down'] = (
            (dataframe['plus_di'] < dataframe['minus_di']) &
            (dataframe['plus_di'].shift(1) >= dataframe['minus_di'].shift(1))
        )

        # ── 5. OBV + SMA ──
        dataframe['obv'] = talib.OBV(dataframe['close'], dataframe['volume'])
        dataframe['obv_sma'] = dataframe['obv'].rolling(
            window=self.obv_sma_period
        ).mean()

        dataframe['obv_bullish'] = dataframe['obv'] > dataframe['obv_sma']
        dataframe['obv_bearish'] = dataframe['obv'] < dataframe['obv_sma']

        # ── 6. EMAs ──
        dataframe['ema200'] = ta.EMA(dataframe, timeperiod=200)
        dataframe['ema21'] = ta.EMA(dataframe, timeperiod=21)

        # ── 7. Volume médio ──
        dataframe['volume_mean'] = dataframe['volume'].rolling(window=20).mean()

        # ── 8. Elliott Wave Oscillator (NOVO) ──
        dataframe['ema_fast_ewo'] = ta.EMA(dataframe, timeperiod=self.ewo_fast)
        dataframe['ema_slow_ewo'] = ta.EMA(dataframe, timeperiod=self.ewo_slow)
        dataframe['ewo'] = (
            (dataframe['ema_fast_ewo'] - dataframe['ema_slow_ewo']) /
            dataframe['ema_slow_ewo'] * 100
        )

        # ── 9. Opening Range (00:00 UTC, janela configurável) ──
        # No 15m, a primeira hora = 4 candles (0:00, 0:15, 0:30, 0:45)
        dataframe['is_opening_range'] = (
            (dataframe['date'].dt.hour == 0) &
            (dataframe['date'].dt.minute < 60)
        )

        # Calcular OR High e OR Low corretamente por dia
        # Agrupa por data e pega max/min apenas dos candles do opening range
        dataframe['trade_date'] = dataframe['date'].dt.date

        # Opening Range High: máxima dos candles da primeira hora
        or_high = dataframe.loc[
            dataframe['is_opening_range']
        ].groupby('trade_date')['high'].transform('max')

        dataframe['opening_range_high'] = np.nan
        dataframe.loc[dataframe['is_opening_range'], 'opening_range_high'] = or_high
        dataframe['opening_range_high'] = dataframe['opening_range_high'].ffill()

        # Opening Range Low: mínima dos candles da primeira hora
        or_low = dataframe.loc[
            dataframe['is_opening_range']
        ].groupby('trade_date')['low'].transform('min')

        dataframe['opening_range_low'] = np.nan
        dataframe.loc[dataframe['is_opening_range'], 'opening_range_low'] = or_low
        dataframe['opening_range_low'] = dataframe['opening_range_low'].ffill()

        # Largura do range (para filtro de range muito estreito)
        dataframe['range_width'] = (
            (dataframe['opening_range_high'] - dataframe['opening_range_low']) /
            dataframe['opening_range_low']
        )

        # ── 10. Janela de Trading (00:00 - 04:00 UTC) ──
        dataframe['in_trade_window'] = (
            (dataframe['date'].dt.hour >= self.trade_hour_start) &
            (dataframe['date'].dt.hour < self.trade_hour_end)
        )

        # ── 11. Não operar DURANTE o Opening Range (esperar formação) ──
        dataframe['after_opening_range'] = (
            (dataframe['date'].dt.hour >= 1) |  # Após 01:00 UTC
            ((dataframe['date'].dt.hour == 0) & (dataframe['date'].dt.minute >= 45))
            # ou último candle de 15m da hora 0 (0:45)
        )

        # Limpeza
        dataframe.drop(columns=['trade_date'], inplace=True, errors='ignore')

        return dataframe

    # ══════════════════════════════════════════════════════
    # SINAL DE COMPRA (ENTRADA)
    # ══════════════════════════════════════════════════════
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        # ── Condições OBRIGATÓRIAS (AND) ──
        mandatory_conditions = []

        # 1. Dentro da janela de trading (00:00 - 04:00 UTC)
        mandatory_conditions.append(dataframe['in_trade_window'])

        # 2. Após formação do Opening Range (não operar durante)
        mandatory_conditions.append(dataframe['after_opening_range'])

        # 3. ADX > 20 (mercado em tendência)
        mandatory_conditions.append(dataframe['adx'] > self.adx_threshold)

        # 4. +DI > -DI (tendência de alta ativa)
        mandatory_conditions.append(dataframe['di_bullish'])

        # 5. OBV acima da SMA (fluxo de dinheiro positivo)
        mandatory_conditions.append(dataframe['obv_bullish'])

        # 6. MACD acima do sinal
        mandatory_conditions.append(dataframe['macd'] > dataframe['macdsignal'])

        # 7. RSI não sobrecomprado
        mandatory_conditions.append(dataframe['rsi'] < 70)

        # 8. Preço acima da EMA200 (tendência de longo prazo)
        mandatory_conditions.append(dataframe['close'] > dataframe['ema200'])

        # 9. Volume acima de 1.2x a média
        mandatory_conditions.append(
            dataframe['volume'] > (dataframe['volume_mean'] * self.volume_multiplier)
        )

        # 10. Opening Range não é muito estreito (evita falsos rompimentos)
        mandatory_conditions.append(dataframe['range_width'] > 0.001)  # > 0.1%

        # ── Condições HÍBRIDAS (OR) — pelo menos uma ──
        hybrid_conditions = []

        # A. Rompimento do Opening Range
        hybrid_conditions.append(
            dataframe['close'] > dataframe['opening_range_high']
        )

        # B. EWO acelerando acima de 1.0 (momentum Elliott)
        hybrid_conditions.append(
            dataframe['ewo'] > self.ewo_threshold
        )

        # Combinar: pelo menos uma condição híbrida deve ser verdadeira
        hybrid_combined = reduce(lambda x, y: x | y, hybrid_conditions)

        # ── Combinar TUDO ──
        all_mandatory = reduce(lambda x, y: x & y, mandatory_conditions)
        final_condition = all_mandatory & hybrid_combined

        dataframe.loc[final_condition, 'enter_long'] = 1

        return dataframe

    # ══════════════════════════════════════════════════════
    # SINAL DE VENDA (SAÍDA POR TENDÊNCIA)
    # ══════════════════════════════════════════════════════
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []

        # 1. ADX caiu abaixo do threshold (tendência enfraquecendo)
        conditions.append(dataframe['adx'] < self.adx_threshold)

        # 2. DI- domina DI+ (pressão vendedora)
        conditions.append(dataframe['di_bearish'])

        # 3. OBV abaixo da SMA (fluxo de dinheiro negativo)
        conditions.append(dataframe['obv_bearish'])

        if conditions:
            dataframe.loc[
                reduce(lambda x, y: x & y, conditions),
                'exit_long'
            ] = 1

        return dataframe

    # ══════════════════════════════════════════════════════
    # STOP LOSS DINÂMICO: 2x ATR
    # ══════════════════════════════════════════════════════
    def custom_stoploss(
        self,
        pair: str,
        trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        after_fill: bool,
        **kwargs
    ) -> float:
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)

        if dataframe is not None and not dataframe.empty:
            last_candle = dataframe.iloc[-1]
            atr = last_candle.get('atr', 0)

            if atr > 0 and trade.open_rate > 0:
                # Stop = 2x ATR abaixo do preço de entrada
                stop_distance = (self.atr_multiplier * atr) / trade.open_rate
                return -min(stop_distance, 0.05)  # Máximo 5%

        return -0.03  # Fallback: 3%

    # ══════════════════════════════════════════════════════
    # TAKE PROFIT DINÂMICO: RR 1.5:1
    # ══════════════════════════════════════════════════════
    def custom_exit(
        self,
        pair: str,
        trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs
    ):
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)

        if dataframe is not None and not dataframe.empty:
            last_candle = dataframe.iloc[-1]
            atr = last_candle.get('atr', 0)

            if atr > 0:
                # Risco = distância do stop
                stop_distance = self.atr_multiplier * atr

                # Take profit = RR ratio x risco
                take_profit_distance = self.risk_reward_ratio * stop_distance
                take_profit_price = trade.open_rate + take_profit_distance

                # Se preço atual atingiu o take profit → sai
                if current_rate >= take_profit_price:
                    return f'take_profit_{self.risk_reward_ratio}RR'

                # ── PROTEÇÃO EXTRA: Saída por tempo ──
                # Se o trade está aberto há mais de 4 horas e não atingiu TP,
                # fecha para liberar capital
                trade_duration = (current_time - trade.open_date_utc).total_seconds() / 3600
                if trade_duration > 4:
                    if current_profit > 0:
                        return 'time_exit_profit'
                    elif trade_duration > 8:
                        return 'time_exit_max_duration'

        return None
