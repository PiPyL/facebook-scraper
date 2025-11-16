"""
Advanced cookie management with rotation and health checking.
"""

import pickle
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class CookieManager:
    """
    Manage multiple cookie sets with rotation and health checking.

    Features:
    - Load multiple cookie files
    - Round-robin rotation
    - Health checking
    - Automatic bad cookie filtering
    """

    def __init__(self, cookie_dir: str = '.fb_cookies'):
        """
        Initialize cookie manager.

        Args:
            cookie_dir: Directory to store/load cookies
        """
        self.cookie_dir = Path(cookie_dir)
        self.cookie_dir.mkdir(exist_ok=True)

        self.cookie_pool: List[Dict[str, Any]] = []
        self.current_index = 0

        self.health_check_interval = 3600  # 1 hour
        self.last_health_check: Dict[str, float] = {}

        logger.info(f"CookieManager initialized with directory: {self.cookie_dir}")

    def load_cookie_pool(self, cookie_files: List[str]):
        """
        Load multiple cookie files into pool.

        Args:
            cookie_files: List of cookie file paths
        """
        for cookie_file in cookie_files:
            try:
                cookies = self._load_single_cookie(cookie_file)
                if self._validate_cookies(cookies):
                    cookie_entry = {
                        'cookies': cookies,
                        'file': str(cookie_file),
                        'health': 'unknown',
                        'last_used': None,
                        'error_count': 0,
                        'success_count': 0,
                        'loaded_at': datetime.now().isoformat(),
                    }
                    self.cookie_pool.append(cookie_entry)
                    logger.info(f"Loaded cookies from {cookie_file}")
                else:
                    logger.warning(f"Invalid cookies in {cookie_file}")
            except Exception as e:
                logger.error(f"Failed to load {cookie_file}: {e}")

        logger.info(f"Cookie pool loaded: {len(self.cookie_pool)} sets available")

    def _load_single_cookie(self, cookie_file: str):
        """
        Load cookies from a single file (supports multiple formats).

        Args:
            cookie_file: Path to cookie file

        Returns:
            Loaded cookies

        Raises:
            Exception: If file cannot be loaded
        """
        path = Path(cookie_file)

        if not path.exists():
            raise FileNotFoundError(f"Cookie file not found: {cookie_file}")

        # Pickle format
        if path.suffix in ['.pckl', '.pkl', '.pickle']:
            with open(path, 'rb') as f:
                return pickle.load(f)

        # JSON format
        elif path.suffix == '.json':
            with open(path, 'r') as f:
                return json.load(f)

        # Netscape format
        else:
            from . import utils
            return utils.parse_cookie_file(str(path))

    def _validate_cookies(self, cookies) -> bool:
        """
        Validate that cookies have required fields.

        Args:
            cookies: Cookie object to validate

        Returns:
            True if valid, False otherwise
        """
        required_cookies = ['c_user', 'xs']

        # Handle different cookie formats
        if hasattr(cookies, '__iter__'):
            # CookieJar or list
            if hasattr(cookies, 'keys'):
                cookie_names = list(cookies.keys())
            else:
                cookie_names = [c.name for c in cookies]
        else:
            logger.warning("Unknown cookie format")
            return False

        missing = [name for name in required_cookies if name not in cookie_names]
        if missing:
            logger.warning(f"Missing required cookies: {missing}")
            return False

        return True

    def get_next_cookie(self, force_rotate: bool = False):
        """
        Get next cookie set from pool (round-robin).

        Args:
            force_rotate: Force rotation even if not at end

        Returns:
            Cookie set or None if pool is empty
        """
        if not self.cookie_pool:
            logger.error("Cookie pool is empty!")
            return None

        # Filter out bad/invalid cookies
        healthy_cookies = self.get_healthy_cookies()
        if not healthy_cookies:
            logger.error("No healthy cookies available!")
            # Reset health status and try again
            self._reset_health_status()
            healthy_cookies = self.cookie_pool

        if force_rotate or self.current_index >= len(healthy_cookies):
            self.current_index = 0

        cookie_set = healthy_cookies[self.current_index]
        self.current_index += 1

        cookie_set['last_used'] = datetime.now().isoformat()
        logger.info(
            f"Using cookie set {self.current_index}/{len(healthy_cookies)} "
            f"from {cookie_set['file']}"
        )

        return cookie_set['cookies']

    def mark_cookie_success(self, cookies):
        """
        Mark cookie as successful.

        Args:
            cookies: Cookie object that succeeded
        """
        for cookie_set in self.cookie_pool:
            if cookie_set['cookies'] == cookies:
                cookie_set['success_count'] += 1
                cookie_set['health'] = 'good'
                cookie_set['error_count'] = max(0, cookie_set['error_count'] - 1)
                logger.debug(f"Cookie success: {cookie_set['file']}")
                break

    def mark_cookie_failure(self, cookies, error_type: str = 'generic'):
        """
        Mark cookie as failed.

        Args:
            cookies: Cookie object that failed
            error_type: Type of error ('login_required', 'rate_limit', 'generic')
        """
        for cookie_set in self.cookie_pool:
            if cookie_set['cookies'] == cookies:
                cookie_set['error_count'] += 1

                # Too many errors → mark as bad
                if cookie_set['error_count'] > 5:
                    cookie_set['health'] = 'bad'
                    logger.warning(
                        f"Cookie marked as bad: {cookie_set['file']} "
                        f"(errors: {cookie_set['error_count']})"
                    )

                # Login error → invalid
                if error_type == 'login_required':
                    cookie_set['health'] = 'invalid'
                    logger.error(f"Cookie invalid: {cookie_set['file']}")

                logger.warning(
                    f"Cookie failure ({error_type}): {cookie_set['file']} "
                    f"(total errors: {cookie_set['error_count']})"
                )
                break

    def get_healthy_cookies(self) -> List[Dict[str, Any]]:
        """
        Get only healthy cookie sets.

        Returns:
            List of healthy cookie sets
        """
        return [
            c
            for c in self.cookie_pool
            if c['health'] not in ['bad', 'invalid']
        ]

    def _reset_health_status(self):
        """Reset health status for all cookies (emergency recovery)."""
        for cookie_set in self.cookie_pool:
            if cookie_set['health'] == 'bad':
                cookie_set['health'] = 'unknown'
                cookie_set['error_count'] = 0
        logger.warning("Cookie health status reset")

    def save_pool_stats(self, output_file: str = 'cookie_stats.json'):
        """
        Save cookie pool statistics to file.

        Args:
            output_file: Output filename
        """
        stats = []
        for cookie_set in self.cookie_pool:
            stats.append({
                'file': cookie_set['file'],
                'health': cookie_set['health'],
                'success_count': cookie_set['success_count'],
                'error_count': cookie_set['error_count'],
                'last_used': cookie_set['last_used'],
                'loaded_at': cookie_set['loaded_at'],
            })

        try:
            with open(output_file, 'w') as f:
                json.dump(stats, f, indent=2)
            logger.info(f"Cookie stats saved to {output_file}")
        except Exception as e:
            logger.error(f"Failed to save cookie stats: {e}")

    def get_pool_summary(self) -> Dict[str, Any]:
        """
        Get summary of cookie pool status.

        Returns:
            Dictionary with pool statistics
        """
        healthy = len(self.get_healthy_cookies())
        total = len(self.cookie_pool)

        health_counts = {}
        for cookie_set in self.cookie_pool:
            health = cookie_set['health']
            health_counts[health] = health_counts.get(health, 0) + 1

        return {
            'total_cookies': total,
            'healthy_cookies': healthy,
            'health_distribution': health_counts,
            'current_index': self.current_index,
        }

    def print_status(self):
        """Print cookie pool status to console."""
        summary = self.get_pool_summary()

        print("\n" + "=" * 50)
        print("COOKIE POOL STATUS")
        print("=" * 50)
        print(f"Total cookie sets: {summary['total_cookies']}")
        print(f"Healthy cookies: {summary['healthy_cookies']}")
        print(f"Current index: {summary['current_index']}")
        print(f"\nHealth distribution:")
        for health, count in summary['health_distribution'].items():
            print(f"  {health}: {count}")
        print("=" * 50 + "\n")
