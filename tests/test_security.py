import copy
import json
import os
import time
from unittest.mock import patch, Mock
import security
import server
import archives
import test_server

class SecurityTests(test_server.TrackerTests):
    # Every scenario uses its own isolated database; never touches university data.
    def setUp(self):
        with server.connect() as db:
            db.execute('DELETE FROM archives');db.execute('DELETE FROM cycles')
            p=server.seed();p.update(startYear=2021,endYear=2031,coordinator='',submissionDate='')
            p['standards'][0]['criteria'][0]['link']='https://docs.google.com/document/d/keep-me'
            p['reviews']=[dict(id='r1',standardId='s1',year=2026,semester='Fall',owner='Team',due='',notes='Minutes',checked=['c1'])]
            db.execute('INSERT INTO cycles VALUES (?,0,?)',('2021-2031',json.dumps(p)))
            db.execute("INSERT OR REPLACE INTO users VALUES ('staff-test','staff@northwestu.edu','staff',1)")
            self.staff_token=security.new_session(db,'staff-test')
            self.staff_csrf=db.execute('SELECT csrf FROM sessions WHERE token=?',(security.digest(self.staff_token),)).fetchone()[0]

    def as_staff(self,method,path='/api/project',payload=None):
        return self.request(method,path,payload,{'Cookie':'tracker_session='+self.staff_token,'X-CSRF-Token':self.staff_csrf,'Origin':security.origin()},auth=False)

    def test_no_auth_bypass(self):
        for route in ['/api/cycles','/api/project','/api/archives','/api/users','/api/audit']:
            self.assertEqual(self.request('GET',route,auth=False)[0],401)
        self.assertEqual(self.request('GET','/login',auth=False)[0],200)
        with patch.dict(os.environ,{'TRACKER_PASSWORD':'old-pass'}):
            self.assertEqual(self.request('GET','/api/project',headers={'Authorization':'Basic c3RhZmY6b2xkLXBhc3M='},auth=False)[0],401)
        self.assertFalse(json.loads(self.request('GET','/api/auth/status',auth=False)[1])['user'])

    def test_staff_cannot_manage_or_bypass_put(self):
        for route in ['/api/users','/api/archives','/api/audit']:
            self.assertEqual(self.as_staff('GET',route)[0],403)
        for route in ['/api/cycles','/api/users/save','/api/archive-cycle','/api/archives/restore','/api/archives/purge']:
            self.assertEqual(self.as_staff('POST',route,{'id':'2021-2031'})[0],403)
        original=json.loads(self.request('GET')[1])
        for change in ['standard','criterion','review','link','owners','add']:
            data=copy.deepcopy(original);p=data['project']
            if change=='standard': p['standards']=p['standards'][1:];p['reviews']=[]
            if change=='criterion':p['standards'][0]['criteria']=p['standards'][0]['criteria'][1:];p['reviews'][0]['checked']=[]
            if change=='review':p['reviews']=[]
            if change=='link':p['standards'][0]['criteria'][0]['link']=''
            if change=='owners':p['owners']=['Unauthorized addition']
            if change=='add':p['standards'].append(dict(id='s99',title='Extra',description='',criteria=[]))
            self.assertEqual(self.as_staff('PUT',payload=data)[0],403,change)
        original['project']['standards'][0]['criteria'][0]['notes']='Staff update allowed'
        original['project']['standards'][0]['criteria'][0]['status']='In Progress'
        self.assertEqual(self.as_staff('PUT',payload=original)[0],200)

    def test_csrf(self):
        data=json.loads(self.request('GET')[1])
        for headers in [{'Cookie':'tracker_session='+self.token},{'Cookie':'tracker_session='+self.token,'X-CSRF-Token':self.csrf,'Origin':'https://evil.example'}]:
            self.assertEqual(self.request('PUT',payload=data,headers=headers,auth=False)[0],403)

    def test_archive_standard_restores_children(self):
        original=json.loads(self.request('GET')[1]);data=copy.deepcopy(original)
        data['project']['standards']=data['project']['standards'][1:];data['project']['reviews']=[]
        self.assertEqual(self.request('PUT',payload=data)[0],200)
        listing=json.loads(self.request('GET','/api/archives')[1])['archives']
        self.assertEqual(len(listing),1);self.assertEqual(listing[0]['kind'],'standard')
        self.assertEqual(self.request('POST','/api/archives/restore',{'id':listing[0]['id']})[0],200)
        restored=json.loads(self.request('GET')[1])
        self.assertEqual(restored['project'],original['project'])
        self.assertEqual(self.request('PUT',payload=original)[0],409)

    def test_criterion_and_link_restoration(self):
        original=json.loads(self.request('GET')[1]);data=copy.deepcopy(original)
        data['project']['standards'][0]['criteria'].pop(0);data['project']['reviews'][0]['checked']=[]
        self.assertEqual(self.request('PUT',payload=data)[0],200)
        identifier=json.loads(self.request('GET','/api/archives')[1])['archives'][0]['id']
        self.assertEqual(self.request('POST','/api/archives/restore',{'id':identifier})[0],200)
        self.assertEqual(json.loads(self.request('GET')[1])['project'],original['project'])
        data=json.loads(self.request('GET')[1]);data['project']['standards'][0]['criteria'][0]['link']=''
        self.assertEqual(self.request('PUT',payload=data)[0],200)
        row=json.loads(self.request('GET','/api/archives')[1])['archives'][0];self.assertEqual(row['kind'],'evidence link')
        self.assertEqual(self.request('POST','/api/archives/restore',{'id':row['id']})[0],200)
        self.assertEqual(json.loads(self.request('GET')[1])['project'],original['project'])

    def test_cycle_delete_purge_does_not_resurrect(self):
        data=json.loads(self.request('GET')[1])
        self.assertEqual(self.request('POST','/api/archive-cycle',{'id':'2021-2031','revision':999})[0],409)
        self.assertEqual(self.request('POST','/api/archive-cycle',{'id':'2021-2031','revision':data['revision']})[0],200)
        self.assertEqual(self.request('GET')[0],404)
        row=json.loads(self.request('GET','/api/archives')[1])['archives'][0]
        self.assertEqual(self.request('POST','/api/archives/purge',{'id':row['id']})[0],400)
        self.assertEqual(self.request('POST','/api/archives/restore',{'id':row['id']})[0],200)
        self.assertEqual(json.loads(self.request('GET')[1])['project'],data['project'])
        rev=json.loads(self.request('GET')[1])['revision']
        self.assertEqual(self.request('POST','/api/archive-cycle',{'id':'2021-2031','revision':rev})[0],200)
        row=json.loads(self.request('GET','/api/archives')[1])['archives'][0]
        with patch('security.client',side_effect=AssertionError('No network permitted')):
            self.assertEqual(self.request('POST','/api/archives/purge',{'id':row['id'],'confirmation':'DELETE'})[0],200)
        for _ in range(3):self.assertEqual(self.request('GET')[0],404)

    def test_restore_parent_and_collision(self):
        data=json.loads(self.request('GET')[1]);old=copy.deepcopy(data)
        data['project']['standards'][0]['criteria'].pop(0);data['project']['reviews'][0]['checked']=[]
        self.request('PUT',payload=data)
        row=json.loads(self.request('GET','/api/archives')[1])['archives'][0]
        current=json.loads(self.request('GET')[1]);old['revision']=current['revision'];self.request('PUT',payload=old)
        self.assertEqual(self.request('POST','/api/archives/restore',{'id':row['id']})[0],409)
        self.assertEqual(len(json.loads(self.request('GET','/api/archives')[1])['archives']),1)

    def test_session_expiration_and_revocation(self):
        with server.connect() as db:db.execute('UPDATE sessions SET touched=? WHERE token=?',(int(time.time())-1801,security.digest(self.staff_token)))
        self.assertEqual(self.as_staff('GET')[0],401)
        with server.connect() as db:db.execute('UPDATE users SET active=0 WHERE oid=?',('staff-test',))
        self.assertEqual(self.as_staff('GET')[0],401)

    def test_people_validation(self):
        oid='12345678-1234-1234-1234-123456789abc'
        for email in ['person@gmail.com','person@northwestu.edu.evil.com','person@fake.northwestu.edu']:
            self.assertEqual(self.request('POST','/api/users/save',{'oid':oid,'email':email,'role':'admin'})[0],400)
        self.assertEqual(self.request('POST','/api/users/save',{'oid':oid,'email':'person@northwestu.edu','role':'staff'})[0],200)
        self.assertEqual(self.request('POST','/api/users/archive',{'oid':oid})[0],200)
        row=json.loads(self.request('GET','/api/archives')[1])['archives'][0]
        self.assertEqual(self.request('POST','/api/archives/restore',{'id':row['id']})[0],200)

    def test_identity_rejects_wrong_tenant_guest_and_suffix(self):
        tenant='11111111-1111-1111-1111-111111111111';oid='22222222-2222-2222-2222-222222222222'
        result={'id_token_claims':{'tid':tenant,'oid':oid},'access_token':'fake-test-token'}
        with patch.dict(os.environ,{'ENTRA_TENANT_ID':tenant}),patch('requests.get') as get:
            get.return_value=Mock();get.return_value.json.return_value={'id':oid,'userType':'Member','userPrincipalName':'staff@northwestu.edu'}
            self.assertEqual(security.verify_identity(result),(oid,'staff@northwestu.edu'))
            for profile in [{'id':oid,'userType':'Guest','userPrincipalName':'staff@northwestu.edu'},{'id':oid,'userType':'Member','userPrincipalName':'staff@northwestu.edu.evil.com'},{'id':'other','userType':'Member','userPrincipalName':'staff@northwestu.edu'}]:
                get.return_value.json.return_value=profile
                with self.assertRaises(ValueError):security.verify_identity(result)
            result['id_token_claims']['tid']='other'
            with self.assertRaises(ValueError):security.verify_identity(result)

    def test_callback_approved_user_and_one_time_flow(self):
        import http.client
        tenant='11111111-1111-1111-1111-111111111111';oid='22222222-2222-2222-2222-222222222222'
        env={'ENTRA_ADMIN_EMAIL':security.ADMIN_EMAIL,'ENTRA_TENANT_ID':tenant,'ENTRA_CLIENT_ID':'33333333-3333-3333-3333-333333333333','ENTRA_CLIENT_SECRET':'test-only','ENTRA_ADMIN_OBJECT_ID':oid}
        flow_token='test-browser-binding'
        def callback(cookie):
            conn=http.client.HTTPConnection('127.0.0.1',self.httpd.server_port)
            conn.request('GET','/auth/callback?state=expected-state&code=one-time-code',headers={'Cookie':cookie})
            response=conn.getresponse();result=(response.status,response.getheader('Location'),response.getheaders());response.read();conn.close();return result
        with patch.dict(os.environ,env),patch('security.client') as client,patch('requests.get') as get:
            with server.connect() as db:
                db.execute('INSERT OR REPLACE INTO users VALUES (?,?,?,1)',(oid,security.ADMIN_EMAIL,'admin'))
                db.execute('INSERT INTO auth_flows VALUES (?,?,?)',(security.digest(flow_token),json.dumps({'state':'expected-state'}),int(time.time())+600))
            client.return_value.acquire_token_by_auth_code_flow.return_value={'id_token_claims':{'oid':oid,'tid':tenant},'access_token':'fake-test-token'}
            get.return_value=Mock();get.return_value.json.return_value={'id':oid,'userPrincipalName':security.ADMIN_EMAIL,'userType':'Member'}
            # Missing browser binding fails before any provider request.
            self.assertIn('error=denied',callback('')[1]);client.assert_not_called()
            result=callback('tracker_flow='+flow_token);self.assertEqual(result[:2],(303,'/login'))
            session_cookie=next(v.split(';')[0] for k,v in result[2] if k.lower()=='set-cookie' and v.startswith('tracker_session='))
            self.assertEqual(self.request('GET',headers={'Cookie':session_cookie},auth=False)[0],200)
            self.assertIn('error=denied',callback('tracker_flow='+flow_token)[1])
            self.assertEqual(client.return_value.acquire_token_by_auth_code_flow.call_count,1)

    def test_expired_flow_and_cookie_properties(self):
        with server.connect() as db:
            db.execute('INSERT INTO auth_flows VALUES (?,?,?)',(security.digest('expired'),'{}',int(time.time())-1))
        self.assertEqual(self.request('GET','/auth/callback?code=fake',headers={'Cookie':'tracker_flow=expired'},auth=False)[0],303)
        with patch.dict(os.environ,{'TRACKER_ORIGIN':'https://tracker.northwestu.edu'}):
            value=security.cookie('tracker_session','token',100)
            for attribute in ['HttpOnly','SameSite=Lax','Secure','Path=/']:self.assertIn(attribute,value)
        self.assertNotIn('Secure',security.cookie('tracker_session','token',100))

    def test_logout_revokes_session(self):
        self.assertEqual(self.as_staff('POST','/api/logout')[0],303)
        self.assertEqual(self.as_staff('GET')[0],401)

    def test_permanent_user_removal_allows_new_approval(self):
        person={'oid':'abcdef01-1234-1234-1234-123456789abc','email':'reapproved@northwestu.edu','role':'staff'}
        self.assertEqual(self.request('POST','/api/users/save',person)[0],200)
        self.assertEqual(self.request('POST','/api/users/archive',{'oid':person['oid']})[0],200)
        row=json.loads(self.request('GET','/api/archives')[1])['archives'][0]
        self.assertEqual(self.request('POST','/api/archives/purge',{'id':row['id'],'confirmation':'DELETE'})[0],200)
        self.assertEqual(self.request('POST','/api/users/save',person)[0],200)
