"""
Smart content detection using heuristic-based pattern matching.

This module provides intelligent detection of Facebook elements when
standard selectors fail due to HTML structure changes.
"""

import re
import logging
from typing import Optional, List, Tuple
from collections import Counter

logger = logging.getLogger(__name__)


class SmartContentDetector:
    """
    Heuristic-based content detection for robust scraping.

    Uses multiple signals to identify content even when HTML structure changes.
    """

    @staticmethod
    def find_comments_area(html_element) -> Optional[object]:
        """
        Use heuristics to find comments area.

        Scoring criteria:
        - Contains 'comment' in ID or class
        - Contains 'ufi' (unified feedback interface)
        - Has multiple child divs (likely comments)
        - Contains timestamps (abbr tags)
        - Contains profile pictures

        Args:
            html_element: HTML element to search within

        Returns:
            Element most likely to be comments area, or None
        """
        candidates = []

        # Find all divs as potential candidates
        all_divs = html_element.find('div')

        for div in all_divs:
            score = 0
            div_html = div.html.lower() if hasattr(div, 'html') else ''
            div_id = div.attrs.get('id', '').lower()
            div_class = ' '.join(div.attrs.get('class', [])).lower() if div.attrs.get('class') else ''

            # Scoring criteria
            if 'comment' in div_id:
                score += 3
            if 'comment' in div_class:
                score += 2
            if 'ufi' in div_id:
                score += 3
            if 'ufi' in div_class:
                score += 2

            # Check for structural patterns
            children = div.find('div')
            if 5 < len(children) < 200:  # Reasonable number of comments
                score += 2

            # Check for timestamps (common in comments)
            abbr_tags = div.find('abbr')
            if len(abbr_tags) > 3:
                score += 2

            # Check for profile pictures
            if 'profpic' in div_html or 'profile' in div_html:
                score += 1

            # Check for comment-like text patterns
            if 'reply' in div_html or 'like' in div_html:
                score += 1

            if score >= 5:  # Threshold for being comments area
                candidates.append((div, score))

        if candidates:
            # Sort by score and return highest
            candidates.sort(key=lambda x: x[1], reverse=True)
            logger.info(f"Found comments area with score {candidates[0][1]}")
            return candidates[0][0]

        return None

    @staticmethod
    def extract_comment_text_smart(comment_elem) -> str:
        """
        Extract comment text using heuristics.

        Strategy: Find longest meaningful text block

        Args:
            comment_elem: Comment element

        Returns:
            Extracted text
        """
        text_blocks = []

        # Find all potential text containers
        for elem in comment_elem.find('div, span, p'):
            text = elem.text.strip()
            # Filter meaningful content (not too short, not too long)
            if 10 < len(text) < 10000:
                text_blocks.append((text, len(text)))

        if text_blocks:
            # Return longest text block (likely the actual comment)
            text_blocks.sort(key=lambda x: x[1], reverse=True)
            return text_blocks[0][0]

        # Fallback to element text
        return comment_elem.text.strip()

    @staticmethod
    def detect_pagination_url(html_text: str, context: str = 'group') -> Optional[str]:
        """
        Detect pagination URL using ML-like pattern scoring.

        Args:
            html_text: HTML text to search
            context: Context ('group', 'comment', 'post')

        Returns:
            Most likely pagination URL or None
        """
        # Extract all potential URLs
        url_pattern = re.compile(r'(?:href|url|data-ajaxify-href)[=:]["\'](\/[^"\']+)["\']')
        urls = url_pattern.findall(html_text)

        if not urls:
            return None

        # Score URLs based on pagination likelihood
        scored_urls = []

        # Context-specific keywords
        keywords_map = {
            'group': ['group', 'bac', 'cursor', 'more', 'next'],
            'comment': ['comment', 'reply', 'more', 'see', 'view'],
            'post': ['story', 'post', 'cursor', 'page', 'more'],
        }

        pagination_keywords = keywords_map.get(context, ['more', 'next', 'cursor'])

        for url in urls:
            score = 0
            url_lower = url.lower()

            # Keyword matching
            for keyword in pagination_keywords:
                if keyword in url_lower:
                    score += 3

            # Pattern matching
            if 'cursor=' in url or 'page=' in url or 'offset=' in url:
                score += 5

            if 'bac=' in url:  # Facebook group pagination
                score += 5

            # Contains numbers (likely pagination)
            if re.search(r'\d+', url):
                score += 1

            # Context-specific boosts
            if context in url_lower:
                score += 3

            # Length heuristic (pagination URLs tend to be longer)
            if len(url) > 50:
                score += 1

            if score >= 5:  # Threshold
                scored_urls.append((url, score))

        if scored_urls:
            # Return highest scoring URL
            scored_urls.sort(key=lambda x: x[1], reverse=True)
            logger.debug(f"Found pagination URL with score {scored_urls[0][1]}: {scored_urls[0][0][:100]}")
            return scored_urls[0][0]

        return None

    @staticmethod
    def identify_element_type(element) -> str:
        """
        Identify what type of element this is.

        Args:
            element: HTML element

        Returns:
            Element type ('comment', 'post', 'reaction', 'unknown')
        """
        html = element.html.lower() if hasattr(element, 'html') else ''
        elem_id = element.attrs.get('id', '').lower()
        elem_class = ' '.join(element.attrs.get('class', [])).lower() if element.attrs.get('class') else ''

        # Scoring for different types
        scores = {
            'comment': 0,
            'post': 0,
            'reaction': 0,
            'ad': 0,
        }

        # Comment signals
        if 'comment' in elem_id or 'comment' in elem_class:
            scores['comment'] += 5
        if 'reply' in html or 'replied' in html:
            scores['comment'] += 2

        # Post signals
        if 'story' in elem_id or 'post' in elem_id:
            scores['post'] += 5
        if 'top_level_post' in html:
            scores['post'] += 5
        if element.find('h3'):  # Posts usually have h3 for author
            scores['post'] += 2

        # Reaction signals
        if 'reaction' in elem_id or 'reaction' in elem_class:
            scores['reaction'] += 5
        if 'like' in html or 'love' in html or 'haha' in html:
            scores['reaction'] += 2

        # Ad signals (to filter out)
        if 'sponsor' in html or 'promoted' in html:
            scores['ad'] += 10

        # Return type with highest score
        if scores['ad'] >= 5:
            return 'ad'

        max_score = max(scores.values())
        if max_score >= 5:
            return max(scores, key=scores.get)

        return 'unknown'

    @staticmethod
    def extract_timestamp_smart(element) -> Optional[str]:
        """
        Extract timestamp using heuristics.

        Args:
            element: HTML element

        Returns:
            Timestamp string or None
        """
        # Strategy 1: Look for abbr tags (most common)
        abbr_tags = element.find('abbr')
        for abbr in abbr_tags:
            # Check for data-utime or data-store attributes
            if abbr.attrs.get('data-utime'):
                return abbr.attrs['data-utime']
            if abbr.attrs.get('data-store'):
                return abbr.attrs['data-store']
            # Fallback to text
            if abbr.text:
                return abbr.text

        # Strategy 2: Look for span with data-utime
        spans = element.find('span[data-utime]')
        if spans:
            return spans[0].attrs['data-utime']

        # Strategy 3: Look for time tags
        time_tags = element.find('time')
        if time_tags:
            return time_tags[0].attrs.get('datetime', time_tags[0].text)

        return None


class ContentValidator:
    """
    Validate extracted content for quality and completeness.
    """

    @staticmethod
    def is_valid_post(post_data: dict) -> Tuple[bool, List[str]]:
        """
        Validate post data.

        Args:
            post_data: Post dictionary

        Returns:
            (is_valid, list_of_issues)
        """
        issues = []

        # Check required fields
        if not post_data.get('post_id'):
            issues.append("Missing post_id")

        if not post_data.get('text') and not post_data.get('post_text'):
            issues.append("Missing text content")

        # Check for suspicious patterns (might be ads or errors)
        text = post_data.get('text', '') or post_data.get('post_text', '')
        if 'sponsored' in text.lower():
            issues.append("Appears to be sponsored content")

        return (len(issues) == 0, issues)

    @staticmethod
    def is_valid_comment(comment_data: dict) -> Tuple[bool, List[str]]:
        """
        Validate comment data.

        Args:
            comment_data: Comment dictionary

        Returns:
            (is_valid, list_of_issues)
        """
        issues = []

        # Check required fields
        if not comment_data.get('comment_text'):
            issues.append("Missing comment text")

        if not comment_data.get('commenter_name'):
            issues.append("Missing commenter name")

        # Check text quality
        text = comment_data.get('comment_text', '')
        if len(text) < 1:
            issues.append("Comment text too short")

        return (len(issues) == 0, issues)

    @staticmethod
    def deduplicate_posts(posts: List[dict]) -> List[dict]:
        """
        Remove duplicate posts based on post_id.

        Args:
            posts: List of post dictionaries

        Returns:
            Deduplicated list
        """
        seen_ids = set()
        unique_posts = []

        for post in posts:
            post_id = post.get('post_id')
            if post_id and post_id not in seen_ids:
                seen_ids.add(post_id)
                unique_posts.append(post)

        removed = len(posts) - len(unique_posts)
        if removed > 0:
            logger.info(f"Removed {removed} duplicate posts")

        return unique_posts
