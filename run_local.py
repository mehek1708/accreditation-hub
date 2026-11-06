#!/usr/bin/env python3
"""Explicit, password-protected localhost development launcher."""
import hashlib
import os
from pathlib import Path
import runpy
import secrets

root = Path(__file__).resolve().parent
os.umask(0o077)
password_file = root / '.local-dev-password'
if not password_file.exists():
    password_file.write_text(secrets.token_urlsafe(18)+'\n')
password_file.chmod(0o600)
password = password_file.read_text().strip()
if len(password)<16:
    raise SystemExit('Local development password must contain at least 16 characters.')
salt = secrets.token_bytes(16)
os.environ.update(HOST='127.0.0.1',PORT='8000',TRACKER_ORIGIN='http://127.0.0.1:8000',TRACKER_LOCAL_DEV='1',
                  TRACKER_LOCAL_HASH=salt.hex()+':'+hashlib.pbkdf2_hmac('sha256',password.encode(),salt,600000).hex())
print('Local development login enabled. Your password is in .local-dev-password in this project folder.',flush=True)
runpy.run_path(str(root/'server.py'),run_name='__main__')
