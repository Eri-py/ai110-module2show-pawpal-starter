"""PawPal+ logic layer: Task, Pet, Owner and the Scheduler that plans their day.

This module is the "brain" of PawPal+ and knows nothing about Streamlit, so it
can be driven from `main.py` (CLI) or `app.py` (UI) alike.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

#: Allowed priority labels, most urgent first.
PRIORITIES = ("high", "medium", "low")

#: Sort weight for each priority label; unknown labels sort last.
PRIORITY_ORDER = {label: index for index, label in enumerate(PRIORITIES)}

#: How far ahead each frequency repeats. "once" never repeats.
RECURRENCE_STEP = {"daily": timedelta(days=1), "weekly": timedelta(weeks=1)}


def parse_time(value: str) -> int:
    """Convert an 'HH:MM' string into minutes past midnight."""
    hours, _, minutes = value.partition(":")
    return int(hours) * 60 + int(minutes)


def format_time(minutes: int) -> str:
    """Convert minutes past midnight back into an 'HH:MM' string."""
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


@dataclass
class Task:
    """A single pet care activity at a fixed time of day."""

    description: str
    time: str = "08:00"
    duration_minutes: int = 15
    priority: str = "medium"
    frequency: str = "once"
    due_date: date = field(default_factory=date.today)
    completed: bool = False
    pet_name: str | None = None

    def __post_init__(self) -> None:
        """Normalise the free-text fields so comparisons stay predictable."""
        self.priority = self.priority.lower()
        self.frequency = self.frequency.lower()

    @property
    def start_minutes(self) -> int:
        """Start time as minutes past midnight (used for sorting)."""
        return parse_time(self.time)

    @property
    def end_minutes(self) -> int:
        """End time as minutes past midnight."""
        return self.start_minutes + self.duration_minutes

    @property
    def is_recurring(self) -> bool:
        """True when this task repeats (daily or weekly)."""
        return self.frequency in RECURRENCE_STEP

    def mark_complete(self) -> None:
        """Flag this task as done."""
        self.completed = True

    def next_occurrence(self) -> Task | None:
        """Return the next instance of a recurring task, or None if it is one-off."""
        step = RECURRENCE_STEP.get(self.frequency)
        if step is None:
            return None
        return Task(
            description=self.description,
            time=self.time,
            duration_minutes=self.duration_minutes,
            priority=self.priority,
            frequency=self.frequency,
            due_date=self.due_date + step,
            completed=False,
            pet_name=self.pet_name,
        )

    def overlaps(self, other: Task) -> bool:
        """True when this task shares clock time with `other` on the same day."""
        if self.due_date != other.due_date:
            return False
        return self.start_minutes < other.end_minutes and other.start_minutes < self.end_minutes

    def __str__(self) -> str:
        """Render the task as one readable schedule line."""
        status = "x" if self.completed else " "
        window = f"{self.time}-{format_time(self.end_minutes)}"
        pet_label = f" ({self.pet_name})" if self.pet_name else ""
        repeat = "" if self.frequency == "once" else f", {self.frequency}"
        return (
            f"[{status}] {window}  {self.description}{pet_label} "
            f"[{self.duration_minutes} min, {self.priority}{repeat}]"
        )


@dataclass
class Pet:
    """A pet, its basic details, and the care tasks that belong to it."""

    name: str
    species: str = "dog"
    age: int | None = None
    notes: str = ""
    tasks: list[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> Task:
        """Attach a task to this pet and stamp it with the pet's name."""
        task.pet_name = self.name
        self.tasks.append(task)
        return task

    def remove_task(self, task: Task) -> None:
        """Detach a task from this pet, ignoring tasks it does not own."""
        if task in self.tasks:
            self.tasks.remove(task)

    def tasks_for_date(self, day: date | None = None) -> list[Task]:
        """Return the tasks due on `day` (defaults to today)."""
        target = day or date.today()
        return [task for task in self.tasks if task.due_date == target]

    def pending_tasks(self, day: date | None = None) -> list[Task]:
        """Return the not-yet-completed tasks due on `day`."""
        return [task for task in self.tasks_for_date(day) if not task.completed]

    def __str__(self) -> str:
        """Render the pet as a short label."""
        age = f", {self.age}y" if self.age is not None else ""
        return f"{self.name} ({self.species}{age})"


@dataclass
class Owner:
    """A pet owner, their pets, and how much care time they have per day."""

    name: str
    daily_minutes_available: int = 120
    pets: list[Pet] = field(default_factory=list)

    def add_pet(self, pet: Pet) -> Pet:
        """Register a pet with this owner."""
        self.pets.append(pet)
        return pet

    def get_pet(self, name: str) -> Pet | None:
        """Look a pet up by name, case-insensitively."""
        for pet in self.pets:
            if pet.name.lower() == name.lower():
                return pet
        return None

    def all_tasks(self) -> list[Task]:
        """Return every task across every pet, in insertion order."""
        return [task for pet in self.pets for task in pet.tasks]

    def pet_for_task(self, task: Task) -> Pet | None:
        """Return the pet a task belongs to, or None if it is orphaned."""
        for pet in self.pets:
            if task in pet.tasks:
                return pet
        return None


class Scheduler:
    """The brain: retrieves, sorts, filters and plans an owner's pet care tasks."""

    def __init__(self, owner: Owner) -> None:
        """Bind the scheduler to the owner whose pets it plans for."""
        self.owner = owner

    # -- retrieval ---------------------------------------------------------

    def _tasks(self, tasks: list[Task] | None = None) -> list[Task]:
        """Default to every task the owner has when no explicit list is given."""
        return list(self.owner.all_tasks() if tasks is None else tasks)

    def sort_by_time(self, tasks: list[Task] | None = None) -> list[Task]:
        """Return tasks in chronological order (date first, then 'HH:MM' start)."""
        return sorted(self._tasks(tasks), key=lambda task: (task.due_date, task.start_minutes))

    def sort_by_priority(self, tasks: list[Task] | None = None) -> list[Task]:
        """Return tasks ordered high to low priority, then chronologically."""
        return sorted(
            self._tasks(tasks),
            key=lambda task: (
                PRIORITY_ORDER.get(task.priority, len(PRIORITIES)),
                task.due_date,
                task.start_minutes,
            ),
        )

    def filter_tasks(
        self,
        tasks: list[Task] | None = None,
        pet_name: str | None = None,
        completed: bool | None = None,
        priority: str | None = None,
        day: date | None = None,
    ) -> list[Task]:
        """Return the tasks matching every filter supplied (None means no filter)."""
        selected = self._tasks(tasks)
        if pet_name is not None:
            selected = [t for t in selected if (t.pet_name or "").lower() == pet_name.lower()]
        if completed is not None:
            selected = [t for t in selected if t.completed is completed]
        if priority is not None:
            selected = [t for t in selected if t.priority == priority.lower()]
        if day is not None:
            selected = [t for t in selected if t.due_date == day]
        return selected

    def tasks_for_date(self, day: date | None = None) -> list[Task]:
        """Return every task due on `day` (defaults to today), chronologically."""
        target = day or date.today()
        return self.sort_by_time(self.filter_tasks(day=target))

    def todays_schedule(self, pet_name: str | None = None) -> list[Task]:
        """Return today's tasks, optionally for one pet, in chronological order."""
        today = self.tasks_for_date()
        if pet_name is not None:
            today = self.filter_tasks(today, pet_name=pet_name)
        return today

    # -- recurrence --------------------------------------------------------

    def mark_task_complete(self, task: Task) -> Task | None:
        """Complete a task; if it recurs, queue the next occurrence and return it."""
        task.mark_complete()
        follow_up = task.next_occurrence()
        if follow_up is None:
            return None
        pet = self.owner.pet_for_task(task)
        if pet is None and task.pet_name:
            pet = self.owner.get_pet(task.pet_name)
        if pet is None:
            return None
        return pet.add_task(follow_up)

    # -- conflict detection ------------------------------------------------

    def find_conflicts(self, tasks: list[Task] | None = None) -> list[str]:
        """Return one warning string per pair of tasks whose time windows overlap."""
        ordered = self.sort_by_time(self._tasks(tasks))
        warnings: list[str] = []
        for index, task in enumerate(ordered):
            for other in ordered[index + 1:]:
                if other.due_date == task.due_date and other.start_minutes >= task.end_minutes:
                    break  # sorted by start time, so nothing later can overlap
                if not task.overlaps(other):
                    continue
                same_pet = task.pet_name == other.pet_name
                who = task.pet_name if same_pet else f"{task.pet_name} and {other.pet_name}"
                warnings.append(
                    f"Conflict for {who} on {task.due_date}: "
                    f"'{task.description}' ({task.time}-{format_time(task.end_minutes)}) "
                    f"overlaps '{other.description}' "
                    f"({other.time}-{format_time(other.end_minutes)})."
                )
        return warnings

    def has_conflicts(self, tasks: list[Task] | None = None) -> bool:
        """True when at least one pair of tasks overlaps."""
        return bool(self.find_conflicts(tasks))

    # -- daily planning ----------------------------------------------------

    def build_daily_plan(
        self, day: date | None = None, available_minutes: int | None = None
    ) -> dict:
        """Fit the day's pending tasks into the owner's time budget, priority first.

        Returns a dict holding the chosen tasks (chronological), the ones that did
        not fit, any time conflicts among the chosen tasks, and one line of
        reasoning per task so the UI can explain the plan.
        """
        target = day or date.today()
        budget = (
            self.owner.daily_minutes_available if available_minutes is None else available_minutes
        )
        candidates = self.sort_by_priority(self.filter_tasks(day=target, completed=False))

        chosen: list[Task] = []
        skipped: list[Task] = []
        reasons: list[str] = []
        remaining = budget
        for task in candidates:
            if task.duration_minutes <= remaining:
                chosen.append(task)
                remaining -= task.duration_minutes
                reasons.append(
                    f"Kept '{task.description}' for {task.pet_name} at {task.time}: "
                    f"{task.priority} priority, {task.duration_minutes} min "
                    f"({remaining} of {budget} min left)."
                )
            else:
                skipped.append(task)
                reasons.append(
                    f"Skipped '{task.description}' for {task.pet_name}: needs "
                    f"{task.duration_minutes} min but only {remaining} min of the "
                    f"{budget} min budget remain."
                )
        return {
            "date": target,
            "available_minutes": budget,
            "scheduled": self.sort_by_time(chosen),
            "skipped": skipped,
            "minutes_used": budget - remaining,
            "minutes_left": remaining,
            "conflicts": self.find_conflicts(chosen),
            "reasons": reasons,
        }

    def format_schedule(
        self, tasks: list[Task] | None = None, title: str = "Today's Schedule"
    ) -> str:
        """Render a task list as a readable block of text for the terminal."""
        ordered = self.sort_by_time(tasks if tasks is not None else self.todays_schedule())
        lines = [title, "=" * len(title)]
        if not ordered:
            lines.append("  (nothing scheduled)")
        lines.extend(f"  {task}" for task in ordered)
        return "\n".join(lines)
