#!/usr/bin/env python3
"""
Simple Usage Example

Basic usage with default improvements enabled.
All Phase 1 features work automatically without configuration.
"""

from facebook_scraper import get_posts

def main():
    """Simple scraping with automatic improvements."""

    # Basic usage - all improvements enabled by default
    print("Scraping Nintendo page...")

    posts = list(get_posts(
        'nintendo',
        pages=2,
        cookies='cookies.txt'  # Optional but recommended
    ))

    print(f"\nCollected {len(posts)} posts")

    # Display results
    for i, post in enumerate(posts, 1):
        print(f"\nPost {i}:")
        print(f"  ID: {post['post_id']}")
        print(f"  Text: {post.get('text', '')[:100]}...")
        print(f"  Likes: {post.get('likes', 0)}")
        print(f"  Comments: {post.get('comments', 0)}")
        print(f"  Shares: {post.get('shares', 0)}")


if __name__ == '__main__':
    main()
