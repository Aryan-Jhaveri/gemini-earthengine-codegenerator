"""
Per-role token usage logging.

Logs input/output tokens per agent role to agents/data/usage.db (SQLite).
The GET /metrics endpoint reads from this table to expose cost breakdowns.

Approximate pricing defaults (USD per million tokens, as of 2025):
  Gemini 2.5 Flash:  input $0.15  output $0.60
  Gemini 2.5 Pro:    input $1.25  output $10.00
  Claude Haiku 4.5:  input $0.80  output $4.00
  Claude Sonnet 4.5: input $3.00  output $15.00

These are estimates — check provider pricing pages for current rates.
"""

import sqlite3
import time
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent / "data" / "usage.db"

# USD per million tokens (rough estimates)
PRICE_TABLE: dict[str, dict[str, float]] = {
    "gemini/gemini-2.5-flash":    {"input": 0.15,  "output": 0.60},
    "gemini/gemini-2.5-pro":      {"input": 1.25,  "output": 10.00},
    "anthropic/claude-haiku-4-5": {"input": 0.80,  "output": 4.00},
    "anthropic/claude-sonnet-4-5":{"input": 3.00,  "output": 15.00},
}


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS usage (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            ts         REAL    NOT NULL,
            role       TEXT    NOT NULL,
            model      TEXT    NOT NULL,
            input_tok  INTEGER NOT NULL DEFAULT 0,
            output_tok INTEGER NOT NULL DEFAULT 0,
            cost_usd   REAL    NOT NULL DEFAULT 0.0
        )
        """
    )
    conn.commit()
    return conn


def _estimate_cost(model: str, input_tok: int, output_tok: int) -> float:
    prices = PRICE_TABLE.get(model, {"input": 0.0, "output": 0.0})
    return (input_tok * prices["input"] + output_tok * prices["output"]) / 1_000_000


def log_usage(role: str, model: str, input_tok: int, output_tok: int) -> None:
    """Insert one usage row. Called by llm.stream_completion() on 'usage' events."""
    cost = _estimate_cost(model, input_tok, output_tok)
    try:
        conn = _conn()
        conn.execute(
            "INSERT INTO usage (ts, role, model, input_tok, output_tok, cost_usd) VALUES (?,?,?,?,?,?)",
            (time.time(), role, model, input_tok, output_tok, cost),
        )
        conn.commit()
        conn.close()
    except Exception as exc:
        # Never let logging blow up the main flow
        print(f"[usage_tracker] warning: {exc}")


def get_metrics() -> dict:
    """
    Return aggregated usage metrics for all roles.

    Shape:
        {
            "total_cost_usd": float,
            "total_input_tokens": int,
            "total_output_tokens": int,
            "by_role": {
                "<role>": {
                    "model": str,
                    "calls": int,
                    "input_tokens": int,
                    "output_tokens": int,
                    "cost_usd": float,
                }
            }
        }
    """
    if not DB_PATH.exists():
        return {"total_cost_usd": 0.0, "total_input_tokens": 0, "total_output_tokens": 0, "by_role": {}}

    try:
        conn = _conn()
        rows = conn.execute(
            """
            SELECT role, model, COUNT(*) as calls,
                   SUM(input_tok) as in_tok, SUM(output_tok) as out_tok,
                   SUM(cost_usd) as cost
            FROM usage
            GROUP BY role, model
            ORDER BY cost DESC
            """
        ).fetchall()
        conn.close()

        by_role: dict = {}
        total_cost = 0.0
        total_in = 0
        total_out = 0
        for role, model, calls, in_tok, out_tok, cost in rows:
            by_role[role] = {
                "model": model,
                "calls": calls,
                "input_tokens": in_tok or 0,
                "output_tokens": out_tok or 0,
                "cost_usd": round(cost or 0.0, 6),
            }
            total_cost += cost or 0.0
            total_in += in_tok or 0
            total_out += out_tok or 0

        return {
            "total_cost_usd": round(total_cost, 6),
            "total_input_tokens": total_in,
            "total_output_tokens": total_out,
            "by_role": by_role,
        }
    except Exception as exc:
        return {"error": str(exc)}
