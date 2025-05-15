# data/load_data.py
import pandas as pd

def load_data(file_path):
    try:
        # Load CSV with pandas
        df = pd.read_csv(file_path)
        
        # Verify required columns exist
        required_columns = ['EnteredAt', 'ExitedAt', 'PnL(Net)', 'WinOrLoss', 'Streak', 'HourOfDay', 'Type']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}. Available columns: {df.columns.tolist()}")
        
        # Convert and clean data
        df['EnteredAt'] = pd.to_datetime(df['EnteredAt'], errors='coerce')
        df['ExitedAt'] = pd.to_datetime(df['ExitedAt'], errors='coerce')
        df['PnL(Net)'] = pd.to_numeric(df['PnL(Net)'], errors='coerce').fillna(0)
        df['WinOrLoss'] = pd.to_numeric(df['WinOrLoss'], errors='coerce').fillna(0)
        df['Streak'] = pd.to_numeric(df['Streak'], errors='coerce').fillna(0)
        df['HourOfDay'] = pd.to_numeric(df['HourOfDay'], errors='coerce').fillna(0)
        df['Type'] = df['Type'].astype(str).fillna('')
        
        # Filter invalid dates
        df = df[df['EnteredAt'].notna() & df['ExitedAt'].notna()]
        
        # Ensure timezone consistency (UTC+03:00 as per CSV)
        df['EnteredAt'] = df['EnteredAt'].dt.tz_convert('UTC+03:00')
        df['ExitedAt'] = df['ExitedAt'].dt.tz_convert('UTC+03:00')
        
        return df
    except Exception as e:
        print(f"Error loading data: {e}")
        # Print CSV columns for debugging
        try:
            temp_df = pd.read_csv(file_path)
            print(f"Available CSV columns: {temp_df.columns.tolist()}")
        except:
            print("Could not read CSV for column inspection")
        return pd.DataFrame()