#!/usr/bin/env python3
"""
Monitoring Example

Demonstrates real-time monitoring of scraping performance
and automatic adjustments.
"""

import logging
import time
from facebook_scraper import FacebookScraper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Monitor scraping performance in real-time."""

    # Initialize with monitoring
    scraper = FacebookScraper(
        enable_rate_limiting=True,
        enable_metrics=True,
        enable_auto_adjust=True,
        cookie_pool=['cookies.txt']
    )

    GROUP_ID = 123456789  # Replace with actual group ID

    logger.info("Starting monitored scraping...")

    posts_collected = 0
    start_time = time.time()

    try:
        for post in scraper.get_group_posts(group=GROUP_ID, pages=5):
            posts_collected += 1

            # Print stats every 5 posts
            if posts_collected % 5 == 0:
                runtime = time.time() - start_time

                print(f"\n{'='*60}")
                print(f"Progress Update - {posts_collected} posts collected")
                print(f"Runtime: {runtime:.2f}s")

                # Rate limiter stats
                if scraper.rate_limiter:
                    rl_stats = scraper.rate_limiter.get_stats()
                    print(f"\nRate Limiter:")
                    print(f"  Success rate: {rl_stats['success_rate']:.1f}%")
                    print(f"  Current delay: {rl_stats['current_delay']:.2f}s")
                    print(f"  Consecutive errors: {rl_stats['consecutive_errors']}")

                # Metrics summary
                if scraper.metrics:
                    summary = scraper.metrics.get_stats_summary()
                    print(f"\nMetrics: {summary}")

                # Cookie health
                if scraper.cookie_manager:
                    summary = scraper.cookie_manager.get_pool_summary()
                    print(f"\nCookie Pool:")
                    print(f"  Total: {summary['total_cookies']}")
                    print(f"  Healthy: {summary['healthy_cookies']}")

                # Auto-adjuster recommendations
                if scraper.auto_adjuster and posts_collected % 20 == 0:
                    print("\nAuto-Adjuster Recommendations:")
                    rec = scraper.auto_adjuster.get_recommendations()
                    for r in rec.get('recommendations', [])[:3]:  # Show top 3
                        print(f"  [{r['severity']}] {r['message']}")

                print(f"{'='*60}\n")

        # Final report
        print("\n" + "="*70)
        print("FINAL REPORT")
        print("="*70)

        if scraper.metrics:
            scraper.metrics.print_report()

        if scraper.auto_adjuster:
            scraper.auto_adjuster.print_recommendations()

    except KeyboardInterrupt:
        logger.warning("\nStopped by user")

        if scraper.metrics:
            scraper.metrics.print_report()


if __name__ == '__main__':
    main()
