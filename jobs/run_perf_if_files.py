import glob
import logging

from dashboard.config.env import LOGGING_PATH, TEMP_PERF_DIR
from dashboard.config.settings import PERFORMANCE_CSV
from dashboard.services.utils.performance_acquisition import acquire_missing_performance


logging.basicConfig(
    filename=LOGGING_PATH,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    pattern = str(TEMP_PERF_DIR / "*.csv")
    temp_files = glob.glob(pattern)
    if temp_files:
        logger.info("Found %d temp performance file(s) in %s", len(temp_files), TEMP_PERF_DIR)
        acquire_missing_performance()
        logger.info("Performance merge completed. Combined output: %s", PERFORMANCE_CSV)
    else:
        logger.info("No temp performance files found in %s", TEMP_PERF_DIR)


if __name__ == "__main__":
    main()
