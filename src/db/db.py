import pandas as pd
import psycopg2
from sqlalchemy import create_engine, text

def save_to_db(logger, df, table):
    # Create a connection to your database
    engine = create_engine('postgresql+psycopg2://ali:finance@localhost:5433/finance')
    # Insert data with ON CONFLICT DO NOTHING
    sql_command_str = f"""
        INSERT INTO {table} (datetime, open, high, low, close, adj_close, volume) 
        VALUES (:datetime, :open, :high, :low, :close, :adj_close, :volume) 
        ON CONFLICT (datetime) DO NOTHING;
    """
    sql_command = text(sql_command_str)
    df.reset_index(inplace=True)
    df.columns = [col.replace(' ', '_').lower() for col in df.columns]  # Converts 'Adj Close' to 'adj_close', etc.
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            for index, row in df.iterrows():
                conn.execute(sql_command, {
                    'datetime': row['datetime'], 
                    'open': row['open'], 
                    'high': row['high'], 
                    'low': row['low'], 
                    'close': row['close'], 
                    'adj_close': row['adj_close'], 
                    'volume': row['volume']
                })
            transaction.commit()  # Committing the transaction
        except:
            transaction.rollback()  # Rolling back in case of error
            raise
    logger.info(f'save to DB table : {table}')