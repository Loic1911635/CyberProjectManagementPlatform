from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, TextAreaField, DateField, SelectField, BooleanField, SelectMultipleField, IntegerField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError, Optional, NumberRange
from models import User

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')

class SignupForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    password_confirm = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    
    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Username already taken.')
    
    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email already registered.')

class ProjectForm(FlaskForm):
    name = StringField('Project Name', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Description')
    start_date = DateField('Start Date', format='%Y-%m-%d', validators=[])
    end_date = DateField('End Date', format='%Y-%m-%d', validators=[])
    sprint_length_days = IntegerField('Sprint Length (days)', validators=[Optional(), NumberRange(min=1, max=60)])
    status = SelectField('Status', choices=[('active', 'Active'), ('completed', 'Completed'), ('archived', 'Archived')])

class TaskForm(FlaskForm):
    title = StringField('Task Title', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Description')
    status = SelectField('Status', choices=[('todo', 'To Do'), ('in_progress', 'In Progress'), ('done', 'Done')])
    priority = SelectField('Priority', choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High')])
    start_date = DateField('Start Date', format='%Y-%m-%d', validators=[Optional()])
    due_date = DateField('Due Date', format='%Y-%m-%d', validators=[])
    end_date = DateField('End Date', format='%Y-%m-%d', validators=[Optional()])
    assigned_to = SelectField('Assign To', coerce=int, choices=[], validators=[])
    sprint_id = SelectField('Sprint', coerce=int, choices=[], validators=[])

class AddMemberForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    
    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if not user:
            raise ValidationError('User not found.')
