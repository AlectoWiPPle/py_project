import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import date

app = Flask(__name__)
app.config['SECRET_KEY'] = 'gqrtq3t1et'

def get_db_connection():
    conn = sqlite3.connect('todo.db')
    conn.row_factory = sqlite3.Row  # let use names instead of indexes
    return conn

def init_db():
    with get_db_connection() as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            completed INTEGER DEFAULT 0,
            completed_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id))''')
        
init_db()


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get('user_id')
        if not user_id:
            return redirect(url_for('login'))
        return f(*args, **kwargs) #return login check result

    return decorated_function

#delete old tasks

def clear_old_completed_tasks(user_id):
    today_str = date.today().isoformat()
    conn = get_db_connection()
    conn.execute(
        'DELETE FROM tasks WHERE user_id = ? AND completed = 1 AND completed_at < ?',
        (user_id, today_str)
    )
    conn.commit()
    conn.close()

    #main page

@app.route('/')
def index():
    user_id = session.get('user_id')
    if not user_id:

        return redirect(url_for('login'))
    clear_old_completed_tasks(user_id)
    conn = get_db_connection()
    tasks = conn.execute('SELECT * FROM tasks WHERE user_id = ? ORDER BY completed ASC, id DESC', (session['user_id'],)).fetchall() # tasks are sorted by completed, then by id
    conn.close()
    
    tasks_list = [dict(task) for task in tasks]
    completed_task_ids = {task['id'] for task in tasks_list if task['completed'] == 1}

    total_tasks = len(tasks_list)
    completed_count = len(completed_task_ids)

    percent_complete = (completed_count / total_tasks) * 100 if total_tasks > 0 else 0
    return render_template('index.html', tasks=tasks_list, percent_complete=int(percent_complete))

# Login route

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, password))
            conn.commit()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError: # username already exists
            Warning(f"Username '{username}' already exists")
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']

            return redirect(url_for('index'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)

    return redirect(url_for('login'))

@app.route('/add', methods=['POST'])
@login_required
def add_task():
    content = request.form['content']
    if content:
        conn = get_db_connection()
        conn.execute('INSERT INTO tasks (content, user_id) VALUES (?, ?)', (content, session['user_id']))
        conn.commit()
        conn.close()
    return redirect(url_for('index'))

@app.route('/complete/<int:task_id>')
@login_required
def complete_task(task_id):
    today_str = date.today().isoformat()
    conn = get_db_connection()
    conn.execute(
        'UPDATE tasks SET completed = 1, completed_at = ? WHERE id = ? AND user_id = ?',
        (today_str, task_id, session['user_id'])
    )
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/delete/<int:task_id>')
@login_required
def delete_task(task_id):
    conn = get_db_connection()
    task = conn.execute('SELECT * FROM tasks WHERE id = ? AND user_id = ?', (task_id, session['user_id'])).fetchone()
    if task:
        conn.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
        conn.commit()
    conn.close()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
