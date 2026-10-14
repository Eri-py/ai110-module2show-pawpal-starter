"""PawPal+ logic layer: Task, Pet, Owner and the Scheduler that plans their day.

This module is the "brain" of PawPal+ and knows nothing about Streamlit, so it
can be driven from `main.py` (CLI) or `app.py` (UI) alike.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path

#: Default file used by Owner.save_to_json() / Owner.load_from_json().
DATA_FILE = Path(__file__).with_name("data.json")

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

    def next_occurrence(self, after: date | None = None) -> Task | None:
        """Return the next instance of a recurring task, or None if it is one-off.

        By default this is simply `due_date + one step`, which keeps the result
        independent of the clock. Pass `after` (normally today) to catch up a
        stale task: the new date is then the first occurrence strictly after
        `after`, reached by whole-period arithmetic so a weekly task keeps its
        weekday and a years-stale task costs one division, not a loop.
        """
        step = RECURRENCE_STEP.get(self.frequency)
        if step is None:
            return None
        due = self.due_date + step
        if after is not None and due <= after:
            due += ((after - due) // step + 1) * step
        return Task(
            description=self.description,
            time=self.time,
            duration_minutes=self.duration_minutes,
            priority=self.priority,
            frequency=self.frequency,
            due_date=due,
            completed=False,
            pet_name=self.pet_name,
        )

    def overlaps(self, other: Task) -> bool:
        """True when this task shares clock time with `other` on the same day."""
        if self.due_date != other.due_date:
            return False
        return self.start_minutes < other.end_minutes and other.start_minutes < self.end_minutes

    def to_dict(self) -> dict:
        """Return a JSON-safe dict (dates become ISO strings)."""
        data = asdict(self)
        data["due_date"] = self.due_date.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> Task:
        """Rebuild a Task from the dict produced by `to_dict()`."""
        fields = dict(data)
        fields["due_date"] = date.fromisoformat(fields["due_date"])
        return cls(**fields)

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

    def to_dict(self) -> dict:
        """Return a JSON-safe dict for this pet and its tasks."""
        return {
            "name": self.name,
            "species": self.species,
            "age": self.age,
            "notes": self.notes,
            "tasks": [task.to_dict() for task in self.tasks],
        }

    @classmethod
    def from_dict(cls, data: dict) -> Pet:
        """Rebuild a Pet (and its tasks) from the dict produced by `to_dict()`."""
        pet = cls(
            name=data["name"],
            species=data.get("species", "dog"),
            age=data.get("age"),
            notes=data.get("notes", ""),
        )
        for task_data in data.get("tasks", []):
            pet.add_task(Task.from_dict(task_data))
        return pet

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

    # -- persistence -------------------------------------------------------

    def to_dict(self) -> dict:
        """Return a JSON-safe dict for the whole household."""
        return {
            "name": self.name,
            "daily_minutes_available": self.daily_minutes_available,
            "pets": [pet.to_dict() for pet in self.pets],
        }

    @classmethod
    def from_dict(cls, data: dict) -> Owner:
        """Rebuild an Owner (with pets and tasks) from `to_dict()` output."""
        owner = cls(
            name=data.get("name", "Owner"),
            daily_minutes_available=data.get("daily_minutes_available", 120),
        )
        for pet_data in data.get("pets", []):
            owner.add_pet(Pet.from_dict(pet_data))
        return owner

    def save_to_json(self, path: str | Path = DATA_FILE) -> Path:
        """Write the household to `path` as JSON and return the path written."""
        target = Path(path)
        target.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return target

    @classmethod
    def load_from_json(cls, path: str | Path = DATA_FILE) -> Owner | None:
        """Load a household from `path`, or return None if the file is missing."""
        source = Path(path)
        if not source.exists():
            return None
        return cls.from_dict(json.loads(source.read_text(encoding="utf-8")))


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

    def mark_task_complete(self, task: Task, catch_up: bool = True) -> Task | None:
        """Complete a task; if it recurs, queue the next occurrence and return it.

        With `catch_up` (the default) a task whose due date is already in the past
        is rolled forward to its first future occurrence instead of landing in the
        past again -- what you want after not opening the app for a week.
        """
        task.mark_complete()
        follow_up = task.next_occurrence(after=date.today() if catch_up else None)
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

    # -- free-slot search --------------------------------------------------

    def busy_intervals(
        self,
        day: date | None = None,
        pet_name: str | None = None,
        ignore: Task | None = None,
    ) -> list[tuple[int, int]]:
        """Return the day's occupied (start, end) minute ranges, merged and sorted."""
        target = day or date.today()
        tasks = [
            task
            for task in self.filter_tasks(day=target, pet_name=pet_name, completed=False)
            if task is not ignore
        ]
        merged: list[tuple[int, int]] = []
        for start, end in sorted((t.start_minutes, t.end_minutes) for t in tasks):
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        return merged

    def next_free_slot(
        self,
        duration_minutes: int,
        day: date | None = None,
        pet_name: str | None = None,
        earliest: str = "07:00",
        latest: str = "21:00",
        ignore: Task | None = None,
    ) -> str | None:
        """Return the earliest 'HH:MM' with `duration_minutes` free, or None if full.

        Walks the gaps between the day's merged busy intervals inside the
        [earliest, latest] window, so it is O(n log n) in the number of tasks.
        """
        window_start, window_end = parse_time(earliest), parse_time(latest)
        if duration_minutes <= 0 or window_end - window_start < duration_minutes:
            return None
        cursor = window_start
        for start, end in self.busy_intervals(day, pet_name, ignore=ignore):
            if end <= cursor:
                continue
            if start - cursor >= duration_minutes:
                return format_time(cursor)
            cursor = max(cursor, end)
            if cursor + duration_minutes > window_end:
                return None
        return format_time(cursor) if cursor + duration_minutes <= window_end else None

    def suggest_reschedule(self, task: Task, pet_only: bool = True) -> str | None:
        """Return the earliest conflict-free start time for `task`, or None if full.

        The search starts at the task's own time and moves later, so a suggestion
        reads as "push this back a bit" rather than "get up earlier". The task
        itself is excluded from the busy map, so a task that does not clash with
        anything keeps its current time.
        """
        return self.next_free_slot(
            task.duration_minutes,
            day=task.due_date,
            pet_name=task.pet_name if pet_only else None,
            earliest=task.time,
            latest="23:00",
            ignore=task,
        )

    def resolve_conflicts(self, day: date | None = None, pet_only: bool = True) -> list[str]:
        """Suggest a new time for each conflicting task without changing anything."""
        target = day or date.today()
        suggestions: list[str] = []
        seen: set[int] = set()
        ordered = self.sort_by_time(self.filter_tasks(day=target, completed=False))
        for index, task in enumerate(ordered):
            for other in ordered[index + 1:]:
                if not task.overlaps(other) or id(other) in seen:
                    continue
                if pet_only and task.pet_name != other.pet_name:
                    continue
                seen.add(id(other))
                slot = self.suggest_reschedule(other, pet_only=pet_only)
                if slot is None:
                    suggestions.append(
                        f"'{other.description}' ({other.pet_name}) clashes with "
                        f"'{task.description}' and the day is full -- shorten something."
                    )
                else:
                    suggestions.append(
                        f"Move '{other.description}' ({other.pet_name}) from {other.time} "
                        f"to {slot} to clear its clash with '{task.description}'."
                    )
        return suggestions

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
