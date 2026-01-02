from flask import Flask, render_template, redirect, url_for, flash, request, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import or_, inspect, text
from models import db, User, Project, Task, Subtask, ProjectMemberPermission
from forms import LoginForm, SignupForm, ProjectForm, TaskForm, AddMemberForm
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cyberpm.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
csrf = CSRFProtect(app)

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def is_project_member(project, user):
    return project.user_id == user.id or user in project.members

def get_member_permissions(project_id, user_id):
    return ProjectMemberPermission.query.filter_by(project_id=project_id, user_id=user_id).first()

def user_can_edit_tasks(project, user):
    if project.user_id == user.id:
        return True
    if user not in project.members:
        return False
    permissions = get_member_permissions(project.id, user.id)
    return bool(permissions and permissions.can_edit_tasks)

def user_can_modify_task(task, user):
    if task.project.user_id == user.id:
        return True
    if task.locked:
        return False
    return user_can_edit_tasks(task.project, user)

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

@app.route('/logout', methods=['POST'])
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
    projects = (
        Project.query.filter(
            or_(
                Project.user_id == current_user.id,
                Project.members.any(User.id == current_user.id),
            )
        )
        .order_by(Project.created_at.desc())
        .all()
    )
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
    if not is_project_member(project, current_user):
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    tasks = project.tasks.order_by(Task.created_at.desc()).all()
    task_stats = {'todo': len([t for t in tasks if t.status == 'todo']), 'in_progress': len([t for t in tasks if t.status == 'in_progress']), 'done': len([t for t in tasks if t.status == 'done']), 'total': len(tasks)}
    form = AddMemberForm()
    member_permissions = {
        perm.user_id: perm
        for perm in ProjectMemberPermission.query.filter_by(project_id=project.id).all()
    }
    return render_template(
        'project_detail.html',
        project=project,
        tasks=tasks,
        task_stats=task_stats,
        form=form,
        is_owner=(project.user_id == current_user.id),
        can_edit_tasks=user_can_edit_tasks(project, current_user),
        member_permissions=member_permissions,
    )

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
    if not is_project_member(project, current_user):
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    if not user_can_edit_tasks(project, current_user):
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
            return redirect(url_for('task_detail', task_id=task.id))
    return render_template(
        'task_form.html',
        form=form,
        project=project,
        title='Create Task',
        can_edit_tasks=user_can_edit_tasks(project, current_user),
    )

@app.route('/task/<int:task_id>')
@login_required
def task_detail(task_id):
    task = Task.query.get_or_404(task_id)
    if not is_project_member(task.project, current_user):
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    subtasks_list = task.subtasks.all()
    completion = task.get_completion_percentage()
    return render_template(
        'task_detail.html',
        task=task,
        subtasks_list=subtasks_list,
        completion=completion,
        can_edit_tasks=user_can_modify_task(task, current_user),
        is_owner=(task.project.user_id == current_user.id),
    )

@app.route('/task/<int:task_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_task(task_id):
    task = Task.query.get_or_404(task_id)
    if not is_project_member(task.project, current_user):
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    if not user_can_modify_task(task, current_user):
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    form = TaskForm(obj=task)
    choices = [(0, 'Unassigned')] + [(u.id, u.username) for u in [task.project.owner] + list(task.project.members)]
    form.assigned_to.choices = choices
    form.assigned_to.validators = []
    if request.method == 'GET':
        form.assigned_to.data = task.assigned_user_id or 0
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
        return redirect(url_for('task_detail', task_id=task.id))
    return render_template(
        'task_form.html',
        form=form,
        project=task.project,
        title='Edit Task',
        task=task,
        can_edit_tasks=user_can_edit_tasks(task.project, current_user),
    )

@app.route('/task/<int:task_id>/lock', methods=['POST'])
@login_required
def toggle_task_lock(task_id):
    task = Task.query.get_or_404(task_id)
    if task.project.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    task.locked = not task.locked
    db.session.commit()
    flash('Task locked.' if task.locked else 'Task unlocked.', 'info')
    return redirect(url_for('task_detail', task_id=task.id))

@app.route('/task/<int:task_id>/status/<new_status>', methods=['POST'])
@login_required
def change_task_status(task_id, new_status):
    task = Task.query.get_or_404(task_id)
    if not user_can_modify_task(task, current_user):
        return jsonify({'error': 'Access denied'}), 403
    if new_status not in ['todo', 'in_progress', 'done']:
        return jsonify({'error': 'Invalid status'}), 400
    task.status = new_status
    task.completed = (new_status == 'done')
    db.session.commit()
    return jsonify({'success': True, 'status': new_status})

@app.route('/task/<int:task_id>/delete', methods=['POST'])
@login_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    if not user_can_modify_task(task, current_user):
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    project_id = task.project_id
    db.session.delete(task)
    db.session.commit()
    flash('Task deleted.', 'success')
    return redirect(url_for('project_detail', project_id=project_id))

@app.route('/task/<int:task_id>/subtask/add', methods=['POST'])
@login_required
def add_subtask(task_id):
    task = Task.query.get_or_404(task_id)
    if not user_can_modify_task(task, current_user):
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    title = request.form.get('title', '').strip()
    if title:
        subtask = Subtask(title=title, task_id=task_id)
        db.session.add(subtask)
        db.session.commit()
        flash('Subtask added!', 'success')
    else:
        flash('Subtask title cannot be empty.', 'warning')
    return redirect(url_for('task_detail', task_id=task_id))

@app.route('/subtask/<int:subtask_id>/toggle', methods=['POST'])
@login_required
def toggle_subtask(subtask_id):
    subtask = Subtask.query.get_or_404(subtask_id)
    task = subtask.task
    if not user_can_modify_task(task, current_user):
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    subtask.completed = not subtask.completed
    db.session.commit()
    status_text = "completed" if subtask.completed else "incomplete"
    flash(f'Subtask marked as {status_text}!', 'success')
    return redirect(url_for('task_detail', task_id=task.id))

@app.route('/subtask/<int:subtask_id>/delete', methods=['POST'])
@login_required
def delete_subtask(subtask_id):
    subtask = Subtask.query.get_or_404(subtask_id)
    task = subtask.task
    if not user_can_modify_task(task, current_user):
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    task_id = task.id
    db.session.delete(subtask)
    db.session.commit()
    flash('Subtask deleted!', 'success')
    return redirect(url_for('task_detail', task_id=task_id))

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
    permissions = get_member_permissions(project.id, user.id)
    if permissions is None:
        permissions = ProjectMemberPermission(project_id=project.id, user_id=user.id)
        db.session.add(permissions)
    db.session.commit()
    flash(f'✅ {user.username} added to project!', 'success')
    return redirect(url_for('project_detail', project_id=project.id))

@app.route('/project/<int:project_id>/member/<int:user_id>/permissions', methods=['POST'])
@login_required
def update_member_permissions(project_id, user_id):
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    if user_id == project.user_id:
        flash('Project owner permissions cannot be changed.', 'warning')
        return redirect(url_for('project_detail', project_id=project.id))
    user = User.query.get_or_404(user_id)
    if user not in project.members:
        flash('User is not a project member.', 'danger')
        return redirect(url_for('project_detail', project_id=project.id))
    permissions = get_member_permissions(project.id, user.id)
    if permissions is None:
        permissions = ProjectMemberPermission(project_id=project.id, user_id=user.id)
        db.session.add(permissions)
    permissions.can_edit_tasks = bool(request.form.get('can_edit_tasks'))
    permissions.can_create_tasks = permissions.can_edit_tasks
    permissions.can_assign_tasks = permissions.can_edit_tasks
    db.session.commit()
    flash(f'Permissions updated for {user.username}.', 'success')
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
        permissions = get_member_permissions(project.id, user.id)
        if permissions is not None:
            db.session.delete(permissions)
        db.session.commit()
        flash(f'{user.username} removed from project.', 'success')
    return redirect(url_for('project_detail', project_id=project.id))

with app.app_context():
    db.create_all()
    inspector = inspect(db.engine)
    task_columns = [column['name'] for column in inspector.get_columns('tasks')]
    if 'locked' not in task_columns:
        db.session.execute(text('ALTER TABLE tasks ADD COLUMN locked BOOLEAN DEFAULT 0'))
        db.session.commit()
    print('✅ Database ready!')

if __name__ == '__main__':
    app.run(debug=True)
