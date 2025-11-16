#!/usr/bin/env python3
"""
Comments Extraction with Checkpoint/Resume

Demonstrates extracting all comments from a post with
checkpoint/resume capability for long-running operations.
"""

import logging
from facebook_scraper import FacebookScraper
from facebook_scraper.checkpoint import CommentCheckpoint

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def extract_all_comments(scraper, post_id: str, use_checkpoint: bool = True):
    """
    Extract all comments from a post with checkpoint/resume.

    Args:
        scraper: FacebookScraper instance
        post_id: Post ID to extract comments from
        use_checkpoint: Use checkpoint/resume functionality
    """

    checkpoint = None
    if use_checkpoint and scraper.checkpoint_manager:
        checkpoint = CommentCheckpoint(post_id, scraper.checkpoint_manager)

        if not checkpoint.data['completed']:
            stats = checkpoint.get_stats()
            logger.info(
                f"Found checkpoint: {stats['comments_collected']} comments already collected"
            )

            resume = input("Resume from checkpoint? (y/n): ")
            if resume.lower() != 'y':
                checkpoint.delete()
                checkpoint = CommentCheckpoint(post_id, scraper.checkpoint_manager)
                logger.info("Starting fresh")
        else:
            logger.info("Checkpoint shows operation already completed")
            return []

    try:
        # Get post with comments
        from facebook_scraper import get_posts

        logger.info(f"Fetching post {post_id} with comments...")

        post = next(get_posts(
            post_urls=[post_id],
            options={
                'comments': True,  # Enable comment extraction
                'comment_reactors': False,  # Disable for faster extraction
            },
            cookies='cookies.txt'
        ))

        comments = post.get('comments_full', [])
        logger.info(f"Extracted {len(comments)} top-level comments")

        # Save checkpoint
        if checkpoint:
            checkpoint.update_progress(len(comments))
            checkpoint.mark_completed()
            logger.info("Checkpoint marked as completed")

        # Print summary
        total_replies = sum(len(c.get('replies', [])) for c in comments)
        logger.info(f"Total comments: {len(comments)}")
        logger.info(f"Total replies: {total_replies}")
        logger.info(f"Total items: {len(comments) + total_replies}")

        return comments

    except Exception as e:
        logger.error(f"Error extracting comments: {e}")

        # Save checkpoint even on error
        if checkpoint and len(comments) > 0:
            checkpoint.update_progress(len(comments))
            logger.info("Progress saved to checkpoint")

        raise


def main():
    """Main function."""

    scraper = FacebookScraper(
        enable_checkpoints=True,
        enable_rate_limiting=True,
        enable_metrics=True,
        cookie_pool=['cookies.txt']
    )

    POST_ID = "1234567890"  # Replace with actual post ID

    logger.info(f"Extracting comments from post {POST_ID}")

    comments = extract_all_comments(scraper, POST_ID, use_checkpoint=True)

    # Save to file
    if comments:
        import json
        filename = f'comments_{POST_ID}.json'
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(comments, f, indent=2, default=str, ensure_ascii=False)
        logger.info(f"Comments saved to {filename}")

    # Print metrics
    if scraper.metrics:
        scraper.metrics.print_report()


if __name__ == '__main__':
    main()
