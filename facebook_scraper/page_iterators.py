import json
import logging
import re
import textwrap
from typing import Iterator, Optional, Union
import time

from requests.exceptions import HTTPError
import warnings

from . import utils
from .constants import FB_MOBILE_BASE_URL, FB_MBASIC_BASE_URL

from .fb_types import URL, Page, RawPage, RequestFunction, Response
from . import exceptions


logger = logging.getLogger(__name__)


def iter_hashtag_pages(hashtag: str, request_fn: RequestFunction, **kwargs) -> Iterator[Page]:
    start_url = kwargs.pop("start_url", None)
    if not start_url:
        start_url = utils.urljoin(FB_MBASIC_BASE_URL, f'/hashtag/{hashtag}/')
        try:
            request_fn(start_url)
        except Exception as ex:
            logger.error(ex)
    return generic_iter_pages(start_url, HashtagPageParser, request_fn, **kwargs)


def iter_pages(account: str, request_fn: RequestFunction, **kwargs) -> Iterator[Page]:
    start_url = kwargs.pop("start_url", None)
    if not start_url:
        start_url = utils.urljoin(FB_MOBILE_BASE_URL, f'/{account}/')
    return generic_iter_pages(start_url, PageParser, request_fn, **kwargs)


def iter_group_pages(
    group: Union[str, int], request_fn: RequestFunction, **kwargs
) -> Iterator[Page]:
    start_url = kwargs.pop("start_url", None)

    if not start_url:
        start_url = utils.urljoin(FB_MOBILE_BASE_URL, f'groups/{group}/')

    return generic_iter_pages(start_url, GroupPageParser, request_fn, **kwargs)


def iter_search_pages(word: str, request_fn: RequestFunction, **kwargs) -> Iterator[Page]:
    start_url = kwargs.pop("start_url", None)
    if not start_url:
        start_url = utils.urljoin(
            FB_MOBILE_BASE_URL,
            f'/search/posts?q={word}'
            f'&filters=eyJyZWNlbnRfcG9zdHM6MCI6IntcIm5hbWVcIjpcInJlY2VudF9wb3N0c1wiLFwiYXJnc1wiOlwiXCJ9In0%3D',
        )
        try:
            request_fn(start_url)
        except Exception as ex:
            logger.error(ex)
            start_url = utils.urljoin(FB_MOBILE_BASE_URL, f'/search/posts?q={word}')
    return generic_iter_pages(start_url, SearchPageParser, request_fn, **kwargs)


def iter_photos(account: str, request_fn: RequestFunction, **kwargs) -> Iterator[Page]:
    start_url = utils.urljoin(FB_MOBILE_BASE_URL, f'/{account}/photos/')
    return generic_iter_pages(start_url, PhotosPageParser, request_fn, **kwargs)


def generic_iter_pages(
    start_url, page_parser_cls, request_fn: RequestFunction, **kwargs
) -> Iterator[Page]:
    next_url = start_url

    base_url = kwargs.get('base_url', FB_MOBILE_BASE_URL)
    request_url_callback = kwargs.get('request_url_callback')
    while next_url:
        # Execute callback of starting a new URL request
        if request_url_callback:
            request_url_callback(next_url)

        RETRY_LIMIT = 6
        for retry in range(1, RETRY_LIMIT + 1):
            try:
                logger.debug("Requesting page from: %s", next_url)
                response = request_fn(next_url)
                break
            except HTTPError as e:
                if e.response.status_code == 500 and retry < RETRY_LIMIT:
                    sleep_duration = retry * 2
                    logger.debug(
                        f"Caught exception, retry number {retry}. Sleeping for {sleep_duration}s"
                    )
                    if retry == (RETRY_LIMIT / 2):
                        logger.debug("Requesting noscript")
                        kwargs["scraper"].set_noscript(True)
                    time.sleep(sleep_duration)
                else:
                    raise

        logger.debug("Parsing page response")
        parser = page_parser_cls(response)

        page = parser.get_page()

        # TODO: If page is actually an iterable calling len(page) might consume it
        logger.debug("Got %s raw posts from page", len(page))
        yield page

        logger.debug("Looking for next page URL")
        next_page = parser.get_next_page()
        if next_page:
            posts_per_page = kwargs.get("options", {}).get("posts_per_page")
            if posts_per_page:
                next_page = next_page.replace("num_to_fetch=4", f"num_to_fetch={posts_per_page}")
            next_url = utils.urljoin(base_url, next_page)
        else:
            logger.info("Page parser did not find next page URL")
            next_url = None


class PageParser:
    """Class for Parsing a single page on a Page"""

    json_prefix = 'for (;;);'

    cursor_regex = re.compile(r'href[:=]"(/page_content[^"]+)"')  # First request
    cursor_regex_2 = re.compile(r'href"[:=]"(\\/page_content[^"]+)"')  # Other requests
    cursor_regex_3 = re.compile(
        r'href:"(/profile/timeline/stream/\?cursor[^"]+)"'
    )  # scroll/cursor based, first request
    cursor_regex_4 = re.compile(
        r'href\\":\\"\\+(/profile\\+/timeline\\+/stream[^"]+)\"'
    )  # scroll/cursor based, other requests

    def __init__(self, response: Response):
        self.response = response
        self.html = None
        self.cursor_blob = None

        self._parse()

    def get_page(self) -> Page:
        # Select only elements that have the data-ft attribute
        return self._get_page('article[data-ft*="top_level_post_id"]', 'article')

    def get_raw_page(self) -> RawPage:
        return self.html

    def get_next_page(self) -> Optional[URL]:
        assert self.cursor_blob is not None

        match = self.cursor_regex.search(self.cursor_blob)
        if match:
            return utils.unquote(match.groups()[0]).replace("&amp;", "&")

        match = self.cursor_regex_2.search(self.cursor_blob)
        if match:
            value = match.groups()[0]
            return utils.unquote(
                value.encode('utf-8').decode('unicode_escape').replace('\\/', '/')
            ).replace("&amp;", "&")

        match = self.cursor_regex_3.search(self.cursor_blob)
        if match:
            return match.groups()[0]

        match = self.cursor_regex_4.search(self.response.text)
        if match:
            value = match.groups()[0]
            return re.sub(r'\\+/', '/', value)

        return None

    def _parse(self):
        if self.response.text.startswith(self.json_prefix):
            self._parse_json()
        else:
            self._parse_html()

    def _parse_html(self):
        self.html = self.response.html
        self.cursor_blob = self.response.text

    def _parse_json(self):
        prefix_length = len(self.json_prefix)
        data = json.loads(self.response.text[prefix_length:])  # Strip 'for (;;);'

        for action in data.get('payload', data)['actions']:
            if action['cmd'] == 'replace':
                self.html = utils.make_html_element(action['html'], url=FB_MOBILE_BASE_URL)
                self.cursor_blob = self.html.html
            elif action['cmd'] == 'script':
                self.cursor_blob = action['code']

        assert self.html is not None

    def _get_page(self, selection, selection_name) -> Page:
        raw_page = self.get_raw_page()
        raw_posts = raw_page.find(selection)
        for post in raw_posts:
            if not post.find("footer"):
                # Due to malformed HTML served by Facebook, lxml might misinterpret where the footer should go in article elements
                # If we limit the parsing just to the section element, it fixes it
                # Please forgive me for parsing HTML with regex
                logger.warning(f"No footer in article - reparsing HTML within <section> element")
                html = re.search(r'<section.+?>(.+)</section>', raw_page.html).group(1)
                raw_page = utils.make_html_element(html=html)
                raw_posts = raw_page.find(selection)
                break

        if not raw_posts:
            logger.warning(
                "No raw posts (<%s> elements) were found in this page." % selection_name
            )
            if logger.isEnabledFor(logging.DEBUG):
                content = textwrap.indent(
                    raw_page.text,
                    prefix='| ',
                    predicate=lambda _: True,
                )
                sep = '+' + '-' * 60
                logger.debug("The page url is: %s", self.response.url)
                logger.debug("The page content is:\n%s\n%s%s\n", sep, content, sep)

        return raw_posts


class GroupPageParser(PageParser):
    """Enhanced class for parsing group pages with multiple pagination strategies"""

    # Multiple regex patterns for different group layouts
    PAGINATION_PATTERNS = [
        # Pattern 1: Standard group pagination with bac parameter
        re.compile(r'href[=:]"(\/groups\/[^"]+bac=[^"]+)"'),

        # Pattern 2: Cursor-based pagination
        re.compile(r'href[=:]"(\/groups\/[^"]+cursor=[^"]+)"'),

        # Pattern 3: Timeline-based
        re.compile(r'href[=:]"(\/groups\/[^"]+timeline[^"]+)"'),

        # Pattern 4: General groups URL with query params
        re.compile(r'"(\/groups\/\d+\/?\?[^"]*)"'),

        # Pattern 5: AJAX load more
        re.compile(r'data-ajaxify-href="([^"]*\/groups\/[^"]+)"'),

        # Pattern 6: Mobile specific "see more" pattern
        re.compile(r'm_more_item[^"]+href[=:]"([^"]+groups[^"]+)"'),

        # Pattern 7: Encoded slashes version
        re.compile(r'"(\\/groups\\/[^"]+(?:bac|cursor)[^"]*)"'),
    ]

    def get_next_page(self) -> Optional[URL]:
        """Try multiple strategies to find next page URL"""

        # Try parent class methods first (standard pagination)
        next_page = super().get_next_page()
        if next_page:
            logger.debug("Found next page using parent parser")
            return next_page

        assert self.cursor_blob is not None

        # Try all pagination patterns
        for i, pattern in enumerate(self.PAGINATION_PATTERNS):
            match = pattern.search(self.cursor_blob)
            if match:
                url = match.group(1)

                # Decode and normalize URL
                url = url.encode('utf-8').decode('unicode_escape')
                url = url.replace('\\/', '/')
                url = url.replace('&amp;', '&')

                logger.debug(f"Found next page using group pattern {i + 1}: {url[:100]}")
                return url

        # Strategy: Search for "See More" or "Load More" buttons in HTML
        if self.html:
            see_more_links = self.html.find('a[data-sigil*="more"], a:contains("See More"), a:contains("View More")')
            for link in see_more_links:
                href = link.attrs.get('href') or link.attrs.get('data-ajaxify-href')
                if href and 'groups' in href.lower():
                    logger.debug("Found next page via 'See More' button")
                    return href

        # Strategy: Look for AJAX triggers in the blob
        if 'ajaxify' in self.cursor_blob or 'async' in self.cursor_blob:
            ajax_match = re.search(r'"([^"]*groups[^"]*(?:cursor|bac|page)[^"]*)"', self.cursor_blob)
            if ajax_match:
                url = ajax_match.group(1).replace('\\', '')
                logger.debug("Found next page via AJAX trigger")
                return url

        logger.warning("Could not find next page URL with any strategy")
        return None

    def _parse(self):
        """Override to handle both HTML and JSON responses"""
        if self.response.text.startswith(self.json_prefix):
            logger.debug("Parsing JSON response for group")
            self._parse_json()
        else:
            logger.debug("Parsing HTML response for group")
            self._parse_html()


class PhotosPageParser(PageParser):
    cursor_regex = re.compile(r'href:"(/photos/pandora/[^"]+)"')
    cursor_regex_2 = re.compile(r'href":"(\\/photos\\/pandora\\/[^"]+)"')

    def get_page(self) -> Page:
        return super()._get_page('div._5v64', "div._5v64")

    def get_next_page(self) -> Optional[URL]:
        if self.cursor_blob is not None:
            match = self.cursor_regex.search(self.cursor_blob)
            if match:
                return match.groups()[0]

            match = self.cursor_regex_2.search(self.cursor_blob)
            if match:
                value = match.groups()[0]
                return value.encode('utf-8').decode('unicode_escape').replace('\\/', '/')


class SearchPageParser(PageParser):
    cursor_regex = re.compile(r'href[:=]"[^"]+(/search/[^"]+)"')
    cursor_regex_2 = re.compile(r'href":"[^"]+(/search/[^"]+)"')

    def get_next_page(self) -> Optional[URL]:
        if self.cursor_blob is not None:
            match = self.cursor_regex.search(self.cursor_blob)
            if match:
                return match.groups()[0]

            match = self.cursor_regex_2.search(self.cursor_blob)
            if match:
                value = match.groups()[0]
                return value.encode('utf-8').decode('unicode_escape').replace('\\/', '/')


class HashtagPageParser(PageParser):
    cursor_regex = re.compile(r'(\/hashtag\/[a-z]+\/\?cursor=[^"]+).*$')

    def get_page(self) -> Page:
        return super()._get_page('article', 'article')

    def get_next_page(self) -> Optional[URL]:
        assert self.cursor_blob is not None

        match = self.cursor_regex.search(self.cursor_blob)
        if match:
            return utils.unquote(match.groups()[0]).replace("&amp;", "&")

        return None
