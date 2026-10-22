"""Activity 3: backend-enforced owner and collaborator access for every operation."""
from datetime import datetime, timezone
from flask import Blueprint, g, jsonify, redirect, render_template, request, url_for
from db import get_db
from auth import login_required

bp = Blueprint('tasks', __name__)

def error(message, status=400):
    return jsonify(error=message), status

def uid():
    return g.user['id']

def permitted_list(list_id):
    return get_db().execute('''SELECT l.* FROM lists l WHERE l.id=? AND
        (l.owner_id=? OR (l.kind='collaborative' AND EXISTS
        (SELECT 1 FROM list_members m WHERE m.list_id=l.id AND m.user_id=?)))''',
        (list_id, uid(), uid())).fetchone()

def task_access(task_id):
    return get_db().execute('''SELECT t.* FROM tasks t JOIN lists l ON l.id=t.list_id
        WHERE t.id=? AND (l.owner_id=? OR (l.kind='collaborative' AND EXISTS
        (SELECT 1 FROM list_members m WHERE m.list_id=l.id AND m.user_id=?)))''',
        (task_id, uid(), uid())).fetchone()

def ensure_personal():
    db=get_db()
    db.execute("INSERT OR IGNORE INTO lists(owner_id,name,kind) VALUES (?,'Personal','personal')",(uid(),))
    db.commit()

def data():
    return request.get_json(silent=True) or {}

def validate(d):
    title=d.get('title','');due=d.get('due_date','')
    if not isinstance(title,str) or not 1<=len(title.strip())<=120 or not isinstance(due,str) or not due.strip() or len(due)>40 or d.get('priority') not in ('Low','Med','High') or d.get('tag') not in ('School','Personal','Others'):
        return False
    try: datetime.fromisoformat(due)
    except ValueError: return False
    return True

@bp.get('/dashboard')
@login_required
def dashboard():
    ensure_personal()
    return render_template('tasks.html')

@bp.get('/api/lists')
@login_required
def lists():
    ensure_personal()
    rows=get_db().execute('''SELECT l.*, (l.owner_id=?) AS is_owner FROM lists l WHERE
        l.owner_id=? OR (l.kind='collaborative' AND EXISTS
        (SELECT 1 FROM list_members m WHERE m.list_id=l.id AND m.user_id=?))
        ORDER BY CASE WHEN l.owner_id=? AND l.kind='personal' THEN 0 ELSE 1 END,l.id''',
        (uid(),uid(),uid(),uid())).fetchall()
    return jsonify([dict(r) for r in rows])

@bp.post('/api/lists')
@login_required
def new_list():
    name=data().get('name','')
    if not isinstance(name,str) or not 1<=len(name.strip())<=100:return error('List name must be 1–100 characters')
    db=get_db();cur=db.execute("INSERT INTO lists(owner_id,name,kind) VALUES (?,?,'collaborative')",(uid(),name.strip()));db.commit()
    return jsonify(id=cur.lastrowid,name=name.strip()),201

@bp.get('/api/lists/<int:list_id>')
@login_required
def list_detail(list_id):
    row=permitted_list(list_id)
    return jsonify(dict(row)) if row else error('List not found',404)

@bp.post('/api/lists/<int:list_id>/members')
@login_required
def add_member(list_id):
    lst=permitted_list(list_id)
    if not lst or lst['owner_id']!=uid() or lst['kind']!='collaborative':return error('List not found',404)
    ident=data().get('identifier','')
    if not isinstance(ident,str) or not ident.strip():return error('Username or email required')
    db=get_db();user=db.execute('SELECT id FROM users WHERE username=? OR email=?',(ident.strip(),ident.strip())).fetchone()
    if not user:return error('Registered user not found',404)
    if user['id']==uid():return error('Owner already has access')
    db.execute('INSERT OR IGNORE INTO list_members(list_id,user_id) VALUES (?,?)',(list_id,user['id']));db.commit()
    return jsonify(message='Member added'),201

@bp.get('/api/lists/<int:list_id>/members')
@login_required
def members(list_id):
    if not permitted_list(list_id):return error('List not found',404)
    rows=get_db().execute('''SELECT u.id,u.username,u.display_name FROM list_members m JOIN users u ON u.id=m.user_id WHERE m.list_id=?''',(list_id,)).fetchall()
    return jsonify([dict(r) for r in rows])

@bp.delete('/api/lists/<int:list_id>/members/<int:member_id>')
@login_required
def remove_member(list_id,member_id):
    lst=permitted_list(list_id)
    if not lst or lst['kind']!='collaborative' or (lst['owner_id']!=uid() and member_id!=uid()):return error('List not found',404)
    db=get_db();db.execute('DELETE FROM list_members WHERE list_id=? AND user_id=?',(list_id,member_id));db.commit()
    return jsonify(message='Membership removed')

@bp.delete('/api/lists/<int:list_id>')
@login_required
def delete_list(list_id):
    lst=permitted_list(list_id)
    if not lst or lst['owner_id']!=uid() or lst['kind']!='collaborative':return error('List not found',404)
    db=get_db();db.execute('DELETE FROM lists WHERE id=? AND owner_id=?',(list_id,uid()));db.commit()
    return jsonify(message='List deleted')

@bp.get('/api/tasks')
@login_required
def get_tasks():
    ensure_personal()
    list_id=request.args.get('list_id',type=int)
    if list_id is None:return error('list_id is required')
    if not permitted_list(list_id):return error('List not found',404)
    db=get_db();db.execute("DELETE FROM tasks WHERE deleted_at IS NOT NULL AND datetime(deleted_at,'+5 seconds') <= datetime('now')");db.commit()
    rows=db.execute('SELECT * FROM tasks WHERE list_id=? AND deleted_at IS NULL ORDER BY due_date',(list_id,)).fetchall()
    return jsonify([dict(r) for r in rows])

@bp.post('/api/tasks')
@login_required
def create_task():
    d=data()
    if not validate(d):return error('Invalid task details')
    list_id=d.get('list_id')
    if type(list_id)!=int or not permitted_list(list_id):return error('List not found',404)
    db=get_db();cur=db.execute('''INSERT INTO tasks(list_id,user_id,title,due_date,priority,tag,created_at) VALUES(?,?,?,?,?,?,?)''',
        (list_id,uid(),d['title'].strip(),d['due_date'],d['priority'],d['tag'],datetime.now(timezone.utc).isoformat()))
    db.commit();return jsonify(dict(db.execute('SELECT * FROM tasks WHERE id=?',(cur.lastrowid,)).fetchone())),201

@bp.get('/api/tasks/<int:task_id>')
@login_required
def get_task(task_id):
    t=task_access(task_id)
    return jsonify(dict(t)) if t and not t['deleted_at'] else error('Task not found',404)

@bp.put('/api/tasks/<int:task_id>')
@login_required
def update_task(task_id):
    t=task_access(task_id)
    if not t or t['deleted_at']:return error('Task not found',404)
    d=data()
    if not validate(d):return error('Invalid task details')
    db=get_db();db.execute('''UPDATE tasks SET title=?,due_date=?,priority=?,tag=? WHERE id=? AND list_id=?''',
        (d['title'].strip(),d['due_date'],d['priority'],d['tag'],task_id,t['list_id']));db.commit()
    return jsonify(dict(db.execute('SELECT * FROM tasks WHERE id=?',(task_id,)).fetchone()))

@bp.patch('/api/tasks/<int:task_id>/complete')
@login_required
def complete(task_id):
    t=task_access(task_id)
    if not t or t['deleted_at']:return error('Task not found',404)
    db=get_db();db.execute('UPDATE tasks SET completed=? WHERE id=? AND list_id=?',(1-int(t['completed']),task_id,t['list_id']));db.commit()
    return jsonify(dict(db.execute('SELECT * FROM tasks WHERE id=?',(task_id,)).fetchone()))

@bp.delete('/api/tasks/<int:task_id>')
@login_required
def delete_task(task_id):
    t=task_access(task_id)
    if not t or t['deleted_at']:return error('Task not found',404)
    db=get_db();db.execute("UPDATE tasks SET deleted_at=datetime('now') WHERE id=? AND list_id=?",(task_id,t['list_id']));db.commit()
    return jsonify(message='Task deleted. You have 5 seconds to undo.')

@bp.post('/api/tasks/<int:task_id>/undo')
@login_required
def undo(task_id):
    t=task_access(task_id)
    if not t or not t['deleted_at']:return error('Task not found',404)
    db=get_db();cur=db.execute("UPDATE tasks SET deleted_at=NULL WHERE id=? AND list_id=? AND datetime(deleted_at,'+5 seconds') > datetime('now')",(task_id,t['list_id']));db.commit()
    if not cur.rowcount:return error('Undo period expired',404)
    return jsonify(dict(db.execute('SELECT * FROM tasks WHERE id=?',(task_id,)).fetchone()))

@bp.delete('/api/tasks/<int:task_id>/finalize')
@login_required
def finalize(task_id):
    t=task_access(task_id)
    if not t:return error('Task not found',404)
    db=get_db();db.execute('DELETE FROM tasks WHERE id=? AND list_id=? AND deleted_at IS NOT NULL',(task_id,t['list_id']));db.commit()
    return jsonify(message='Deletion finalized')
