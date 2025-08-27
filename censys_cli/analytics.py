"""
Analytics module for tracking CAPTCHA bypass metrics.
Stores success/failure rates and response times in SQLite.
Provides recommendations for optimal bypass method.
"""
import sqlite3
from datetime import datetime
import texttable
from typing import Optional

class Analytics:
    """Manages CAPTCHA bypass metrics and recommendations."""
    def __init__(self, db_path: str = "./analytics.sqlite"):
        """Initialise analytics with SQLite database."""
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Create SQLite table for storing CAPTCHA metrics."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS captcha_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                method TEXT NOT NULL,
                success INTEGER NOT NULL,
                response_time REAL,
                error_message TEXT,
                timestamp TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()

    def log_success(self, method: str, response_time: float):
        """Record a successful CAPTCHA bypass attempt."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "INSERT INTO captcha_metrics (method, success, response_time, timestamp) VALUES (?, ?, ?, ?)",
                (method, 1, response_time, datetime.utcnow().isoformat() + "Z")
            )
            conn.commit()
        finally:
            conn.close()

    def log_failure(self, method: str, error_message: str):
        """Record a failed CAPTCHA bypass attempt."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "INSERT INTO captcha_metrics (method, success, error_message, timestamp) VALUES (?, ?, ?, ?)",
                (method, 0, error_message, datetime.utcnow().isoformat() + "Z")
            )
            conn.commit()
        finally:
            conn.close()

    def get_stats(self) -> dict:
        """Retrieve aggregated CAPTCHA bypass statistics."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute("""
                SELECT method, 
                       COUNT(*) as attempts,
                       SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successes,
                       AVG(response_time) as avg_time
                FROM captcha_metrics
                GROUP BY method
            """)
            stats = {}
            for row in cursor:
                method, attempts, successes, avg_time = row
                stats[method] = {
                    "attempts": attempts,
                    "success_rate": successes / attempts if attempts > 0 else 0,
                    "avg_time": avg_time or 0
                }
            return stats
        finally:
            conn.close()

    def recommend_method(self) -> str:
        """Recommend the optimal CAPTCHA bypass method."""
        stats = self.get_stats()
        if not stats:
            return "pow"  # Default to PoW for initial runs
        best_method = "pow"
        best_score = -1
        for method, data in stats.items():
            score = data["success_rate"] / (data["avg_time"] or 1)  # Prioritise high success, low time
            if score > best_score:
                best_score = score
                best_method = method
        return best_method

    def print_stats(self):
        """Display a table of CAPTCHA bypass statistics."""
        stats = self.get_stats()
        table = texttable.Texttable()
        table.header(["Method", "Attempts", "Success Rate", "Avg Time (s)"])
        for method, data in stats.items():
            table.add_row([
                method,
                data["attempts"],
                f"{data['success_rate']:.2%}",
                f"{data['avg_time']:.2f}" if data['avg_time'] else "-"
            ])
        print("\nCAPTCHA Bypass Statistics:")
        print(table.draw())
        print(f"Recommended Method: {self.recommend_method()}")