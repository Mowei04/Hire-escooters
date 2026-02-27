"""Thin runtime entrypoint that serves the Flask app from app.py."""

from app import app, init_db


if __name__ == "__main__":
    # Ensure schema/seed data exists before starting the web server.
    init_db()
    # Start development server.
    app.run(host="127.0.0.1", port=8000, debug=True)
