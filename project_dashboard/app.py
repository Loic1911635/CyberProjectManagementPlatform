from flask import Flask, render_template, redirect, url_for, flash, request, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, Project, Task
from forms import LoginForm, SignupForm, ProjectForm, TaskForm, AddMemberForm
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cyberpm.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)
            flash(f'Welcome back, {user.username}!', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid username or password', 'danger')
    return render_template('login.html', form=form)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    form = SignupForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Account created successfully! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('signup.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/')
def index():
    return redirect(url_for('dashboard') if current_user.is_authenticated else url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    projects = current_user.projects.order_by(Project.created_at.desc()).all()
    stats = {
        'total_projects': len(projects),
        'active_projects': len([p for p in projects if p.status == 'active']),
        'total_tasks': sum(p.tasks.count() for p in projects),
        'completed_tasks': sum(p.tasks.filter_by(completed=True).count() for p in projects)
    }
    return render_template('dashboard.html', projects=projects, stats=stats)

@app.route('/project/new', methods=['GET', 'POST'])
@login_required
def create_project():
    form = ProjectForm()
    if form.validate_on_submit():
        project = Project(name=form.name.data, description=form.description.data, start_date=form.start_date.data, end_date=form.end_date.data, status=form.status.data, user_id=current_user.id)
        db.session.add(project)
        db.session.commit()
        flash(f'Project "{project.name}" created!', 'success')
        return redirect(url_for('project_detail', project_id=project.id))
    return render_template('project_form.html', form=form, title='Create Project')

@app.route('/project/<int:project_id>')
@login_required
def project_detail(project_id):
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    tasks = project.tasks.order_by(Task.created_at.desc()).all()
    task_stats = {'todo': len([t for t in tasks if t.status == 'todo']), 'in_progress': len([t for t in tasks if t.status == 'in_progress']), 'done': len([t for t in tasks if t.status == 'done']), 'total': len(tasks)}
    form = AddMemberForm()
    return render_template('project_detail.html', project=project, tasks=tasks, task_stats=task_stats, form=form)

@app.route('/project/<int:project_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_project(project_id):
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    form = ProjectForm(obj=project)
    if form.validate_on_submit():
        project.name = form.name.data
        project.description = form.description.data
        project.start_date = form.start_date.data
        project.end_date = form.end_date.data
        project.status = form.status.data
        db.session.commit()
        flash('Project updated!', 'success')
        return redirect(url_for('project_detail', project_id=project.id))
    return render_template('project_form.html', form=form, title='Edit Project', project=project)

@app.route('/project/<int:project_id>/delete', methods=['POST'])
@login_required
def delete_project(project_id):
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    db.session.delete(project)
    db.session.commit()
    flash('Project deleted.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/project/<int:project_id>/task/new', methods=['GET', 'POST'])
@login_required
def create_task(project_id):
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    
    form = TaskForm()
    choices = [(0, 'Unassigned')] + [(u.id, u.username) for u in [project.owner] + list(project.members)]
    form.assigned_to.choices = choices
    form.assigned_to.validators = []
    
    if request.method == 'POST':
        if form.validate():
            assigned_id = form.assigned_to.data if form.assigned_to.data != 0 else None
            task = Task(
                title=form.title.data,
                description=form.description.data,
                status=form.status.data,
                priority=form.priority.data,
                due_date=form.due_date.data,
                project_id=project.id,
                assigned_user_id=assigned_id
            )
            db.session.add(task)
            db.session.commit()
            flash('Task created!', 'success')
            return redirect(url_for('project_detail', project_id=project.id))
    
    return render_template('task_form.html', form=form, project=project, title='Create Task')

@app.route('/task/<int:task_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_task(task_id):
    task = Task.query.get_or_404(task_id)
    if task.project.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    form = TaskForm(obj=task)
    choices = [(0, 'Unassigned')] + [(u.id, u.username) for u in [task.project.owner] + list(task.project.members)]
    form.assigned_to.choices = choices
    form.assigned_to.validators = []
    if request.method == 'POST' and form.validate():
        task.title = form.title.data
        task.description = form.description.data
        task.status = form.status.data
        task.priority = form.priority.data
        task.due_date = form.due_date.data
        task.assigned_user_id = form.assigned_to.data if form.assigned_to.data != 0 else None
        task.completed = (form.status.data == 'done')
        db.session.commit()
        flash('Task updated!', 'success')
        return redirect(url_for('project_detail', project_id=task.project_id))
    return render_template('task_form.html', form=form, project=task.project, title='Edit Task', task=task)

@app.route('/task/<int:task_id>/toggle', methods=['POST'])
@login_required
def toggle_task(task_id):
    task = Task.query.get_or_404(task_id)
    if task.project.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    task.completed = not task.completed
    task.status = 'done' if task.completed else 'todo'
    db.session.commit()
    return redirect(url_for('project_detail', project_id=task.project_id))

@app.route('/task/<int:task_id>/delete', methods=['POST'])
@login_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    if task.project.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    project_id = task.project_id
    db.session.delete(task)
    db.session.commit()
    flash('Task deleted.', 'success')
    return redirect(url_for('project_detail', project_id=project_id))

@app.route('/search-users')
@login_required
def search_users():
    query = request.args.get('q', '').strip()
    if len(query) < 1:
        return jsonify([])
    
    users = User.query.filter(User.username.ilike(f'%{query}%')).limit(10).all()
    return jsonify([{'id': u.id, 'username': u.username, 'email': u.email} for u in users])

@app.route('/project/<int:project_id>/add-member', methods=['POST'])
@login_required
def add_member(project_id):
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    
    user_id = request.form.get('user_id')
    if not user_id:
        flash('Please select a user.', 'danger')
        return redirect(url_for('project_detail', project_id=project.id))
    
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        flash('You are already the project owner.', 'info')
        return redirect(url_for('project_detail', project_id=project.id))
    
    if user in project.members:
        flash(f'{user.username} is already a member.', 'info')
    else:
        project.members.append(user)
        db.session.commit()
        flash(f'✅ {user.username} added to project!', 'success')
    
    return redirect(url_for('project_detail', project_id=project.id))

@app.route('/project/<int:project_id>/remove-member/<int:user_id>', methods=['POST'])
@login_required
def remove_member(project_id, user_id):
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    user = User.query.get_or_404(user_id)
    if user in project.members:
        project.members.remove(user)
        db.session.commit()
        flash(f'{user.username} removed from project.', 'success')
    return redirect(url_for('project_detail', project_id=project.id))

with app.app_context():
    db.create_all()
    print('✅ Database ready!')

if __name__ == '__main__':
    app.run(debug=True)