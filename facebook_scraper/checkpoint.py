"""
Checkpoint and resume functionality for long-running scraping operations.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class CheckpointManager:
    """
    Manage checkpoints for scraping operations to enable resume on failure.

    Features:
    - Save progress periodically
    - Resume from last successful checkpoint
    - Track visited URLs to avoid duplicates
    - Store collected data counts
    """

    def __init__(self, checkpoint_dir: str = '.checkpoints'):
        """
        Initialize checkpoint manager.

        Args:
            checkpoint_dir: Directory to store checkpoint files
        """
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(exist_ok=True)
        logger.info(f"CheckpointManager initialized with directory: {self.checkpoint_dir}")

    def create_checkpoint_file(self, operation_id: str) -> Path:
        """
        Create checkpoint file path for an operation.

        Args:
            operation_id: Unique identifier for the operation

        Returns:
            Path to checkpoint file
        """
        filename = f"{operation_id}.checkpoint.json"
        return self.checkpoint_dir / filename

    def save_checkpoint(
        self,
        operation_id: str,
        data: Dict[str, Any],
        append_history: bool = False
    ):
        """
        Save checkpoint data.

        Args:
            operation_id: Unique identifier for the operation
            data: Checkpoint data to save
            append_history: Append to history instead of overwriting
        """
        filepath = self.create_checkpoint_file(operation_id)

        # Add metadata
        checkpoint = {
            'operation_id': operation_id,
            'timestamp': datetime.now().isoformat(),
            'data': data,
        }

        if append_history and filepath.exists():
            # Load existing and append
            try:
                with open(filepath, 'r') as f:
                    existing = json.load(f)
                    if 'history' not in existing:
                        existing['history'] = []
                    existing['history'].append(checkpoint)
                    checkpoint = existing
            except Exception as e:
                logger.warning(f"Could not load existing checkpoint: {e}")

        try:
            with open(filepath, 'w') as f:
                json.dump(checkpoint, f, indent=2)
            logger.debug(f"Checkpoint saved: {filepath}")
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")

    def load_checkpoint(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """
        Load checkpoint data.

        Args:
            operation_id: Unique identifier for the operation

        Returns:
            Checkpoint data or None if not found
        """
        filepath = self.create_checkpoint_file(operation_id)

        if not filepath.exists():
            logger.debug(f"No checkpoint found for {operation_id}")
            return None

        try:
            with open(filepath, 'r') as f:
                checkpoint = json.load(f)
            logger.info(f"Checkpoint loaded: {filepath}")
            return checkpoint.get('data')
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            return None

    def delete_checkpoint(self, operation_id: str):
        """
        Delete checkpoint file.

        Args:
            operation_id: Unique identifier for the operation
        """
        filepath = self.create_checkpoint_file(operation_id)

        if filepath.exists():
            try:
                filepath.unlink()
                logger.info(f"Checkpoint deleted: {filepath}")
            except Exception as e:
                logger.error(f"Failed to delete checkpoint: {e}")

    def list_checkpoints(self) -> List[str]:
        """
        List all available checkpoints.

        Returns:
            List of operation IDs
        """
        checkpoints = []
        for filepath in self.checkpoint_dir.glob('*.checkpoint.json'):
            operation_id = filepath.stem.replace('.checkpoint', '')
            checkpoints.append(operation_id)
        return checkpoints


class CommentCheckpoint:
    """
    Specialized checkpoint for comment extraction operations.
    """

    def __init__(self, post_id: str, checkpoint_manager: Optional[CheckpointManager] = None):
        """
        Initialize comment checkpoint.

        Args:
            post_id: Post ID being processed
            checkpoint_manager: CheckpointManager instance
        """
        self.post_id = post_id
        self.manager = checkpoint_manager or CheckpointManager()

        # Initialize or load checkpoint data
        self.data = self.manager.load_checkpoint(f"comments_{post_id}")
        if not self.data:
            self.data = {
                'post_id': post_id,
                'visited_urls': [],
                'comments_collected': 0,
                'last_comment_url': None,
                'completed': False,
                'started_at': datetime.now().isoformat(),
            }

    def mark_url_visited(self, url: str):
        """Mark URL as visited."""
        if url not in self.data['visited_urls']:
            self.data['visited_urls'].append(url)
            self.save()

    def is_url_visited(self, url: str) -> bool:
        """Check if URL was already visited."""
        return url in self.data['visited_urls']

    def update_progress(
        self,
        comments_count: int,
        current_url: Optional[str] = None
    ):
        """
        Update progress.

        Args:
            comments_count: Total comments collected so far
            current_url: Current pagination URL
        """
        self.data['comments_collected'] = comments_count
        if current_url:
            self.data['last_comment_url'] = current_url
        self.data['last_update'] = datetime.now().isoformat()
        self.save()

    def mark_completed(self):
        """Mark operation as completed."""
        self.data['completed'] = True
        self.data['completed_at'] = datetime.now().isoformat()
        self.save()

    def save(self):
        """Save checkpoint."""
        self.manager.save_checkpoint(f"comments_{self.post_id}", self.data)

    def delete(self):
        """Delete checkpoint."""
        self.manager.delete_checkpoint(f"comments_{self.post_id}")

    def get_resume_url(self) -> Optional[str]:
        """Get URL to resume from."""
        return self.data.get('last_comment_url')

    def get_stats(self) -> Dict[str, Any]:
        """Get checkpoint statistics."""
        return {
            'post_id': self.data['post_id'],
            'comments_collected': self.data['comments_collected'],
            'urls_visited': len(self.data['visited_urls']),
            'completed': self.data['completed'],
            'started_at': self.data.get('started_at'),
            'last_update': self.data.get('last_update'),
        }


class PostCheckpoint:
    """
    Specialized checkpoint for post extraction operations.
    """

    def __init__(
        self,
        operation_name: str,
        checkpoint_manager: Optional[CheckpointManager] = None
    ):
        """
        Initialize post checkpoint.

        Args:
            operation_name: Name of the scraping operation
            checkpoint_manager: CheckpointManager instance
        """
        self.operation_name = operation_name
        self.manager = checkpoint_manager or CheckpointManager()

        # Initialize or load checkpoint data
        self.data = self.manager.load_checkpoint(f"posts_{operation_name}")
        if not self.data:
            self.data = {
                'operation_name': operation_name,
                'posts_collected': 0,
                'pages_visited': 0,
                'last_page_url': None,
                'post_ids_seen': [],
                'completed': False,
                'started_at': datetime.now().isoformat(),
            }

    def mark_post_seen(self, post_id: str):
        """Mark post ID as seen to avoid duplicates."""
        if post_id not in self.data['post_ids_seen']:
            self.data['post_ids_seen'].append(post_id)

    def is_post_seen(self, post_id: str) -> bool:
        """Check if post was already seen."""
        return post_id in self.data['post_ids_seen']

    def update_progress(
        self,
        posts_count: int,
        pages_count: int,
        current_url: Optional[str] = None
    ):
        """
        Update progress.

        Args:
            posts_count: Total posts collected
            pages_count: Total pages visited
            current_url: Current page URL
        """
        self.data['posts_collected'] = posts_count
        self.data['pages_visited'] = pages_count
        if current_url:
            self.data['last_page_url'] = current_url
        self.data['last_update'] = datetime.now().isoformat()
        self.save()

    def mark_completed(self):
        """Mark operation as completed."""
        self.data['completed'] = True
        self.data['completed_at'] = datetime.now().isoformat()
        self.save()

    def save(self):
        """Save checkpoint."""
        self.manager.save_checkpoint(f"posts_{self.operation_name}", self.data)

    def delete(self):
        """Delete checkpoint."""
        self.manager.delete_checkpoint(f"posts_{self.operation_name}")

    def get_resume_url(self) -> Optional[str]:
        """Get URL to resume from."""
        return self.data.get('last_page_url')

    def get_stats(self) -> Dict[str, Any]:
        """Get checkpoint statistics."""
        return {
            'operation_name': self.data['operation_name'],
            'posts_collected': self.data['posts_collected'],
            'pages_visited': self.data['pages_visited'],
            'unique_posts': len(self.data['post_ids_seen']),
            'completed': self.data['completed'],
            'started_at': self.data.get('started_at'),
            'last_update': self.data.get('last_update'),
        }
