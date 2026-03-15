import pandas as pd
import numpy as np
from botcito_core.alerts import generate_signal, Signal
from botcito_core.types import PairModel

def run_backtest(prices: pd.DataFrame,
                 model: PairModel,
                 start: str,
                 end: str,
                 transaction_cost: float = 0.001) -> dict:
    """
    Simula la estrategia en datos históricos.
    transaction_cost: 0.001 = 0.1% por operación (round-trip = 0.2%)
    """
    p_a = prices.loc[start:end, model.ticker_a]
    p_b = prices.loc[start:end, model.ticker_b]
    p_a, p_b = p_a.align(p_b, join="inner")

    # Recalcular spread con parámetros del entrenamiento
    spread = p_a - model.hedge_ratio * p_b
    zscore = (spread - model.spread_mean) / model.spread_std

    # Simular posiciones
    position = 0  # 1=long_a_short_b, -1=short_a_long_b, 0=flat
    entry_spread = None
    returns = []
    trades = []

    for i in range(1, len(zscore)):
        z = zscore.iloc[i]
        signal = generate_signal(z, model)

        # Lógica de entrada
        if position == 0:

            if signal == Signal.LONG_A_SHORT_B:
                position = 1
                entry_spread = spread.iloc[i]

                trades.append({
                    "type": "OPEN_LONG",
                    "date": zscore.index[i],
                    "z": float(z)
                })

            elif signal == Signal.SHORT_A_LONG_B:
                position = -1
                entry_spread = spread.iloc[i]

                trades.append({
                    "type": "OPEN_SHORT",
                    "date": zscore.index[i],
                    "z": float(z)
                })

        # Lógica de salida
        elif position != 0:

            if signal in (Signal.CLOSE_POSITION, Signal.STOP_LOSS):

                pnl = position * (spread.iloc[i] - entry_spread)

                # Normalizar por volatilidad del spread
                pnl = pnl / model.spread_std

                # Costos de transacción
                pnl -= transaction_cost

                returns.append(pnl)

                trades.append({
                    "type": "CLOSE",
                    "date": zscore.index[i],
                    "pnl": float(pnl)
                })

                position = 0
                entry_spread = None

    # Cerrar posicion

    if position != 0 and entry_spread is not None:

        pnl = position * (spread.iloc[-1] - entry_spread)
        pnl = pnl / model.spread_std
        pnl -= transaction_cost

        returns.append(pnl)

        trades.append({
            "type": "FORCED_CLOSE",
            "date": zscore.index[-1],
            "pnl": float(pnl)
        })

    returns_arr = np.array(returns)

    # Métricas
    if len(returns_arr) == 0:
        sharpe = 0
        win_rate = 0
    else:

        if returns_arr.std() == 0:
            sharpe = 0
        else:
            sharpe = returns_arr.mean() / returns_arr.std()

        win_rate = (returns_arr > 0).mean()

    return {
        "total_trades": len(returns),
        "total_pnl": float(returns_arr.sum()),
        "sharpe_ratio": round(float(sharpe), 4),
        "win_rate": round(float(win_rate), 4),
        "max_drawdown": round(float(_max_drawdown(returns_arr)), 4),
        "trades": trades,
    }


def _max_drawdown(returns: np.ndarray) -> float:
    
    if len(returns) == 0:
        return 0

    cumulative = np.cumsum(returns)
    running_max = np.maximum.accumulate(cumulative)
    drawdown = running_max - cumulative

    return drawdown.max()