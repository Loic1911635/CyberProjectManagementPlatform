from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

# Many-to-many association table for project members
project_members = db.Table('project_members',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('project_id', db.Integer, db.ForeignKey('projects.id'), primary_key=True)
)

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    projects = db.relationship('Project', backref='owner', lazy='dynamic', cascade='all, delete-orphan')
    assigned_tasks = db.relationship('Task', backref='assigned_to', lazy='dynamic')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'

class Project(db.Model):
    __tablename__ = 'projects'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    status = db.Column(db.String(50), default='active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Many-to-many relationship with users as members
    members = db.relationship('User', secondary=project_members, backref='projects_as_member')
    tasks = db.relationship('Task', backref='project', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Project {self.name}>'

class Task(db.Model):
    __tablename__ = 'tasks'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(50), default='todo')
    priority = db.Column(db.String(20), default='medium')
    due_date = db.Column(db.Date)
    completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    assigned_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # Relationship to subtasks
    subtasks = db.relationship('Subtask', backref='task', lazy='dynamic', cascade='all, delete-orphan')
    
    def get_completion_percentage(self):
        """Calculate task completion based on subtasks"""
        total = self.subtasks.count()
        if total == 0:
            return 0
        completed = self.subtasks.filter_by(completed=True).count()
        return int((completed / total) * 100)
    
    def __repr__(self):
        return f'<Task {self.title}>'

class Subtask(db.Model):
    __tablename__ = 'subtasks'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)
    
    def __repr__(self):
        return f'<Subtask {self.title}>'