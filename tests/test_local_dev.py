import hashlib
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import security
import server
import test_server

class LocalDevTests(test_server.TrackerTests):
    def test_local_login_and_production_rejection(self):
        password='test-only-local-password';salt=b'local-test-salt'
        encoded=salt.hex()+':'+hashlib.pbkdf2_hmac('sha256',password.encode(),salt,600000).hex()
        env={'TRACKER_LOCAL_DEV':'1','TRACKER_LOCAL_HASH':encoded,'TRACKER_ORIGIN':'http://127.0.0.1:8000'}
        headers={'Host':'127.0.0.1:8000','Origin':'http://127.0.0.1:8000'}
        with patch.dict(os.environ,env),patch('security.configured',return_value=False):
            server.LOCAL_LOGIN_ATTEMPTS.clear()
            self.assertEqual(self.request('POST','/api/auth/local',{'password':'wrong'},headers,auth=False)[0],401)
            self.assertEqual(self.request('POST','/api/auth/local',{'password':password},{**headers,'Origin':'https://evil.example'},auth=False)[0],403)
            self.assertEqual(self.request('POST','/api/auth/local',{'password':password},headers,auth=False)[0],303)
            with server.connect() as db:
                token=security.new_session(db,security.DEV_USER)
            self.assertEqual(self.request('GET','/api/cycles',headers={**headers,'Cookie':'tracker_session='+token},auth=False)[0],200)
            with patch.dict(os.environ,{'TRACKER_LOCAL_DEV':'0'}):
                self.assertEqual(self.request('POST','/api/auth/local',{'password':password},headers,auth=False)[0],403)
                self.assertEqual(self.request('GET','/api/cycles',headers={**headers,'Cookie':'tracker_session='+token},auth=False)[0],401)
            for _ in range(4):self.request('POST','/api/auth/local',{'password':'wrong'},headers,auth=False)
            self.assertEqual(self.request('POST','/api/auth/local',{'password':password},headers,auth=False)[0],429)

    def test_local_gates(self):
        handler=SimpleNamespace(server=SimpleNamespace(server_address=('127.0.0.1',8000)),client_address=('127.0.0.1',1234),headers={'Host':'127.0.0.1:8000'})
        with patch.dict(os.environ,{'TRACKER_LOCAL_DEV':'1','TRACKER_LOCAL_HASH':'set','TRACKER_ORIGIN':'http://127.0.0.1:8000'}),patch('security.configured',return_value=False):
            self.assertTrue(security.local_enabled(handler))
            handler.server.server_address=('0.0.0.0',8000);self.assertFalse(security.local_enabled(handler))
            handler.server.server_address=('127.0.0.1',8000);handler.client_address=('192.168.1.2',1234);self.assertFalse(security.local_enabled(handler))
            handler.client_address=('127.0.0.1',1234);handler.headers['Host']='evil.example';self.assertFalse(security.local_enabled(handler))
            handler.headers['Host']='127.0.0.1:8000'
            with patch('security.configured',return_value=True):self.assertFalse(security.local_enabled(handler))
