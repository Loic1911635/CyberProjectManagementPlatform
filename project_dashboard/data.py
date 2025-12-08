# data.py
from dataclasses import dataclass, field
from typing import List

@dataclass
class Task:
    id: int
    title: str
    done: bool = False

@dataclass
class Sprint:
    id: int
    name: str
    start: str
    end: str
    overview: str
    goals: List[str]
    acceptance: List[str]
    tasks: List[Task] = field(default_factory=list)

sprints: List[Sprint] = [
    Sprint(
        id=1,
        name="Week 3 – Base App",
        start="2025-12-01",
        end="2025-12-07",
        overview="Develop the skeleton of the core application and ensure a basic, testable structure is in place.",
        goals=[
            "Set up main Flask modules",
            "Scaffold key routes",
            "Establish configuration and bootstrap",
            "Build basic UI template",
        ],
        acceptance=[
            "All contributors can run and test the base app",
            "Main modules working and documented",
            "Basic UI loads and is responsive",
        ],
        tasks=[
            Task(1, "Configure base app structure"),
            Task(2, "Implement main entrypoints/routes"),
            Task(3, "Integrate initial UI template"),
            Task(4, "Set up automated tests/dummy data"),
        ],
    )
]

