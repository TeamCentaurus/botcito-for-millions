import functions_framework
import pandas as pd
import logging
import json
import pytz
import os
from google.cloud import storage
from twelvedata import TDClient
from datetime import datetime, UTC

REQUIRED_ENV_VARS = ["BUCKET_NAME", "TWELVEDATA_API_KEY"]
for var in REQUIRED_ENV_VARS:
    if not os.getenv(var):
        raise RuntimeError(f"Missing env var: {var}")

client = storage.Client()

def load_ticker_list() -> str:
    path = os.path.join(os.path.dirname(__file__), 'tickers.json')
    with open(path, 'r') as f:
        tickers = json.load(f)
        return ",".join(tickers['tickers'])


def save_to_gcs(df: pd.DataFrame, event_id: str, event_time: datetime) -> str:
    """ Guarda el DataFrame en Google Cloud Storage en formato parquet. """
    bucket_name = os.environ.get('BUCKET_NAME')
    bucket = client.bucket(bucket_name)

    folder = event_time.strftime("%Y-%m-%d")
    filename = event_time.strftime("%H%M%S")
    blob_path = (f"botcito/stocks/{folder}/{filename}_{event_id}.parquet")
    blob = bucket.blob(blob_path)

    from io import BytesIO
    buffer = BytesIO()
    df.to_parquet(buffer, engine="pyarrow", index=False)
    buffer.seek(0)
    
    blob.upload_from_file(buffer, content_type='application/octet-stream')
    
    return f'gs://{bucket.name}/{blob_path}'
    
@functions_framework.cloud_event
def handle_stock_request(cloud_event):
    """ Cloud Function to fetch stock data and save to GCS. """
    event_id = cloud_event["id"]
    event_time = datetime.fromisoformat(cloud_event["time"].replace("Z", "+00:00"))
    print("Event received:", event_id)
    tickers = load_ticker_list()
    api_key = os.environ.get('TWELVEDATA_API_KEY')

    td = TDClient(apikey=api_key)
    
    try:
        ts = td.time_series(
            symbol=tickers,
            interval="1min",
            outputsize=1,
            timezone="UTC",
        )

        df = ts.as_pandas()
        if df.empty:
            logging.warning(f"Event {event_id}: DataFrame empty.")
            return

        if isinstance(df.index, pd.MultiIndex):
            df = df.reset_index()
            df.rename(columns={
                'level_0': 'ticker',
                'level_1': 'datetime'
            }, inplace=True)
        else:
            df = df.reset_index()
            df.insert(0, 'ticker', tickers)  
        
        df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
        ny_tz = pytz.timezone('America/New_York')
        today_ny = datetime.now(ny_tz).date()
        df_ny_dates = df["datetime"].dt.tz_convert('America/New_York').dt.date
        if not (df_ny_dates == today_ny).all():
            print(f"El dato no pertenece a hoy ({today_ny}), es data antigua. Abortando guardado.")
            return
        
        now = datetime.now(UTC)
        df['ingested_at'] = now
        df["event_time"] = event_time.astimezone(UTC)
        # Calculate lateness para manejo de datos atrasados
        delta = event_time.astimezone(UTC) - df["datetime"]
        df["is_late"] = delta > pd.Timedelta(minutes=1)
        df["lateness_seconds"] = delta.dt.total_seconds()

        gcs_path = save_to_gcs(df, event_id, event_time)
        logging.info("Data saved", extra={"gcs_path": gcs_path})
        
    except Exception as e:
        print(f"Error fetching data: {e}")
        raise