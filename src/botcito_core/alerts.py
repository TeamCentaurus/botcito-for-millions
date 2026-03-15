from enum import Enum
from botcito_core.types import PairModel

class Signal(Enum):
    LONG_A_SHORT_B   = "COMPRAR A / VENDER B"    # Spread muy bajo (A barata vs B)
    SHORT_A_LONG_B   = "VENDER A / COMPRAR B"    # Spread muy alto (A cara vs B)
    CLOSE_POSITION   = "CERRAR POSICIÓN"          # Spread volvió a la media
    STOP_LOSS        = "STOP LOSS - DIVERGENCIA EXTREMA"
    NEUTRAL          = "SIN SEÑAL"

def generate_signal(zscore: float, model: PairModel) -> Signal:
    """
    Genera señal de trading basada en el Z-Score actual.

    Diagrama de estados:

    z < -entry  →  LONG A / SHORT B   (spread inusualmente bajo)
    z > +entry  →  SHORT A / LONG B   (spread inusualmente alto)
    |z| < exit  →  CERRAR POSICIÓN    (spread volvió a la media)
    |z| > stop  →  STOP LOSS          (divergencia peligrosa)
    """
    abs_z = abs(zscore)

    if abs_z > model.stop_loss_threshold:
        return Signal.STOP_LOSS

    if zscore < -model.entry_threshold:
        return Signal.LONG_A_SHORT_B

    if zscore > model.entry_threshold:
        return Signal.SHORT_A_LONG_B

    if abs_z < model.exit_threshold:
        return Signal.CLOSE_POSITION

    return Signal.NEUTRAL