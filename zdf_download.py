"""Main module for the ZDF Downloader."""
import os
import re
from typing import List
from datetime import datetime

import logging
import subprocess
import feedparser
import requests
from dateutil import parser


from configuration import Configuration, ShowConfiguration, DownloadConfiguration
from history import History

log = logging.getLogger("zdf-download")


class ZDFDownload():
    """Main-class to handle downloads."""

    def __init__(self, history: History, config: Configuration) -> None:
        self.history: History = history
        self.config: Configuration = config


    def should_download(self, entry, show_config: ShowConfiguration) -> bool:
        """Check if an episode should be downloaded."""
        # check if episode was already downloaded
        if self.history.is_in_history(entry.get("link")):
            log.debug('episode "%s" is in history', entry.get("title"))
            return False

        show_filter = show_config.filter
        if show_filter:

            # check episode-field against regex filter
            regex: str = show_filter.regex
            regex_field: str = show_filter.regex_field
            if (regex and regex_field and not re.search(regex, entry.get(regex_field))):
                log.debug('episode "%s" does not fit regex', entry.get("title"))
                return False

            # check if episode before minimum date
            min_date = show_filter.min_date
            if min_date:
                min_date = parser.parse(min_date)
                entry_date = parser.parse(entry.get("published"))
                if entry_date < min_date:
                    log.debug('episode "%s" is before mindate', entry.get("title"))
                    return False

            if not self.is_episode_released(entry.get("link")):
                log.debug('episode "%s" is not yet released', entry.get("title"))
                return False

        return True


    def is_episode_released(self, url: str) -> bool:
        """Check if an episode has actually been released (rss feed has future episode)."""
        result = requests.get(url)
        return "verfügbar bis" in result.text


    def find_filename(self, download: DownloadConfiguration) -> str:
        """Generate a new filename by adding one to the current newest filename."""
        episode_files: List[str] = list(filter(lambda filename: download.filename in filename and '.mp4' in filename, sorted(os.listdir(download.folder))))
        season = datetime.strftime(datetime.now(), '%y')

        if len(episode_files) > 0:
            newest_filename = os.path.splitext(episode_files[-1])[0]
            regex = re.match(r"^(.* )S(\d+)E(\d+)", newest_filename)
            if season == regex.group(2):
                filename_number: str = regex.group(3)
            else:
                filename_number: str = "00"
            new_episode_number = int(filename_number) + 1
            new_filename: str = "{} S{}E{:0>2d}".format(download.filename, season, new_episode_number)

        else:
            new_filename = download.filename + " S{}E01".format(season)

        return new_filename


    def download_episode(self, url: str, download: DownloadConfiguration):
        """Download episode using youtube-dl."""
        filename = self.find_filename(download)
        download_path = download.folder + "/" + filename + ".%(ext)s"
        try:
            subprocess.run(["youtube-dl", url, "-o", download_path], check=True)
            self.history.add_to_history(url)
        except subprocess.CalledProcessError:
            log.error('error downloading %s', url)

    def check_show(self, show: ShowConfiguration) -> None:
        """Check all episodes of a show for new downloads."""
        feed = feedparser.parse(show.feed_url)
        entries = feed.entries
        entries.reverse()
        for entry in entries:
            if self.should_download(entry, show):
                log.info('downloading episode %s: %s', entry.get("title"), entry.get("link"))
                self.save_thumb(entry, show.download)
                self.write_nfo(entry, show.download)
                self.download_episode(entry.get("link"), show.download)

    def write_nfo(self, entry, download):
        """Write nfo file for episode."""
        filename = self.find_filename(download)
        title = entry.get('title')
        plot = entry.get('description')
        aired = datetime.strptime(entry.get('published'), '%a, %d %b %Y %H:%M:%S %z').strftime('%Y-%m-%d')
        regex = re.match(r".*S(\d+)E(\d+)", filename)
        season = int(regex.group(1))
        episode = int(regex.group(2))
        with open(os.path.join(download.folder, filename) + ".nfo", "w") as f:
            f.write("<?xml version=\"1.0\" encoding=\"utf-8\" standalone=\"yes\"?>\n<episodedetails>\n  <plot>{}</plot>\n  <title>{}</title>\n  <aired>{}</aired>\n  <season>{}</season>\n  <episode>{}</episode>\n</episodedetails>".format(plot, title, aired, season, episode))

    def save_thumb(self, entry, download):
        """Save thumbnail for episode."""
        filename = self.find_filename(download)
        html = requests.get(entry.get('link'))
        thumb_url = re.match(r".*<meta property=\"og:image\"\W+content=\"(.+?)\"", str(html.content)).group(1)
        print(thumb_url)
        thumb = requests.get(thumb_url)
        with open(os.path.join(download.folder, filename) + "-thumb.jpg", 'wb') as f:
            f.write(thumb.content)

    def check_all_shows(self, shows: List[ShowConfiguration]) -> None:
        """Check all shows in configuration for new downloads."""
        log.info("checking all shows")
        for show in shows:
            self.check_show(show)
        log.info("finished checking all shows")
