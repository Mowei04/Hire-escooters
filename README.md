# Hire e-scooters MVP (Flask)

## Stack
- Backend: Flask
- DB: SQLite
- Frontend: Jinja2 templates + HTML/CSS + Bootstrap

## Run locally
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python server.py
```

Open:
- Home page: http://127.0.0.1:8000/
- Health API: http://127.0.0.1:8000/api/health

## Current endpoints
- `GET /api/health`
- `POST /api/auth/register`
- `POST /api/auth/login` (placeholder)
- `GET /api/customer/pricing` (placeholder)
- `POST /api/customer/bookings` (placeholder)
- `GET /api/admin/scooters` (placeholder)
- `GET /api/admin/revenue/weekly` (placeholder)

## Test
```bash
cd backend
pytest -q
```
