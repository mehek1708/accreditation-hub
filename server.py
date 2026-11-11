#!/usr/bin/env python3
"""ACBSP Tracker: shared SQLite application with university Microsoft sign-in."""
import threading
import secrets
import time
import security
import archives
import evidence_store
import hmac
import json
import os
from pathlib import Path
import sqlite3
import re
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, quote

ROOT = Path(__file__).resolve().parent
DB = ROOT / 'data' / 'tracker.sqlite3'
STATUSES = ['Not Started', 'In Progress', 'Ready for Review', 'Complete']
EVIDENCE = ['Needed', 'Partially Collected', 'Complete', 'Not needed']

def seed():
    titles = ['Leadership', 'Strategic Planning', 'Student and Stakeholder Focus', 'Student Learning Assessment', 'Faculty Focus', 'Curriculum', 'Business Unit Performance']
    return {'name': 'ACBSP 2031', 'description': 'Our shared workspace for the 2026–2031 accreditation cycle.', 'standards': [{'id': 's'+str(i), 'title': title, 'description': '', 'criteria': [{'id': 'c'+str(i) if j == 1 else 'c'+str(i)+'_'+str(j), 'code': str(i)+'.'+str(j), 'title': 'criteria name', 'owner': '', 'status': 'Not Started', 'evidence': 'Needed', 'year': 2026, 'link': '', 'evidenceLink': '', 'notes': ''} for j in range(1, (6 if i == 6 else 4) + 1)]} for i, title in enumerate(titles, 1)], 'reviews': []}

def connect():
    DB.parent.mkdir(exist_ok=True)
    db = sqlite3.connect(str(DB), timeout=10)
    db.execute('CREATE TABLE IF NOT EXISTS project (id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL, body TEXT NOT NULL)')
    db.execute('INSERT OR IGNORE INTO project VALUES (1,0,?)', (json.dumps(seed()),))
    db.execute('CREATE TABLE IF NOT EXISTS cycles (id TEXT PRIMARY KEY, revision INTEGER NOT NULL, body TEXT NOT NULL)')
    security.schema(db)
    evidence_store.schema(db)
    if not db.execute("SELECT 1 FROM migrations WHERE name='cycles'").fetchone():
        revision, body = db.execute('SELECT revision, body FROM project WHERE id=1').fetchone()
        project = json.loads(body)
        project.update(startYear=2021, endYear=2031, coordinator='', submissionDate='')
        db.execute('INSERT OR IGNORE INTO cycles VALUES (?,?,?)', ('2021-2031', revision, json.dumps(project)))
        db.execute("INSERT INTO migrations VALUES ('cycles')")
    db.commit()
    return db

def cycle_id(path):
    if path == '/api/project': return '2021-2031'  # Preserve old clients and bookmarks.
    match = re.fullmatch(r'/api/cycles/([0-9]{4}-[0-9]{4})/project', path)
    return match.group(1) if match else None

def cycle_metadata(p):
    start, end = p.get('startYear', 2021), p.get('endYear', 2031)
    if type(start) is not int or type(end) is not int or not 2000 <= start < end <= 2200 or end-start > 30:
        raise ValueError('Choose a start and end year between 2000 and 2200, with a cycle of 1–30 years.')
    for key in ['coordinator', 'submissionDate']:
        if not isinstance(p.get(key, ''), str) or len(p.get(key, '')) > 300: raise ValueError('Invalid '+key)
    if p.get('submissionDate'):
        due = date.fromisoformat(p['submissionDate'])
        if not start <= due.year <= end: raise ValueError('Submission date must be within the cycle years.')
    return start, end

def validate(p):
    def string(obj, key, required=False):
        value = obj.get(key)
        if not isinstance(value, str) or len(value) > 30000 or (required and not value.strip()):
            raise ValueError('Invalid '+key)
    if not isinstance(p, dict): raise ValueError('Invalid project')
    string(p, 'name', True); string(p, 'description')
    start_year, end_year = cycle_metadata(p)
    if not isinstance(p.get('standards'), list) or not isinstance(p.get('reviews'), list): raise ValueError('Invalid project lists')
    if not isinstance(p.get('owners',[]),list) or any(not isinstance(owner,str) or len(owner)>300 for owner in p.get('owners',[])): raise ValueError('Invalid owner list')
    ids = set(); standard_ids = {}; review_keys = set()
    def unique(obj):
        if not isinstance(obj, dict): raise ValueError('Invalid record')
        string(obj, 'id', True)
        if obj['id'] in ids: raise ValueError('Duplicate ID')
        ids.add(obj['id'])
    for s in p['standards']:
        unique(s); string(s, 'title', True); string(s, 'description')
        if not isinstance(s.get('criteria'), list): raise ValueError('Invalid criteria')
        standard_ids[s['id']] = set()
        for c in s['criteria']:
            unique(c); standard_ids[s['id']].add(c['id'])
            for key in ['code','title','owner','link','notes']: string(c,key,key in ['code','title'])
            if c.get('status') not in STATUSES or c.get('evidence') not in EVIDENCE or type(c.get('year')) is not int or not start_year <= c['year'] <= end_year: raise ValueError('Invalid criterion status or year')
            evidence_store.normalize_link(c.get('evidenceLink',''))
            if c['link']:
                u = urlparse(c['link'])
                if u.scheme != 'https' or u.hostname not in ['drive.google.com','docs.google.com']: raise ValueError('Use an HTTPS Google Drive or Google Docs link')
    if not isinstance(p.get('workspaceTasks',[]),list) or len(p.get('workspaceTasks',[]))>100: raise ValueError('Use up to 100 workspace tasks.')
    hidden=p.get('hiddenSections',[])
    if not isinstance(hidden,list) or any(x not in ['standards','evidence','reviews','submission'] for x in hidden) or len(set(hidden))!=len(hidden): raise ValueError('Invalid workspace sections.')
    task_names=set()
    for task in p.get('workspaceTasks',[]):
        unique(task)
        for key in ['name','category','content','link']: string(task,key,key in ['name','category'])
        if len(task['name'])>120 or len(task['category'])>60: raise ValueError('Task name or category is too long.')
        if 'chart' in task:
            import chart_config
            chart_config.validate(task['chart'])
        normalized=task['name'].strip().casefold()
        if normalized in task_names: raise ValueError('A workspace task already uses this name.')
        task_names.add(normalized)
        evidence_store.normalize_link(task['link'])
    for r in p['reviews']:
        unique(r)
        for key in ['owner','notes','due']: string(r,key)
        if r['due']:
            from datetime import date
            date.fromisoformat(r['due'])
        if r.get('standardId') not in standard_ids or r.get('semester') not in ['Spring','Fall'] or type(r.get('year')) is not int or not start_year <= r['year'] <= end_year: raise ValueError('Invalid review period')
        key = (r['standardId'],r['semester'],r['year'])
        if key in review_keys: raise ValueError('Duplicate semester review')
        review_keys.add(key)
        if not isinstance(r.get('checked'), list) or len(set(r['checked'])) != len(r['checked']) or not set(r['checked']) <= standard_ids[r['standardId']]: raise ValueError('Invalid review checklist')

LOCAL_LOGIN_LOCK = threading.Lock()
LOCAL_LOGIN_ATTEMPTS = []

class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(30)

    def log_message(self, format, *args):
        # Never log callback codes, tokens, or request query strings.
        print("%s %s" % (self.command, urlparse(self.path).path), flush=True)

    def respond(self, status, payload, content_type='application/json'):
        data = json.dumps(payload).encode() if content_type == 'application/json' else payload
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Referrer-Policy', 'no-referrer')
        if security.origin().startswith('https://'): self.send_header('Strict-Transport-Security','max-age=31536000')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; style-src 'self'; script-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
        self.end_headers(); self.wfile.write(data)

    def redirect(self, target, cookies=()):
        self.send_response(303)
        self.send_header('Location',target)
        self.send_header('Cache-Control','no-store')
        self.send_header('Referrer-Policy','no-referrer')
        for cookie in cookies: self.send_header('Set-Cookie',cookie)
        self.send_header('Content-Length','0');self.end_headers()

    def authorized(self):
        with connect() as db: self.user=security.user(self,db)
        if not self.user:
            if self.command=='GET' and not self.path.startswith('/api/'):
                path=urlparse(self.path).path
                self.redirect('/login?next='+quote(path,safe='') if re.fullmatch(r'/evidence/[0-9a-f]{32}',path) else '/login')
            else: self.respond(401,{'error':'Please sign in with your approved university account.'})
            return False
        if self.command!='GET':
            if self.headers.get('Origin')!=security.origin() or not hmac.compare_digest(self.headers.get('X-CSRF-Token',''),self.user['csrf']):
                self.respond(403,{'error':'Security check failed. Reload and try again.'});return False
        return True

    def admin(self):
        if self.user['role']=='admin': return True
        self.respond(403,{'error':'Only administrators can add, delete, restore, or manage people.'})
        return False

    def public_get(self, path):
        public={'/error.css':('error.css','text/css'),'/error.js':('error.js','text/javascript'),'/sw.js':('sw.js','text/javascript'),'/offline.html':('offline.html','text/html'),'/login':('login.html','text/html'),'/auth.js':('auth.js','text/javascript'),'/security.css':('security.css','text/css'),'/style.css':('style.css','text/css'),'/theme.css':('theme.css','text/css'),'/theme.js':('theme.js','text/javascript'),'/nu-logo-reversed.svg':('nu-logo-reversed.svg','image/svg+xml')}
        if path in public:
            file,mime=public[path];self.respond(200,(ROOT/'static'/file).read_bytes(),mime+'; charset=utf-8');return True
        if path=='/api/auth/status':
            with connect() as db: user=security.user(self,db)
            self.respond(200,{'configured':security.configured(),'localDevelopment':security.local_enabled(self),'user':user});return True
        if path=='/auth/login':
            if not security.configured(): self.redirect('/login?setup=1');return True
            try:
                flow=security.client().initiate_auth_code_flow(scopes=['User.Read'],redirect_uri=security.origin()+'/auth/callback',prompt='select_account')
                if 'auth_uri' not in flow: raise ValueError('Sign-in unavailable')
                token=secrets.token_urlsafe(32)
                with connect() as db:
                    if db.execute('SELECT COUNT(*) FROM auth_flows').fetchone()[0]>=1000: raise ValueError('Try later')
                    db.execute('INSERT INTO auth_flows VALUES (?,?,?)',(security.digest(token),json.dumps(flow),int(time.time())+600))
                self.redirect(flow['auth_uri'],[security.cookie('tracker_flow',token,600)])
            except Exception: self.redirect('/login?error=unavailable')
            return True
        if path=='/auth/callback':
            try:
                if not security.configured(): raise ValueError('Not configured')
                with connect() as db:
                    db.execute('BEGIN IMMEDIATE')
                    token=security.digest(security.cookie_value(self,'tracker_flow'))
                    row=db.execute('SELECT body FROM auth_flows WHERE token=? AND expires>?',(token,int(time.time()))).fetchone()
                    db.execute('DELETE FROM auth_flows WHERE token=?',(token,))
                if not row: raise ValueError('Expired sign-in')
                response={k:v[0] for k,v in parse_qs(urlparse(self.path).query).items()}
                result=security.client().acquire_token_by_auth_code_flow(json.loads(row[0]),response)
                oid,email=security.verify_identity(result)
                with connect() as db:
                    allowed=db.execute('SELECT email FROM users WHERE oid=? AND active=1',(oid,)).fetchone()
                    if not allowed or allowed[0]!=email: raise ValueError('Account not approved')
                    db.execute('DELETE FROM sessions WHERE token=?',(security.digest(security.cookie_value(self,'tracker_session')),))
                    session=security.new_session(db,oid)
                    security.audit(db,oid,'sign in',email)
                self.redirect('/login',[security.cookie('tracker_session',session,8*3600),security.cookie('tracker_flow','',0)])
            except Exception: self.redirect('/login?error=denied',[security.cookie('tracker_flow','',0)])
            return True
        return False

    def admin_get(self, path):
        if path not in ['/api/archives','/api/users','/api/audit']: return False
        if not self.admin(): return True
        with connect() as db:
            if path=='/api/archives':
                rows=db.execute('SELECT id,kind,cycle,label,actor,deleted FROM archives ORDER BY deleted DESC').fetchall()
                result={'archives':[dict(zip(['id','kind','cycle','label','actor','deleted'],r)) for r in rows]}
            elif path=='/api/users':
                result={'users':[dict(zip(['oid','email','role'],r)) for r in db.execute('SELECT oid,email,role FROM users WHERE active=1 ORDER BY email')]}
            else:
                result={'audit':[dict(zip(['actor','action','target','created'],r)) for r in db.execute('SELECT actor,action,target,created FROM audit ORDER BY id DESC LIMIT 200')]}
        self.respond(200,result);return True

    def admin_post(self):
        if self.path=='/api/logout':
            with connect() as db: db.execute('DELETE FROM sessions WHERE token=?',(security.digest(security.cookie_value(self,'tracker_session')),))
            self.redirect('/login',[security.cookie('tracker_session','',0)]);return True
        if self.path not in ['/api/archive-cycle','/api/archives/restore','/api/archives/purge','/api/users/save','/api/users/archive']: return False
        if not self.admin(): return True
        try:
            if self.headers.get('Content-Type')!='application/json': raise ValueError('JSON required')
            data=self.read_json();actor=self.user['oid']
            with connect() as db:
                db.execute('BEGIN IMMEDIATE')
                if self.path=='/api/archive-cycle':
                    identifier=data.get('id');row=db.execute('SELECT revision,body FROM cycles WHERE id=?',(identifier,)).fetchone()
                    if not row: raise archives.Conflict('Cycle no longer exists.')
                    if data.get('revision')!=row[0]: raise archives.Conflict('Cycle changed. Reload before deleting.')
                    p=json.loads(row[1]);archives.store(db,'cycle',identifier,p['name'],{'revision':row[0],'project':p},actor)
                    db.execute('DELETE FROM cycles WHERE id=?',(identifier,))
                elif self.path.startswith('/api/archives/'):
                    row=db.execute('SELECT * FROM archives WHERE id=?',(data.get('id'),)).fetchone()
                    if not row: raise archives.Conflict('Archive no longer exists.')
                    if self.path.endswith('/restore'): archives.restore(db,row,validate,actor)
                    else:
                        if data.get('confirmation')!='DELETE': raise ValueError('Type DELETE to permanently remove this tracker record.')
                        if row[1]=='cycle':
                            db.execute('UPDATE evidence_documents SET state=-1,revision=revision+1 WHERE cycle=? AND state=1',(row[2],))
                        if row[1]=='evidence document':
                            db.execute('UPDATE evidence_documents SET state=-1,revision=revision+1 WHERE id=?',(json.loads(row[4])['documentId'],))
                        if row[1]=='user':
                            db.execute('DELETE FROM users WHERE oid=? AND active=0',(json.loads(row[4])['oid'],))
                        db.execute('DELETE FROM archives WHERE id=?',(row[0],));security.audit(db,actor,'permanently delete '+row[1],row[2]+':'+row[3])
                else:
                    oid=data.get('oid','').lower()
                    if not security.GUID.fullmatch(oid): raise ValueError('Enter the Microsoft Entra user Object ID supplied by IT.')
                    existing=db.execute('SELECT email,role,active FROM users WHERE oid=?',(oid,)).fetchone()
                    if self.path.endswith('/archive'):
                        if oid==actor: raise ValueError('You cannot remove your own access.')
                        if not existing or not existing[2]: raise archives.Conflict('This person no longer has access.')
                        archives.store(db,'user','',existing[0],{'oid':oid,'email':existing[0],'role':existing[1]},actor)
                        db.execute('UPDATE users SET active=0 WHERE oid=?',(oid,));db.execute('DELETE FROM sessions WHERE oid=?',(oid,))
                    else:
                        email=data.get('email','').lower().strip();role=data.get('role')
                        if not security.valid_email(email) or role not in ['admin','staff']: raise ValueError('Use an @northwestu.edu address and a valid role.')
                        if oid==actor and (role!='admin' or email!=existing[0]): raise ValueError('You cannot change your own administrator identity or role.')
                        if db.execute('SELECT 1 FROM users WHERE email=? AND oid<>? AND active=1',(email,oid)).fetchone(): raise ValueError('That email already has an approved account.')
                        if existing and not existing[2]: raise ValueError('Restore this person from Archives first.')
                        db.execute('INSERT OR REPLACE INTO users VALUES (?,?,?,1)',(oid,email,role))
                        db.execute('DELETE FROM sessions WHERE oid=? AND oid<>?',(oid,actor))
                        security.audit(db,actor,'save user '+role,oid)
            self.respond(200,{'ok':True})
        except archives.Conflict as e: self.respond(409,{'error':str(e)})
        except (ValueError,TypeError,KeyError) as e: self.respond(400,{'error':str(e)})
        return True

    def serve_video(self):
        path = ROOT / 'static' / 'eagle-flight.mp4'
        size = path.stat().st_size
        start, end, status = 0, size - 1, 200
        requested = self.headers.get('Range')
        if requested:
            import re
            match = re.fullmatch(r'bytes=(\d*)-(\d*)', requested)
            try:
                if not match or not any(match.groups()): raise ValueError()
                first, last = match.groups()
                if first:
                    start = int(first)
                    end = min(int(last), size - 1) if last else size - 1
                else:
                    length = int(last)
                    if length <= 0: raise ValueError()
                    start = max(0, size - length)
                if start >= size or start > end: raise ValueError()
                status = 206
            except ValueError:
                self.send_response(416)
                self.send_header('Content-Range', 'bytes */%d' % size)
                self.send_header('Content-Length', '0')
                self.end_headers()
                return
        self.send_response(status)
        self.send_header('Content-Type', 'video/mp4')
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Content-Length', str(end - start + 1))
        self.send_header('Cache-Control', 'private, max-age=86400')
        self.send_header('X-Content-Type-Options', 'nosniff')
        if status == 206: self.send_header('Content-Range', 'bytes %d-%d/%d' % (start, end, size))
        self.end_headers()
        try:
            with path.open('rb') as video:
                video.seek(start)
                remaining = end - start + 1
                while remaining:
                    chunk = video.read(min(65536, remaining))
                    if not chunk: break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass  # A visitor skipped the intro or navigated away.

    def do_GET(self):
        path = urlparse(self.path).path
        if self.public_get(path): return
        if not self.authorized(): return
        if self.admin_get(path): return
        if evidence_store.get(self,path,connect): return
        if re.fullmatch(r'/evidence/[0-9a-f]{32}',path):
            return self.respond(200,(ROOT/'static'/'evidence.html').read_bytes(),'text/html; charset=utf-8')
        if path in ['/archives','/people']:
            if not self.admin(): return
            return self.respond(200,(ROOT/'static'/'admin.html').read_bytes(),'text/html; charset=utf-8')
        if path == '/eagle-flight.mp4': return self.serve_video()
        if path == '/api/cycles':
            with connect() as db:
                rows = db.execute('SELECT id, body FROM cycles ORDER BY id DESC').fetchall()
            return self.respond(200, {'cycles': [dict(id=identifier, **{key: json.loads(body).get(key, '') for key in ['name','description','startYear','endYear','coordinator','submissionDate']}) for identifier, body in rows]})
        identifier = cycle_id(path)
        if identifier:
            with connect() as db: row = db.execute('SELECT revision, body FROM cycles WHERE id=?', (identifier,)).fetchone()
            if not row: return self.respond(404, {'error':'Cycle not found'})
            return self.respond(200, {'revision':row[0], 'project':json.loads(row[1])})
        if path.startswith('/cycles/'):
            identifier = path.removeprefix('/cycles/').rstrip('/')
            with connect() as db: exists = db.execute('SELECT 1 FROM cycles WHERE id=?', (identifier,)).fetchone()
            if not exists: return self.respond(404, (ROOT/'static'/'error.html').read_bytes(), 'text/html; charset=utf-8')
            return self.respond(200, (ROOT/'static'/'index.html').read_bytes(), 'text/html; charset=utf-8')
        files = {'/charts.js':('charts.js','text/javascript; charset=utf-8'), '/echarts.min.js':('echarts.min.js','text/javascript; charset=utf-8'), '/evidence.js':('evidence.js','text/javascript; charset=utf-8'), '/workspace.css':('workspace.css','text/css; charset=utf-8'), '/admin.js':('admin.js','text/javascript'), '/cycles.js':('cycles.js','text/javascript; charset=utf-8'), '/eagle-perched.png':('eagle-perched.png','image/png'), '/eagle-original-flight.png':('eagle-original-flight.png','image/png'), '/eagle-sprite.png':('eagle-sprite.png','image/png'), '/eagle-cutout.png':('eagle-cutout.png','image/png'), '/eagle-poster.jpg':('eagle-poster.jpg','image/jpeg'), '/eagle-intro.js':('eagle-intro.js','text/javascript; charset=utf-8'), '/eagle-intro.css':('eagle-intro.css','text/css; charset=utf-8'), '/theme.js':('theme.js','text/javascript; charset=utf-8'), '/theme.css':('theme.css','text/css; charset=utf-8'), '/':('home.html','text/html; charset=utf-8'), '/cycles/2021-2031':('index.html','text/html; charset=utf-8'), '/home.css':('home.css','text/css; charset=utf-8'), '/nu-logo-reversed.svg':('nu-logo-reversed.svg','image/svg+xml'), '/app.js':('app.js','text/javascript; charset=utf-8'), '/style.css':('style.css','text/css; charset=utf-8')}
        if path not in files:
            if path.startswith('/api/') or 'text/html' not in self.headers.get('Accept',''): return self.respond(404, {'error':'Not found'})
            return self.respond(404, (ROOT/'static'/'error.html').read_bytes(), 'text/html; charset=utf-8')
        name, mime = files[path]
        self.respond(200,(ROOT/'static'/name).read_bytes(),mime)

    def read_json(self):
        size = int(self.headers.get('Content-Length','0'))
        if not 0 < size <= 5_000_000: raise ValueError('Project must be under 5 MB')
        data = json.loads(self.rfile.read(size))
        if not isinstance(data, dict): raise ValueError('Expected a JSON object')
        return data

    def local_login(self):
        if not security.local_enabled(self): return self.respond(403,{'error':'Local development login is unavailable.'})
        if self.headers.get('Origin')!=security.origin() or self.headers.get('Content-Type')!='application/json':
            return self.respond(403,{'error':'Open the login page at http://127.0.0.1:8000.'})
        with LOCAL_LOGIN_LOCK:
            now=time.time()
            LOCAL_LOGIN_ATTEMPTS[:]=[t for t in LOCAL_LOGIN_ATTEMPTS if now-t<60]
            if len(LOCAL_LOGIN_ATTEMPTS)>=5: return self.respond(429,{'error':'Too many attempts. Wait one minute and try again.'})
            LOCAL_LOGIN_ATTEMPTS.append(now)
        try:
            password=self.read_json().get('password','')
            if not isinstance(password,str) or len(password)>256 or not security.local_password_matches(password):
                return self.respond(401,{'error':'Incorrect local development password.'})
            with connect() as db:
                db.execute('INSERT OR REPLACE INTO users VALUES (?,?,?,1)',(security.DEV_USER,'Local development','admin'))
                db.execute('DELETE FROM sessions WHERE token=?',(security.digest(security.cookie_value(self,'tracker_session')),))
                token=security.new_session(db,security.DEV_USER)
                security.audit(db,security.DEV_USER,'local development sign in','localhost')
            self.redirect('/',[security.cookie('tracker_session',token,8*3600)])
        except (ValueError,TypeError): self.respond(400,{'error':'Invalid login request.'})

    def do_POST(self):
        if self.path=='/api/auth/local': return self.local_login()
        if not self.authorized(): return
        if self.admin_post(): return
        if evidence_store.post(self,self.path,connect): return
        if not self.admin(): return
        if self.path != '/api/cycles': return self.respond(404, {'error':'Not found'})
        if self.headers.get('Content-Type') != 'application/json': return self.respond(415, {'error':'JSON required'})
        try:
            data = self.read_json()
            if 'startYear' not in data or 'endYear' not in data: raise ValueError('Enter both cycle years')
            start, end = cycle_metadata(data)
            for key in ['name', 'coordinator']:
                if not isinstance(data.get(key), str) or not data[key].strip() or len(data[key]) > 300:
                    raise ValueError('Enter a '+key)
            if not isinstance(data.get('description',''), str) or len(data.get('description','')) > 30000: raise ValueError('Invalid description')
            identifier = '%d-%d' % (start, end)
            source_id = data.get('template', 'starter')
            with connect() as db:
                db.execute('BEGIN IMMEDIATE')
                if db.execute("SELECT 1 FROM archives WHERE cycle=? AND kind='cycle'",(identifier,)).fetchone():
                    raise ValueError('This cycle is in Archives. Restore it instead.')
                if db.execute('SELECT 1 FROM cycles WHERE id=?', (identifier,)).fetchone():
                    return self.respond(409, {'error':'A cycle with these years already exists. Choose it from the landing page.'})
                if source_id in ['starter', 'blank']:
                    project = seed()
                    if source_id == 'blank': project['standards'] = []
                else:
                    if not isinstance(source_id, str): raise ValueError('Invalid template')
                    row = db.execute('SELECT body FROM cycles WHERE id=?', (source_id,)).fetchone()
                    if not row: raise ValueError('The template cycle no longer exists. Reload and try again.')
                    original = json.loads(row[0])
                    project = seed()
                    project['standards'] = original['standards']
                    # Copy the framework only, not assignments, evidence, notes, or progress.
                    for standard in project['standards']:
                        standard['description'] = ''
                project.update(name=data['name'].strip(), description=data.get('description','').strip(), startYear=start, endYear=end,
                               coordinator=data['coordinator'].strip(), submissionDate=data.get('submissionDate',''), reviews=[], owners=[])
                for standard in project['standards']:
                    for criterion in standard['criteria']:
                        criterion.update(owner='', status='Not Started', evidence='Needed', year=start, link='', evidenceLink='', notes='')
                validate(project)
                db.execute('INSERT INTO cycles VALUES (?,0,?)', (identifier, json.dumps(project)))
                security.audit(db,self.user['oid'],'create cycle',identifier)
            self.respond(201, {'id':identifier, 'url':'/cycles/'+identifier})
        except sqlite3.IntegrityError:
            self.respond(409, {'error':'That cycle was just created. Reload the cycle list.'})
        except (ValueError, KeyError, TypeError) as e:
            self.respond(400, {'error':str(e)})

    def do_PUT(self):
        if not self.authorized(): return
        identifier = cycle_id(self.path)
        if not identifier: return self.respond(404, {'error':'Not found'})
        if self.headers.get('Content-Type') != 'application/json': return self.respond(415, {'error':'JSON required'})
        try:
            data = self.read_json()
            if type(data['revision']) is not int: raise ValueError('Invalid revision')
            with connect() as db:
                db.execute('BEGIN IMMEDIATE')
                row = db.execute('SELECT body FROM cycles WHERE id=?', (identifier,)).fetchone()
                if not row: return self.respond(404, {'error':'Cycle not found'})
                existing = json.loads(row[0])
                project = data['project']
                if not isinstance(project, dict): raise ValueError('Invalid project')
                for key in ['startYear','endYear','coordinator','submissionDate']:
                    project.setdefault(key, existing.get(key, ''))
                if (project['startYear'], project['endYear']) != (existing['startYear'], existing['endYear']):
                    raise ValueError('Backup belongs to different cycle years. Open that cycle before restoring it.')
                for standard in project['standards']:
                    for criterion in standard['criteria']:
                        value=evidence_store.normalize_link(criterion.get('evidenceLink',''))
                        if value.startswith('/evidence/'):
                            linked=db.execute('SELECT cycle FROM evidence_documents WHERE id=?',(value.rsplit('/',1)[1],)).fetchone()
                            if not linked or linked[0]!=identifier: raise ValueError('Choose an evidence document uploaded to this cycle.')
                        if 'evidenceLink' in criterion:criterion['evidenceLink']=value
                for task in project.get('workspaceTasks',[]):
                    task['link']=evidence_store.normalize_link(task['link'])
                    if task['link'].startswith('/evidence/'):
                        linked=db.execute('SELECT cycle FROM evidence_documents WHERE id=?',(task['link'].rsplit('/',1)[1],)).fetchone()
                        if not linked or linked[0]!=identifier: raise ValueError('Choose a document uploaded to this cycle.')
                validate(project)
                if archives.needs_admin(existing,project) and not self.admin(): return
                result = db.execute('UPDATE cycles SET body=?, revision=revision+1 WHERE id=? AND revision=?', (json.dumps(project),identifier,data['revision']))
                if result.rowcount != 1: return self.respond(409, {'error':'Another staff member saved changes. Download your backup, then reload before editing again.'})
                archives.capture_removed(db,identifier,existing,project,self.user['oid'])
                security.audit(db,self.user['oid'],'update cycle',identifier)
            self.respond(200, {'revision':data['revision']+1})
        except (ValueError, KeyError, TypeError) as e:
            self.respond(400, {'error':str(e)})

if __name__ == '__main__':
    os.umask(0o077)
    host = os.getenv('HOST','127.0.0.1'); port = int(os.getenv('PORT','8000'))
    public=urlparse(security.origin())
    if public.scheme not in ['http','https'] or not public.netloc or public.path or public.query or public.fragment:
        raise SystemExit('TRACKER_ORIGIN must be an origin, without a path or query.')
    if public.scheme!='https' and public.hostname not in ['localhost','127.0.0.1']:
        raise SystemExit('HTTPS is required outside localhost.')
    if host not in ['127.0.0.1','localhost'] and (not security.configured() or public.scheme!='https'):
        raise SystemExit('Configure Microsoft sign-in and an HTTPS TRACKER_ORIGIN before exposing the server.')
    connect().close()
    httpd = ThreadingHTTPServer((host,port),Handler)
    print('ACBSP Tracker running at http://%s:%s' % (host,port), flush=True)
    httpd.serve_forever()
