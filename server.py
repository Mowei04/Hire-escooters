from app import app, init_db


if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=8000, debug=True)
