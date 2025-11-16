#!/usr/bin/env python3
"""
Advanced Group Scraping Example

Demonstrates all Phase 2 & 3 features:
- Rate limiting
- Cookie rotation
- Metrics tracking
- Checkpoint/resume
- Auto-adjustment
"""

import logging
from facebook_scraper import FacebookScraper

# Enable debug logging to see what's happening
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    """Scrape Facebook group with all advanced features enabled."""

    # Initialize scraper with all features
    scraper = FacebookScraper(
        # Core features
        enable_rate_limiting=True,
        enable_metrics=True,
        enable_checkpoints=True,
        enable_auto_adjust=True,

        # Cookie rotation (provide multiple cookie files)
        cookie_pool=[
            'cookies1.txt',  # Replace with actual cookie files
            # 'cookies2.txt',
            # 'cookies3.txt',
        ],

        # Custom rate limiting
        rate_limit_config={
            'min_delay': 3.0,      # Minimum 3s between requests
            'max_delay': 10.0,     # Maximum 10s delay
            'adaptive': True,      # Adjust based on errors
            'cooldown_period': 120 # 2 min cooldown if banned
        }
    )

    # Configuration
    GROUP_ID = 123456789  # Replace with your group ID
    PAGES_TO_SCRAPE = 10
    OPERATION_NAME = f"group_{GROUP_ID}_scrape"

    logger.info(f"Starting scrape of group {GROUP_ID}")

    # Check for existing checkpoint
    if scraper.checkpoint_manager:
        checkpoint = scraper.checkpoint_manager.load_checkpoint(f"posts_{OPERATION_NAME}")
        if checkpoint:
            logger.info(f"Found checkpoint! Already collected {checkpoint['posts_collected']} posts")
            resume = input("Resume from checkpoint? (y/n): ")
            if resume.lower() != 'y':
                scraper.checkpoint_manager.delete_checkpoint(f"posts_{OPERATION_NAME}")
                logger.info("Starting fresh")

    try:
        # Scrape posts
        posts = []
        pages_count = 0

        for post in scraper.get_group_posts(
            group=GROUP_ID,
            pages=PAGES_TO_SCRAPE,
            options={
                'comments': True,          # Extract comments
                'allow_extra_requests': True,
                'progress': True           # Show progress bar
            }
        ):
            posts.append(post)
            pages_count = max(pages_count, pages_count + 1)

            logger.info(f"Scraped post {post['post_id']}: {post.get('text', '')[:100]}...")

            # Save checkpoint every 10 posts
            if scraper.checkpoint_manager and len(posts) % 10 == 0:
                from facebook_scraper.checkpoint import PostCheckpoint
                checkpoint = PostCheckpoint(OPERATION_NAME, scraper.checkpoint_manager)
                checkpoint.mark_post_seen(post['post_id'])
                checkpoint.update_progress(len(posts), pages_count)
                checkpoint.save()
                logger.info(f"Checkpoint saved: {len(posts)} posts")

        logger.info(f"Scraping complete! Collected {len(posts)} posts")

        # Print final metrics
        if scraper.metrics:
            print("\n" + "=" * 70)
            scraper.metrics.print_report()

            # Save metrics to file
            scraper.metrics.save_report(f'{OPERATION_NAME}_metrics.json')
            logger.info(f"Metrics saved to {OPERATION_NAME}_metrics.json")

        # Print cookie pool status
        if scraper.cookie_manager:
            scraper.cookie_manager.print_status()
            scraper.cookie_manager.save_pool_stats(f'{OPERATION_NAME}_cookies.json')

        # Get auto-adjuster recommendations
        if scraper.auto_adjuster:
            scraper.auto_adjuster.print_recommendations()

        # Mark checkpoint as completed
        if scraper.checkpoint_manager:
            from facebook_scraper.checkpoint import PostCheckpoint
            checkpoint = PostCheckpoint(OPERATION_NAME, scraper.checkpoint_manager)
            checkpoint.mark_completed()
            checkpoint.save()

        # Save posts to JSON
        import json
        with open(f'{OPERATION_NAME}_posts.json', 'w', encoding='utf-8') as f:
            json.dump(posts, f, indent=2, default=str, ensure_ascii=False)
        logger.info(f"Posts saved to {OPERATION_NAME}_posts.json")

        return posts

    except KeyboardInterrupt:
        logger.warning("\n\nInterrupted by user!")
        logger.info("Progress has been saved. Run again to resume.")

        if scraper.metrics:
            scraper.metrics.print_report()

    except Exception as e:
        logger.error(f"Error during scraping: {e}", exc_info=True)

        if scraper.metrics:
            scraper.metrics.print_report()

        raise


if __name__ == '__main__':
    main()
