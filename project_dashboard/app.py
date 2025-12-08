# app.py
from flask import Flask, render_template, redirect, url_for
from data import sprints, Sprint, Task

app = Flask(__name__)

def find_sprint(sprint_id: int) -> Sprint | None:
    return next((s for s in sprints if s.id == sprint_id), None)

def find_task(sprint: Sprint, task_id: int) -> Task | None:
    return next((t for t in sprint.tasks if t.id == task_id), None)

@app.route("/")
def index():
    return render_template("index.html", sprints=sprints)

@app.route("/sprint/<int:sprint_id>")
def sprint_detail(sprint_id):
    sprint = find_sprint(sprint_id)
    if not sprint:
        return "Sprint not found", 404
    return render_template("sprint_detail.html", sprint=sprint)

@app.route("/sprint/<int:sprint_id>/task/<int:task_id>/toggle")
def toggle_task(sprint_id, task_id):
    sprint = find_sprint(sprint_id)
    if not sprint:
        return "Sprint not found", 404
    task = find_task(sprint, task_id)
    if not task:
        return "Task not found", 404
    task.done = not task.done
    return redirect(url_for("sprint_detail", sprint_id=sprint_id))

if __name__ == "__main__":
    app.run(debug=True)
