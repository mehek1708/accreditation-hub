import copy
import json
import test_server
import server
import archives

class WorkspaceTaskTests(test_server.TrackerTests):
    def setUp(self):
        with server.connect() as db:
            db.execute('DELETE FROM archives')
            p=server.seed();p.update(startYear=2021,endYear=2031,coordinator='',submissionDate='')
            db.execute('INSERT OR REPLACE INTO cycles VALUES (?,0,?)',('2021-2031',json.dumps(p)))

    def task(self):return dict(id='task-demo',name='Demo draft',category='Text',content='Important draft text',link='https://docs.google.com/document/d/demo')

    def test_task_creation_edit_delete_restore(self):
        data=json.loads(self.request('GET')[1]);data['project']['workspaceTasks']=[self.task()]
        self.assertEqual(self.request('PUT',payload=data)[0],200)
        data=json.loads(self.request('GET')[1]);self.assertEqual(data['project']['workspaceTasks'][0],self.task())
        data['project']['workspaceTasks'][0]['content']='Updated draft';self.assertEqual(self.request('PUT',payload=data)[0],200)
        original=json.loads(self.request('GET')[1]);data=copy.deepcopy(original);data['project']['workspaceTasks']=[]
        self.assertEqual(self.request('PUT',payload=data)[0],200)
        archive=json.loads(self.request('GET','/api/archives')[1])['archives'][0]
        self.assertEqual(archive['kind'],'workspace task')
        self.assertEqual(self.request('POST','/api/archives/restore',{'id':archive['id']})[0],200)
        self.assertEqual(json.loads(self.request('GET')[1])['project'],original['project'])

    def test_task_validation_and_role_boundary(self):
        original=server.seed();original['workspaceTasks']=[self.task()];server.validate(original)
        edited=copy.deepcopy(original);edited['workspaceTasks'][0]['content']='Staff can edit'
        self.assertFalse(archives.needs_admin(original,edited))
        for key in ['id','name','category']:
            edited=copy.deepcopy(original);edited['workspaceTasks'][0][key]='Changed'
            self.assertTrue(archives.needs_admin(original,edited))
        edited=copy.deepcopy(original);edited['workspaceTasks']=[];self.assertTrue(archives.needs_admin(original,edited))
        for key,value in [('category',''),('name',' '),('link','javascript:alert(1)'),('id','s1')]:
            p=copy.deepcopy(original);p['workspaceTasks'][0][key]=value
            with self.assertRaises(ValueError):server.validate(p)
        p=copy.deepcopy(original);p['workspaceTasks'].append({**self.task(),'id':'different'})
        with self.assertRaises(ValueError):server.validate(p)

    def test_restore_collision_keeps_archive(self):
        data=json.loads(self.request('GET')[1]);data['project']['workspaceTasks']=[self.task()];self.request('PUT',payload=data)
        data=json.loads(self.request('GET')[1]);data['project']['workspaceTasks']=[];self.request('PUT',payload=data)
        archive=json.loads(self.request('GET','/api/archives')[1])['archives'][0]
        data=json.loads(self.request('GET')[1]);data['project']['workspaceTasks']=[{**self.task(),'id':'another-id'}];self.request('PUT',payload=data)
        self.assertEqual(self.request('POST','/api/archives/restore',{'id':archive['id']})[0],409)
        self.assertEqual(len(json.loads(self.request('GET','/api/archives')[1])['archives']),1)

    def test_builtin_section_archive_preserves_records(self):
        data=json.loads(self.request('GET')[1]);original=copy.deepcopy(data['project'])
        data['project']['hiddenSections']=['standards']
        self.assertTrue(archives.needs_admin(original,data['project']))
        self.assertEqual(self.request('PUT',payload=data)[0],200)
        saved=json.loads(self.request('GET')[1])['project']
        self.assertEqual(saved['standards'],original['standards'])
        archive=json.loads(self.request('GET','/api/archives')[1])['archives'][0]
        self.assertEqual(archive['kind'],'workspace section')
        self.assertEqual(self.request('POST','/api/archives/restore',{'id':archive['id']})[0],200)
        self.assertEqual(json.loads(self.request('GET')[1])['project']['hiddenSections'],[])

    def test_chart_saved_and_restored_with_task(self):
        config=dict(type='bar',title='Test',subtitle='',xTitle='',yTitle='',font='Arial',fontSize=14,legend=True,grid=True,labels=True,smooth=False,legendPosition='bottom',background='#ffffff',textColor='#000000',colors=['#123456'],headers=['Category','Count'],rows=[['A',12],['B',25]])
        data=json.loads(self.request('GET')[1]);data['project']['workspaceTasks']=[dict(self.task(),category='Charts',chart=config)]
        self.assertEqual(self.request('PUT',payload=data)[0],200)
        data=json.loads(self.request('GET')[1]);self.assertEqual(data['project']['workspaceTasks'][0]['chart'],config)
        data['project']['workspaceTasks']=[];self.assertEqual(self.request('PUT',payload=data)[0],200)
        archive=json.loads(self.request('GET','/api/archives')[1])['archives'][0]
        self.assertEqual(self.request('POST','/api/archives/restore',{'id':archive['id']})[0],200)
        self.assertEqual(json.loads(self.request('GET')[1])['project']['workspaceTasks'][0]['chart'],config)
        import chart_config
        for key,value in [('rows',[['A',float('nan')]]),('colors',['javascript:bad']),('type','unsupported'),('fontSize',100)]:
            invalid=dict(config);invalid[key]=value
            with self.assertRaises(ValueError):chart_config.validate(invalid)
