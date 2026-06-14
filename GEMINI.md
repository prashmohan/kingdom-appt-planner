# GEMINI.MD: AI Collaboration Guide

This document provides essential context for AI models interacting with this project. Adhering to these guidelines will ensure consistency and maintain code quality.

## 1. Project Overview & Purpose

* **Primary Goal:** The Kingdom Appointment Planner is a specialized Flask-based scheduling and optimization web application designed for the *Kingdom vs Kingdom (KvK)* phase in the game "KingShot" (Century Games). It coordinates the scheduling of kingdom players to receive time-limited "King's Buffs" (Construction, Training, and Research) to maximize points and coordinate alliances.
* **Business Domain:** Gaming Analytics, Operations, Coordination, and Scheduling Optimization.

## 2. Core Technologies & Stack

* **Languages:** Python (3.9+ indicated, running on 3.12 locally), Javascript, HTML, CSS.
* **Frameworks & Runtimes:** Flask 3.x backend, Jinja2 template engine, Tailwind CSS (via client-side play CDN library `tailwind.js`).
* **Databases:** SQLite (utilizing WAL mode for concurrency) with direct `sqlite3` driver connections.
* **Key Libraries/Dependencies:** `flask`, `flask-wtf` (CSRF Protection), `python-dotenv`, `requests` (for external player API checks), `gunicorn` (production WSGI), `markdown` (guide page rendering), `pytest` (testing).
* **Package Manager(s):** `pip` (managing `requirements.txt`).

## 3. Architectural Patterns

* **Overall Architecture:** Model-View-Controller (MVC) monolithic web application. Views and controllers are defined as Flask routes inside `app/__init__.py`. Database interaction is handled in `app/database.py`, and domain allocation logic is in `app/logic.py`.
* **Directory Structure Philosophy:**
    * `/app`: The Flask application package.
        * `__init__.py`: Application factory (`create_app`), routes, and middleware.
        * `database.py`: Database connection helpers and schema initialization/migrations.
        * `logic.py`: Pure scheduling algorithm execution (e.g., "Protected Greedy" allocation) and formatting.
        * `/templates`: Jinja2 HTML templates.
        * `/static`: Client-side static assets (icons, Tailwind CDN script, screenshots, and uploads).
    * `/tests`: Suite of unit, route, and logic tests utilizing `pytest` and `tempfile` database fixtures.
    * `/scripts`: Administrative shell scripts (e.g., database backup/restore operations via Docker).
    * `/logs`: Ephemeral application audit trails (`audit.log`).
    * `/backups`: Directory for database backups.
    * `/data`: Persistent folder for the SQLite database.

## 4. Coding Conventions & Style Guide

* **Formatting:** Python code is checked and formatted using `ruff` and is PEP 8 compliant. Indentation is 4 spaces for Python, 4 spaces for HTML/JS (in templates).
* **Naming Conventions:**
    * Variable/Function names: snake_case (e.g., `run_distribution_algorithm`, `fetch_player_info`).
    * Classes: PascalCase (e.g., `Config` in `config.py`).
    * Database Tables & Columns: snake_case (e.g., `submissions`, `event_uid`, `feasible_slots`).
* **API Design:** standard HTTP POST/GET endpoints returning HTML or JSON responses.
* **Error Handling:** 
    * Route errors are handled with simple Flask redirects or text/JSON responses with appropriate status codes (e.g., 400, 403, 404).
    * Suppresses some integration exceptions (e.g., `requests` errors in `fetch_player_info` are silently passed).

## 5. Key Files & Entrypoints

* **Main Entrypoint(s):** `app:app` (defined by the factory in `app/__init__.py`). Run in development using the environment or locally through `gunicorn` in production.
* **Configuration:** 
    * `config.py`: Contains the `Config` class which reads options from environment variables (fallback values provided).
    * `.env` and `.env.example`: Hold local environment variables (e.g., `SECRET_KEY`, `DATABASE_PATH`).
* **CI/CD Pipeline:** `.github/workflows/main.yml` is used for automated testing.

## 6. Development & Testing Workflow

* **Local Development Environment:**
    * Start the app locally: Run `python -m flask --app app run` or `gunicorn --bind 0.0.0.0:5000 app:app` (or via Docker Compose: `docker-compose up --build`).
    * The SQLite database file will automatically initialize on first request at `/app/data/planner.db` or the path specified by `DATABASE_PATH`.
* **Testing:**
    * Run test suite: `./venv/bin/pytest`
    * The test suite uses temporary database mock fixtures (`tests/conftest.py`) to isolate test runs.
    * Linting: Ensure code conforms to ruff style checks by running `./venv/bin/ruff check .` and formatting with `./venv/bin/ruff format .`.

## 7. Specific Instructions for AI Collaboration

* **Linting:** The project uses `ruff`. All Python modifications must pass `./venv/bin/ruff check .` and `./venv/bin/ruff format --check .`.
* **Security:** 
    * Avoid hardcoding secrets. Always read credentials (e.g., API secrets, keys) from `config.py` which gets them from environment variables.
    * Ensure CSRF protection is maintained on all POST/PUT requests using `X-CSRFToken` headers or `csrf_token` form variables.
    * Enable `PRAGMA foreign_keys = ON` when modifying DB behaviors.
* **Dependencies:** Add packages to `requirements.txt` only when necessary.
* **Database Updates:** When modifying table structures, remember that database initializations are run concurrently across Gunicorn workers. Make sure migrations are backwards-compatible and safely handled.
* **Commit Messages:** Follow standard concise descriptive commit messages (e.g., `feat: validate slot bounds in logic`, `fix: handle request errors in proxy`).
