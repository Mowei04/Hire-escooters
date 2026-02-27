"""Legacy admin blueprint module kept for reference.

This module is not the active runtime path (app.py is the source of truth),
but it is documented to keep repository code consistently commented.
"""

import sqlite3

from flask import Blueprint, jsonify, request

admin_bp = Blueprint("admin", __name__)


def get_db_connection():
    """Open DB connection with dict-like row access."""
    conn = sqlite3.connect("scooter_mvp.db")
    conn.row_factory = sqlite3.Row
    return conn


@admin_bp.route("/api/admin/scooters", methods=["GET"])
def list_scooters():
    """Return scooter inventory list for admin views."""
    conn = get_db_connection()
    scooters = conn.execute("SELECT id, code, status, location_text FROM scooters").fetchall()
    conn.close()
    return jsonify({"items": [dict(row) for row in scooters]}), 200


@admin_bp.route("/api/admin/revenue/weekly", methods=["GET"])
def weekly_revenue():
    """Return mock weekly revenue payload for blueprint compatibility."""
    # Keep default values aligned with historical API examples in api.md.
    week_start = request.args.get("week_start", "2026-02-16")

    # NOTE: This blueprint returns mock data; real aggregation is in app.py.
    mock_data = {
        "week_start": week_start,
        "week_end": "2026-02-22",
        "total_revenue": "120.50",
        "by_plan": [
            {"plan_type": "1h", "revenue": "42.00"},
            {"plan_type": "4h", "revenue": "38.50"},
            {"plan_type": "1d", "revenue": "40.00"},
        ],
    }
    return jsonify(mock_data), 200
