"""PawPal+ logic layer -- class skeletons generated from diagrams/uml_draft.mmd."""

from dataclasses import dataclass, field


@dataclass
class Task:
    """A single pet care activity."""

    description: str
    time: str
    duration_minutes: int = 15
    priority: str = "medium"
    frequency: str = "once"
    completed: bool = False

    def mark_complete(self) -> None:
        """Flag this task as done."""
        raise NotImplementedError

    def next_occurrence(self) -> "Task | None":
        """Return the follow-up task for a recurring activity."""
        raise NotImplementedError


@dataclass
class Pet:
    """A pet and the tasks that belong to it."""

    name: str
    species: str = "dog"
    age: int | None = None
    tasks: list[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> Task:
        """Attach a task to this pet."""
        raise NotImplementedError

    def tasks_for_today(self) -> list[Task]:
        """Return the tasks due today."""
        raise NotImplementedError


@dataclass
class Owner:
    """A pet owner managing one or more pets."""

    name: str
    pets: list[Pet] = field(default_factory=list)

    def add_pet(self, pet: Pet) -> Pet:
        """Register a pet with this owner."""
        raise NotImplementedError

    def get_pet(self, name: str) -> Pet | None:
        """Look a pet up by name."""
        raise NotImplementedError

    def all_tasks(self) -> list[Task]:
        """Return every task across every pet."""
        raise NotImplementedError


class Scheduler:
    """The brain: organises tasks across an owner's pets."""

    def __init__(self, owner: Owner) -> None:
        self.owner = owner

    def sort_by_time(self, tasks: list[Task] | None = None) -> list[Task]:
        """Return tasks in chronological order."""
        raise NotImplementedError

    def filter_tasks(self, pet_name: str | None = None, completed: bool | None = None) -> list[Task]:
        """Return tasks matching the given pet and/or completion status."""
        raise NotImplementedError

    def todays_schedule(self) -> list[Task]:
        """Return today's tasks, sorted."""
        raise NotImplementedError

    def find_conflicts(self) -> list[str]:
        """Return human-readable warnings for clashing tasks."""
        raise NotImplementedError

    def mark_task_complete(self, task: Task) -> Task | None:
        """Complete a task and roll recurring ones forward."""
        raise NotImplementedError
