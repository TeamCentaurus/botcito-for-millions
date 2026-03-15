import time
import schedule
import pandas as pd
from src.data_loader import load_prices
from src.model import load_model
from src.spread_calculator import compute_spread, compute_zscore
from src.alerts import generate_signal, send_alert, Signal

# Cargar pares entrenados
PARES_ACTIVOS = [
    load_model("data/pairs/AAPL_MSFT.pkl"),
    load_model("data/pairs/KO_PEP.pkl"),
]

def check_pairs():
    """Se ejecuta según el intervalo configurado."""
    prices = load_prices("data/raw/precios_actuales.csv")

    for model in PARES_ACTIVOS:
        try:
            p_a = prices[model.ticker_a]
            p_b = prices[model.ticker_b]

            spread = compute_spread(p_a, p_b, model.hedge_ratio)
            zscore = compute_zscore(spread, window=model.zscore_window)

            current_z = zscore.iloc[-1]
            current_spread = spread.iloc[-1]
            current_prices = {
                model.ticker_a: p_a.iloc[-1],
                model.ticker_b: p_b.iloc[-1],
            }

            signal = generate_signal(current_z, model)

            # Solo alertar si hay señal relevante
            if signal != Signal.NEUTRAL:
                send_alert(
                    signal=signal,
                    model=model,
                    zscore=current_z,
                    spread=current_spread,
                    prices=current_prices,
                    method="telegram"  # o "email"
                )

        except Exception as e:
            print(f"Error procesando {model.ticker_a}/{model.ticker_b}: {e}")


# Configurar frecuencia de monitoreo
# Para datos diarios: revisar al cierre del mercado (16:00 ET)
schedule.every().day.at("16:05").do(check_pairs)

# Para datos por minuto: revisar cada N minutos
# schedule.every(5).minutes.do(check_pairs)

print("Monitor iniciado. Esperando próxima ejecución...")
while True:
    schedule.run_pending()
    time.sleep(30)