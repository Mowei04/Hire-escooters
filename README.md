# Hire e-scooters MVP

## Stack
- Backend framework: Flask
- DB: SQLite (`scooter_mvp.db`)
- Frontend: Jinja2 templates + HTML/CSS + Bootstrap

## Run locally
```bash
cd "/Users/mowei/Software_Engineering/Hire-escooters"
python -m pip install -r requirements.txt
python server.py
```

## Pages
- Home: `http://127.0.0.1:8000/`
- Register/Login: `http://127.0.0.1:8000/customer/register`, `http://127.0.0.1:8000/customer/login`
- Customer dashboard: `http://127.0.0.1:8000/customer/dashboard`
- Admin page: `http://127.0.0.1:8000/admin`

## Demo accounts
- Customer: `demo_user@example.com / 123456`
- Admin: `manager@example.com / admin123`

## Delivered APIs
- Auth/session: `/api/auth/register`, `/api/auth/login`, `/api/auth/logout`, `/api/auth/me`
- Customer: `/api/customer/pricing`, `/api/customer/bookings` (create/list/cancel)
- Admin: `/api/admin/scooters` (list/update), `/api/admin/revenue/weekly`
- Health: `/api/health`

## Test
```bash
cd "/Users/mowei/Software_Engineering/Hire-escooters"
python -m pytest -q
```

Smoke test coverage is in `tests/test_smoke.py`.
