"""
Comprehensive metrics collection and reporting for scraper performance monitoring.
"""

import time
import json
import logging
import threading
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class ScraperMetrics:
    """
    Collect and report metrics for scraper operations.

    Tracks:
    - Success/failure counts by operation
    - Timing information
    - Error details
    - Success rates
    """

    def __init__(self):
        self.metrics = defaultdict(int)
        self.timings = defaultdict(list)
        self.errors: List[Dict[str, Any]] = []
        self.lock = threading.Lock()
        self.start_time = time.time()

        logger.info("ScraperMetrics initialized")

    def record_success(self, operation: str, duration: Optional[float] = None):
        """
        Record successful operation.

        Args:
            operation: Name of the operation
            duration: Operation duration in seconds
        """
        with self.lock:
            self.metrics[f'{operation}_success'] += 1

            if duration is not None:
                self.timings[operation].append(duration)

            logger.debug(f"Success: {operation} (duration={duration:.3f}s)" if duration else f"Success: {operation}")

    def record_failure(self, operation: str, error_type: str, error_msg: str):
        """
        Record failed operation.

        Args:
            operation: Name of the operation
            error_type: Type/class of error
            error_msg: Error message
        """
        with self.lock:
            self.metrics[f'{operation}_failure'] += 1

            error_entry = {
                'operation': operation,
                'error_type': error_type,
                'error_msg': str(error_msg)[:200],  # Truncate long messages
                'timestamp': datetime.now().isoformat(),
            }

            self.errors.append(error_entry)

            logger.warning(f"Failure: {operation} - {error_type}: {error_msg[:100]}")

    def get_success_rate(self, operation: str) -> float:
        """
        Calculate success rate for an operation.

        Args:
            operation: Name of the operation

        Returns:
            Success rate as percentage (0-100)
        """
        success = self.metrics.get(f'{operation}_success', 0)
        failure = self.metrics.get(f'{operation}_failure', 0)
        total = success + failure

        return (success / total * 100) if total > 0 else 0

    def get_average_timing(self, operation: str) -> Optional[float]:
        """
        Get average timing for an operation.

        Args:
            operation: Name of the operation

        Returns:
            Average duration in seconds, or None if no data
        """
        timings = self.timings.get(operation, [])
        return sum(timings) / len(timings) if timings else None

    def get_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive metrics report.

        Returns:
            Dictionary containing all metrics
        """
        with self.lock:
            runtime = time.time() - self.start_time

            # Identify all operations
            operations = set()
            for key in self.metrics.keys():
                op = key.replace('_success', '').replace('_failure', '')
                operations.add(op)

            # Calculate success rates
            success_rates = {}
            for op in operations:
                rate = self.get_success_rate(op)
                success_rates[op] = f"{rate:.2f}%"

            # Calculate average timings
            averages = {}
            for op, times in self.timings.items():
                if times:
                    avg_ms = (sum(times) / len(times)) * 1000
                    averages[f'{op}_avg_ms'] = round(avg_ms, 2)

            # Calculate overall success rate
            total_success = sum(v for k, v in self.metrics.items() if k.endswith('_success'))
            total_failure = sum(v for k, v in self.metrics.items() if k.endswith('_failure'))
            total_ops = total_success + total_failure
            overall_rate = (total_success / total_ops * 100) if total_ops > 0 else 0

            return {
                'runtime_seconds': round(runtime, 2),
                'overall_success_rate': f"{overall_rate:.2f}%",
                'total_operations': total_ops,
                'total_successes': total_success,
                'total_failures': total_failure,
                'success_rates': success_rates,
                'average_timings': averages,
                'total_errors': len(self.errors),
                'recent_errors': self.errors[-10:],  # Last 10 errors
                'raw_metrics': dict(self.metrics),
            }

    def print_report(self):
        """Print formatted metrics report to console."""
        report = self.get_report()

        print("\n" + "=" * 70)
        print("FACEBOOK SCRAPER METRICS REPORT")
        print("=" * 70)
        print(f"Runtime: {report['runtime_seconds']}s")
        print(f"Overall Success Rate: {report['overall_success_rate']}")
        print(f"Total Operations: {report['total_operations']} "
              f"(Success: {report['total_successes']}, Failure: {report['total_failures']})")

        if report['success_rates']:
            print(f"\nSuccess Rates by Operation:")
            for op, rate in sorted(report['success_rates'].items()):
                success = self.metrics.get(f'{op}_success', 0)
                failure = self.metrics.get(f'{op}_failure', 0)
                print(f"  {op:30s}: {rate:>7s} ({success}/{success + failure})")

        if report['average_timings']:
            print(f"\nAverage Timings:")
            for op, avg in sorted(report['average_timings'].items()):
                print(f"  {op:30s}: {avg:>8.2f}ms")

        print(f"\nTotal Errors: {report['total_errors']}")
        if report['recent_errors']:
            print("\nRecent Errors:")
            for err in report['recent_errors'][-5:]:  # Show last 5
                print(f"  [{err['timestamp']}] {err['operation']}")
                print(f"    {err['error_type']}: {err['error_msg'][:80]}")

        print("=" * 70 + "\n")

    def save_report(self, filename: str = 'scraper_metrics.json'):
        """
        Save metrics report to JSON file.

        Args:
            filename: Output filename
        """
        report = self.get_report()

        try:
            with open(filename, 'w') as f:
                json.dump(report, f, indent=2)
            logger.info(f"Metrics report saved to {filename}")
        except Exception as e:
            logger.error(f"Failed to save metrics report: {e}")

    def reset(self):
        """Reset all metrics."""
        with self.lock:
            self.metrics.clear()
            self.timings.clear()
            self.errors.clear()
            self.start_time = time.time()
            logger.info("Metrics reset")

    def get_stats_summary(self) -> str:
        """
        Get quick stats summary as string.

        Returns:
            Formatted summary string
        """
        report = self.get_report()
        return (
            f"Runtime: {report['runtime_seconds']}s | "
            f"Success: {report['overall_success_rate']} | "
            f"Ops: {report['total_operations']} | "
            f"Errors: {report['total_errors']}"
        )
