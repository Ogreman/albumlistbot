import re

from albumlistbot import constants


def scrape_links_from_text(text):
    return [url for url in re.findall(constants.URL_REGEX, text)]