import copy
import http.client
import json
from urllib.parse import quote
import test_server
import server
import security
import evidence_store

class EvidenceTests(test_server.TrackerTests):
    def setUp(self):
        with server.connect() as db:
            db.execute('DELETE FROM evidence_documents');db.execute('DELETE FROM evidence_versions');db.execute('DELETE FROM archives')
            p=server.seed();p.update(startYear=2021,endYear=2031,coordinator='',submissionDate='')
            db.execute('INSERT OR REPLACE INTO cycles VALUES (?,0,?)',('2021-2031',json.dumps(p)))
            db.execute("INSERT OR REPLACE INTO users VALUES ('staff-evidence','staff@northwestu.edu','staff',1)")
            self.staff_token=security.new_session(db,'staff-evidence')
            self.staff_csrf=db.execute('SELECT csrf FROM sessions WHERE token=?',(security.digest(self.staff_token),)).fetchone()[0]

    def upload(self,name='report.txt',data=b'Private evidence',path='/api/cycles/2021-2031/evidence',revision=None,staff=False,auth=True):
        h={'Content-Type':'application/octet-stream','X-File-Name':quote(name),'Origin':security.origin()}
        if auth:h.update(Cookie='tracker_session='+(self.staff_token if staff else self.token),**{'X-CSRF-Token':self.staff_csrf if staff else self.csrf})
        if revision is not None:h['X-Evidence-Revision']=str(revision)
        c=http.client.HTTPConnection('127.0.0.1',self.httpd.server_port)
        c.request('POST',path,data,h);r=c.getresponse();result=r.status,json.loads(r.read());c.close();return result

    def test_upload_link_download_versions_and_scope(self):
        status,result=self.upload(staff=True);self.assertEqual(status,201,result);identifier=result['id']
        detail=json.loads(self.request('GET','/api/evidence/'+identifier)[1]);self.assertEqual(detail['revision'],1)
        first=detail['versions'][0]['id']
        self.assertEqual(self.request('GET','/api/evidence/'+identifier+'/download/'+first)[1],b'Private evidence')
        self.assertEqual(self.request('GET','/api/evidence/'+identifier,auth=False)[0],401)
        self.assertEqual(self.request('GET',result['url'],auth=False)[0],303)
        self.assertEqual(self.request('GET',result['url'])[0],200)
        original=json.loads(self.request('GET')[1]);original['project']['standards'][0]['criteria'][0]['evidenceLink']=security.origin()+result['url']
        self.assertEqual(self.request('PUT',payload=original)[0],200)
        loaded=json.loads(self.request('GET')[1]);self.assertEqual(loaded['project']['standards'][0]['criteria'][0]['evidenceLink'],result['url'])
        status,new=self.upload('updated.txt',b'Updated evidence','/api/evidence/'+identifier+'/versions',1,True);self.assertEqual(status,201,new);self.assertEqual(new['url'],result['url'])
        self.assertEqual(self.upload(path='/api/evidence/'+identifier+'/versions',revision=1)[0],409)
        detail=json.loads(self.request('GET','/api/evidence/'+identifier)[1]);self.assertEqual(len(detail['versions']),2)
        self.assertEqual(self.request('GET','/api/evidence/'+identifier+'/download/'+first)[1],b'Private evidence')
        self.assertEqual(self.upload(path='/api/cycles/2999-3000/evidence')[0],409)

    def test_invalid_uploads_and_links(self):
        for name,data in [('bad.html',b'<script>bad</script>'),('../file.txt',b'text'),('file.pdf',b'not a PDF'),('bad.docx',b'not a zip'),('file.txt',b'')]:
            self.assertEqual(self.upload(name,data)[0],400)
        self.assertEqual(self.upload(auth=False)[0],401)
        for value in ['javascript:alert(1)','http://evil.example','//evil.example','/evidence/nope','https://user:password@example.com']:
            with self.assertRaises(ValueError):evidence_store.normalize_link(value)
        p=json.loads(self.request('GET')[1]);p['project']['standards'][0]['criteria'][0]['evidenceLink']='/evidence/'+'f'*32
        self.assertEqual(self.request('PUT',payload=p)[0],400)

    def test_archive_purge_preserves_files_and_permissions(self):
        _,result=self.upload();identifier=result['id'];path='/api/evidence/'+identifier
        detail=json.loads(self.request('GET',path)[1]);version=detail['versions'][0]['id']
        staff_headers={'Cookie':'tracker_session='+self.staff_token,'Origin':security.origin(),'X-CSRF-Token':self.staff_csrf}
        self.assertEqual(self.request('POST',path+'/archive',{'revision':1},staff_headers,auth=False)[0],403)
        self.assertEqual(self.request('POST',path+'/archive',{'revision':1})[0],200)
        self.assertEqual(self.request('GET',path,headers=staff_headers,auth=False)[0],404)
        archive=json.loads(self.request('GET','/api/archives')[1])['archives'][0]
        self.assertEqual(self.request('POST','/api/archives/restore',{'id':archive['id']})[0],200)
        detail=json.loads(self.request('GET',path)[1]);self.assertTrue(detail['available'])
        self.assertEqual(self.request('POST',path+'/archive',{'revision':detail['revision']})[0],200)
        archive=json.loads(self.request('GET','/api/archives')[1])['archives'][0]
        self.assertEqual(self.request('POST','/api/archives/purge',{'id':archive['id'],'confirmation':'DELETE'})[0],200)
        self.assertEqual(self.request('GET',path+'/download/'+version)[1],b'Private evidence')
        with server.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM evidence_versions').fetchone()[0],1)

    def test_cycle_archive_restore_and_permanent_delete_keep_files(self):
        _,result=self.upload();identifier=result['id'];path='/api/evidence/'+identifier
        version=json.loads(self.request('GET',path)[1])['versions'][0]['id']
        self.assertEqual(self.request('POST','/api/archive-cycle',{'id':'2021-2031','revision':0})[0],200)
        archive=json.loads(self.request('GET','/api/archives')[1])['archives'][0]
        self.assertEqual(self.request('POST','/api/archives/restore',{'id':archive['id']})[0],200)
        self.assertEqual(len(json.loads(self.request('GET','/api/cycles/2021-2031/evidence')[1])['documents']),1)
        self.assertEqual(self.request('POST','/api/archive-cycle',{'id':'2021-2031','revision':1})[0],200)
        archive=json.loads(self.request('GET','/api/archives')[1])['archives'][0]
        self.assertEqual(self.request('POST','/api/archives/purge',{'id':archive['id'],'confirmation':'DELETE'})[0],200)
        self.assertEqual(self.request('GET',path+'/download/'+version)[1],b'Private evidence')

    def test_links_cannot_cross_cycles_and_reference_archive_restores(self):
        _,result=self.upload()
        self.request('POST','/api/cycles',{'name':'Second','startYear':2081,'endYear':2090,'coordinator':'Team','template':'starter'})
        path='/api/cycles/2081-2090/project'
        data=json.loads(self.request('GET',path)[1]);data['project']['standards'][0]['criteria'][0]['evidenceLink']=result['url']
        self.assertEqual(self.request('PUT',path,data)[0],400)
        data=json.loads(self.request('GET')[1]);data['project']['standards'][0]['criteria'][0]['evidenceLink']=result['url']
        self.assertEqual(self.request('PUT',payload=data)[0],200)
        data=json.loads(self.request('GET')[1]);data['project']['standards'][0]['criteria'][0]['evidenceLink']=''
        self.assertEqual(self.request('PUT',payload=data)[0],200)
        archive=json.loads(self.request('GET','/api/archives')[1])['archives'][0]
        self.assertEqual(archive['kind'],'criterion evidence link')
        self.assertEqual(self.request('POST','/api/archives/restore',{'id':archive['id']})[0],200)
        self.assertEqual(json.loads(self.request('GET')[1])['project']['standards'][0]['criteria'][0]['evidenceLink'],result['url'])

    def test_upload_csrf_and_limits(self):
        from unittest.mock import patch
        conn=http.client.HTTPConnection('127.0.0.1',self.httpd.server_port)
        conn.request('POST','/api/cycles/2021-2031/evidence',b'text',{'Content-Type':'application/octet-stream','X-File-Name':'report.txt','Cookie':'tracker_session='+self.token,'Origin':'https://evil.example','X-CSRF-Token':self.csrf})
        response=conn.getresponse();self.assertEqual(response.status,403);response.read();conn.close()
        with patch.object(evidence_store,'MAX_FILE',3):self.assertEqual(self.upload(data=b'four')[0],400)
        with patch.object(evidence_store,'MAX_STORAGE',3):self.assertEqual(self.upload(data=b'four')[0],400)
