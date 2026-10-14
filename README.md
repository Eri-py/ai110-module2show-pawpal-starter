# PawPal+ (Module 2 Project)

**PawPal+** is a Streamlit app that helps a busy pet owner plan care tasks for their
pets. You enter the household (owner, pets, how much care time you have today) and the
tasks each pet needs, and PawPal+ produces a sorted daily schedule, warns about
clashing tasks, rolls recurring tasks forward when you complete them, and packs the
highest-priority work into the time you actually have — explaining each choice.

## Architecture

| File | Role |
|------|------|
| `pawpal_system.py` | Logic layer: `Task`, `Pet`, `Owner`, `Scheduler`. No Streamlit imports. |
| `main.py` | CLI demo that exercises every scheduler behaviour in the terminal. |
| `app.py` | Streamlit UI. Keeps one `Owner` in `st.session_state` and calls the `Scheduler`. |
| `tests/test_pawpal.py` | 20 `pytest` tests over the logic layer. |
| `diagrams/uml_draft.mmd` | Phase 1 design sketch. |
| `diagrams/uml_final.mmd` | Final UML, matching the shipped code. |

`Owner` has many `Pet`s, each `Pet` owns its `Task`s, and `Scheduler` is a thin brain
that reads tasks through the `Owner` rather than storing any of its own.

## Features

- **Time-sorted schedules** — `Scheduler.sort_by_time()` parses `"HH:MM"` into minutes
  past midnight and sorts on `(due_date, start_minutes)`, so `"9:00"` still sorts before
  `"10:00"` (plain string sorting would not).
- **Priority ordering** — `Scheduler.sort_by_priority()` orders high → medium → low,
  breaking ties chronologically.
- **Filtering** — `Scheduler.filter_tasks()` narrows by pet, completion status, priority
  and date; each argument is optional, so `None` means "don't filter on this".
- **Conflict warnings** — `Scheduler.find_conflicts()` returns a human-readable warning
  per overlapping pair (same pet or different pets) instead of raising.
- **Recurring tasks** — `Scheduler.mark_task_complete()` completes a task and, if its
  frequency is `daily` or `weekly`, uses `Task.next_occurrence()` to queue a fresh copy
  one day / one week later via `timedelta`.
- **Constraint-aware daily plan** — `Scheduler.build_daily_plan()` greedily packs the
  day's pending tasks into the owner's `daily_minutes_available`, highest priority first,
  returns them in time order, and includes a `reasons` list explaining every keep/skip.

## Getting started

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Run

```bash
streamlit run app.py   # the UI
python main.py         # the CLI demo
python -m pytest       # the tests
```

## 🖥️ Sample Output

Terminal output from `python main.py` (sample household: Jordan, with Biscuit the dog
and Mochi the cat, and a 60-minute care budget):

```
PawPal+ demo for Jordan -- Tuesday 13 October 2026
Pets: Biscuit (dog, 4y), Mochi (cat, 2y)
Care time available today: 60 min

Today's Schedule (sorted by time)
=================================
  [ ] 07:30-07:40  Breakfast (Mochi) [10 min, high, daily]
  [ ] 07:35-07:40  Thyroid meds (Mochi) [5 min, high, daily]
  [ ] 08:00-08:30  Morning walk (Biscuit) [30 min, high, daily]
  [ ] 18:30-19:00  Evening walk (Biscuit) [30 min, medium, daily]
  [ ] 19:00-19:20  Play session (Mochi) [20 min, medium]
  [ ] 20:00-20:15  Brush coat (Biscuit) [15 min, low, weekly]

Filtered -- Mochi only
  [ ] 07:30-07:40  Breakfast (Mochi) [10 min, high, daily]
  [ ] 07:35-07:40  Thyroid meds (Mochi) [5 min, high, daily]
  [ ] 19:00-19:20  Play session (Mochi) [20 min, medium]

Conflict check
  WARNING: Conflict for Mochi on 2026-10-13: 'Breakfast' (07:30-07:40) overlaps 'Thyroid meds' (07:35-07:40).

Recurrence
  Completed: [x] 08:00-08:30  Morning walk (Biscuit) [30 min, high, daily]
  Queued next: [ ] 08:00-08:30  Morning walk (Biscuit) [30 min, high, daily]  (due 2026-10-14)

Pending after completion
  [ ] 07:30-07:40  Breakfast (Mochi) [10 min, high, daily]
  [ ] 07:35-07:40  Thyroid meds (Mochi) [5 min, high, daily]
  [ ] 18:30-19:00  Evening walk (Biscuit) [30 min, medium, daily]
  [ ] 19:00-19:20  Play session (Mochi) [20 min, medium]
  [ ] 20:00-20:15  Brush coat (Biscuit) [15 min, low, weekly]

Tomorrow's Schedule
====================
  [ ] 08:00-08:30  Morning walk (Biscuit) [30 min, high, daily]

Daily plan (60/60 min used)
  [ ] 07:30-07:40  Breakfast (Mochi) [10 min, high, daily]
  [ ] 07:35-07:40  Thyroid meds (Mochi) [5 min, high, daily]
  [ ] 18:30-19:00  Evening walk (Biscuit) [30 min, medium, daily]
  [ ] 20:00-20:15  Brush coat (Biscuit) [15 min, low, weekly]
  Did not fit:
    [ ] 19:00-19:20  Play session (Mochi) [20 min, medium]
  Reasoning:
    - Kept 'Breakfast' for Mochi at 07:30: high priority, 10 min (50 of 60 min left).
    - Kept 'Thyroid meds' for Mochi at 07:35: high priority, 5 min (45 of 60 min left).
    - Kept 'Evening walk' for Biscuit at 18:30: medium priority, 30 min (15 of 60 min left).
    - Skipped 'Play session' for Mochi: needs 20 min but only 15 min of the 60 min budget remain.
    - Kept 'Brush coat' for Biscuit at 20:00: low priority, 15 min (0 of 60 min left).
  Conflicts inside the plan:
    - Conflict for Mochi on 2026-10-13: 'Breakfast' (07:30-07:40) overlaps 'Thyroid meds' (07:35-07:40).
```

(The morning walk is absent from the plan because the demo completes it first — the
planner only spends time on tasks that are still pending.)

## 🧪 Testing PawPal+

```bash
# Run the full test suite:
python -m pytest
```

The suite covers: task completion and task-count growth; chronological sorting
(including `"9:00"` vs `"10:00"`); priority sorting; filtering by pet, status and
priority; today-only schedules; daily and weekly recurrence (and that recurrence does
not compound); one-off tasks not reappearing; conflicts at identical times and at
partial overlaps; back-to-back tasks *not* conflicting; same clock time on different
days not conflicting; a pet with no tasks; and the daily planner respecting the time
budget, skipping completed work, and returning results in time order.

Sample test output:

```
============================= test session starts =============================
platform win32 -- Python 3.12.13, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\eriol\Desktop\Projects\Foundations Of AI Engineering\ai110-module2show-pawpal-starter
plugins: anyio-4.15.1
collected 20 items

tests\test_pawpal.py ....................                                [100%]

============================= 20 passed in 0.01s ==============================
```

**Confidence level: ★★★★☆ (4/5).** The scheduling, recurrence and conflict paths are
covered by tests on both the happy path and the edge cases I could think of. The point
off is for what is not covered: malformed time strings (`"7"`, `"25:00"`) are not
validated, the UI layer itself has no automated tests, and nothing is persisted between
runs, so a Streamlit session restart loses the household.

## 📐 Smarter Scheduling

| Feature | Method(s) | Notes |
|---------|-----------|-------|
| Task sorting | `Scheduler.sort_by_time()`, `Scheduler.sort_by_priority()` | `sorted()` with a key that parses `"HH:MM"` into minutes, so sorting is numeric, not alphabetic. Priority sort uses a `PRIORITY_ORDER` weight map and falls back to time. |
| Filtering | `Scheduler.filter_tasks()`, `Scheduler.todays_schedule()`, `Pet.pending_tasks()` | Filters by pet, completion status, priority and date; each is optional and `None` means "ignore this filter". |
| Conflict handling | `Scheduler.find_conflicts()`, `Scheduler.has_conflicts()`, `Task.overlaps()` | Interval overlap (`start < other_end and other_start < end`) on same-day tasks, so partial overlaps count and back-to-back tasks don't. Returns warning strings; never raises. |
| Recurring tasks | `Task.next_occurrence()`, `Task.is_recurring`, `Scheduler.mark_task_complete()` | Completing a `daily`/`weekly` task clones it forward by `timedelta(days=1)` / `timedelta(weeks=1)` and attaches the copy to the same pet. `once` tasks return `None`. |
| Time-budget planning | `Scheduler.build_daily_plan()` | Greedy priority-first packing into `Owner.daily_minutes_available`, returning scheduled/skipped tasks, minutes used/left, conflicts and a per-task `reasons` explanation. |

## 📸 Demo Walkthrough

The app opens with a seeded household (Jordan, Biscuit the dog, Mochi the cat) so there
is something to look at immediately.

1. **Set up the household (sidebar).** Edit the owner name, drag the *Care time available
   today* slider (15–480 min — this is the constraint the planner packs against), and add
   a pet with the *Add a pet* form. Duplicate and blank names are rejected with a warning.
   Each pet is listed with its pending-task count.
2. **Schedule a task.** Pick the pet, type a description, choose the date, start time,
   duration, priority (high/medium/low) and whether it repeats (once/daily/weekly), then
   submit. The UI calls `Pet.add_task()` and immediately re-runs `find_conflicts()` for
   that day, so if the new task lands on top of an existing one you get a
   `⚠️ Conflict for Mochi …` warning right under the form.
3. **Read the schedule.** The *Schedule* section shows the day's tasks through
   `Scheduler.tasks_for_date()` — always in time order — as an `st.table` with a
   priority dot (🔴/🟠/🟢) and a done box. Three dropdowns filter the view by day
   (today/tomorrow), pet and status (all/pending/completed) via
   `Scheduler.filter_tasks()`. Above the table, conflicts appear as `st.warning` lines, or
   a green `✅ No scheduling conflicts for this day.` when there are none.
4. **Complete a task.** Pick a pending task and press *Mark complete ✅*. The UI calls
   `Scheduler.mark_task_complete()`; the row flips to ✅, and for a recurring task an
   `st.info` box reports the copy that was queued (`🔁 Next 'Morning walk' queued for
   Wed 14 Oct at 08:00`) — switch the day filter to *Tomorrow* to see it waiting there.
5. **Generate the daily plan.** Press *Generate plan*. `build_daily_plan()` fills the time
   budget highest-priority-first; the UI shows an `st.metric` + progress bar for minutes
   used, the kept tasks in time order, a warning table of tasks that did not fit, any
   conflicts inside the plan, and a *Why this plan?* expander listing one reasoning line
   per task ("Skipped 'Play session' for Mochi: needs 20 min but only 15 min … remain").
6. **State persists across clicks.** The `Owner` lives in `st.session_state`, so pets and
   tasks survive every rerun — but not a restart of the app (see Confidence level above).

Sample CLI output from `python main.py` is in the [Sample Output](#-sample-output)
section above.

**Screenshot or video** *(optional)*: not included — the walkthrough above and the CLI
output are the demo of record.
