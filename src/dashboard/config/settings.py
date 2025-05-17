# config/settings.py
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PERFORMANCE_DIR = os.path.join(BASE_DIR, '../../' , 'data', 'performance')
FUTURE_DIR = os.path.join(BASE_DIR, '../../' , 'data', 'future', 'aggregated')

PERFORMANCE_CSV = os.path.normpath(os.path.join(PERFORMANCE_DIR, 'Combined_Performance_with_Streaks.csv'))
MES_CSV = os.path.normpath(os.path.join(FUTURE_DIR, 'MES.csv'))
MNQ_CSV = os.path.normpath(os.path.join(FUTURE_DIR, 'MNQ.csv'))
MGC_CSV = os.path.normpath(os.path.join(FUTURE_DIR, 'MGC.csv'))


DEBUG = True
PORT = 8050
TIMEZONE = 'Europe/Helsinki'