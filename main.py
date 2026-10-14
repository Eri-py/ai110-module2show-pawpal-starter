"""CLI demo for PawPal+: builds a sample household and exercises the Scheduler."""

import sys
from datetime import date, timedelta

from pawpal_system import Owner, Pet, Scheduler, Task, format_time

try:  # Pretty tables when tabulate is installed (see requirements.txt).
    from tabulate import tabulate
except ImportError:  # pragma: no cover - fallback keeps the demo runnable
    tabulate = None

# The table borders and status icons below are non-ASCII, and the default Windows
# console encoding (cp1252) cannot encode them -- so ask stdout for UTF-8 and
# degrade to "?" rather than crashing on a terminal that still refuses.
if hasattr(sys.stdout, "reconfigure"):  # pragma: no cover - console plumbing
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PRIORITY_ICON = {"high": "\U0001f534", "medium": "\U0001f7e0", "low": "\U0001f7e2"}
STATUS_ICON = {True: "\u2705 done", False: "\u2b1c todo"}
TABLE_HEADERS = ("Time", "Pet", "Task", "Min", "Priority", "Repeats", "Status")


def heading(text: str) -> None:
    """Print a section heading."""
    print(f"\n{text}\n{'-' * len(text)}")


def task_table(tasks: list[Task], empty: str = "(nothing scheduled)") -> str:
    """Render tasks as a table, falling back to plain lines without tabulate."""
    if not tasks:
        return f"  {empty}"
    if tabulate is None:
        return "\n".join(f"  {task}" for task in tasks)
    rows = [
        (
            f"{task.time}-{format_time(task.end_minutes)}",
            task.pet_name,
            task.description,
            task.duration_minutes,
            f"{PRIORITY_ICON.get(task.priority, '')} {task.priority}",
            task.frequency,
            STATUS_ICON[task.completed],
        )
        for task in tasks
    ]
    return tabulate(rows, headers=TABLE_HEADERS, tablefmt="simple_outline")


def build_demo_owner() -> Owner:
    """Create a sample owner with two pets and a deliberately messy task list."""
    owner = Owner(name="Jordan", daily_minutes_available=60)

    biscuit = owner.add_pet(Pet(name="Biscuit", species="dog", age=4))
    mochi = owner.add_pet(Pet(name="Mochi", species="cat", age=2))

    # Added out of chronological order on purpose, so sorting has work to do.
    biscuit.add_task(
        Task(description="Evening walk", time="18:30", duration_minutes=30, priority="medium",
             frequency="daily")
    )
    biscuit.add_task(
        Task(description="Morning walk", time="08:00", duration_minutes=30, priority="high",
             frequency="daily")
    )
    biscuit.add_task(
        Task(description="Brush coat", time="20:00", duration_minutes=15, priority="low",
             frequency="weekly")
    )
    mochi.add_task(
        Task(description="Breakfast", time="07:30", duration_minutes=10, priority="high",
             frequency="daily")
    )
    mochi.add_task(
        Task(description="Thyroid meds", time="07:35", duration_minutes=5, priority="high",
             frequency="daily")
    )
    mochi.add_task(
        Task(description="Play session", time="19:00", duration_minutes=20, priority="medium")
    )
    # Late but urgent: makes priority sorting visibly diverge from time sorting.
    mochi.add_task(
        Task(description="Evening meds", time="21:00", duration_minutes=5, priority="high",
             frequency="daily")
    )
    return owner


def main() -> None:
    """Run the demo end to end and print each scheduler behaviour."""
    owner = build_demo_owner()
    scheduler = Scheduler(owner)
    today = date.today()

    print(f"PawPal+ demo for {owner.name} -- {today:%A %d %B %Y}")
    print(f"Pets: {', '.join(str(pet) for pet in owner.pets)}")
    print(f"Care time available today: {owner.daily_minutes_available} min")

    # 1. Sorting: tasks were added out of order; print them chronologically.
    heading("Today's schedule (sorted by time)")
    print(task_table(scheduler.todays_schedule()))

    # 2. Priority sorting: the same tasks ranked by urgency instead of clock time.
    heading("Same tasks, sorted by priority then time")
    print(task_table(scheduler.sort_by_priority(scheduler.todays_schedule())))

    # 3. Filtering: one pet at a time.
    heading("Filtered -- Mochi only")
    print(task_table(scheduler.todays_schedule(pet_name="Mochi")))

    # 4. Conflict detection: Mochi's breakfast and meds overlap.
    heading("Conflict check")
    conflicts = scheduler.find_conflicts()
    for warning in conflicts or ["No conflicts found."]:
        print(f"  {'WARNING: ' if conflicts else ''}{warning}")

    # 5. Free-slot search: turn each conflict into an actionable suggestion.
    heading("Suggested fixes (next free slot)")
    for suggestion in scheduler.resolve_conflicts() or ["Nothing to reschedule."]:
        print(f"  {suggestion}")
    print(f"  Next 45-min gap in Biscuit's day: {scheduler.next_free_slot(45, pet_name='Biscuit')}")

    # 6. Recurrence: completing a daily task queues tomorrow's copy.
    morning_walk = scheduler.filter_tasks(pet_name="Biscuit", priority="high")[0]
    follow_up = scheduler.mark_task_complete(morning_walk)
    heading("Recurrence")
    print(f"  Completed:   {morning_walk}")
    print(f"  Queued next: {follow_up}  (due {follow_up.due_date})")

    stale = owner.get_pet("Mochi").add_task(
        Task(description="Flea treatment", time="21:00", duration_minutes=5,
             frequency="weekly", due_date=today - timedelta(days=23))
    )
    caught_up = scheduler.mark_task_complete(stale)
    print(f"  Stale task from {stale.due_date} ({stale.due_date:%A}) caught up to "
          f"{caught_up.due_date} ({caught_up.due_date:%A}) -- same weekday, now in the future")

    heading("Tomorrow's schedule")
    print(task_table(scheduler.tasks_for_date(today + timedelta(days=1))))

    # 7. Daily plan: priority-first packing into the owner's time budget.
    plan = scheduler.build_daily_plan()
    heading(f"Daily plan ({plan['minutes_used']}/{plan['available_minutes']} min used)")
    print(task_table(plan["scheduled"], empty="(nothing left to schedule)"))
    if plan["skipped"]:
        print("\n  Did not fit the time budget:")
        print(task_table(plan["skipped"]))
    print("\n  Reasoning:")
    for reason in plan["reasons"]:
        print(f"    - {reason}")
    for warning in plan["conflicts"]:
        print(f"    ! {warning}")

    # 8. Persistence: save the household, reload it, prove it survived.
    heading("Persistence")
    path = owner.save_to_json()
    reloaded = Owner.load_from_json(path)
    print(f"  Saved {len(owner.all_tasks())} tasks for {len(owner.pets)} pets to {path.name}")
    print(f"  Reloaded {reloaded.name}: "
          f"{', '.join(f'{pet.name} ({len(pet.tasks)} tasks)' for pet in reloaded.pets)}")
    print(f"  Round-trip identical: {reloaded.to_dict() == owner.to_dict()}")


if __name__ == "__main__":
    main()
