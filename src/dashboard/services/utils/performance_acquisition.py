import glob
import logging
import os
import re
import time
from collections import deque
from datetime import timedelta
from pathlib import Path

import pandas as pd
import pytz
import yfinance as yf

from dashboard.config.settings import PERFORMANCE_DIR, TIMEZONE, PERFORMANCE_CSV
from dashboard.config.env import TEMP_PERF_DIR, BASE_DIR
from dashboard.services.portfolio import sync_trade_sum_from_performance_rows
from dashboard.services.utils.trade_enrichment import ensure_trade_id, merge_trade_labels
from dashboard.services.utils.trade_journal import sync_trade_journal

logger = logging.getLogger(__name__)

TRADE_SIGNATURE_COLUMNS = [
    "ContractName",
    "EnteredAt",
    "ExitedAt",
    "EntryPrice",
    "ExitPrice",
    "Size",
    "Type",
]

CONTRACT_SPECS_CSV = BASE_DIR / "data" / "future" / "contract_specs.csv"
_DEFAULT_POINT_VALUES = {
    "MES": 5.0,
    "MNQ": 2.0,
    "M2K": 5.0,
    "M6E": 12500.0,
    "M6B": 6250.0,
    "MBT": 0.1,
    "MET": 0.1,
}


def _symbol_root(raw_symbol: object) -> str:
    sym = str(raw_symbol or "").strip().upper()
    if not sym:
        return ""
    # Remove exchange suffix, e.g. MESH26.CME -> MESH26
    sym = sym.split(".")[0]
    # Match futures code with month code + year (e.g. MESH26 -> MES)
    m = re.match(r"^([A-Z]+?)([FGHJKMNQUVXZ])(\d{1,2})$", sym)
    if m:
        return m.group(1)
    # Fallback to leading alpha token.
    m2 = re.match(r"^([A-Z]+)", sym)
    return m2.group(1) if m2 else sym


def _load_point_values() -> dict[str, float]:
    specs = dict(_DEFAULT_POINT_VALUES)
    if CONTRACT_SPECS_CSV.exists():
        try:
            df = pd.read_csv(CONTRACT_SPECS_CSV)
            if {"symbol", "point_value"}.issubset(df.columns):
                for _, row in df.iterrows():
                    root = _symbol_root(row.get("symbol"))
                    if not root:
                        continue
                    try:
                        specs[root] = float(row.get("point_value"))
                    except (TypeError, ValueError):
                        continue
        except (OSError, pd.errors.ParserError) as exc:
            logger.warning("Failed to load contract specs from %s: %s", CONTRACT_SPECS_CSV, exc)
    return specs


def _sort_combined(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    sort_cols = []
    if "EnteredAt" in out.columns:
        out["EnteredAt"] = pd.to_datetime(out["EnteredAt"], utc=True, errors="coerce")
        sort_cols.append("EnteredAt")
    if "ExitedAt" in out.columns:
        out["ExitedAt"] = pd.to_datetime(out["ExitedAt"], utc=True, errors="coerce")
        sort_cols.append("ExitedAt")
    if "ContractName" in out.columns:
        sort_cols.append("ContractName")
    if "IntradayIndex" in out.columns:
        sort_cols.append("IntradayIndex")
    if sort_cols:
        out = out.sort_values(sort_cols, kind="stable").reset_index(drop=True)
    return out


def _dedupe_by_trade_signature(df: pd.DataFrame, *, label: str) -> pd.DataFrame:
    out = df.copy()
    missing = [c for c in TRADE_SIGNATURE_COLUMNS if c not in out.columns]
    if missing:
        logger.warning("Skip dedupe for %s: missing signature columns %s", label, missing)
        return out
    before = len(out)
    out = out.drop_duplicates(subset=TRADE_SIGNATURE_COLUMNS, keep="last").reset_index(drop=True)
    removed = before - len(out)
    if removed > 0:
        logger.info("Deduped %s by trade signature: removed %d duplicate row(s)", label, removed)
    return out

def process_csv(file_path):
    # Read the CSV data
    df = pd.read_csv(file_path)

    # Convert 'Date/Time' to datetime
    df['Date/Time'] = pd.to_datetime(df['Date/Time'], format='%Y%m%d;%H%M%S')

    # Localize to Eastern Time (America/New_York)
    eastern_tz = pytz.timezone('America/New_York')
    df['Date/Time'] = df['Date/Time'].apply(lambda x: x.tz_localize(eastern_tz))

    # Sort by 'Date/Time' for FIFO
    df = df.sort_values('Date/Time').reset_index(drop=True)

    # Calculate per-unit fees
    def calculate_trade_fee(row):
        return (
            abs(row['BrokerExecutionCommission']) +
            abs(row['ThirdPartyExecutionCommission']) +
            abs(row['ThirdPartyRegulatoryCommission'])
        )

    df['TotalFee'] = df.apply(calculate_trade_fee, axis=1)
    df['FeePerUnit'] = df['TotalFee'] / df['Quantity'].abs()

    # Initialize round trips list
    round_trips = []

    point_values = _load_point_values()

    # Group trades by symbol
    for symbol in df['Symbol'].unique():
        symbol_df = df[df['Symbol'] == symbol].copy()
        symbol_root = _symbol_root(symbol)
        point_value = point_values.get(symbol_root)
        if point_value is None:
            point_value = _DEFAULT_POINT_VALUES.get("MES", 5.0)
            logger.warning(
                "Missing point_value for symbol '%s' (root '%s'); defaulting to %.2f. Add row to %s",
                symbol,
                symbol_root,
                point_value,
                CONTRACT_SPECS_CSV,
            )

        # Initialize queues for this symbol
        buy_trades = deque()
        sell_trades = deque()

        # Split trades into single-unit trades
        for _, row in symbol_df.iterrows():
            qty = int(row['Quantity'])
            fee_per_unit = row['TotalFee'] / abs(qty)
            trade = {
                'Time': row['Date/Time'],
                'Price': row['Price'],
                'FeePerUnit': fee_per_unit,
                'TradeDate': row['TradeDate'],
                'Symbol': row['Symbol'],
                'OriginalQty': qty
            }
            if qty > 0:
                for _ in range(qty):
                    buy_trades.append(trade.copy())
            else:
                for _ in range(-qty):
                    sell_trades.append(trade.copy())

        # Generate round trips for this symbol
        while buy_trades and sell_trades:
            buy = buy_trades.popleft()
            sell = sell_trades.popleft()
            
            # Determine trade type
            if buy['Time'] <= sell['Time']:
                trade_type = 'Long'
                entered_at = buy['Time']
                exited_at = sell['Time']
                entry_price = buy['Price']
                exit_price = sell['Price']
                fees = buy['FeePerUnit'] + sell['FeePerUnit']
                pnl = (exit_price - entry_price) * point_value - fees
            else:
                trade_type = 'Short'
                entered_at = sell['Time']
                exited_at = buy['Time']
                entry_price = sell['Price']
                exit_price = buy['Price']
                fees = buy['FeePerUnit'] + sell['FeePerUnit']
                pnl = (entry_price - exit_price) * point_value - fees

            # Calculate duration
            trade_duration_seconds = (exited_at - entered_at).total_seconds()
            trade_duration_days = trade_duration_seconds // (24 * 3600)
            trade_duration_seconds %= (24 * 3600)
            trade_duration_hours = trade_duration_seconds // 3600
            trade_duration_seconds %= 3600
            trade_duration_minutes = trade_duration_seconds // 60
            trade_duration_seconds %= 60
            trade_duration_seconds = int(trade_duration_seconds)
            trade_duration_str = f"{int(trade_duration_days)} days {int(trade_duration_hours):02}:{int(trade_duration_minutes):02}:{trade_duration_seconds:02}"

            # Convert to +03:00 timezone
            target_tz = pytz.timezone('US/Central')
            entered_at_tz = entered_at.astimezone(target_tz)
            exited_at_tz = exited_at.astimezone(target_tz)
            entered_at_str = entered_at_tz.strftime('%m/%d/%Y %H:%M:%S %z').replace('+0300', '+03:00')
            exited_at_str = exited_at_tz.strftime('%m/%d/%Y %H:%M:%S %z').replace('+0300', '+03:00')

            # Create round trip
            round_trip = {
                'ContractName': buy['Symbol'],
                'EnteredAt': entered_at_str,
                'ExitedAt': exited_at_str,
                'EntryPrice': entry_price,
                'ExitPrice': exit_price,
                'Fees': round(fees, 2),
                'PnL': round(pnl, 2),
                'Size': 1,
                'Type': trade_type,
                'TradeDay': entered_at_str,
                'TradeDuration': trade_duration_str
            }
            round_trips.append(round_trip)

        # Print unmatched buy trades
        if buy_trades:
            print(f"\nUnmatched BUY trades for symbol {symbol}:")
            for t in buy_trades:
                print(f"  Time: {t['Time']}, Price: {t['Price']}, Qty: 1, Symbol: {t['Symbol']}")

        # Print unmatched sell trades
        if sell_trades:
            print(f"\nUnmatched SELL trades for symbol {symbol}:")
            for t in sell_trades:
                print(f"  Time: {t['Time']}, Price: {t['Price']}, Qty: 1, Symbol: {t['Symbol']}")

    # Convert to DataFrame
    round_trips_df = pd.DataFrame(round_trips)

    # Combine round trips with identical EnteredAt and ExitedAt
    grouped = round_trips_df.groupby([
        'EnteredAt', 'ExitedAt', 'ContractName', 'Type', 'EntryPrice', 'ExitPrice'
    ]).agg({
        'Size': 'sum',
        'PnL': 'sum',
        'Fees': 'sum',
        'TradeDay': 'first',
        'TradeDuration': 'first'
    }).reset_index()

    # Assign Ids based on US/Central trade day. Parse in UTC first to handle mixed offsets safely.
    trade_day_ts = pd.to_datetime(
        grouped['TradeDay'],
        format='%m/%d/%Y %H:%M:%S %z',
        errors='coerce',
        utc=True,
    )
    entered_at_ts = pd.to_datetime(
        grouped['EnteredAt'],
        format='%m/%d/%Y %H:%M:%S %z',
        errors='coerce',
        utc=True,
    )
    grouped['TradeDate'] = trade_day_ts.fillna(entered_at_ts).dt.tz_convert('US/Central').dt.date
    grouped = grouped[grouped['TradeDate'].notna()].copy()
    grouped = grouped.sort_values(['TradeDate', 'EnteredAt']).reset_index(drop=True)
    
    # Reset Id for each unique trade date
    grouped['Id'] = 1
    for date in grouped['TradeDate'].unique():
        mask = grouped['TradeDate'] == date
        grouped.loc[mask, 'Id'] = range(1, mask.sum() + 1)

    # Drop temporary TradeDate column
    grouped = grouped.drop(columns=['TradeDate'])

    # Reorder columns
    output_columns = [
        'Id', 'ContractName', 'EnteredAt', 'ExitedAt', 'EntryPrice', 'ExitPrice',
        'Fees', 'PnL', 'Size', 'Type', 'TradeDay', 'TradeDuration'
    ]
    round_trips_df = grouped[output_columns]

    return round_trips_df


def calculate_streaks(df):
    df['WinOrLoss'] = df['PnL'].apply(lambda x: 1 if x > 0 else -1)
    df['Streak'] = 0
    streak_counter = 0

    for i in range(len(df)):
        if i == 0 or df['WinOrLoss'].iloc[i] != df['WinOrLoss'].iloc[i - 1]:
            streak_counter = 1
        else:
            streak_counter += 1
        df.loc[i, 'Streak'] = streak_counter * df['WinOrLoss'].iloc[i]

    return df

def generate_aggregated_data(valid_dataframes):
    past_performance_df = pd.read_csv(PERFORMANCE_CSV) if os.path.exists(PERFORMANCE_CSV) else pd.DataFrame()
    if not past_performance_df.empty:
        past_performance_df = _dedupe_by_trade_signature(past_performance_df, label="past_performance")
        past_performance_df = ensure_trade_id(past_performance_df)
        past_performance_df = merge_trade_labels(past_performance_df)
        past_performance_df['EnteredAt'] = pd.to_datetime(past_performance_df['EnteredAt'], utc=True).dt.tz_convert(TIMEZONE)
        past_performance_df['ExitedAt'] = pd.to_datetime(past_performance_df['ExitedAt'], utc=True).dt.tz_convert(TIMEZONE)
        past_performance_df['TradeDay'] = past_performance_df['EnteredAt'].dt.strftime('%Y-%m-%d')
        past_performance_df['DayOfWeek'] = past_performance_df['EnteredAt'].dt.day_name()
        past_performance_df['YearMonth'] = past_performance_df['EnteredAt'].dt.tz_localize(None).dt.to_period('M')
        past_performance_df['HourOfDay'] = past_performance_df['EnteredAt'].dt.hour

    combined_df = pd.concat(valid_dataframes, ignore_index=True)
    logger.info("All valid files have been successfully concatenated.")
    combined_df['EnteredAt'] = pd.to_datetime(combined_df['EnteredAt'], utc=True).dt.tz_convert(TIMEZONE)
    combined_df['ExitedAt'] = pd.to_datetime(combined_df['ExitedAt'], utc=True).dt.tz_convert(TIMEZONE)
    combined_df['TradeDay'] = pd.to_datetime(combined_df['EnteredAt'], utc=True).dt.tz_convert(TIMEZONE).dt.strftime('%Y-%m-%d')
    combined_df.sort_values(by='EnteredAt', inplace=True)
    combined_df.reset_index(drop=True, inplace=True)
    combined_df = calculate_streaks(combined_df)
    combined_df['DayOfWeek'] = combined_df['EnteredAt'].dt.day_name()
    combined_df['YearMonth'] = combined_df['EnteredAt'].dt.tz_localize(None).dt.to_period('M')
    combined_df['HourOfDay'] = combined_df['EnteredAt'].dt.hour
    combined_df = combined_df.rename(columns={'Id': 'IntradayIndex'})
    combined_df = _dedupe_by_trade_signature(combined_df, label="incoming_combined")
    combined_df = ensure_trade_id(combined_df)

    combined_df = combined_df.rename(columns={'PnL': 'PnL(Net)'})
    combined_df['Comment'] = combined_df.get('Comment', '')
    desired_columns = [
            'trade_id', 'YearMonth', 'TradeDay', 'DayOfWeek', 'HourOfDay', 'ContractName', 'IntradayIndex',
            'EnteredAt', 'ExitedAt', 'EntryPrice', 'ExitPrice', 'Fees', 'PnL(Net)',
            'Size', 'Type', 'TradeDuration', 'WinOrLoss', 'Streak', 'Comment'
        ]
    available_columns = [col for col in desired_columns if col in combined_df.columns]
    combined_df = combined_df[available_columns]

    updated_count = 0
    affected_dates: set[str] = set()
    # Upsert by stable trade_id so broker-corrected financial fields update existing rows.
    if not past_performance_df.empty and "trade_id" in past_performance_df.columns and "trade_id" in combined_df.columns:
        incoming_latest = combined_df.drop_duplicates(subset=["trade_id"], keep="last").copy()
        past_ids = set(past_performance_df["trade_id"].astype(str))
        incoming_ids = set(incoming_latest["trade_id"].astype(str))
        shared_ids = incoming_ids.intersection(past_ids)
        new_ids = incoming_ids.difference(past_ids)
        update_columns = [c for c in incoming_latest.columns if c != "trade_id" and c in past_performance_df.columns]

        if shared_ids and update_columns:
            before = past_performance_df[past_performance_df["trade_id"].astype(str).isin(shared_ids)].copy()
            incoming_map_df = incoming_latest[incoming_latest["trade_id"].astype(str).isin(shared_ids)][
                ["trade_id"] + update_columns
            ].copy()
            incoming_map_df["trade_id"] = incoming_map_df["trade_id"].astype(str)
            for col in update_columns:
                mapping = incoming_map_df.set_index("trade_id")[col]
                past_performance_df[col] = (
                    past_performance_df["trade_id"].astype(str).map(mapping).combine_first(past_performance_df[col])
                )
            after = past_performance_df[past_performance_df["trade_id"].astype(str).isin(shared_ids)][
                ["trade_id"] + update_columns
            ].copy()
            before_norm = before[["trade_id"] + update_columns].fillna("__NA__").astype(str).sort_values("trade_id").reset_index(drop=True)
            after_norm = after.fillna("__NA__").astype(str).sort_values("trade_id").reset_index(drop=True)
            updated_count = int((before_norm[update_columns] != after_norm[update_columns]).any(axis=1).sum())
            for raw_day in list(before.get("TradeDay", pd.Series(dtype="object"))) + list(after.get("TradeDay", pd.Series(dtype="object"))):
                if pd.notna(raw_day):
                    affected_dates.add(str(raw_day))

        new_rows_df = incoming_latest[incoming_latest["trade_id"].astype(str).isin(new_ids)].copy()
        for raw_day in new_rows_df.get("TradeDay", pd.Series(dtype="object")):
            if pd.notna(raw_day):
                affected_dates.add(str(raw_day))
        logger.info("Performance upsert completed: %d updated, %d inserted", updated_count, len(new_rows_df))
    else:
        new_rows_df = combined_df.copy()
        for raw_day in new_rows_df.get("TradeDay", pd.Series(dtype="object")):
            if pd.notna(raw_day):
                affected_dates.add(str(raw_day))

    new_rows_df = merge_trade_labels(new_rows_df)

    # Concatenate old and new
    final_df = pd.concat([past_performance_df, new_rows_df], ignore_index=True)
    final_df = _dedupe_by_trade_signature(final_df, label="final_combined")
    final_df = ensure_trade_id(final_df)
    final_df = merge_trade_labels(final_df)
    final_df = _sort_combined(final_df)
    try:
        sync_trade_journal(final_df)
        logger.info("Trade journal synced with latest combined performance data")
    except (TypeError, ValueError, OSError, KeyError) as e:
        logger.error(f"Failed to sync trade journal: {e}")
    if not new_rows_df.empty:
        print(f"New trades added: {new_rows_df}")
    else:
        logger.info("No new trades to add.")

    # Persist daily trade sums for impacted days only.
    try:
        if affected_dates:
            sync_trade_sum_from_performance_rows(final_df.to_dict(orient="records"), affected_dates)
            logger.info("Updated trade_sum for %d affected day(s)", len(affected_dates))
        else:
            logger.info("No affected trade days; trade_sum not updated")
    except (TypeError, ValueError, OSError, KeyError) as e:
        logger.error(f"Failed to sync trade_sum: {e}")

    # Save and return
    final_df.to_csv(PERFORMANCE_CSV, index=False)
    logger.info(f"Processed data saved to {PERFORMANCE_CSV}")
    return final_df

def round_trip_converter():
    root_dir = TEMP_PERF_DIR
    target_dir = PERFORMANCE_DIR
    Path(target_dir).mkdir(parents=True, exist_ok=True)
    csv_files = glob.glob(str(Path(root_dir) / "*.csv"))
    if not csv_files:
        logger.info("No temp files to convert in %s", root_dir)
        return

    # Process each CSV file
    for file_path in csv_files:
        logger.info("Processing temp performance file: %s", file_path)
        try:
            round_trips_df = process_csv(file_path)
            if round_trips_df.empty:
                logger.warning("No round-trip rows generated from %s; leaving file in place", file_path)
                continue
            round_trips_df["TradeDay"] = pd.to_datetime(round_trips_df["TradeDay"], errors="raise")
            startdate = round_trips_df["TradeDay"].min().date()
            enddate = round_trips_df["TradeDay"].max().date()
            output_filename = os.path.join(target_dir, f"Performance_{startdate}_to_{enddate}.csv")
            round_trips_df.to_csv(output_filename, index=False)
            logger.info("Saved converted performance file: %s", output_filename)
            os.remove(file_path)
        except (pd.errors.ParserError, ValueError, OSError, KeyError) as exc:
            logger.error("Failed to convert temp performance file %s: %s", file_path, exc)


def acquire_missing_performance():
    round_trip_converter()
    """Acquire missing performace data"""
    try:
        all_dataframes = []
        for filename in os.listdir(PERFORMANCE_DIR):
            if filename.startswith('Performance_') and filename.endswith('.csv'):
                file_path = os.path.join(PERFORMANCE_DIR, filename)
                try:
                    df = pd.read_csv(file_path)
                    if not df.empty:
                        all_dataframes.append(df)
                except (pd.errors.ParserError, OSError, ValueError) as e:
                    logger.error(f"Failed to read {filename}: {e}")
        # Concatenate all dataframes
        valid_dataframes = [df for df in all_dataframes if not df.empty]
        if valid_dataframes:
            generate_aggregated_data(valid_dataframes)
        else:
            logger.warning("No valid data was found to concatenate.")
    except Exception:
        logger.exception("Performance merge pipeline failed unexpectedly")
        raise


if __name__ == "__main__":
    acquire_missing_performance()
