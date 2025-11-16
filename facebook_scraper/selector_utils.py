"""
Utility for robust element selection with multiple fallback strategies.
"""

import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class RobustElementFinder:
    """
    Find elements using multiple selector strategies with fallbacks.

    Provides intelligent fallback when primary selectors fail due to
    HTML structure changes.
    """

    # Define multiple selector strategies for common elements
    SELECTOR_STRATEGIES = {
        'comments_area': [
            'div[id^="ufi_"]',                    # Primary
            'div[data-sigil="ufi"]',              # Fallback 1
            'div.ufi',                             # Fallback 2
            'div[role="article"] + div',           # Fallback 3
            'footer + div',                        # Fallback 4
            'div[id*="comment"]',                  # Fallback 5
        ],
        'comments': [
            'div[data-sigil="comment"]',           # Primary
            'div.comment',                         # Fallback 1
            'div[id^="comment_"]',                 # Fallback 2
            'div[class*="comment"]',               # Fallback 3
            'div[data-ft*="comment"]',             # Fallback 4
        ],
        'comment_text': [
            '[data-sigil="comment-body"]',         # Primary
            'div._14ye',                           # Fallback 1
            'div.bl',                              # Fallback 2
            'div[class*="text"]',                  # Fallback 3
            'div>div>div',                         # Fallback 4 (generic)
        ],
        'comment_author': [
            'h3',                                  # Primary
            'h3 a',                                # Fallback 1
            'a.actor-link',                        # Fallback 2
            '[data-sigil="comment-author"]',      # Fallback 3
        ],
        'next_comments': [
            'div#see_next_{post_id} a',           # Primary
            'div#see_prev_{post_id} a',           # Fallback 1
            'a[data-sigil="more"]',               # Fallback 2
            'a:contains("View more comments")',   # Fallback 3
            'a:contains("See more")',             # Fallback 4
            'a[href*="comment"]',                 # Fallback 5
        ],
        'post_text': [
            'div[data-ft]',                       # Primary
            'div.story_body_container',           # Fallback 1
            'div.msg',                            # Fallback 2
            'div[class*="text"]',                 # Fallback 3
        ],
        'post_author': [
            'h3 strong a',                        # Primary
            'a.actor-link',                       # Fallback 1
            'h3 a',                               # Fallback 2
            '[data-sigil="post-author"]',         # Fallback 3
        ],
        'post_timestamp': [
            'abbr',                               # Primary
            'abbr[data-utime]',                   # Fallback 1
            'abbr[data-store]',                   # Fallback 2
            'span[data-utime]',                   # Fallback 3
        ],
        'reactions': [
            'div[data-sigil="reactions-bling-bar"]',  # Primary
            'div[class*="reaction"]',             # Fallback 1
            'div[id*="like"]',                    # Fallback 2
        ],
        'shares_count': [
            'a[href*="sharer"]',                  # Primary
            'a:contains("Share")',                # Fallback 1
            '[data-sigil="share"]',               # Fallback 2
        ],
    }

    @classmethod
    def find_element(
        cls,
        parent,
        selector_key: str,
        first: bool = True,
        **format_kwargs
    ) -> Optional[Any]:
        """
        Find element using multiple selector strategies.

        Args:
            parent: Parent element to search within
            selector_key: Key for selector strategy
            first: Return first match only
            **format_kwargs: Variables for selector formatting (e.g., post_id)

        Returns:
            Found element(s) or None
        """
        selectors = cls.SELECTOR_STRATEGIES.get(selector_key, [selector_key])

        for i, selector in enumerate(selectors):
            try:
                # Format selector with dynamic values
                formatted_selector = selector.format(**format_kwargs)

                # Try to find element
                if first:
                    elem = parent.find(formatted_selector, first=True)
                    if elem:
                        if i > 0:
                            logger.info(
                                f"Selector fallback {i} worked for '{selector_key}': {formatted_selector}"
                            )
                        return elem
                else:
                    elems = parent.find(formatted_selector)
                    if elems:
                        if i > 0:
                            logger.info(
                                f"Selector fallback {i} worked for '{selector_key}': {formatted_selector}"
                            )
                        return elems

            except Exception as e:
                logger.debug(f"Selector '{selector}' failed for '{selector_key}': {e}")
                continue

        logger.warning(f"All selectors failed for '{selector_key}'")
        return None

    @classmethod
    def find_elements(
        cls,
        parent,
        selector_key: str,
        **format_kwargs
    ) -> List[Any]:
        """
        Find multiple elements using selector strategies.

        Args:
            parent: Parent element to search within
            selector_key: Key for selector strategy
            **format_kwargs: Variables for selector formatting

        Returns:
            List of found elements (empty if none found)
        """
        result = cls.find_element(parent, selector_key, first=False, **format_kwargs)
        return list(result) if result else []

    @classmethod
    def add_selector_strategy(cls, key: str, selectors: List[str]):
        """
        Add or update a selector strategy.

        Args:
            key: Strategy key
            selectors: List of selectors (ordered by priority)
        """
        cls.SELECTOR_STRATEGIES[key] = selectors
        logger.info(f"Added/updated selector strategy for '{key}' with {len(selectors)} selectors")

    @classmethod
    def get_selector_stats(cls) -> Dict[str, int]:
        """
        Get statistics about selector strategies.

        Returns:
            Dictionary with strategy counts
        """
        return {
            key: len(selectors)
            for key, selectors in cls.SELECTOR_STRATEGIES.items()
        }


class SmartTextExtractor:
    """
    Intelligently extract text from elements using heuristics.
    """

    @staticmethod
    def extract_text(element, prefer_longest: bool = True) -> str:
        """
        Extract text from element using smart heuristics.

        Args:
            element: HTML element
            prefer_longest: Prefer longest text block if multiple found

        Returns:
            Extracted text
        """
        if not element:
            return ""

        # Strategy 1: Try specific text containers first
        text_containers = element.find('div, span, p')

        if text_containers:
            texts = []
            for container in text_containers:
                text = container.text.strip()
                if len(text) > 10:  # Meaningful content
                    texts.append(text)

            if texts:
                if prefer_longest:
                    # Return longest text block
                    return max(texts, key=len)
                else:
                    # Return first text block
                    return texts[0]

        # Strategy 2: Fallback to element text
        text = element.text.strip()
        if text:
            return text

        # Strategy 3: Try to extract from HTML
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(element.html, 'html.parser')
            # Remove script and style tags
            for script in soup(['script', 'style']):
                script.decompose()
            text = soup.get_text(separator=' ', strip=True)
            if text:
                return text
        except Exception as e:
            logger.debug(f"BeautifulSoup extraction failed: {e}")

        return ""

    @staticmethod
    def clean_text(text: str) -> str:
        """
        Clean extracted text.

        Args:
            text: Raw text

        Returns:
            Cleaned text
        """
        if not text:
            return ""

        # Remove excessive whitespace
        import re
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()

        return text
