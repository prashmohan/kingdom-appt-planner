# Security Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remediate all vulnerabilities identified in the security audit report (`security-issues.md`), verify with comprehensive automated tests, commit with clear atomic messages, and push to remote.

**Architecture:** Harden Flask configuration and session cookie attributes, enforce constant-time authentication secret verification across all admin endpoints, sanitize client-side DOM rendering to eliminate XSS, isolate audit logs per event, validate URL schemes, verify upload magic bytes, and add security headers.

**Tech Stack:** Python 3.12, Flask 3.x, SQLite 3, Jinja2, HTML5/Vanilla JS, Docker, pytest.

**Spec:** [`security-issues.md`](file:///home/prmohan/projects/kvk-appt/security-issues.md)

## Global Constraints
- All Python modifications must pass `./venv/bin/ruff check .` and `./venv/bin/ruff format --check .`.
- All existing 108 pytest tests must continue to pass without regression.
- New security unit tests must be added to verify each fix.

---

### Task 1: Secure Configuration and Defaults

**Files:**
- Modify: `config.py`
- Modify: `docker-compose.yml`
- Test: `tests/test_security.py`

- [ ] **Step 1: Write failing test in `tests/test_security.py` checking cookie security settings**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Update `config.py` and `docker-compose.yml` with secure cookie defaults and production warnings**
- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit `feat(security): configure secure session cookies and harden configuration defaults`**

---

### Task 2: Constant-Time Admin Secret Authentication

**Files:**
- Modify: `app/__init__.py`
- Test: `tests/test_security.py`

- [ ] **Step 1: Write failing test verifying constant-time secret comparison and handling of empty/invalid secret tokens**
- [ ] **Step 2: Run test to verify it fails or exposes insecure comparison**
- [ ] **Step 3: Update all 13 admin routes in `app/__init__.py` to use `hmac.compare_digest`**
- [ ] **Step 4: Run tests to verify all routes pass**
- [ ] **Step 5: Commit `fix(security): use constant-time hmac compare_digest for admin secret authentication`**

---

### Task 3: Prevent Stored DOM XSS in Admin Dashboard Drawer

**Files:**
- Modify: `app/templates/admin_dashboard.html`
- Test: `tests/test_security.py`

- [ ] **Step 1: Write route test with XSS payloads in `player_name` and `alliance_name`**
- [ ] **Step 2: Update `admin_dashboard.html` with safe HTML escaping and programmatic event handlers in `selectSlot`**
- [ ] **Step 3: Run route tests to verify template renders cleanly without breaking**
- [ ] **Step 4: Commit `fix(security): sanitize dynamic player data and eliminate DOM XSS in admin dashboard`**

---

### Task 4: Audit Log Isolation by Event UID

**Files:**
- Modify: `app/__init__.py`
- Test: `tests/test_security.py`

- [ ] **Step 1: Write test checking `/admin/<event_uid>/logs` returns only logs relevant to `event_uid`**
- [ ] **Step 2: Update `view_logs` in `app/__init__.py` to filter lines by `event_uid`**
- [ ] **Step 3: Run test to verify cross-tenant log isolation passes**
- [ ] **Step 4: Commit `fix(security): enforce per-event tenant isolation for admin audit log viewer`**

---

### Task 5: HTTP Security Headers & Referrer-Policy Hardening

**Files:**
- Modify: `app/__init__.py`
- Test: `tests/test_security.py`

- [ ] **Step 1: Write test verifying presence of `Referrer-Policy: no-referrer` and `Strict-Transport-Security` headers**
- [ ] **Step 2: Update `add_security_headers` in `app/__init__.py`**
- [ ] **Step 3: Run test to verify headers are present**
- [ ] **Step 4: Commit `feat(security): add Referrer-Policy and HSTS security headers`**

---

### Task 6: URL Scheme Validation for `avatar_url` and `backpack_url`

**Files:**
- Modify: `app/__init__.py`
- Test: `tests/test_security.py`

- [ ] **Step 1: Write test attempting to submit `javascript:...` or unsafe URLs in `avatar_url` and `backpack_url`**
- [ ] **Step 2: Add URL schema validator helper in `app/__init__.py` / `app/logic.py` and sanitize URLs on submit and import**
- [ ] **Step 3: Run test to verify unsafe schemes are rejected or sanitized to `None`**
- [ ] **Step 4: Commit `fix(security): validate URL schemes for avatar and backpack links`**

---

### Task 7: File Upload Magic Byte Verification

**Files:**
- Modify: `app/__init__.py`
- Test: `tests/test_security.py`

- [ ] **Step 1: Write test attempting to upload a text/executable file with `.png` extension**
- [ ] **Step 2: Add image header magic byte check for PNG, JPEG, GIF in `submit`**
- [ ] **Step 3: Run test to verify upload rejection of fake image files**
- [ ] **Step 4: Commit `fix(security): verify magic byte signatures on uploaded screenshot images`**

---

### Task 8: Dockerfile Non-Root User Hardening

**Files:**
- Modify: `Dockerfile`

- [ ] **Step 1: Update `Dockerfile` to create and switch to unprivileged user `appuser`**
- [ ] **Step 2: Commit `fix(security): configure non-root user execution in Docker container`**

---

### Task 9: Clean Linter, Complete Verification & Push to Remote

**Files:**
- Repository Root

- [ ] **Step 1: Run `./venv/bin/ruff check .` and `./venv/bin/ruff format .`**
- [ ] **Step 2: Run `./venv/bin/pytest` and verify all tests pass**
- [ ] **Step 3: Push commits to remote origin**
