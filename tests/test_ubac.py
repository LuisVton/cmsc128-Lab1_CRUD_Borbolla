"""Run: python -m unittest discover -s tests -v"""
import os, tempfile, unittest
from pathlib import Path
from unittest.mock import patch

class AccessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.path=str(Path(cls.tmp.name)/'test.db')
        os.environ['SECRET_KEY']='test-only-not-for-production'
        import app
        cls.app=app.app
        cls.app.config.update(TESTING=True,DATABASE=cls.path)
        from db import init_db
        init_db(cls.app)
        with cls.app.app_context():
            from db import get_db
            from werkzeug.security import generate_password_hash
            db=get_db()
            for n in ('alice','bob','charlie'):
                db.execute('INSERT INTO users(username,email,display_name,password_hash) VALUES(?,?,?,?)',
                    (n,n+'@example.com',n,generate_password_hash('Password123')))
            db.commit()

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def setUp(self):self.c=self.app.test_client()

    def login(self,name):
        with self.c.session_transaction() as sess:
            sess['uid']={'alice':1,'bob':2,'charlie':3}[name];sess['sv']=0;sess['_csrf']='test-token'

    def req(self,method,url,**kwargs):
        return getattr(self.c,method)(url,headers={'X-CSRF-Token':'test-token'},**kwargs)

    def test_isolation_and_collaboration(self):
        self.login('alice')
        la=self.c.get('/api/lists').json[0]['id']
        task={'title':'Alice only','due_date':'2026-11-01T10:00','priority':'Med','tag':'School','list_id':la}
        t=self.req('post','/api/tasks',json=task);self.assertEqual(t.status_code,201);tid=t.json['id']
        group=self.req('post','/api/lists',json={'name':'Team'}).json['id']
        self.assertEqual(self.req('post',f'/api/lists/{group}/members',json={'identifier':'bob'}).status_code,201)
        shared=self.req('post','/api/tasks',json={**task,'list_id':group}).json['id']
        self.login('bob')
        lb=self.c.get('/api/lists').json[0]['id']
        self.assertNotEqual(la,lb)
        self.assertEqual(self.c.get(f'/api/tasks?list_id={la}').status_code,404)
        self.assertEqual(self.c.get(f'/api/tasks/{tid}').status_code,404)
        self.assertEqual(self.req('put',f'/api/tasks/{tid}',json=task).status_code,404)
        self.assertEqual(self.req('patch',f'/api/tasks/{tid}/complete').status_code,404)
        self.assertEqual(self.req('delete',f'/api/tasks/{tid}').status_code,404)
        self.assertEqual(self.req('post',f'/api/tasks/{tid}/undo').status_code,404)
        self.assertEqual(self.req('delete',f'/api/tasks/{tid}/finalize').status_code,404)
        self.assertEqual(self.c.get(f'/api/tasks?list_id={group}').status_code,200)
        self.assertEqual(self.req('patch',f'/api/tasks/{shared}/complete').status_code,200)
        self.assertEqual(self.req('post',f'/api/lists/{group}/members',json={'identifier':'charlie'}).status_code,404)
        self.login('charlie')
        self.assertEqual(self.c.get(f'/api/tasks?list_id={group}').status_code,404)
        self.assertEqual(self.c.get(f'/api/lists/{group}/members').status_code,404)

    def test_csrf_and_anonymous(self):
        self.assertEqual(self.c.get('/dashboard').status_code,302)
        self.login('alice')
        self.assertEqual(self.c.post('/api/lists',json={'name':'No token'}).status_code,400)

if __name__=='__main__':unittest.main()
