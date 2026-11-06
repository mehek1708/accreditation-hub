"""Private, versioned evidence storage. Record deletion never deletes file bytes."""
import hashlib
import io
import json
import re
import secrets
import time
import zipfile
from pathlib import PurePosixPath
from urllib.parse import unquote, quote, urlparse
import archives
import security

MAX_FILE = 10 * 1024 * 1024
MAX_STORAGE = 1024 * 1024 * 1024
ID = r'[0-9a-f]{32}'

def schema(db):
    db.execute('CREATE TABLE IF NOT EXISTS evidence_documents (id TEXT PRIMARY KEY, cycle TEXT NOT NULL, title TEXT NOT NULL, state INTEGER NOT NULL, revision INTEGER NOT NULL, created INTEGER NOT NULL, actor TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS evidence_versions (id TEXT PRIMARY KEY, document TEXT NOT NULL, filename TEXT NOT NULL, size INTEGER NOT NULL, sha256 TEXT NOT NULL, created INTEGER NOT NULL, actor TEXT NOT NULL, body BLOB NOT NULL)')
    db.execute('CREATE INDEX IF NOT EXISTS evidence_cycle ON evidence_documents(cycle)')
    db.execute('CREATE INDEX IF NOT EXISTS evidence_document ON evidence_versions(document)')

def normalize_link(value):
    if not isinstance(value,str) or len(value)>2048: raise ValueError('Invalid evidence link')
    value=value.strip()
    if not value:return ''
    u=urlparse(value)
    if u.scheme+'://'+u.netloc==security.origin() and re.fullmatch('/evidence/'+ID,u.path) and not u.query and not u.fragment:
        return u.path
    if re.fullmatch('/evidence/'+ID,value):return value
    if u.scheme=='https' and u.hostname and not u.username and not u.password and not any(ord(c)<32 for c in value):return value
    raise ValueError('Paste a copied portal evidence link or an HTTPS document link.')

def check_file(name,data):
    if not name or len(name)>180 or any(ord(c)<32 for c in name) or any(c in name for c in '/\\:'):
        raise ValueError('Use a filename without path characters, up to 180 characters.')
    ext=PurePosixPath(name).suffix.lower()
    if ext=='.pdf': valid=data.startswith(b'%PDF-')
    elif ext=='.png':valid=data.startswith(b'\x89PNG\r\n\x1a\n')
    elif ext in ['.jpg','.jpeg']:valid=data.startswith(b'\xff\xd8\xff')
    elif ext in ['.txt','.csv']:
        try:data.decode('utf-8-sig');valid=b'\x00' not in data
        except UnicodeDecodeError:valid=False
    elif ext in ['.docx','.xlsx','.pptx']:
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                names=z.namelist();prefix={'.docx':'word/document.xml','.xlsx':'xl/workbook.xml','.pptx':'ppt/presentation.xml'}[ext]
                valid=('[Content_Types].xml' in names and prefix in names and len(names)<=10000 and sum(i.file_size for i in z.infolist())<=100*1024*1024 and not any('vbaproject' in n.lower() for n in names))
        except (zipfile.BadZipFile,ValueError):valid=False
    else:raise ValueError('Use PDF, DOCX, XLSX, PPTX, TXT, CSV, PNG, or JPG files (up to 10 MB).')
    if not valid:raise ValueError('The file contents do not match a supported document format.')

def document(db,identifier,role):
    row=db.execute('SELECT id,cycle,title,state,revision,created,actor FROM evidence_documents WHERE id=?',(identifier,)).fetchone()
    if not row:return None
    p=dict(zip(['id','cycle','title','state','revision','created','actor'],row))
    parent=db.execute('SELECT 1 FROM cycles WHERE id=?',(p['cycle'],)).fetchone()
    if (p['state']!=1 or not parent) and role!='admin':return None
    p['available']=bool(parent and p['state']==1)
    p['url']='/evidence/'+p['id']
    p['versions']=[dict(zip(['id','filename','size','sha256','created','actor'],r)) for r in db.execute('SELECT id,filename,size,sha256,created,actor FROM evidence_versions WHERE document=? ORDER BY rowid DESC',(identifier,))]
    return p

def get(h,path,connect):
    listing=re.fullmatch(r'/api/cycles/([0-9]{4}-[0-9]{4})/evidence',path)
    detail=re.fullmatch(r'/api/evidence/('+ID+')',path)
    download=re.fullmatch(r'/api/evidence/('+ID+r')/download/('+ID+')',path)
    if not any([listing,detail,download]):return False
    with connect() as db:
        if listing:
            cycle=listing.group(1)
            if not db.execute('SELECT 1 FROM cycles WHERE id=?',(cycle,)).fetchone():h.respond(404,{'error':'Cycle not found'});return True
            ids=[r[0] for r in db.execute('SELECT id FROM evidence_documents WHERE cycle=? AND state=1 ORDER BY created DESC,id',(cycle,))]
            h.respond(200,{'documents':[document(db,i,h.user['role']) for i in ids]});return True
        identifier=(detail or download).group(1)
        p=document(db,identifier,h.user['role'])
        if not p:h.respond(404,{'error':'Evidence is unavailable. It may have been deleted; ask an administrator to restore it.'});return True
        if detail:h.respond(200,p);return True
        row=db.execute('SELECT filename,body FROM evidence_versions WHERE id=? AND document=?',(download.group(2),identifier)).fetchone()
        if not row:h.respond(404,{'error':'Version not found'});return True
        name,data=row
    h.send_response(200)
    h.send_header('Content-Type','application/octet-stream')
    h.send_header('Content-Disposition',"attachment; filename=\"evidence\"; filename*=UTF-8''"+quote(name,safe=''))
    h.send_header('Content-Length',str(len(data)))
    h.send_header('Cache-Control','no-store')
    h.send_header('X-Content-Type-Options','nosniff')
    h.send_header('Content-Security-Policy',"sandbox; default-src 'none'")
    h.end_headers();h.wfile.write(data)
    return True

def post(h,path,connect):
    upload=re.fullmatch(r'/api/cycles/([0-9]{4}-[0-9]{4})/evidence',path)
    replace=re.fullmatch(r'/api/evidence/('+ID+')/versions',path)
    remove=re.fullmatch(r'/api/evidence/('+ID+')/archive',path)
    if not any([upload,replace,remove]):return False
    try:
        if remove:
            if not h.admin():return True
            data=h.read_json()
            with connect() as db:
                db.execute('BEGIN IMMEDIATE')
                p=document(db,remove.group(1),'admin')
                if not p or not p['available']:raise archives.Conflict('This document is no longer active.')
                if data.get('revision')!=p['revision']:raise archives.Conflict('The document changed. Reload and try again.')
                archives.store(db,'evidence document',p['cycle'],p['title'],{'documentId':p['id']},h.user['oid'])
                db.execute('UPDATE evidence_documents SET state=0,revision=revision+1 WHERE id=?',(p['id'],))
            h.respond(200,{'ok':True});return True
        if h.headers.get('Content-Type')!='application/octet-stream':raise ValueError('Send a document file.')
        size=int(h.headers.get('Content-Length','0'))
        if not 0<size<=MAX_FILE:raise ValueError('Choose a nonempty document up to 10 MB.')
        name=unquote(h.headers.get('X-File-Name',''))
        data=h.rfile.read(size)
        if len(data)!=size:raise ValueError('Upload was interrupted. Please retry.')
        check_file(name,data)
        identifier=secrets.token_hex(16) if upload else replace.group(1)
        version=secrets.token_hex(16);now=int(time.time())
        with connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if upload:
                cycle=upload.group(1)
                if not db.execute('SELECT 1 FROM cycles WHERE id=?',(cycle,)).fetchone():raise archives.Conflict('The cycle no longer exists.')
            else:
                p=document(db,identifier,h.user['role'])
                if not p or not p['available']:raise archives.Conflict('The document is no longer active.')
                if int(h.headers.get('X-Evidence-Revision','-1'))!=p['revision']:raise archives.Conflict('Another person uploaded a version. Reload before replacing it.')
                cycle=p['cycle']
            if db.execute('SELECT COALESCE(SUM(size),0) FROM evidence_versions').fetchone()[0]+size>MAX_STORAGE:raise ValueError('Evidence storage has reached its 1 GB limit. Contact the portal administrator.')
            if upload:db.execute('INSERT INTO evidence_documents VALUES (?,?,?,1,1,?,?)',(identifier,cycle,name,now,h.user['oid']))
            else:db.execute('UPDATE evidence_documents SET revision=revision+1 WHERE id=?',(identifier,))
            db.execute('INSERT INTO evidence_versions VALUES (?,?,?,?,?,?,?,?)',(version,identifier,name,size,hashlib.sha256(data).hexdigest(),now,h.user['oid'],data))
            security.audit(db,h.user['oid'],'upload evidence version',cycle+':'+identifier)
        h.respond(201,{'id':identifier,'url':'/evidence/'+identifier})
    except archives.Conflict as e:h.respond(409,{'error':str(e)})
    except (ValueError,TypeError,KeyError) as e:h.respond(400,{'error':str(e)})
    return True
