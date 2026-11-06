"""Local tracker archives. This module never contacts cloud file providers."""
import json
import secrets
import time
from security import audit

class Conflict(ValueError): pass

def store(db, kind, cycle, label, body, actor):
    identifier=secrets.token_hex(16)
    db.execute('INSERT INTO archives VALUES (?,?,?,?,?,?,?)',(identifier,kind,cycle,label,json.dumps(body),actor,int(time.time())))
    audit(db,actor,'archive '+kind,cycle+':'+label)
    return identifier

def structure(p):
    return ([(s['id'],[c['id'] for c in s['criteria']]) for s in p['standards']], [(r['id'],r['standardId'],r['year'],r['semester']) for r in p['reviews']],p.get('owners',[]),[(t['id'],t['name'],t['category']) for t in p.get('workspaceTasks',[])])

def needs_admin(old,new):
    if structure(old)!=structure(new) or old.get('hiddenSections',[])!=new.get('hiddenSections',[]): return True
    old_c={c['id']:c for s in old['standards'] for c in s['criteria']}
    return any((old_c[c['id']]['link']!=c['link'] or (old_c[c['id']].get('evidenceLink') and old_c[c['id']].get('evidenceLink')!=c.get('evidenceLink',''))) for s in new['standards'] for c in s['criteria'])

def capture_removed(db, cycle, old, new, actor):
    for section in set(new.get('hiddenSections',[]))-set(old.get('hiddenSections',[])):
        store(db,'workspace section',cycle,section,{'section':section},actor)
    task_ids={t['id'] for t in new.get('workspaceTasks',[])}
    for index,task in enumerate(old.get('workspaceTasks',[])):
        if task['id'] not in task_ids:store(db,'workspace task',cycle,task['name'],{'item':task,'index':index},actor)
    standards={s['id']:s for s in new['standards']}
    removed_standards=set()
    for index,s in enumerate(old['standards']):
        if s['id'] not in standards:
            removed_standards.add(s['id'])
            store(db,'standard',cycle,s['title'],{'item':s,'index':index,'reviews':[r for r in old['reviews'] if r['standardId']==s['id']]},actor)
            continue
        criteria={c['id']:c for c in standards[s['id']]['criteria']}
        for ci,c in enumerate(s['criteria']):
            if c['id'] not in criteria:
                store(db,'criterion',cycle,c['code']+' '+c['title'],{'item':c,'parent':s['id'],'index':ci,'checked':[r['id'] for r in old['reviews'] if c['id'] in r['checked']]},actor)
            elif c['link'] and c['link']!=criteria[c['id']]['link']:
                store(db,'evidence link',cycle,c['code']+' document link',{'criterion':c['id'],'link':c['link']},actor)
            if c['id'] in criteria and c.get('evidenceLink') and c.get('evidenceLink')!=criteria[c['id']].get('evidenceLink',''):
                store(db,'criterion evidence link',cycle,c['code']+' evidence link',{'criterion':c['id'],'link':c['evidenceLink']},actor)
    review_ids={r['id'] for r in new['reviews']}
    for index,r in enumerate(old['reviews']):
        if r['id'] not in review_ids and r['standardId'] not in removed_standards:
            store(db,'review',cycle,r['semester']+' '+str(r['year']),{'item':r,'index':index},actor)

def restore(db, row, validate, actor):
    identifier,kind,cycle,label,body,_,_=row
    saved=json.loads(body)
    if kind=='user':
        oid=saved['oid']
        if db.execute('SELECT 1 FROM users WHERE oid=? AND active=1',(oid,)).fetchone(): raise Conflict('This person already has access.')
        if db.execute('SELECT 1 FROM users WHERE email=? AND oid<>? AND active=1',(saved['email'],oid)).fetchone(): raise Conflict('Another active account already uses this email. Nothing was overwritten.')
        db.execute('INSERT OR REPLACE INTO users VALUES (?,?,?,1)',(oid,saved['email'],saved['role']))
    elif kind=='evidence document':
        if not db.execute('SELECT 1 FROM cycles WHERE id=?',(cycle,)).fetchone(): raise Conflict('Restore the parent cycle first.')
        updated=db.execute('UPDATE evidence_documents SET state=1,revision=revision+1 WHERE id=? AND state=0',(saved['documentId'],))
        if updated.rowcount!=1: raise Conflict('This document is no longer archived.')
    elif kind=='cycle':
        if db.execute('SELECT 1 FROM cycles WHERE id=?',(cycle,)).fetchone(): raise Conflict('A cycle with these years already exists. Nothing was overwritten.')
        validate(saved['project'])
        db.execute('INSERT INTO cycles VALUES (?,?,?)',(cycle,saved['revision']+1,json.dumps(saved['project'])))
    else:
        current=db.execute('SELECT revision,body FROM cycles WHERE id=?',(cycle,)).fetchone()
        if not current: raise Conflict('Restore the parent cycle first.')
        p=json.loads(current[1]);item=saved.get('item')
        ids={s['id'] for s in p['standards']}|{c['id'] for s in p['standards'] for c in s['criteria']}|{r['id'] for r in p['reviews']}|{t['id'] for t in p.get('workspaceTasks',[])}
        if item and item['id'] in ids: raise Conflict('An item with this ID already exists. Nothing was overwritten.')
        if kind=='workspace section':
            if saved['section'] not in p.get('hiddenSections',[]): raise Conflict('This section is already visible.')
            p['hiddenSections'].remove(saved['section'])
        elif kind=='workspace task':
            p.setdefault('workspaceTasks',[]).insert(saved['index'],item)
        elif kind=='standard':
            if any(c['id'] in ids for c in item['criteria']) or any(r['id'] in ids for r in saved['reviews']): raise Conflict('Some child items already exist. Nothing was overwritten.')
            p['standards'].insert(saved['index'],item);p['reviews'].extend(saved['reviews'])
        elif kind=='criterion':
            parent=next((s for s in p['standards'] if s['id']==saved['parent']),None)
            if parent is None: raise Conflict('Restore the parent standard first.')
            parent['criteria'].insert(saved['index'],item)
            for r in p['reviews']:
                if r['id'] in saved['checked'] and r['standardId']==parent['id'] and item['id'] not in r['checked']: r['checked'].append(item['id'])
        elif kind=='review': p['reviews'].insert(saved['index'],item)
        elif kind in ['evidence link','criterion evidence link']:
            c=next((c for s in p['standards'] for c in s['criteria'] if c['id']==saved['criterion']),None)
            if c is None: raise Conflict('Restore the parent criterion first.')
            key='evidenceLink' if kind=='criterion evidence link' else 'link'
            if c.get(key): raise Conflict('This criterion already has a document link. Clear it before restoring this link.')
            c[key]=saved['link']
        else: raise ValueError('Unsupported archive type')
        try: validate(p)
        except ValueError as exc: raise Conflict('Restore conflicts with the current framework: '+str(exc))
        db.execute('UPDATE cycles SET revision=revision+1,body=? WHERE id=?',(json.dumps(p),cycle))
    db.execute('DELETE FROM archives WHERE id=?',(identifier,))
    audit(db,actor,'restore '+kind,cycle+':'+label)
