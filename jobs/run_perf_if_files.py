import glob
from dashboard.services.utils.performance_acquisition import acquire_missing_performance


def main():
    if glob.glob("/app/data/temp_performance/*.csv"):
        acquire_missing_performance()


if __name__ == "__main__":
    main()
