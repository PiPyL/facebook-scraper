# Facebook Scraper Examples

This directory contains examples demonstrating various features and use cases.

## Examples

### 1. Simple Usage (`simple_usage.py`)

**What it demonstrates:**
- Basic scraping with default improvements
- All Phase 1 features work automatically
- No configuration needed

**Usage:**
```bash
python simple_usage.py
```

**Features used:**
- Automatic rate limiting
- Built-in metrics
- Improved pagination

---

### 2. Advanced Group Scraping (`advanced_group_scraping.py`)

**What it demonstrates:**
- All Phase 2 & 3 features
- Cookie rotation
- Checkpoint/resume
- Auto-adjustment
- Comprehensive monitoring

**Usage:**
```bash
# Edit the script to set your GROUP_ID and cookie files
python advanced_group_scraping.py
```

**Features used:**
- Rate limiting with custom configuration
- Multiple cookie rotation
- Checkpoint/resume on interruption
- Auto-adjustment of parameters
- Metrics tracking and reporting
- Cookie health monitoring

**Output files:**
- `group_{ID}_scrape_posts.json` - Scraped posts
- `group_{ID}_scrape_metrics.json` - Performance metrics
- `group_{ID}_scrape_cookies.json` - Cookie health stats
- `.checkpoints/posts_group_{ID}_scrape.checkpoint.json` - Checkpoint data

---

### 3. Monitoring Example (`monitoring_example.py`)

**What it demonstrates:**
- Real-time performance monitoring
- Auto-adjustment in action
- Rate limiter statistics
- Cookie health tracking

**Usage:**
```bash
python monitoring_example.py
```

**Features used:**
- Live metrics display
- Rate limiter stats every 5 posts
- Auto-adjuster recommendations
- Cookie pool monitoring

**Sample output:**
```
============================================================
Progress Update - 5 posts collected
Runtime: 15.34s

Rate Limiter:
  Success rate: 95.2%
  Current delay: 2.45s
  Consecutive errors: 0

Metrics: Runtime: 15.34s | Success: 95.24% | Ops: 21 | Errors: 1

Cookie Pool:
  Total: 2
  Healthy: 2
============================================================
```

---

### 4. Comments with Checkpoint (`comments_with_checkpoint.py`)

**What it demonstrates:**
- Extract all comments from a post
- Checkpoint/resume for long operations
- Nested reply extraction

**Usage:**
```bash
# Edit the script to set your POST_ID
python comments_with_checkpoint.py
```

**Features used:**
- CommentCheckpoint for progress tracking
- Resume on interruption
- Nested replies extraction
- Progress saving every batch

**Output files:**
- `comments_{POST_ID}.json` - All extracted comments
- `.checkpoints/comments_{POST_ID}.checkpoint.json` - Progress checkpoint

---

## Prerequisites

### Required

1. **Cookie files**: Most examples require `cookies.txt`
   ```bash
   # Get cookies using browser extension
   # Recommended: EditThisCookie (Chrome/Edge)
   ```

2. **Python packages**: Installed automatically with facebook-scraper
   ```bash
   pip install facebook-scraper
   ```

### Optional

- Multiple cookie files for rotation (`cookies1.txt`, `cookies2.txt`, etc.)
- Proxy configuration (for large-scale scraping)

---

## Configuration

### Cookie Files

Examples expect cookie files in the same directory:
```
examples/
  ├── cookies.txt          # Primary cookie file
  ├── cookies1.txt         # Optional: for rotation
  ├── cookies2.txt         # Optional: for rotation
  └── *.py                 # Example scripts
```

### Group IDs

Find your Facebook group ID:
1. Go to the group page
2. Look at the URL: `facebook.com/groups/123456789`
3. The number is your GROUP_ID

### Post IDs

Find post ID from URL:
- `facebook.com/permalink/1234567890` → POST_ID = "1234567890"
- `facebook.com/story.php?story_fbid=1234567890` → POST_ID = "1234567890"

---

## Troubleshooting

### "No cookies available"

**Solution:** Create `cookies.txt` file with your Facebook cookies

```bash
# Get cookies using EditThisCookie extension
# Export as Netscape format
# Save to cookies.txt
```

### "LoginRequired" error

**Solution:** Your cookies expired or are invalid
1. Clear cookies
2. Login to Facebook in browser
3. Export fresh cookies
4. Retry

### "TemporarilyBanned" error

**Solution:** Rate limiting triggered
1. Wait 30-60 minutes
2. Increase rate limiting delays
3. Use cookie rotation
4. Consider using proxies

### Low success rate

**Solution:** Check auto-adjuster recommendations
```python
if scraper.auto_adjuster:
    scraper.auto_adjuster.print_recommendations()
```

---

## Advanced Usage

### Custom Rate Limiting

```python
scraper = FacebookScraper(
    rate_limit_config={
        'min_delay': 5.0,       # Slower for safety
        'max_delay': 15.0,      # Higher ceiling
        'adaptive': True,       # Auto-adjust
        'cooldown_period': 180  # 3 min on ban
    }
)
```

### Cookie Rotation

```python
scraper = FacebookScraper(
    cookie_pool=[
        'cookies1.txt',
        'cookies2.txt',
        'cookies3.txt',
    ]
)

# Manual rotation
scraper.rotate_cookies()
```

### Checkpoint Management

```python
from facebook_scraper.checkpoint import CheckpointManager

checkpoint_mgr = CheckpointManager()

# List all checkpoints
checkpoints = checkpoint_mgr.list_checkpoints()

# Delete specific checkpoint
checkpoint_mgr.delete_checkpoint('operation_id')
```

### Metrics Analysis

```python
# Get metrics programmatically
report = scraper.metrics.get_report()
success_rate = report['overall_success_rate']

# Save for analysis
scraper.metrics.save_report('metrics.json')
```

---

## Performance Tips

### For Best Success Rates

1. **Use fresh cookies** (< 1 day old)
2. **Enable all features**:
   ```python
   FacebookScraper(
       enable_rate_limiting=True,
       enable_metrics=True,
       enable_checkpoints=True,
       enable_auto_adjust=True,
   )
   ```
3. **Start with conservative delays** (3-5s minimum)
4. **Use cookie rotation** for large scrapes
5. **Monitor metrics** and adjust based on recommendations

### For Large-Scale Scraping

1. **Multiple cookies** (5+ accounts)
2. **Proxy rotation** (optional)
3. **Checkpoint/resume** enabled
4. **Run in batches** (50-100 posts per session)
5. **Respect rate limits** (don't go below 2s delay)

---

## Expected Performance

### With Default Settings

- **Success Rate**: 70-85%
- **Pages per Group**: 3-8
- **Comments per Post**: 50-150
- **Speed**: ~3-5 posts/minute

### With Optimal Settings

- **Success Rate**: 85-95%
- **Pages per Group**: 8-15
- **Comments per Post**: 150-500
- **Speed**: ~2-4 posts/minute (slower but safer)

---

## Support

For issues:
1. Check metrics report first
2. Enable debug logging
3. Review auto-adjuster recommendations
4. Check cookie health
5. Verify group/post IDs

Debug logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```
