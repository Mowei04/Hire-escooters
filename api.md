# API Contract (MVP)

Base URL: `http://127.0.0.1:8000`

## Common Conventions
- Content-Type: `application/json`
- Time format: ISO8601 string (planned for booking timestamps)
- Currency: GBP, decimal string (planned)
- Auth header (planned): `Authorization: Bearer <token>`

## Error Response (Unified, Planned)
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human readable message"
  }
}
```

---

## 1) Health

### GET `/api/health`
Purpose: service health check.

Response `200`
```json
{
  "status": "ok",
  "framework": "flask"
}
```

---

## 2) Auth

### POST `/api/auth/register`
Purpose: create customer account.

Request body
```json
{
  "email": "user@example.com",
  "password": "123456"
}
```

Response `201`
```json
{
  "message": "User registered"
}
```

Error `400` (missing email/password)
```json
{
  "message": "email and password are required"
}
```

Error `409` (duplicate email)
```json
{
  "message": "Email already exists"
}
```

### POST `/api/auth/login` (placeholder -> to implement)
Purpose: login and return token + user profile.

Request body (contract)
```json
{
  "email": "user@example.com",
  "password": "123456"
}
```

Response `200` (target contract)
```json
{
  "token": "<jwt-token>",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "role": "customer"
  }
}
```

Error `401`
```json
{
  "error": {
    "code": "INVALID_CREDENTIALS",
    "message": "Email or password is invalid"
  }
}
```

---

## 3) Customer

### GET `/api/customer/pricing` (placeholder -> to implement)
Purpose: list available hire plans.

Response `200` (target contract)
```json
{
  "plans": [
    {"plan_type": "1h", "duration_minutes": 60, "price": "2.99"},
    {"plan_type": "4h", "duration_minutes": 240, "price": "8.99"},
    {"plan_type": "1d", "duration_minutes": 1440, "price": "19.99"},
    {"plan_type": "1w", "duration_minutes": 10080, "price": "79.99"}
  ]
}
```

### POST `/api/customer/bookings` (placeholder -> to implement)
Purpose: create booking for a scooter.

Request body (contract)
```json
{
  "scooter_id": 1,
  "plan_type": "1h"
}
```

Response `201` (target contract)
```json
{
  "booking": {
    "id": 101,
    "user_id": 1,
    "scooter_id": 1,
    "plan_type": "1h",
    "status": "PENDING_PAYMENT",
    "total_cost": "2.99"
  }
}
```

Error `404`
```json
{
  "error": {
    "code": "SCOOTER_NOT_FOUND",
    "message": "Scooter does not exist"
  }
}
```

Error `409`
```json
{
  "error": {
    "code": "SCOOTER_UNAVAILABLE",
    "message": "Scooter is not available"
  }
}
```

---

## 4) Admin

### GET `/api/admin/scooters` (placeholder -> to implement)
Purpose: list scooters and status for management UI.

Response `200` (target contract)
```json
{
  "items": [
    {"id": 1, "code": "SC-001", "status": "available", "location_text": "City Centre"}
  ]
}
```

Error `403`
```json
{
  "error": {
    "code": "FORBIDDEN",
    "message": "Manager role required"
  }
}
```

### GET `/api/admin/revenue/weekly` (placeholder -> to implement)
Purpose: weekly revenue summary.

Query params (contract)
- `week_start` (optional): `YYYY-MM-DD`

Response `200` (target contract)
```json
{
  "week_start": "2026-02-16",
  "week_end": "2026-02-22",
  "total_revenue": "120.50",
  "by_plan": [
    {"plan_type": "1h", "revenue": "42.00"},
    {"plan_type": "4h", "revenue": "38.50"},
    {"plan_type": "1d", "revenue": "40.00"}
  ]
}
```

---

## 5) Implementation Status Summary
- Implemented now: `GET /api/health`, `POST /api/auth/register`
- Placeholder now: `POST /api/auth/login`, `GET /api/customer/pricing`, `POST /api/customer/bookings`, `GET /api/admin/scooters`, `GET /api/admin/revenue/weekly`
- This file is the source of truth for field names/status codes while the team builds remaining endpoints.
