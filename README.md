# Hire e-scooters MVP (Frontend-first Scaffold)

## Stack
- Backend framework: Flask (mock API mode)
- DB: SQLite (not used in current frontend-only phase)
- Frontend: Jinja2 templates + HTML/CSS + Bootstrap

## Run locally
```bash
cd "/Users/mowei/Software_Engineering/Hire-escooters"
python -m pip install -r requirements.txt
python server.py
```

## Pages
- Home: `http://127.0.0.1:8000/`
- Register: `http://127.0.0.1:8000/customer/register`
- Login: `http://127.0.0.1:8000/customer/login`
- Customer dashboard: `http://127.0.0.1:8000/customer/dashboard`
- Admin page: `http://127.0.0.1:8000/admin`

## API mode
Current APIs return mock data so frontend pages can be developed and demoed now.

## Test
```bash
cd "/Users/mowei/Software_Engineering/Hire-escooters"
python -m pytest -q
```
