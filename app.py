from __future__ import annotations

"""Main Flask application for auth, customer booking flow, and admin operations."""

import sqlite3
from datetime import date, datetime, timedelta
from decimal import Decimal
from functools import wraps
from pathlib import Path

from flask import Flask, g, jsonify, redirect, render_template, request, session, url_for

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "scooter_mvp.db"

app = Flask(__name__)
# NOTE: Keep this in environment variables for production deployments.
app.config["SECRET_KEY"] = "hire-escooters-dev-secret"

# Pricing catalog used by customer pricing and booking endpoints.
PLANS = {
    "1h": {"duration_minutes": 60, "price": "2.99"},
    "4h": {"duration_minutes": 240, "price": "8.99"},
    "1d": {"duration_minutes": 1440, "price": "19.99"},
    "1w": {"duration_minutes": 10080, "price": "79.99"},
}

# Allowed state transitions for admin scooter updates.
ALLOWED_SCOOTER_STATUS = {"available", "in_use", "maintenance"}
# Booking statuses considered currently running.
ACTIVE_BOOKING_STATUSES = {"PENDING_PAYMENT"}
# Fixed countdown window for PENDING_PAYMENT booking lifecycle.
PENDING_PAYMENT_TIMEOUT_MINUTES = 5


def get_db() -> sqlite3.Connection:
    """Return a SQLite connection with row-access by column name."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def api_error(status_code: int, code: str, message: str):
    """Build a standardized API error payload."""
    return jsonify({"error": {"code": code, "message": message}}), status_code


def normalize_username(value: str) -> str:
    """Normalize usernames to a lowercase, trimmed value."""
    return value.strip().lower()


def ensure_unique_username(base: str, used: set[str]) -> str:
    """Generate a unique username candidate when duplicates exist."""
    candidate = base or "user"
    suffix = 1
    while candidate in used:
        suffix += 1
        candidate = f"{base or 'user'}{suffix}"
    used.add(candidate)
    return candidate


def parse_db_datetime(value: str | None) -> datetime | None:
    """Parse sqlite datetime text into naive datetime object."""
    if not value:
        return None
    normalized = value.replace(" ", "T")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        # Fallback for unusual sqlite timestamp formats.
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
    return None


def sync_expired_bookings(conn: sqlite3.Connection) -> int:
    """Auto-complete expired active bookings and release scooters."""
    cur = conn.cursor()
    active_rows = cur.execute(
        """
        SELECT id, scooter_id, plan_type, created_at
        FROM bookings
        WHERE status IN ({})
        """.format(",".join("?" * len(ACTIVE_BOOKING_STATUSES))),
        tuple(ACTIVE_BOOKING_STATUSES),
    ).fetchall()

    now = datetime.utcnow()
    expired_booking_ids: list[int] = []
    affected_scooters: set[int] = set()

    for row in active_rows:
        duration_minutes = PENDING_PAYMENT_TIMEOUT_MINUTES
        started_at = parse_db_datetime(row["created_at"])
        if duration_minutes is None or started_at is None:
            continue

        expires_at = started_at + timedelta(minutes=duration_minutes)
        if now >= expires_at:
            expired_booking_ids.append(row["id"])
            affected_scooters.add(row["scooter_id"])

    if not expired_booking_ids:
        return 0

    # Mark expired active bookings as completed.
    cur.executemany(
        """
        UPDATE bookings
        SET status = 'COMPLETED', ended_at = CURRENT_TIMESTAMP
        WHERE id = ?
          AND status IN ({})
        """.format(",".join("?" * len(ACTIVE_BOOKING_STATUSES))),
        [(booking_id, *tuple(ACTIVE_BOOKING_STATUSES)) for booking_id in expired_booking_ids],
    )

    # Release scooter only if no other active booking remains.
    for scooter_id in affected_scooters:
        active_left = cur.execute(
            """
            SELECT 1
            FROM bookings
            WHERE scooter_id = ?
              AND status IN ({})
            LIMIT 1
            """.format(",".join("?" * len(ACTIVE_BOOKING_STATUSES))),
            (scooter_id, *tuple(ACTIVE_BOOKING_STATUSES)),
        ).fetchone()
        if not active_left:
            cur.execute("UPDATE scooters SET status = 'available' WHERE id = ?", (scooter_id,))

    conn.commit()
    return len(expired_booking_ids)


def init_db() -> None:
    """Create tables, apply lightweight migrations, and seed baseline data."""
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'customer'
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS scooters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            status TEXT NOT NULL DEFAULT 'available',
            location_text TEXT NOT NULL DEFAULT ''
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            scooter_id INTEGER NOT NULL,
            plan_type TEXT NOT NULL,
            total_cost TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING_PAYMENT',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ended_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (scooter_id) REFERENCES scooters (id)
        )
        """
    )

    # Lightweight migration for old DB files.
    scooter_columns = {row["name"] for row in cur.execute("PRAGMA table_info(scooters)").fetchall()}
    if "location_text" not in scooter_columns:
        cur.execute("ALTER TABLE scooters ADD COLUMN location_text TEXT NOT NULL DEFAULT ''")

    user_columns = {row["name"] for row in cur.execute("PRAGMA table_info(users)").fetchall()}
    if "username" not in user_columns:
        cur.execute("ALTER TABLE users ADD COLUMN username TEXT")

    booking_columns = {row["name"] for row in cur.execute("PRAGMA table_info(bookings)").fetchall()}
    if "ended_at" not in booking_columns:
        cur.execute("ALTER TABLE bookings ADD COLUMN ended_at TIMESTAMP")

    # Normalize and backfill usernames for existing rows before adding unique index.
    users = cur.execute("SELECT id, username, email FROM users ORDER BY id").fetchall()
    used_usernames: set[str] = set()
    for row in users:
        current = normalize_username(row["username"] or "")
        email_base = normalize_username((row["email"] or "").split("@")[0])
        base = current or email_base or f"user{row['id']}"
        username = ensure_unique_username(base, used_usernames)
        if username != (row["username"] or ""):
            cur.execute("UPDATE users SET username = ? WHERE id = ?", (username, row["id"]))

    # Add unique indexes to enforce integrity at database level.
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_unique ON users(email)")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username_unique ON users(username)")

    # Seed scooter records once for local/demo usage.
    cur.execute("SELECT COUNT(*) AS count FROM scooters")
    if cur.fetchone()["count"] == 0:
        cur.executemany(
            "INSERT INTO scooters (code, status, location_text) VALUES (?, ?, ?)",
            [
                ("SC-001", "available", "City Center A"),
                ("SC-002", "available", "City Center B"),
                ("SC-003", "maintenance", "North Station"),
            ],
        )

    # Seed default accounts used in demos/tests if they do not exist.
    cur.execute(
        "INSERT OR IGNORE INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
        ("manager", "manager@example.com", "plain::admin123", "admin"),
    )
    cur.execute(
        "INSERT OR IGNORE INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
        ("demo_user", "demo_user@example.com", "plain::123456", "customer"),
    )

    conn.commit()
    conn.close()


def get_current_user() -> sqlite3.Row | None:
    """Resolve current session user from DB; return None when not logged in."""
    user_id = session.get("user_id")
    if not user_id:
        return None

    conn = get_db()
    try:
        user = conn.execute("SELECT id, username, email, role FROM users WHERE id = ?", (user_id,)).fetchone()
    finally:
        conn.close()
    return user


def require_role(role: str | None = None):
    """Decorator to require login and optional role match for protected endpoints."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = get_current_user()
            if not user:
                return api_error(401, "UNAUTHORIZED", "Login required")
            if role and user["role"] != role:
                return api_error(403, "FORBIDDEN", "Insufficient permissions")
            g.current_user = user
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def to_money(value: Decimal) -> str:
    """Format decimal value to 2-digit currency-like text."""
    return f"{value.quantize(Decimal('0.01'))}"


def redirect_after_login(user: sqlite3.Row):
    """Route users to the correct dashboard based on role."""
    if user["role"] == "admin":
        return redirect(url_for("admin_page"))
    return redirect(url_for("customer_dashboard_page"))


@app.context_processor
def inject_current_user():
    """Inject session user into all templates for role-based rendering."""
    return {"current_user": get_current_user()}


@app.get("/")
def home():
    """Render public homepage."""
    return render_template("index.html")


@app.get("/customer")
def customer_home():
    """Shortcut customer entrypoint; redirect logged-in users by role."""
    user = get_current_user()
    if user:
        return redirect_after_login(user)
    return render_template("customer_login.html")


@app.get("/customer/register")
def customer_register_page():
    """Render register page for anonymous users only."""
    user = get_current_user()
    if user:
        return redirect_after_login(user)
    return render_template("customer_register.html")


@app.get("/customer/login")
def customer_login_page():
    """Render login page for anonymous users only."""
    user = get_current_user()
    if user:
        return redirect_after_login(user)
    return render_template("customer_login.html")


@app.get("/customer/dashboard")
def customer_dashboard_page():
    """Render customer dashboard; block anonymous/non-customer roles."""
    user = get_current_user()
    if not user:
        return redirect(url_for("customer_login_page"))
    if user["role"] != "customer":
        return redirect(url_for("admin_page"))
    return render_template("customer_dashboard.html")


@app.get("/admin")
def admin_page():
    """Render admin dashboard; block anonymous/non-admin roles."""
    user = get_current_user()
    if not user:
        return redirect(url_for("customer_login_page"))
    if user["role"] != "admin":
        return redirect(url_for("customer_dashboard_page"))
    return render_template("admin.html")


@app.get("/api/health")
def health_check():
    """Basic health endpoint used by smoke tests and monitoring."""
    return jsonify({"status": "ok", "framework": "flask"})


@app.post("/api/auth/register")
def register_user():
    """Register a new customer with unique username/email constraints."""
    payload = request.get_json(silent=True) or {}
    username = normalize_username(payload.get("username") or "")
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    if not username or not email or not password:
        return jsonify({"message": "username, email and password are required"}), 400

    conn = get_db()
    try:
        # Validate uniqueness with explicit messages for better UX.
        email_exists = conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone()
        if email_exists:
            return jsonify({"message": "Email already exists"}), 409

        username_exists = conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone()
        if username_exists:
            return jsonify({"message": "Username already exists"}), 409

        conn.execute(
            "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
            (username, email, f"plain::{password}", "customer"),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        return jsonify({"message": "Username or email already exists"}), 409
    finally:
        conn.close()

    return jsonify({"message": "User registered"}), 201


@app.post("/api/auth/login")
def login_user():
    """Authenticate user credentials and start session."""
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    if not email or not password:
        return jsonify({"message": "email and password are required"}), 400

    conn = get_db()
    try:
        user = conn.execute(
            "SELECT id, username, email, role FROM users WHERE email = ? AND password_hash = ?",
            (email, f"plain::{password}"),
        ).fetchone()
    finally:
        conn.close()

    if not user:
        return api_error(401, "INVALID_CREDENTIALS", "Invalid email or password")

    # Reset session to prevent stale identity leakage, then set active user.
    session.clear()
    session["user_id"] = user["id"]

    return jsonify({"message": "Login success", "user": dict(user)})


@app.post("/api/auth/logout")
@require_role()
def logout_user():
    """Clear active session."""
    session.clear()
    return jsonify({"message": "Logged out"})


@app.get("/api/auth/me")
@require_role()
def whoami():
    """Return current authenticated user profile."""
    return jsonify({"user": dict(g.current_user)})


@app.get("/api/customer/pricing")
@require_role("customer")
def get_pricing():
    """Return available pricing plans for customer role."""
    plans_list = [{"plan_type": k, **v} for k, v in PLANS.items()]
    return jsonify({"plans": plans_list})


@app.get("/api/customer/scooters")
@require_role("customer")
def list_scooters_customer():
    """Return scooter inventory with status for customer browsing."""
    conn = get_db()
    try:
        sync_expired_bookings(conn)
        rows = conn.execute(
            "SELECT id, code, status, location_text FROM scooters ORDER BY id"
        ).fetchall()
    finally:
        conn.close()

    items = []
    for row in rows:
        data = dict(row)
        data["is_available"] = data["status"] == "available"
        items.append(data)

    return jsonify({"items": items})


@app.post("/api/customer/bookings")
@require_role("customer")
def create_booking():
    """Create a booking and mark the scooter as in_use."""
    payload = request.get_json(silent=True) or {}
    scooter_id = payload.get("scooter_id")
    plan_type = payload.get("plan_type")

    if not isinstance(scooter_id, int) or plan_type not in PLANS:
        return api_error(400, "VALIDATION_ERROR", "Invalid scooter_id or plan_type")

    conn = get_db()
    cur = conn.cursor()
    try:
        # Ensure any timed-out active booking is finalized before availability check.
        sync_expired_bookings(conn)

        # Check scooter existence and availability before booking.
        scooter = cur.execute("SELECT id, status FROM scooters WHERE id = ?", (scooter_id,)).fetchone()
        if not scooter:
            return api_error(404, "SCOOTER_NOT_FOUND", "Scooter does not exist")
        if scooter["status"] != "available":
            return api_error(409, "SCOOTER_UNAVAILABLE", "Scooter is not available")

        cost = PLANS[plan_type]["price"]
        expires_at = datetime.utcnow() + timedelta(minutes=PENDING_PAYMENT_TIMEOUT_MINUTES)
        # Persist booking and lock scooter status in the same transaction.
        cur.execute(
            "INSERT INTO bookings (user_id, scooter_id, plan_type, total_cost, status) VALUES (?, ?, ?, ?, ?)",
            (g.current_user["id"], scooter_id, plan_type, cost, "PENDING_PAYMENT"),
        )
        booking_id = cur.lastrowid
        cur.execute("UPDATE scooters SET status = 'in_use' WHERE id = ?", (scooter_id,))
        conn.commit()

        return jsonify(
            {
                "booking": {
                    "id": booking_id,
                    "user_id": g.current_user["id"],
                    "scooter_id": scooter_id,
                    "plan_type": plan_type,
                    "status": "PENDING_PAYMENT",
                    "total_cost": cost,
                    "duration_minutes": PENDING_PAYMENT_TIMEOUT_MINUTES,
                    "expires_at": expires_at.strftime("%Y-%m-%d %H:%M:%S"),
                }
            }
        ), 201
    except Exception:
        # Roll back any partial DB updates if an unexpected error occurs.
        conn.rollback()
        raise
    finally:
        conn.close()


@app.get("/api/customer/bookings")
@require_role("customer")
def list_bookings():
    """List current user bookings with controllable cancelled-history window."""
    include_cancelled = (request.args.get("include_cancelled") or "recent").strip().lower()
    cancelled_days_raw = (request.args.get("cancelled_days") or "3").strip()
    try:
        cancelled_days = max(1, min(3650, int(cancelled_days_raw)))
    except ValueError:
        cancelled_days = 3

    conn = get_db()
    try:
        sync_expired_bookings(conn)

        base_query = """
            SELECT
                b.id,
                b.user_id,
                b.scooter_id,
                b.plan_type,
                b.total_cost,
                b.status,
                b.created_at,
                b.ended_at,
                s.status AS scooter_current_status
            FROM bookings b
            JOIN scooters s ON s.id = b.scooter_id
            WHERE b.user_id = ?
        """
        params: list[object] = [g.current_user["id"]]

        if include_cancelled == "none":
            base_query += " AND b.status IN ({})".format(",".join("?" * len(ACTIVE_BOOKING_STATUSES)))
            params.extend(tuple(ACTIVE_BOOKING_STATUSES))
        elif include_cancelled == "all":
            pass
        else:
            # Default behavior: keep active bookings and recent ended bookings.
            include_cancelled = "recent"
            base_query += " AND (b.status IN ({}) OR datetime(COALESCE(b.ended_at, b.created_at)) >= datetime('now', ?))".format(
                ",".join("?" * len(ACTIVE_BOOKING_STATUSES))
            )
            params.extend(tuple(ACTIVE_BOOKING_STATUSES))
            params.append(f"-{cancelled_days} days")

        base_query += " ORDER BY b.id DESC"
        rows = conn.execute(base_query, params).fetchall()
    finally:
        conn.close()

    now = datetime.utcnow()
    items = []
    for row in rows:
        data = dict(row)
        duration_minutes = PENDING_PAYMENT_TIMEOUT_MINUTES
        started_at = parse_db_datetime(data["created_at"])
        data["duration_minutes"] = duration_minutes
        data["expires_at"] = None
        data["remaining_seconds"] = 0

        if duration_minutes is not None and started_at is not None:
            expires_at = started_at + timedelta(minutes=duration_minutes)
            data["expires_at"] = expires_at.strftime("%Y-%m-%d %H:%M:%S")
            data["remaining_seconds"] = max(0, int((expires_at - now).total_seconds()))

        if data["status"] in ACTIVE_BOOKING_STATUSES:
            # Active bookings are expected to keep scooter in_use.
            data["scooter_status_aligned"] = data["scooter_current_status"] == "in_use"
        else:
            # Ended bookings should not lock scooter into in_use.
            data["scooter_status_aligned"] = data["scooter_current_status"] != "in_use"
        items.append(data)

    return jsonify(
        {
            "items": items,
            "filters": {
                "include_cancelled": include_cancelled,
                "cancelled_days": cancelled_days,
            },
        }
    )


@app.delete("/api/customer/bookings/<int:booking_id>")
@require_role("customer")
def cancel_booking(booking_id: int):
    """Cancel an owned booking and release scooter availability."""
    conn = get_db()
    cur = conn.cursor()
    sync_expired_bookings(conn)

    booking = cur.execute(
        "SELECT id, user_id, scooter_id, status FROM bookings WHERE id = ?",
        (booking_id,),
    ).fetchone()

    if not booking:
        conn.close()
        return api_error(404, "BOOKING_NOT_FOUND", "Booking does not exist")

    if booking["user_id"] != g.current_user["id"]:
        conn.close()
        return api_error(403, "FORBIDDEN", "Cannot cancel another user's booking")

    if booking["status"] == "CANCELLED":
        conn.close()
        return api_error(409, "BOOKING_ALREADY_CANCELLED", "Booking already cancelled")
    if booking["status"] not in ACTIVE_BOOKING_STATUSES:
        conn.close()
        return api_error(409, "BOOKING_ALREADY_ENDED", "Booking already ended")

    try:
        cur.execute("UPDATE bookings SET status = 'CANCELLED' WHERE id = ?", (booking_id,))
        # Keep scooter locked if other active bookings exist because of historical/manual inconsistencies.
        active_count = cur.execute(
            """
            SELECT COUNT(*) AS count
            FROM bookings
            WHERE scooter_id = ?
              AND id != ?
              AND status IN ({})
            """.format(",".join("?" * len(ACTIVE_BOOKING_STATUSES))),
            (booking["scooter_id"], booking_id, *tuple(ACTIVE_BOOKING_STATUSES)),
        ).fetchone()["count"]
        if active_count == 0:
            cur.execute("UPDATE scooters SET status = 'available' WHERE id = ?", (booking["scooter_id"],))
        conn.commit()
    finally:
        conn.close()

    return jsonify({"message": "Booking cancelled", "booking_id": booking_id})


@app.get("/api/admin/scooters")
@require_role("admin")
def list_scooters_admin():
    """List all scooters for admin management view."""
    conn = get_db()
    try:
        sync_expired_bookings(conn)
        rows = conn.execute(
            "SELECT id, code, status, location_text FROM scooters ORDER BY id"
        ).fetchall()
    finally:
        conn.close()

    return jsonify({"items": [dict(row) for row in rows]})


@app.patch("/api/admin/scooters/<int:scooter_id>")
@require_role("admin")
def update_scooter_admin(scooter_id: int):
    """Update scooter status and/or location for admin operations."""
    payload = request.get_json(silent=True) or {}
    updates: list[str] = []
    values: list[str] = []

    if "status" in payload:
        status = payload["status"]
        if status not in ALLOWED_SCOOTER_STATUS:
            return api_error(400, "VALIDATION_ERROR", "Invalid scooter status")
        updates.append("status = ?")
        values.append(status)

    if "location_text" in payload:
        location_text = str(payload["location_text"] or "").strip()
        updates.append("location_text = ?")
        values.append(location_text)

    if not updates:
        return api_error(400, "VALIDATION_ERROR", "No valid fields to update")

    values.append(str(scooter_id))

    conn = get_db()
    cur = conn.cursor()
    sync_expired_bookings(conn)
    # Prevent manual availability override when unresolved bookings still exist for this scooter.
    if "status" in payload and payload["status"] == "available":
        active_booking = cur.execute(
            """
            SELECT 1
            FROM bookings
            WHERE scooter_id = ?
              AND status IN ({})
            LIMIT 1
            """.format(",".join("?" * len(ACTIVE_BOOKING_STATUSES))),
            (scooter_id, *tuple(ACTIVE_BOOKING_STATUSES)),
        ).fetchone()
        if active_booking:
            conn.close()
            return api_error(
                409,
                "ACTIVE_BOOKING_EXISTS",
                "Cannot set scooter to available while active booking exists",
            )

    cur.execute(f"UPDATE scooters SET {', '.join(updates)} WHERE id = ?", values)
    if cur.rowcount == 0:
        conn.close()
        return api_error(404, "SCOOTER_NOT_FOUND", "Scooter does not exist")

    conn.commit()
    row = cur.execute("SELECT id, code, status, location_text FROM scooters WHERE id = ?", (scooter_id,)).fetchone()
    conn.close()

    return jsonify({"item": dict(row)})


@app.get("/api/admin/revenue/weekly")
@require_role("admin")
def weekly_revenue():
    """Aggregate weekly non-cancelled booking revenue by plan."""
    week_start_raw = request.args.get("week_start", "").strip()
    if week_start_raw:
        try:
            week_start = datetime.strptime(week_start_raw, "%Y-%m-%d").date()
        except ValueError:
            return api_error(400, "VALIDATION_ERROR", "week_start must be YYYY-MM-DD")
    else:
        today = date.today()
        week_start = today - timedelta(days=today.weekday())

    week_end = week_start + timedelta(days=6)

    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT plan_type, COALESCE(SUM(CAST(total_cost AS REAL)), 0) AS revenue
            FROM bookings
            WHERE DATE(created_at) BETWEEN ? AND ?
              AND status != 'CANCELLED'
            GROUP BY plan_type
            """,
            (week_start.isoformat(), week_end.isoformat()),
        ).fetchall()
    finally:
        conn.close()

    revenue_by_plan = {row["plan_type"]: Decimal(str(row["revenue"])) for row in rows}
    by_plan = []
    total = Decimal("0")

    for plan_type in PLANS.keys():
        amount = revenue_by_plan.get(plan_type, Decimal("0"))
        total += amount
        by_plan.append({"plan_type": plan_type, "revenue": to_money(amount)})

    return jsonify(
        {
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "total_revenue": to_money(total),
            "by_plan": by_plan,
        }
    )


# Initialize schema/data at import time for local runs and tests.
init_db()

if __name__ == "__main__":
    # Local development entrypoint.
    app.run(host="127.0.0.1", port=8000, debug=True)
