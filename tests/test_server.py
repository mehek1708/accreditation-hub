import base64
import copy
import http.client
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import server
import security
import archives

class TrackerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(dir=server.ROOT / 'data')
        cls.original_db = server.DB
        server.DB = Path(cls.temp.name) / 'test.sqlite3'
        with server.connect() as db:
            db.execute("INSERT INTO users VALUES ('admin-test','admin@northwestu.edu','admin',1)")
            cls.token=security.new_session(db,'admin-test')
            cls.csrf=db.execute('SELECT csrf FROM sessions').fetchone()[0]
        cls.httpd = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown(); cls.httpd.server_close()
        server.DB = cls.original_db
        cls.temp.cleanup()

    def request(self, method, path='/api/project', payload=None, headers=None, auth=True):
        conn = http.client.HTTPConnection('127.0.0.1', self.httpd.server_port)
        h={'Content-Type':'application/json',**(headers or {})}
        if auth: h.update({'Cookie':'tracker_session='+self.token,'X-CSRF-Token':self.csrf,'Origin':security.origin()})
        conn.request(method, path, json.dumps(payload) if payload else None, h)
        r = conn.getresponse(); result = (r.status, r.read()); conn.close()
        return result

    def test_recovery_pages_keep_api_errors_json(self):
        status, body = self.request('GET', '/missing-page', headers={'Accept':'text/html'})
        self.assertEqual(status, 404)
        self.assertIn(b'data-error-page="missing"', body)
        status, body = self.request('GET', '/api/missing', headers={'Accept':'text/html'})
        self.assertEqual(status, 404)
        self.assertEqual(json.loads(body)['error'], 'Not found')
        for path in ['/offline.html', '/error.js', '/error.css', '/sw.js']:
            self.assertEqual(self.request('GET', path, auth=False)[0], 200)

    def test_persistence_and_conflict(self):
        status, body = self.request('GET'); self.assertEqual(status, 200)
        data = json.loads(body); data['project']['name'] = 'Team Project'
        self.assertEqual(self.request('PUT', payload=data)[0], 200)
        self.assertEqual(self.request('PUT', payload=data)[0], 409)
        loaded = json.loads(self.request('GET')[1]); self.assertEqual(loaded['project']['name'], 'Team Project')
        with server.connect() as db:
            self.assertEqual(json.loads(db.execute("SELECT body FROM cycles WHERE id='2021-2031'").fetchone()[0])['name'], 'Team Project')

    def test_validation(self):
        original = server.seed(); server.validate(original)
        for key, value in [('year',2032),('status','Unknown'),('evidence','Unknown'),('link','javascript:alert(1)'),('link','https://docs.google.com.evil.test/a')]:
            p = copy.deepcopy(original); p['standards'][0]['criteria'][0][key] = value
            with self.assertRaises(ValueError): server.validate(p)
        p = copy.deepcopy(original); p['reviews'] = [{'id':'r1','standardId':'s1','year':2026,'semester':'Fall','owner':'A','due':'2026-12-01','notes':'','checked':['c1']}]
        server.validate(p)
        p['reviews'][0]['checked'] = ['missing']
        with self.assertRaises(ValueError): server.validate(p)

    def test_invalid_request_does_not_save(self):
        data=json.loads(self.request('GET')[1]); data['project']['standards'][0]['criteria'][0]['year']=2035
        self.assertEqual(self.request('PUT',payload=data)[0],400)
        self.assertNotEqual(json.loads(self.request('GET')[1])['project']['standards'][0]['criteria'][0]['year'],2035)

    def test_landing_and_cycle_routes(self):
        status, body = self.request('GET', '/')
        self.assertEqual(status, 200)
        self.assertIn(b'Choose an accreditation cycle', body)
        self.assertIn(b'id="add-cycle"', body)
        self.assertIn(b'id="cycle-list"', body)
        status, body = self.request('GET', '/cycles/2021-2031')
        self.assertEqual(status, 200)
        self.assertIn(b'id="content"', body)
        self.assertIn(b'nu-logo-reversed.svg', body)
        self.assertEqual(self.request('GET','/nu-logo-reversed.svg')[0],200)
        self.assertEqual(self.request('GET','/home.css')[0],200)
        self.assertEqual(self.request('GET','/cycles/2032-2042')[0],404)
        self.assertEqual(self.request('GET','/',auth=False)[0],303)
        self.assertEqual(self.request('GET','/api/project',auth=False)[0],401)

    def test_cycle_creation_and_isolation(self):
        before=json.loads(self.request('GET')[1])
        payload={'name':'ACBSP 2041','startYear':2032,'endYear':2041,'coordinator':'Accreditation team','submissionDate':'2041-06-01','description':'Next cycle','template':'2021-2031'}
        status,body=self.request('POST','/api/cycles',payload)
        self.assertEqual(status,201,body)
        identifier=json.loads(body)['id']
        path='/api/cycles/'+identifier+'/project'
        data=json.loads(self.request('GET',path)[1])
        self.assertEqual(data['project']['coordinator'],'Accreditation team')
        self.assertEqual(data['project']['reviews'],[])
        self.assertEqual([len(s['criteria']) for s in data['project']['standards']],[4,4,4,4,4,6,4])
        for standard in data['project']['standards']:
            for c in standard['criteria']:
                self.assertEqual((c['year'],c['status'],c['owner'],c['link'],c['notes']),(2032,'Not Started','','',''))
        c=data['project']['standards'][0]['criteria'][0]
        c.update(owner='New owner',status='In Progress')
        data['project']['reviews']=[{'id':'review-new','standardId':'s1','year':2040,'semester':'Fall','owner':'Team','due':'2040-12-01','notes':'New review','checked':['c1']}]
        self.assertEqual(self.request('PUT',path,data)[0],200)
        self.assertEqual(self.request('PUT',path,data)[0],409)
        self.assertEqual(json.loads(self.request('GET')[1]),before)
        self.assertEqual(self.request('GET','/cycles/'+identifier)[0],200)
        self.assertEqual(self.request('POST','/api/cycles',payload)[0],409)
        fresh=json.loads(self.request('GET',path)[1]);fresh['project']['endYear']=2042
        self.assertEqual(self.request('PUT',path,fresh)[0],400)
        listing=json.loads(self.request('GET','/api/cycles')[1])['cycles']
        self.assertIn(identifier,[c['id'] for c in listing])

    def test_blank_framework_creation(self):
        before=json.loads(self.request('GET')[1])
        payload={'name':'Custom framework','startYear':2070,'endYear':2080,'coordinator':'Team','template':'blank'}
        status,body=self.request('POST','/api/cycles',payload)
        self.assertEqual(status,201,body)
        path='/api/cycles/2070-2080/project'
        data=json.loads(self.request('GET',path)[1])
        self.assertEqual(data['project']['standards'],[])
        self.assertEqual(data['project']['reviews'],[])
        standard=copy.deepcopy(server.seed()['standards'][0])
        for c in standard['criteria']:c['year']=2070
        data['project']['standards'].append(standard)
        self.assertEqual(self.request('PUT',path,data)[0],200)
        self.assertEqual(len(json.loads(self.request('GET',path)[1])['project']['standards']),1)
        self.assertEqual(json.loads(self.request('GET')[1]),before)

    def test_invalid_cycles_and_auth(self):
        base={'name':'Future','startYear':2050,'endYear':2060,'coordinator':'Team','submissionDate':'','template':'starter'}
        for change in [{'endYear':2049},{'endYear':2100},{'coordinator':''},{'submissionDate':'2061-01-01'},{'template':'missing'}]:
            payload=dict(base,**change)
            self.assertEqual(self.request('POST','/api/cycles',payload)[0],400)
        self.assertEqual(self.request('POST','/api/cycles',base,auth=False)[0],401)
        self.assertEqual(self.request('GET','/api/cycles/2090-2100/project')[0],404)
        self.assertEqual(self.request('PUT','/api/cycles/2090-2100/project',{'revision':0,'project':server.seed()})[0],404)

    def test_legacy_migration_preserves_data(self):
        import sqlite3
        with tempfile.TemporaryDirectory(dir=server.ROOT/'data') as folder:
            legacy=Path(folder)/'legacy.sqlite3'
            original=server.seed();original['standards'][0]['criteria'][0]['notes']='Preserve this school record'
            with sqlite3.connect(str(legacy)) as db:
                db.execute('CREATE TABLE project (id INTEGER PRIMARY KEY, revision INTEGER, body TEXT)')
                db.execute('INSERT INTO project VALUES (1,17,?)',(json.dumps(original),))
            with patch.object(server,'DB',legacy):
                with server.connect() as db:
                    revision,body=db.execute("SELECT revision,body FROM cycles WHERE id='2021-2031'").fetchone()
                    self.assertEqual(revision,17)
                    migrated=json.loads(body)
                    self.assertEqual(migrated['standards'],original['standards'])
                    db.execute("UPDATE cycles SET revision=18 WHERE id='2021-2031'")
                with server.connect() as db:
                    self.assertEqual(db.execute('SELECT revision FROM cycles').fetchone()[0],18)

    def test_video_ranges(self):
        if not (server.ROOT / 'static' / 'eagle-flight.mp4').exists():
            self.skipTest('Optional legacy reference video is not distributed.')
        size = (server.ROOT / 'static' / 'eagle-flight.mp4').stat().st_size
        status, body = self.request('GET','/eagle-flight.mp4',headers={'Range':'bytes=0-99'})
        self.assertEqual(status,206)
        self.assertEqual(len(body),100)
        self.assertEqual(self.request('GET','/eagle-flight.mp4',headers={'Range':'bytes=-50'})[0],206)
        self.assertEqual(self.request('GET','/eagle-flight.mp4',headers={'Range':'bytes=%d-' % size})[0],416)
        self.assertEqual(self.request('GET','/eagle-poster.jpg')[0],200)
        self.assertEqual(self.request('GET','/eagle-flight.mp4',auth=False)[0],303)

    def test_auth_and_static(self):
        self.assertEqual(self.request('GET','/')[0],200)
        self.assertEqual(self.request('GET','/../server.py')[0],404)
        self.assertEqual(self.request('PUT',payload={'x':1},headers={'Content-Type':'text/plain'})[0],415)
        self.assertEqual(self.request('GET',auth=False)[0],401)

if __name__ == '__main__': unittest.main()
