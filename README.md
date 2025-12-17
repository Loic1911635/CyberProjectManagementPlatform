# 🔐 Temporary Working Title: CyberPM


A secure, enterprise-grade project management application built with Flask, designed for cybersecurity teams to manage projects, tasks, and team collaboration.

## ✨ Features

### 🔒 Security-First Design
- **User Authentication**: Secure login/signup with password hashing (Werkzeug)
- **Session Management**: Flask-Login with "Remember Me" functionality
- **Access Control**: Project-level permissions (owner-only access)
- **Password Security**: Minimum 6-character passwords with confirmation validation
- **Production-Ready**: Configurable secret keys via environment variables

### 📊 Project Management
- **Create & Manage Projects**: Full CRUD operations for projects
- **Project Status Tracking**: Active, Completed, or Archived states
- **Date Management**: Start/end date tracking for project timelines
- **Project Ownership**: Each project has a dedicated owner with full control
- **Team Collaboration**: Add/remove team members to projects

### ✅ Task Management
- **Task Creation**: Create tasks within projects
- **Status Workflow**: To Do → In Progress → Done
- **Priority Levels**: Low, Medium, High priority settings
- **Task Assignment**: Assign tasks to project members or keep unassigned
- **Due Date Tracking**: Set and monitor task deadlines
- **Task Completion**: Toggle task completion status

### 📈 Dashboard & Analytics
- **Real-Time Stats**: Total projects, active projects, total tasks, completed tasks
- **Project Overview**: View all your projects sorted by creation date
- **Task Statistics**: Per-project task breakdown by status
- **User-Specific Views**: Each user sees only their own projects and tasks

## 🏗️ Technology Stack

| Component | Technology |
|-----------|-----------|
| **Backend** | Flask 2.3.3 |
| **Database** | SQLite (SQLAlchemy ORM) |
| **Authentication** | Flask-Login |
| **Forms** | Flask-WTF + WTForms |
| **Password Hashing** | Werkzeug Security |
| **Frontend** | Bootstrap 5.3 |
| **Server** | Gunicorn (production) |

