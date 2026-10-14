"""Test suite for the PawPal+ logic layer."""

from datetime import date, timedelta

import pytest

from pawpal_system import Owner, Pet, Scheduler, Task

TODAY = date.today()
TOMORROW = TODAY + timedelta(days=1)


@pytest.fixture
def household():
    """An owner with one dog, one cat and no tasks yet."""
    owner = Owner(name="Jordan", daily_minutes_available=60)
    owner.add_pet(Pet(name="Biscuit", species="dog", age=4))
    owner.add_pet(Pet(name="Mochi", species="cat", age=2))
    return owner, Scheduler(owner)


# -- core behaviour --------------------------------------------------------


def test_mark_complete_changes_status():
    """mark_complete() flips a task from pending to done."""
    task = Task(description="Feed", time="07:30")
    assert task.completed is False
    task.mark_complete()
    assert task.completed is True


def test_adding_a_task_increases_the_pets_task_count(household):
    """Pet.add_task() grows the pet's task list and stamps the pet's name."""
    _, scheduler = household
    pet = scheduler.owner.get_pet("Biscuit")
    assert len(pet.tasks) == 0
    task = pet.add_task(Task(description="Morning walk", time="08:00"))
    assert len(pet.tasks) == 1
    assert task.pet_name == "Biscuit"


def test_owner_collects_tasks_from_every_pet(household):
    """Owner.all_tasks() reaches across all pets."""
    owner, _ = household
    owner.get_pet("Biscuit").add_task(Task(description="Walk", time="08:00"))
    owner.get_pet("Mochi").add_task(Task(description="Breakfast", time="07:30"))
    assert len(owner.all_tasks()) == 2


# -- sorting and filtering -------------------------------------------------


def test_sort_by_time_returns_chronological_order(household):
    """Tasks added out of order come back sorted by their 'HH:MM' time."""
    owner, scheduler = household
    pet = owner.get_pet("Biscuit")
    pet.add_task(Task(description="Evening walk", time="18:30"))
    pet.add_task(Task(description="Morning walk", time="08:00"))
    pet.add_task(Task(description="Lunch", time="12:05"))
    assert [t.time for t in scheduler.sort_by_time()] == ["08:00", "12:05", "18:30"]


def test_sort_by_time_handles_single_digit_hours(household):
    """'09:00' sorts before '10:00' (string compare would get this right, but
    '9:00' would not -- the key parses the time instead of comparing text)."""
    owner, scheduler = household
    pet = owner.get_pet("Mochi")
    pet.add_task(Task(description="Late", time="10:00"))
    pet.add_task(Task(description="Early", time="9:00"))
    assert [t.description for t in scheduler.sort_by_time()] == ["Early", "Late"]


def test_sort_by_priority_puts_high_first(household):
    """High priority wins over an earlier start time."""
    owner, scheduler = household
    pet = owner.get_pet("Biscuit")
    pet.add_task(Task(description="Brush", time="07:00", priority="low"))
    pet.add_task(Task(description="Meds", time="21:00", priority="high"))
    assert [t.description for t in scheduler.sort_by_priority()] == ["Meds", "Brush"]


def test_filter_by_pet_and_status(household):
    """filter_tasks() narrows by pet name and completion status."""
    owner, scheduler = household
    walk = owner.get_pet("Biscuit").add_task(Task(description="Walk", time="08:00"))
    owner.get_pet("Mochi").add_task(Task(description="Breakfast", time="07:30"))
    walk.mark_complete()

    assert [t.description for t in scheduler.filter_tasks(pet_name="Mochi")] == ["Breakfast"]
    assert [t.description for t in scheduler.filter_tasks(completed=False)] == ["Breakfast"]
    assert [t.description for t in scheduler.filter_tasks(completed=True)] == ["Walk"]
    assert scheduler.filter_tasks(pet_name="nobody") == []


def test_todays_schedule_ignores_other_days(household):
    """Only tasks due today appear in today's schedule."""
    owner, scheduler = household
    pet = owner.get_pet("Biscuit")
    pet.add_task(Task(description="Today walk", time="08:00", due_date=TODAY))
    pet.add_task(Task(description="Tomorrow walk", time="08:00", due_date=TOMORROW))
    assert [t.description for t in scheduler.todays_schedule()] == ["Today walk"]


def test_pet_with_no_tasks_is_not_an_error(household):
    """An empty household schedules nothing and reports no conflicts."""
    _, scheduler = household
    assert scheduler.todays_schedule() == []
    assert scheduler.find_conflicts() == []
    assert scheduler.build_daily_plan()["scheduled"] == []


# -- recurrence ------------------------------------------------------------


def test_completing_a_daily_task_queues_tomorrow(household):
    """Completing a daily task creates the next instance one day later."""
    owner, scheduler = household
    pet = owner.get_pet("Biscuit")
    walk = pet.add_task(
        Task(description="Morning walk", time="08:00", frequency="daily", due_date=TODAY)
    )

    follow_up = scheduler.mark_task_complete(walk)

    assert walk.completed is True
    assert follow_up is not None
    assert follow_up.completed is False
    assert follow_up.due_date == TOMORROW
    assert follow_up.description == "Morning walk"
    assert follow_up in pet.tasks
    assert len(pet.tasks) == 2


def test_completing_a_weekly_task_queues_next_week(household):
    """Weekly tasks roll forward seven days."""
    owner, scheduler = household
    pet = owner.get_pet("Biscuit")
    groom = pet.add_task(
        Task(description="Brush coat", time="20:00", frequency="weekly", due_date=TODAY)
    )
    follow_up = scheduler.mark_task_complete(groom)
    assert follow_up.due_date == TODAY + timedelta(days=7)


def test_completing_a_one_off_task_queues_nothing(household):
    """A 'once' task does not reappear after being completed."""
    owner, scheduler = household
    pet = owner.get_pet("Mochi")
    vet = pet.add_task(Task(description="Vet visit", time="11:00", frequency="once"))
    assert scheduler.mark_task_complete(vet) is None
    assert len(pet.tasks) == 1


def test_recurrence_does_not_compound(household):
    """Completing the generated copy adds exactly one more instance, not two."""
    owner, scheduler = household
    pet = owner.get_pet("Mochi")
    meds = pet.add_task(Task(description="Meds", time="07:35", frequency="daily"))
    tomorrows = scheduler.mark_task_complete(meds)
    scheduler.mark_task_complete(tomorrows)
    assert len(pet.tasks) == 3
    assert [t.due_date for t in pet.tasks] == [TODAY, TOMORROW, TODAY + timedelta(days=2)]


# -- conflict detection ----------------------------------------------------


def test_conflict_detected_for_identical_times(household):
    """Two tasks at the exact same time raise one warning, not an exception."""
    owner, scheduler = household
    owner.get_pet("Biscuit").add_task(Task(description="Walk", time="08:00", duration_minutes=30))
    owner.get_pet("Mochi").add_task(Task(description="Breakfast", time="08:00", duration_minutes=10))

    conflicts = scheduler.find_conflicts()

    assert len(conflicts) == 1
    assert "Walk" in conflicts[0] and "Breakfast" in conflicts[0]
    assert scheduler.has_conflicts() is True


def test_conflict_detected_for_partial_overlap(household):
    """An overlap that is not an exact time match still counts."""
    owner, scheduler = household
    pet = owner.get_pet("Mochi")
    pet.add_task(Task(description="Breakfast", time="07:30", duration_minutes=10))
    pet.add_task(Task(description="Meds", time="07:35", duration_minutes=5))
    assert len(scheduler.find_conflicts()) == 1


def test_back_to_back_tasks_do_not_conflict(household):
    """A task starting exactly when another ends is fine."""
    owner, scheduler = household
    pet = owner.get_pet("Biscuit")
    pet.add_task(Task(description="Walk", time="08:00", duration_minutes=30))
    pet.add_task(Task(description="Feed", time="08:30", duration_minutes=10))
    assert scheduler.find_conflicts() == []


def test_same_time_on_different_days_does_not_conflict(household):
    """Overlap is only checked within a single day."""
    owner, scheduler = household
    pet = owner.get_pet("Biscuit")
    pet.add_task(Task(description="Walk", time="08:00", due_date=TODAY))
    pet.add_task(Task(description="Walk", time="08:00", due_date=TOMORROW))
    assert scheduler.find_conflicts() == []


# -- daily planning --------------------------------------------------------


def test_daily_plan_respects_the_time_budget(household):
    """Low priority work is dropped once the budget runs out."""
    owner, scheduler = household
    pet = owner.get_pet("Biscuit")
    pet.add_task(Task(description="Walk", time="08:00", duration_minutes=45, priority="high"))
    pet.add_task(Task(description="Brush", time="20:00", duration_minutes=30, priority="low"))

    plan = scheduler.build_daily_plan(available_minutes=60)

    assert [t.description for t in plan["scheduled"]] == ["Walk"]
    assert [t.description for t in plan["skipped"]] == ["Brush"]
    assert plan["minutes_used"] == 45
    assert plan["minutes_left"] == 15
    assert len(plan["reasons"]) == 2


def test_daily_plan_is_returned_in_time_order(household):
    """The plan is chosen by priority but presented chronologically."""
    owner, scheduler = household
    pet = owner.get_pet("Mochi")
    pet.add_task(Task(description="Evening play", time="19:00", priority="high"))
    pet.add_task(Task(description="Breakfast", time="07:30", priority="medium"))
    plan = scheduler.build_daily_plan(available_minutes=120)
    assert [t.description for t in plan["scheduled"]] == ["Breakfast", "Evening play"]


def test_daily_plan_skips_completed_tasks(household):
    """Finished work does not eat into the remaining time budget."""
    owner, scheduler = household
    pet = owner.get_pet("Biscuit")
    done = pet.add_task(Task(description="Walk", time="08:00", duration_minutes=30))
    done.mark_complete()
    plan = scheduler.build_daily_plan(available_minutes=60)
    assert plan["scheduled"] == []
    assert plan["minutes_used"] == 0
