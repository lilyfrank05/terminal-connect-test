# Remaining Fixes

## P2 — Medium

### 1. DB init subprocess chain in run.py and entrypoint.sh

`run.py` calls `init_db.py` via subprocess, which itself calls `flask db upgrade` via subprocess. In Docker, `entrypoint.sh` does the same. Multiple Python processes spawning each other before one request can be served. Race between gunicorn workers on startup.

**Fix:** Use `flask db upgrade` directly instead of subprocess chaining. Move DB init into `create_app()` or a one-shot CLI command.

### 2. Invite and password-reset tokens are bare UUIDs

`Invite.__init__` and `User.generate_reset_token` both generate `str(uuid.uuid4())`. UUIDs are not KDF-based tokens — if the invites/users table leaks or a token is brute-forced, attacker can register or hijack an account.

**Fix:** Use `secrets.token_urlsafe(32)` instead of `uuid.uuid4()` for security tokens.

### 3. FLASK_ENV deprecated in run.py

`run.py` sets `FLASK_ENV=development` and `FLASK_DEBUG=1`. These are deprecated since Flask 2.3.

**Fix:** Use `--debug` flag instead, or remove `FLASK_ENV` entirely.

---

## P3 — Lower

### 4. utc_now() returns timezone-naive datetimes

`utc_now()` strips timezone info to avoid SQLite warnings. Works with SQLite, but `TypeError: can't compare offset-naive and offset-aware datetimes` if you ever query against PostgreSQL's timezone-aware timestamps.

**Fix:** Store aware datetimes and handle SQLite compatibility differently, or add a helper that adapts comparisons.

### 5. Marshmallow schemas duplicated across route files

Each route file defines its own `class XxxSchema(Schema)` — `validate.OneOf(["admin", "user"])` appears in both `admin.py` and `user.py`.

**Fix:** Create a shared `app/schemas.py` module.

### 6. No dependency lockfile

`requirements.txt` pins versions but has no `requirements.lock`. Docker builds are non-deterministic.

**Fix:** Generate `requirements.lock` via `pip freeze` and use `pip install --no-deps -r requirements.lock` in Docker.

### 7. certifi dependency barely used

`app/utils/api.py` imports `certifi` only as fallback when `/etc/ssl/certs/ca-certificates.crt` is absent. In Docker (Debian slim), the system CA bundle is always present.

**Fix:** Remove `certifi` import; always use the system CA bundle in Docker, and a sensible default for bare-metal dev.

### 8. wsgi.py has a __main__ block with dev server

`python wsgi.py` starts Flask's dev server with `threaded=True` — not gunicorn.

**Fix:** Remove the `__main__` block or guard it with a warning when not in debug mode.