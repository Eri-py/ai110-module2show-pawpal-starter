"""CLI demo for PawPal+: builds a sample household and exercises the Scheduler."""

from datetime import date, timedelta

from pawpal_system import Owner, Pet, Scheduler, Task


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
    return owner


def main() -> None:
    """Run the demo end to end and print each scheduler behaviour."""
    owner = build_demo_owner()
    scheduler = Scheduler(owner)
    today = date.today()

    print(f"PawPal+ demo for {owner.name} -- {today:%A %d %B %Y}")
    print(f"Pets: {', '.join(str(pet) for pet in owner.pets)}")
    print(f"Care time available today: {owner.daily_minutes_available} min\n")

    # 1. Sorting: tasks were added out of order; print them chronologically.
    print(scheduler.format_schedule(title="Today's Schedule (sorted by time)"))

    # 2. Filtering: one pet at a time, and by completion status.
    print("\nFiltered -- Mochi only")
    for task in scheduler.todays_schedule(pet_name="Mochi"):
        print(f"  {task}")

    # 3. Conflict detection: Mochi's breakfast and meds overlap.
    print("\nConflict check")
    conflicts = scheduler.find_conflicts()
    if conflicts:
        for warning in conflicts:
            print(f"  WARNING: {warning}")
    else:
        print("  No conflicts found.")

    # 4. Recurrence: completing a daily task queues tomorrow's copy.
    morning_walk = scheduler.filter_tasks(pet_name="Biscuit", priority="high")[0]
    follow_up = scheduler.mark_task_complete(morning_walk)
    print("\nRecurrence")
    print(f"  Completed: {morning_walk}")
    print(f"  Queued next: {follow_up}  (due {follow_up.due_date})")

    print("\nPending after completion")
    for task in scheduler.filter_tasks(scheduler.todays_schedule(), completed=False):
        print(f"  {task}")

    print(scheduler.format_schedule(
        scheduler.tasks_for_date(today + timedelta(days=1)), title="\nTomorrow's Schedule"
    ))

    # 5. Daily plan: priority-first packing into the owner's time budget.
    plan = scheduler.build_daily_plan()
    print(f"\nDaily plan ({plan['minutes_used']}/{plan['available_minutes']} min used)")
    for task in plan["scheduled"]:
        print(f"  {task}")
    if plan["skipped"]:
        print("  Did not fit:")
        for task in plan["skipped"]:
            print(f"    {task}")
    print("  Reasoning:")
    for reason in plan["reasons"]:
        print(f"    - {reason}")
    if plan["conflicts"]:
        print("  Conflicts inside the plan:")
        for warning in plan["conflicts"]:
            print(f"    - {warning}")


if __name__ == "__main__":
    main()
