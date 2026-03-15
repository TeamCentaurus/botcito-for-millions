from dataclasses import dataclass

@dataclass
class PairModel:
    """Contiene todos los parámetros de un par entrenado."""
    ticker_a: str
    ticker_b: str
    hedge_ratio: float
    spread_mean: float
    spread_std: float
    half_life: float
    zscore_window: int
    entry_threshold: float    # Z-score para abrir posición
    exit_threshold: float     # Z-score para cerrar posición
    stop_loss_threshold: float  # Z-score para stop-loss