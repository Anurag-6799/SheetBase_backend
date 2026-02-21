# ⚡ SheetBase: The Instant Backend API

![Python 3.14](https://img.shields.io/badge/Python-3.14-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.129.0-009688.svg)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791.svg)
![Redis](https://img.shields.io/badge/Redis-7.0-DC382D.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

SheetBase is a high-performance REST API generator that instantly converts any Google Sheet into a secure, low-latency JSON endpoint. Built with a focus on high availability, it utilizes a multi-level caching strategy to drop external API latency from ~600ms to <20ms.

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

### Phase 1 (Core)
* Secure Google OAuth2 integration with encrypted refresh token storage (Fernet symmetric encryption).
* Dynamic sheet parsing: Automatically identifies headers and maps subsequent rows into clean JSON arrays.
* Multi-level Redis caching implementation to guarantee fault tolerance and high-speed reads.

### Phase 2 (Advanced Query Engine)
* Column filtering (e.g., request only `Name` and `Price`).
* Pagination and row limits (`?limit=50&offset=10`).
* Real-time cache invalidation on write operations.

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