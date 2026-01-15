import functions_framework
import pandas as pd
import json
import os
from google.cloud import storage
from twelvedata import TDClient
from datetime import datetime

BUCKET_NAME = os.environ.get('BUCKET_NAME')

def load_ticker_list() -> str:
    path = os.path.join(os.path.dirname(__file__), 'tickers.json')
    with open(path, 'r') as f:
        tickers = json.load(f)
        return ",".join(tickers['tickers'])


def save_to_gcs(df: pd.DataFrame) -> str:
    """Guarda el DataFrame en Google Cloud Storage en formato parquet."""
    if not BUCKET_NAME:
        raise ValueError("BUCKET_NAME environment variable is not set.")
    
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)

    now = datetime.utcnow()
    folder = now.strftime('%Y-%m-%d')
    timestamp = now.strftime('%H%M%S')
    blob_path = f'botcito/stocks/{folder}/{timestamp}.parquet'
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
    
    tickers = load_ticker_list()
    api_key = os.environ.get('TWELVEDATA_API_KEY')

    if not api_key:
        raise ValueError("TWELVEDATA_API_KEY environment variable is not set.")

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
            print("DataFrame is empty, nothing to save.")
            return
        
        df = df.reset_index()

        if 'level_1' in df.columns:
            df.rename(columns={'level_1': 'datetime', 'level_0': 'ticker'}, inplace=True)
        else:
            df.insert(0, 'ticker', tickers)

        df['ingested_at'] = datetime.utcnow()

        gcs_path = save_to_gcs(df)
        print(f"Data saved to {gcs_path}")
        
    except Exception as e:
        print(f"Error fetching data: {e}")
        raise