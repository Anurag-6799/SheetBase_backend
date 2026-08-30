# ⚡ SheetBase: The Instant Backend API

![Python 3.14](https://img.shields.io/badge/Python-3.14-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.129.0-009688.svg)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791.svg)
![Redis](https://img.shields.io/badge/Redis-7.0-DC382D.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

SheetBase is a REST API generator that converts any Google Sheet into a secure JSON endpoint. Reads are served cache-aside from Redis, so repeat requests skip Google's slow, aggressively rate-limited Sheets API entirely; a cache outage degrades latency rather than availability.

## 🎯 The Problem & Solution
Frontend and mobile developers often need a simple database with an accessible UI for non-technical stakeholders (e.g., marketers managing product catalogs). Google Sheets is the perfect UI, but a terrible database. 

SheetBase bridges this gap by providing:
1. **OAuth2 Flow:** Secure "Login with Google" to access Drive/Sheets.
2. **Instant API Generation:** Toggle a sheet and immediately receive a highly available REST endpoint.
3. **The Speed Layer:** A robust Cache-Aside pattern utilizing Redis to bypass Google's severe rate limits and slow response times.

---

## 🏗️ Architecture

The codebase strictly follows **Clean Architecture** principles (Domain-Driven Design), separating HTTP routing from core business logic to ensure the system is highly testable and scalable.

* **`api/`**: The presentation layer. Pure HTTP routing, input validation, and response formatting.
* **`services/`**: The core business logic. Google API communication, token rotation, and data transformation.
* **`db/`**: The data access layer handling async PostgreSQL queries and Redis caching.

## ✨ Features

### Auth
* Google OAuth2 authorisation-code flow, scoped read-only to Drive and Sheets.
* Refresh tokens encrypted at rest with Fernet; client config from env vars, never a checked-in JSON file.
* Opaque, expiring session tokens (Fernet-authenticated, 7-day TTL) guard the management endpoints.

### Publishing
* `GET /api/v1/sheets` lists your spreadsheets; `GET /api/v1/sheets/{id}/tabs` lists a file's tabs.
* `POST /api/v1/apis` publishes one tab and returns its public endpoint. Idempotent: re-publishing the same tab returns the existing URL instead of minting a second one.
* Publishing verifies the sheet is readable up front, so you never receive a URL that fails later.
* Endpoint ids are random UUIDs - knowing one URL tells you nothing about anyone else's.

### Reads (cache-aside)
* Redis first, Google only on a miss, then populate the cache (TTL `CACHE_TTL_SECONDS`, default 300s).
* Every response reports `"source": "cache" | "google"`, which makes staleness debuggable.
* If Redis is unreachable the read still succeeds from Google - a cache outage is a latency event, not an outage.
* `POST /api/v1/apis/{id}/refresh` invalidates on demand; deleting an API clears its cache first, so an unpublished endpoint cannot keep serving rows for the rest of the TTL.

### Query engine
* Column projection: `?columns=Name,Price`
* Pagination: `?limit=50&offset=10`
* Sorting: `?order_by=Price&order=desc` - numeric when the column is numeric, so `"10"` does not sort before `"9"`.
* Equality filters on any column: `?Status=active` (case-insensitive; filters apply *before* pagination).
* Ragged rows are handled: Google truncates trailing empty cells, so short rows are padded and stray extra cells never produce a `None` key.

---

## 📡 Example

```bash
# Publish a tab
curl -X POST localhost:8000/api/v1/apis \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"spreadsheet_id": "1AbC...", "sheet_name": "Products"}'
# -> {"id": "3f2a...", "endpoint": "/api/v1/data/3f2a..."}

# Read it - no auth required, that is the point of publishing
curl "localhost:8000/api/v1/data/3f2a...?columns=Name,Price&Status=active&order_by=Price&order=desc&limit=10"
```

```json
{
  "api_id": "3f2a...", "source": "cache", "total": 402, "count": 10,
  "data": [{"Name": "Widget", "Price": "100"}]
}
```

---

## 🚀 Quickstart (Local Development)

### Prerequisites
* Docker & Docker Compose
* Python 3.14+ (Managed via `pyenv` recommended)
* Google Cloud Console Credentials (Sheets API & Drive API enabled)

### 1. Clone & Environment Setup
```bash
git clone [https://github.com/Anurag-6799/SheetBase_backend.git](https://github.com/Anurag-6799/SheetBase_backend.git)
cd SheetBase_backend

# Set up the virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install exact dependencies
pip install -r requirements.txt