"""Single-tenant Microsoft sign-in and database-backed, revocable sessions."""
import hashlib
import json
import os
import re
import secrets
import time
from http.cookies import SimpleCookie
from urllib.parse import urlparse

ADMIN_EMAIL = os.getenv('ENTRA_ADMIN_EMAIL', 'admin@northwestu.edu').strip().lower()
GUID = re.compile(r'^[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$')

def origin():
    return os.getenv('TRACKER_ORIGIN', 'http://127.0.0.1:8000').rstrip('/')

def configured():
    return bool(valid_email(os.getenv('ENTRA_ADMIN_EMAIL','')) and GUID.fullmatch(os.getenv('ENTRA_TENANT_ID','')) and GUID.fullmatch(os.getenv('ENTRA_CLIENT_ID','')) and os.getenv('ENTRA_CLIENT_SECRET') and GUID.fullmatch(os.getenv('ENTRA_ADMIN_OBJECT_ID','')))

def schema(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS users (oid TEXT PRIMARY KEY, email TEXT NOT NULL, role TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1);
    CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, oid TEXT NOT NULL, csrf TEXT NOT NULL, expires INTEGER NOT NULL, touched INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS auth_flows (token TEXT PRIMARY KEY, body TEXT NOT NULL, expires INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS archives (id TEXT PRIMARY KEY, kind TEXT NOT NULL, cycle TEXT NOT NULL, label TEXT NOT NULL, body TEXT NOT NULL, actor TEXT NOT NULL, deleted INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY, actor TEXT NOT NULL, action TEXT NOT NULL, target TEXT NOT NULL, created INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS migrations (name TEXT PRIMARY KEY);
    ''')
    if configured() and not db.execute("SELECT 1 FROM migrations WHERE name='initial-admin'").fetchone():
        db.execute('INSERT INTO users VALUES (?,?,?,1)', (os.environ['ENTRA_ADMIN_OBJECT_ID'].lower(), ADMIN_EMAIL, 'admin'))
        db.execute("INSERT INTO migrations VALUES ('initial-admin')")
    now = int(time.time())
    db.execute('DELETE FROM auth_flows WHERE expires < ?', (now,))
    db.execute('DELETE FROM sessions WHERE expires < ? OR touched < ?', (now, now-1800))

def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()

def cookie_value(handler, name):
    try:
        cookies = SimpleCookie(handler.headers.get('Cookie',''))
        return cookies[name].value if name in cookies else ''
    except Exception:
        return ''

def cookie(name, value, age):
    return '%s=%s; Path=/; HttpOnly; SameSite=Lax; Max-Age=%d%s' % (name,value,age,'; Secure' if origin().startswith('https://') else '')

def user(handler, db):
    token = digest(cookie_value(handler, 'tracker_session'))
    now = int(time.time())
    row = db.execute('SELECT u.oid,u.email,u.role,s.csrf FROM sessions s JOIN users u ON u.oid=s.oid WHERE s.token=? AND u.active=1 AND s.expires>? AND s.touched>?', (token,now,now-1800)).fetchone()
    if not row: return None
    if row[0] == DEV_USER and not local_enabled(handler): return None
    db.execute('UPDATE sessions SET touched=? WHERE token=?',(now,token))
    return dict(zip(['oid','email','role','csrf'], row))

def new_session(db, oid):
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    now = int(time.time())
    db.execute('INSERT INTO sessions VALUES (?,?,?,?,?)',(digest(token),oid,csrf,now+8*3600,now))
    return token

def client():
    import msal
    return msal.ConfidentialClientApplication(os.environ['ENTRA_CLIENT_ID'], authority='https://login.microsoftonline.com/'+os.environ['ENTRA_TENANT_ID'], client_credential=os.environ['ENTRA_CLIENT_SECRET'], timeout=15)

def verify_identity(result):
    import requests
    claims = result.get('id_token_claims',{})
    if claims.get('tid','').lower() != os.environ['ENTRA_TENANT_ID'].lower() or not GUID.fullmatch(claims.get('oid','')):
        raise ValueError('University account required')
    # Microsoft Graph supplies the directory identity; a self-entered email is never trusted.
    response = requests.get('https://graph.microsoft.com/v1.0/me?$select=id,userPrincipalName,userType', headers={'Authorization':'Bearer '+result['access_token']}, timeout=15)
    response.raise_for_status()
    profile = response.json()
    email = profile.get('userPrincipalName','').lower()
    if profile.get('id','').lower()!=claims['oid'].lower() or profile.get('userType')!='Member' or not valid_email(email):
        raise ValueError('A Northwest University member account is required')
    return claims['oid'].lower(), email

def valid_email(email):
    return isinstance(email,str) and bool(re.fullmatch(r'[^\s@]+@northwestu\.edu',email)) and len(email)<=254

def audit(db, actor, action, target):
    db.execute('INSERT INTO audit(actor,action,target,created) VALUES (?,?,?,?)',(actor,action,target,int(time.time())))

# Explicit local development mode; the normal server never enables this.
DEV_USER = 'local-development-admin'
def local_enabled(handler):
    return (os.getenv('TRACKER_LOCAL_DEV') == '1' and not configured()
            and bool(os.getenv('TRACKER_LOCAL_HASH'))
            and origin() == 'http://127.0.0.1:8000'
            and handler.server.server_address[0] == '127.0.0.1'
            and handler.client_address[0] == '127.0.0.1'
            and handler.headers.get('Host') == '127.0.0.1:8000')

def local_password_matches(password):
    import hmac
    try:
        salt, expected = os.environ['TRACKER_LOCAL_HASH'].split(':')
        actual = hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),600000).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, KeyError):
        return False
