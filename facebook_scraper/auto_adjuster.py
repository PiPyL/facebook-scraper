"""
Auto-adjustment system that dynamically tunes scraper parameters based on performance.
"""

import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class AutoAdjuster:
    """
    Automatically adjust scraper parameters based on real-time metrics.

    Monitors:
    - Success rates
    - Error patterns
    - Response times
    - Ban detection

    Adjusts:
    - Rate limiting delays
    - Cookie rotation frequency
    - Request retry parameters
    """

    def __init__(self, scraper, adjustment_interval: int = 50):
        """
        Initialize auto-adjuster.

        Args:
            scraper: FacebookScraper instance
            adjustment_interval: Adjust after this many requests
        """
        self.scraper = scraper
        self.adjustment_interval = adjustment_interval
        self.request_count = 0

        # Thresholds for adjustments
        self.success_rate_low = 70.0  # Below this, increase caution
        self.success_rate_high = 90.0  # Above this, can be more aggressive
        self.error_rate_high = 30.0  # Above this, be very cautious

        logger.info(f"AutoAdjuster initialized (interval={adjustment_interval})")

    def should_adjust(self) -> bool:
        """
        Check if it's time to adjust parameters.

        Returns:
            True if adjustment should be performed
        """
        self.request_count += 1
        return self.request_count % self.adjustment_interval == 0

    def auto_adjust(self):
        """
        Perform automatic parameter adjustment based on metrics.
        """
        if not self.scraper.metrics:
            logger.warning("No metrics available for auto-adjustment")
            return

        metrics = self.scraper.metrics

        # Get success rates
        request_success_rate = metrics.get_success_rate('http_request')
        post_success_rate = metrics.get_success_rate('extract_post')
        comment_success_rate = metrics.get_success_rate('extract_comments')

        logger.info(
            f"Auto-adjust check: "
            f"requests={request_success_rate:.1f}%, "
            f"posts={post_success_rate:.1f}%, "
            f"comments={comment_success_rate:.1f}%"
        )

        # Adjust rate limiter
        self._adjust_rate_limiter(request_success_rate)

        # Adjust cookie rotation
        self._adjust_cookie_rotation(request_success_rate)

        # Adjust circuit breaker
        self._adjust_circuit_breaker(request_success_rate)

    def _adjust_rate_limiter(self, success_rate: float):
        """
        Adjust rate limiter parameters.

        Args:
            success_rate: Current success rate percentage
        """
        if not self.scraper.rate_limiter:
            return

        rate_limiter = self.scraper.rate_limiter
        current_min = rate_limiter.min_delay
        current_max = rate_limiter.max_delay

        if success_rate < self.success_rate_low:
            # Low success - slow down significantly
            new_min = min(current_min * 1.5, 10.0)
            new_max = min(current_max * 1.5, 20.0)
            rate_limiter.min_delay = new_min
            rate_limiter.max_delay = new_max
            rate_limiter.current_delay = new_min

            logger.warning(
                f"Low success rate ({success_rate:.1f}%). "
                f"Increased delays: min={new_min:.2f}s, max={new_max:.2f}s"
            )

        elif success_rate > self.success_rate_high:
            # High success - can be slightly more aggressive
            new_min = max(current_min * 0.9, 1.5)  # Don't go below 1.5s
            new_max = max(current_max * 0.9, 5.0)  # Don't go below 5s
            rate_limiter.min_delay = new_min
            rate_limiter.max_delay = new_max

            logger.info(
                f"High success rate ({success_rate:.1f}%). "
                f"Decreased delays: min={new_min:.2f}s, max={new_max:.2f}s"
            )

    def _adjust_cookie_rotation(self, success_rate: float):
        """
        Adjust cookie rotation behavior.

        Args:
            success_rate: Current success rate percentage
        """
        if not self.scraper.cookie_manager:
            return

        if success_rate < 60.0:
            # Very low success - try rotating cookies
            logger.warning(
                f"Very low success rate ({success_rate:.1f}%). "
                "Attempting cookie rotation..."
            )
            self.scraper.rotate_cookies()

    def _adjust_circuit_breaker(self, success_rate: float):
        """
        Adjust circuit breaker parameters.

        Args:
            success_rate: Current success rate percentage
        """
        if not self.scraper.circuit_breaker:
            return

        circuit_breaker = self.scraper.circuit_breaker

        if success_rate < self.success_rate_low:
            # Lower threshold for opening circuit
            circuit_breaker.failure_threshold = max(3, circuit_breaker.failure_threshold - 1)
            logger.info(
                f"Lowered circuit breaker threshold to {circuit_breaker.failure_threshold}"
            )

        elif success_rate > self.success_rate_high:
            # Increase threshold (more tolerant)
            circuit_breaker.failure_threshold = min(7, circuit_breaker.failure_threshold + 1)
            logger.debug(
                f"Raised circuit breaker threshold to {circuit_breaker.failure_threshold}"
            )

    def get_recommendations(self) -> Dict[str, Any]:
        """
        Get recommendations for manual adjustment.

        Returns:
            Dictionary with recommendations
        """
        if not self.scraper.metrics:
            return {'error': 'No metrics available'}

        metrics = self.scraper.metrics
        recommendations = []

        # Check request success rate
        request_success_rate = metrics.get_success_rate('http_request')

        if request_success_rate < 50:
            recommendations.append({
                'severity': 'critical',
                'message': 'Very low request success rate',
                'suggestions': [
                    'Check if cookies are still valid',
                    'Increase rate limiting delays',
                    'Consider using proxies',
                    'Verify account is not banned'
                ]
            })
        elif request_success_rate < 70:
            recommendations.append({
                'severity': 'warning',
                'message': 'Below average request success rate',
                'suggestions': [
                    'Increase delays between requests',
                    'Rotate cookies if available',
                    'Check for temporary bans'
                ]
            })

        # Check error patterns
        total_errors = len(metrics.errors)
        if total_errors > 50:
            # Analyze error types
            error_types = {}
            for error in metrics.errors[-50:]:  # Last 50 errors
                error_type = error['error_type']
                error_types[error_type] = error_types.get(error_type, 0) + 1

            most_common = max(error_types, key=error_types.get) if error_types else None

            if most_common:
                recommendations.append({
                    'severity': 'warning',
                    'message': f'High error count ({total_errors})',
                    'most_common_error': most_common,
                    'suggestions': [
                        f'Most common error: {most_common}',
                        'Review recent error logs',
                        'Consider pausing and resuming later'
                    ]
                })

        # Check rate limiter stats
        if self.scraper.rate_limiter:
            rl_stats = self.scraper.rate_limiter.get_stats()
            if rl_stats['consecutive_errors'] >= 3:
                recommendations.append({
                    'severity': 'warning',
                    'message': 'Multiple consecutive errors detected',
                    'suggestions': [
                        'Rate limiter has detected issues',
                        'Consider increasing delays',
                        'May be experiencing throttling'
                    ]
                })

        # Check cookie health
        if self.scraper.cookie_manager:
            summary = self.scraper.cookie_manager.get_pool_summary()
            healthy_ratio = summary['healthy_cookies'] / max(summary['total_cookies'], 1)

            if healthy_ratio < 0.5:
                recommendations.append({
                    'severity': 'critical',
                    'message': 'Most cookies are unhealthy',
                    'suggestions': [
                        'Refresh cookie files',
                        'Login with different accounts',
                        'Check for account bans'
                    ]
                })

        return {
            'success_rate': request_success_rate,
            'total_errors': total_errors,
            'recommendations': recommendations,
            'auto_adjustments_applied': self.request_count // self.adjustment_interval
        }

    def print_recommendations(self):
        """Print recommendations to console."""
        rec = self.get_recommendations()

        print("\n" + "=" * 60)
        print("AUTO-ADJUSTER RECOMMENDATIONS")
        print("=" * 60)
        print(f"Success Rate: {rec.get('success_rate', 0):.1f}%")
        print(f"Total Errors: {rec.get('total_errors', 0)}")
        print(f"Auto-adjustments Applied: {rec.get('auto_adjustments_applied', 0)}")

        recommendations = rec.get('recommendations', [])

        if not recommendations:
            print("\n✓ Everything looks good!")
        else:
            print(f"\n⚠ {len(recommendations)} recommendation(s):")
            for i, r in enumerate(recommendations, 1):
                severity = r['severity'].upper()
                print(f"\n{i}. [{severity}] {r['message']}")
                print("   Suggestions:")
                for suggestion in r.get('suggestions', []):
                    print(f"   - {suggestion}")

        print("=" * 60 + "\n")
