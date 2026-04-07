"""
Token Usage Tracker for TradingAgents-CN

Uses a LangChain callback handler to intercept LLM responses and record
token usage (prompt_tokens, completion_tokens) to a SQLite database.
"""

import sqlite3
import json
import os
import threading
from datetime import datetime
from typing import Any, Dict, Optional
from pathlib import Path

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

# Database path
DB_PATH = os.environ.get("USAGE_DB_PATH", "/root/stock-analyzer/data/usage.db")


def _get_conn() -> sqlite3.Connection:
    """Get a thread-local database connection."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize the usage database schema."""
    conn = _get_conn()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS token_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                provider TEXT NOT NULL,
                model_name TEXT NOT NULL,
                session_id TEXT,
                prompt_tokens INTEGER DEFAULT 0,
                completion_tokens INTEGER DEFAULT 0,
                total_tokens INTEGER GENERATED ALWAYS AS (prompt_tokens + completion_tokens) STORED,
                cost DECIMAL(10, 6) DEFAULT 0,
                currency TEXT DEFAULT 'CNY',
                analysis_type TEXT,
                symbol TEXT,
                node_name TEXT,
                raw_response TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_token_usage_timestamp ON token_usage(timestamp)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_token_usage_session ON token_usage(session_id)
        """)
        conn.commit()
    finally:
        conn.close()


# MiniMax pricing (CNY per 1M tokens) — approximate
MINIMAX_PRICING = {
    "MiniMax-M2.1": {"input": 0.5, "output": 0.5},
    "MiniMax-M2.7": {"input": 0.5, "output": 0.5},
    "MiniMax-M2": {"input": 0.5, "output": 0.5},
    "default": {"input": 0.5, "output": 0.5},
}


def _calc_cost(model_name: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Calculate cost based on model pricing."""
    prices = MINIMAX_PRICING.get(model_name, MINIMAX_PRICING["default"])
    prompt_cost = (prompt_tokens / 1_000_000) * prices["input"]
    completion_cost = (completion_tokens / 1_000_000) * prices["output"]
    return round(prompt_cost + completion_cost, 6)


class UsageTrackingCallback(BaseCallbackHandler):
    """
    LangChain callback handler that records LLM token usage to SQLite.

    Attach to LLM client or graph via `callbacks=[UsageTrackingCallback()]`.
    """

    def __init__(self, session_id: str = "", analysis_type: str = "", symbol: str = ""):
        self.session_id = session_id
        self.analysis_type = analysis_type
        self.symbol = symbol
        self._local = threading.local()

    def _conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn"):
            self._local.conn = _get_conn()
        return self._local.conn

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Called after an LLM invocation completes. Extracts token usage."""
        try:
            # Support both single and multiple generations
            if not response.generations:
                return

            # Flatten all generation chunks
            for gen_list in response.generations:
                for gen in gen_list:
                    msg = gen.message
                    if msg is None:
                        continue

                    # LangChain stores usage in AIMessage.usage_metadata
                    usage = None
                    if hasattr(msg, "usage_metadata") and msg.usage_metadata:
                        usage = msg.usage_metadata
                    elif hasattr(msg, "lc_serializable") and hasattr(msg, "response_metadata"):
                        # Fallback: try response_metadata
                        usage = getattr(msg, "usage_metadata", None)

                    if usage is None:
                        continue

                    # Extract token counts
                    input_tokens = usage.get("input_tokens", 0)
                    output_tokens = usage.get("output_tokens", 0)

                    if input_tokens == 0 and output_tokens == 0:
                        continue

                    # Get model name from LLM result
                    model_name = ""
                    if response.llm_output and isinstance(response.llm_output, dict):
                        model_name = response.llm_output.get("model_name", "") or ""

                    # Determine node name from kwargs (usually passed by the graph)
                    node_name = kwargs.get("run_id", "")

                    cost = _calc_cost(model_name, input_tokens, output_tokens)
                    timestamp = datetime.now().isoformat()

                    self._conn().execute(
                        """
                        INSERT INTO token_usage
                            (timestamp, provider, model_name, session_id,
                             prompt_tokens, completion_tokens, cost, currency,
                             analysis_type, symbol, node_name)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            timestamp,
                            "minimax",
                            model_name,
                            self.session_id,
                            input_tokens,
                            output_tokens,
                            cost,
                            "CNY",
                            self.analysis_type,
                            self.symbol,
                            str(node_name) if node_name else None,
                        ),
                    )
                    self._conn().commit()
        except Exception as e:
            # Don't let tracking errors break the main flow
            import sys
            sys.stderr.write(f"[UsageTracker] on_llm_end error: {e}\n")


# ─── Statistics API helpers ────────────────────────────────────────────────────

def get_usage_stats(days: int = 7) -> Dict[str, Any]:
    """Return aggregated usage statistics from the database."""
    conn = _get_conn()
    try:
        cur = conn.execute(
            """
            SELECT
                COUNT(*) as total_requests,
                COALESCE(SUM(prompt_tokens), 0) as total_prompt_tokens,
                COALESCE(SUM(completion_tokens), 0) as total_completion_tokens,
                COALESCE(SUM(cost), 0.0) as total_cost
            FROM token_usage
            WHERE timestamp >= datetime('now', ? || ' days')
            """,
            (-days,),
        )
        row = cur.fetchone()

        # By provider
        by_provider = {}
        cur.execute(
            """
            SELECT provider,
                   COUNT(*) as requests,
                   SUM(prompt_tokens) as prompt,
                   SUM(completion_tokens) as completion,
                   SUM(cost) as cost
            FROM token_usage
            WHERE timestamp >= datetime('now', ? || ' days')
            GROUP BY provider
            """,
            (-days,),
        )
        for r in cur.fetchall():
            by_provider[r["provider"]] = {
                "requests": r["requests"],
                "prompt_tokens": r["prompt"],
                "completion_tokens": r["completion"],
                "cost": r["cost"],
            }

        # By model
        by_model = {}
        cur.execute(
            """
            SELECT model_name,
                   COUNT(*) as requests,
                   SUM(prompt_tokens) as prompt,
                   SUM(completion_tokens) as completion,
                   SUM(cost) as cost
            FROM token_usage
            WHERE timestamp >= datetime('now', ? || ' days')
            GROUP BY model_name
            """,
            (-days,),
        )
        for r in cur.fetchall():
            by_model[r["model_name"] or "unknown"] = {
                "requests": r["requests"],
                "prompt_tokens": r["prompt"],
                "completion_tokens": r["completion"],
                "cost": r["cost"],
            }

        # By date
        by_date = {}
        cur.execute(
            """
            SELECT date(timestamp) as day,
                   SUM(prompt_tokens) as prompt,
                   SUM(completion_tokens) as completion,
                   SUM(cost) as cost
            FROM token_usage
            WHERE timestamp >= datetime('now', ? || ' days')
            GROUP BY date(timestamp)
            ORDER BY day
            """,
            (-days,),
        )
        for r in cur.fetchall():
            by_date[r["day"]] = {
                "prompt_tokens": r["prompt"],
                "completion_tokens": r["completion"],
                "cost": r["cost"],
            }

        return {
            "total_requests": row["total_requests"] or 0,
            "total_prompt_tokens": row["total_prompt_tokens"] or 0,
            "total_completion_tokens": row["total_completion_tokens"] or 0,
            "total_cost": row["total_cost"] or 0.0,
            "by_provider": by_provider,
            "by_model": by_model,
            "by_date": by_date,
        }
    finally:
        conn.close()


def get_usage_records(
    limit: int = 100,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Return individual usage records."""
    conn = _get_conn()
    try:
        query = "SELECT * FROM token_usage WHERE 1=1"
        params = []
        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date)
        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date)
        if provider:
            query += " AND provider = ?"
            params.append(provider)
        if model_name:
            query += " AND model_name = ?"
            params.append(model_name)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cur = conn.execute(query, params)
        rows = [dict(r) for r in cur.fetchall()]
        cur.execute(
            "SELECT COUNT(*) as total FROM token_usage WHERE 1=1"
            + (" AND timestamp >= ?" if start_date else "")
            + (" AND timestamp <= ?" if end_date else "")
            + (" AND provider = ?" if provider else "")
            + (" AND model_name = ?" if model_name else ""),
            [v for v in params[:-1] if v is not None],
        )
        total = cur.fetchone()["total"]
        return {"records": rows, "total": total}
    finally:
        conn.close()


def get_daily_cost(days: int = 7) -> Dict[str, Any]:
    """Return daily cost breakdown."""
    conn = _get_conn()
    try:
        cur = conn.execute(
            """
            SELECT date(timestamp) as day,
                   provider,
                   model_name,
                   SUM(prompt_tokens) as prompt_tokens,
                   SUM(completion_tokens) as completion_tokens,
                   SUM(cost) as cost
            FROM token_usage
            WHERE timestamp >= datetime('now', ? || ' days')
            GROUP BY date(timestamp), provider, model_name
            ORDER BY day
            """,
            (-days,),
        )
        rows = [dict(r) for r in cur.fetchall()]
        return {"costs": rows}
    finally:
        conn.close()


def get_cost_by_model(days: int = 7) -> Dict[str, Any]:
    """Return cost grouped by model."""
    conn = _get_conn()
    try:
        cur = conn.execute(
            """
            SELECT model_name,
                   SUM(prompt_tokens) as prompt_tokens,
                   SUM(completion_tokens) as completion_tokens,
                   SUM(cost) as cost,
                   COUNT(*) as request_count
            FROM token_usage
            WHERE timestamp >= datetime('now', ? || ' days')
            GROUP BY model_name
            """,
            (-days,),
        )
        rows = {r["model_name"] or "unknown": dict(r) for r in cur.fetchall()}
        return {"costs": rows}
    finally:
        conn.close()


def get_cost_by_provider(days: int = 7) -> Dict[str, Any]:
    """Return cost grouped by provider."""
    conn = _get_conn()
    try:
        cur = conn.execute(
            """
            SELECT provider,
                   SUM(prompt_tokens) as prompt_tokens,
                   SUM(completion_tokens) as completion_tokens,
                   SUM(cost) as cost,
                   COUNT(*) as request_count
            FROM token_usage
            WHERE timestamp >= datetime('now', ? || ' days')
            GROUP BY provider
            """,
            (-days,),
        )
        rows = {r["provider"]: dict(r) for r in cur.fetchall()}
        return {"costs": rows}
    finally:
        conn.close()
