"""Main module for the ZDF Downloader."""
import logging
import os
import time

import schedule

from configuration import Configuration, load_configuration_from_yaml
from history import History
from zdf_download import ZDFDownload


def main() -> None:


    config: Configuration = load_configuration_from_yaml("configuration/configuration.yaml")
    history: History = History("configuration/history.yaml")
    zdf_downloader: ZDFDownload = ZDFDownload(history=history, config=config)

    log = logging.getLogger("zdf-download")
    if os.environ.get("DEBUG", False) == "True":
        log.setLevel(logging.DEBUG)
    else:
        log.setLevel(logging.INFO)
    log.info("launching application")

    schedule.every(config.interval).minutes.do(zdf_downloader.check_all_shows, shows=config.shows)
    schedule.run_all()

    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == '__main__':
    main()
