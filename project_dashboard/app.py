from flask import Flask, render_template, redirect, url_for, flash, request, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import or_, inspect, text
from datetime import timedelta, date
import calendar
from models import db, User, Project, Task, Subtask, ProjectMemberPermission, Sprint
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

def build_sprints(project):
    if not project.start_date or not project.end_date or not project.sprint_length_days:
        return []
    sprint_length = project.sprint_length_days
    if sprint_length < 1:
        return []
    sprints = []
    current_start = project.start_date
    index = 1
    while current_start <= project.end_date:
        current_end = min(current_start + timedelta(days=sprint_length - 1), project.end_date)
        sprints.append(
            Sprint(
                name=f'Sprint {index}',
                start_date=current_start,
                end_date=current_end,
                project_id=project.id,
            )
        )
        index += 1
        current_start = current_end + timedelta(days=1)
    return sprints

def shift_month(year, month, delta):
    new_month = month + delta
    new_year = year + (new_month - 1) // 12
    new_month = (new_month - 1) % 12 + 1
    return new_year, new_month

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
        project = Project(
            name=form.name.data,
            description=form.description.data,
            start_date=form.start_date.data,
            end_date=form.end_date.data,
            sprint_length_days=form.sprint_length_days.data or 7,
            status=form.status.data,
            user_id=current_user.id,
        )
        db.session.add(project)
        db.session.commit()
        sprints = build_sprints(project)
        if sprints:
            db.session.add_all(sprints)
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
    sprints = project.sprints.order_by(Sprint.start_date.asc()).all()
    return render_template(
        'project_detail.html',
        project=project,
        tasks=tasks,
        task_stats=task_stats,
        form=form,
        is_owner=(project.user_id == current_user.id),
        can_edit_tasks=user_can_edit_tasks(project, current_user),
        member_permissions=member_permissions,
        sprints=sprints,
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
        if form.sprint_length_days.data:
            project.sprint_length_days = form.sprint_length_days.data
        db.session.commit()
        flash('Project updated!', 'success')
        return redirect(url_for('project_detail', project_id=project.id))
    return render_template('project_form.html', form=form, title='Edit Project', project=project)

@app.route('/project/<int:project_id>/sprints/generate', methods=['POST'])
@login_required
def generate_sprints(project_id):
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    if not project.start_date or not project.end_date or not project.sprint_length_days:
        flash('Please set start date, end date, and sprint length before generating sprints.', 'warning')
        return redirect(url_for('project_detail', project_id=project.id))
    Task.query.filter_by(project_id=project.id).update({Task.sprint_id: None})
    Sprint.query.filter_by(project_id=project.id).delete()
    db.session.commit()
    sprints = build_sprints(project)
    if not sprints:
        flash('Unable to generate sprints with the current settings.', 'warning')
        return redirect(url_for('project_detail', project_id=project.id))
    db.session.add_all(sprints)
    db.session.commit()
    flash(f'{len(sprints)} sprint(s) generated.', 'success')
    return redirect(url_for('project_detail', project_id=project.id))

@app.route('/project/<int:project_id>/sprint/<int:sprint_id>/update', methods=['POST'])
@login_required
def update_sprint(project_id, sprint_id):
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    sprint = Sprint.query.get_or_404(sprint_id)
    if sprint.project_id != project.id:
        flash('Invalid sprint.', 'danger')
        return redirect(url_for('project_detail', project_id=project.id))
    name = (request.form.get('name') or '').strip()
    description = (request.form.get('description') or '').strip()
    if name:
        sprint.name = name
    sprint.description = description or None
    db.session.commit()
    flash('Sprint updated.', 'success')
    return redirect(url_for('project_detail', project_id=project.id))

@app.route('/project/<int:project_id>/calendar')
@login_required
def project_calendar(project_id):
    project = Project.query.get_or_404(project_id)
    if not is_project_member(project, current_user):
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    month_param = request.args.get('month', '').strip()
    ref_date = project.start_date or date.today()
    year = ref_date.year
    month = ref_date.month
    if month_param:
        try:
            parts = month_param.split('-')
            year = int(parts[0])
            month = int(parts[1])
        except (ValueError, IndexError):
            pass
    try:
        month_start = date(year, month, 1)
    except ValueError:
        year = ref_date.year
        month = ref_date.month
        month_start = date(year, month, 1)
    month_end = date(year, month, calendar.monthrange(year, month)[1])

    events = {}
    def add_event_range(start_date, end_date, label, event_type):
        if not start_date or not end_date:
            return
        current = max(start_date, month_start)
        final = min(end_date, month_end)
        while current <= final:
            key = current.isoformat()
            events.setdefault(key, []).append({'label': label, 'type': event_type})
            current += timedelta(days=1)

    for sprint in project.sprints.all():
        add_event_range(sprint.start_date, sprint.end_date, f"Sprint: {sprint.name}", 'sprint')

    tasks = Task.query.filter_by(project_id=project.id).all()
    for task in tasks:
        start = task.start_date or task.due_date
        end = task.end_date or task.due_date or task.start_date
        if not start or not end:
            continue
        add_event_range(start, end, f"Task: {task.title}", 'task')

    cal = calendar.Calendar(firstweekday=0)
    weeks = cal.monthdatescalendar(year, month)
    prev_year, prev_month = shift_month(year, month, -1)
    next_year, next_month = shift_month(year, month, 1)

    return render_template(
        'project_calendar.html',
        project=project,
        weeks=weeks,
        events=events,
        month_label=month_start.strftime('%B %Y'),
        current_month=month,
        current_year=year,
        prev_month=f"{prev_year:04d}-{prev_month:02d}",
        next_month=f"{next_year:04d}-{next_month:02d}",
        today=date.today(),
    )

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
    sprint_choices = [(0, 'No Sprint')] + [
        (s.id, f"{s.name} ({s.start_date} - {s.end_date})")
        for s in project.sprints.order_by(Sprint.start_date.asc()).all()
    ]
    form.sprint_id.choices = sprint_choices
    form.sprint_id.validators = []
    if request.method == 'POST':
        if form.validate():
            assigned_id = form.assigned_to.data if form.assigned_to.data != 0 else None
            sprint_id = form.sprint_id.data if form.sprint_id.data != 0 else None
            task = Task(
                title=form.title.data,
                description=form.description.data,
                status=form.status.data,
                priority=form.priority.data,
                start_date=form.start_date.data,
                due_date=form.due_date.data,
                end_date=form.end_date.data,
                project_id=project.id,
                assigned_user_id=assigned_id,
                sprint_id=sprint_id,
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
    sprint_choices = [(0, 'No Sprint')] + [
        (s.id, f"{s.name} ({s.start_date} - {s.end_date})")
        for s in task.project.sprints.order_by(Sprint.start_date.asc()).all()
    ]
    form.sprint_id.choices = sprint_choices
    form.sprint_id.validators = []
    if request.method == 'GET':
        form.assigned_to.data = task.assigned_user_id or 0
        form.sprint_id.data = task.sprint_id or 0
    if request.method == 'POST' and form.validate():
        task.title = form.title.data
        task.description = form.description.data
        task.status = form.status.data
        task.priority = form.priority.data
        task.start_date = form.start_date.data
        task.due_date = form.due_date.data
        task.end_date = form.end_date.data
        task.assigned_user_id = form.assigned_to.data if form.assigned_to.data != 0 else None
        task.sprint_id = form.sprint_id.data if form.sprint_id.data != 0 else None
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
    if 'sprint_id' not in task_columns:
        db.session.execute(text('ALTER TABLE tasks ADD COLUMN sprint_id INTEGER'))
        db.session.commit()
    if 'start_date' not in task_columns:
        db.session.execute(text('ALTER TABLE tasks ADD COLUMN start_date DATE'))
        db.session.commit()
    if 'end_date' not in task_columns:
        db.session.execute(text('ALTER TABLE tasks ADD COLUMN end_date DATE'))
        db.session.commit()
    project_columns = [column['name'] for column in inspector.get_columns('projects')]
    if 'sprint_length_days' not in project_columns:
        db.session.execute(text('ALTER TABLE projects ADD COLUMN sprint_length_days INTEGER DEFAULT 7'))
        db.session.commit()
    if 'sprints' in inspector.get_table_names():
        sprint_columns = [column['name'] for column in inspector.get_columns('sprints')]
        if 'description' not in sprint_columns:
            db.session.execute(text('ALTER TABLE sprints ADD COLUMN description TEXT'))
            db.session.commit()
    print('✅ Database ready!')

if __name__ == '__main__':
    app.run(debug=True)
