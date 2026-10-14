# AI Interactions Log

> **Stretch features only.** Only the sections that apply are filled in. I did not attempt
> the prompt-comparison stretch feature, so that section is omitted.

---

## Agent Workflow (SF7)

> Documenting the agent run used for the algorithmic layer (Phase 4), which touched
> several files at once.

**What task did you give the agent?**

"Add the algorithmic layer: sort tasks by time and by priority, filter by pet / status /
priority / date, make completing a `daily` or `weekly` task queue its next occurrence,
detect overlapping tasks as warning strings rather than exceptions, and pack the day's
pending tasks into the owner's time budget with an explanation per task. Then update the
CLI demo so each behaviour is visible in the terminal, including two tasks that overlap
and one task that does not fit the budget."

**What did the agent do?**

Files modified:

- `pawpal_system.py` — added `parse_time()` / `format_time()` helpers,
  `Task.start_minutes` / `end_minutes` / `is_recurring` / `next_occurrence()` /
  `overlaps()`, `Pet.tasks_for_date()` / `pending_tasks()`, `Owner.pet_for_task()`, and
  the `Scheduler` methods `sort_by_time`, `sort_by_priority`, `filter_tasks`,
  `tasks_for_date`, `todays_schedule`, `mark_task_complete`, `find_conflicts`,
  `has_conflicts`, `build_daily_plan`, `format_schedule`. Added `due_date` and `pet_name`
  fields to `Task` and `daily_minutes_available` to `Owner` (the recurrence and budget
  work needed both).
- `main.py` — demo household with tasks deliberately added out of chronological order,
  plus prints for each behaviour: sorted schedule, Mochi-only filter, conflict check,
  completion + queued next occurrence, tomorrow's schedule, and the daily plan with its
  reasoning lines.
- `tests/test_pawpal.py` — tests for each new method.
- `app.py` — the new `Scheduler` methods wired into the UI.

Commands run: `python main.py` and `python -m pytest` after each increment, plus a
`streamlit.testing.v1.AppTest` script to confirm `app.py` renders without raising.

**What did you have to verify or fix manually?**

- **Sorting key.** The first version sorted on the raw `"HH:MM"` string, which breaks on
  a non-zero-padded time (`"9:00"` > `"10:00"`). Replaced with a `parse_time()` key and
  added a regression test.
- **Conflict detection.** The first version compared start times for equality only, so
  Mochi's 07:30 breakfast and 07:35 meds came back clean. Rewrote as interval overlap and
  added both a partial-overlap test and a back-to-back *non*-conflict test.
- **Recurrence attachment.** `mark_task_complete()` initially returned the new `Task`
  without attaching it to the pet, so tomorrow's walk existed but was in nobody's list.
  Fixed to resolve the owning pet (`Owner.pet_for_task()`, falling back to the
  `pet_name` stamp) and `add_task()` the copy.
- **Demo realism.** The first demo had a 90-minute budget and an 80-minute task list, so
  nothing was ever skipped and the budget constraint was invisible. Dropped the budget to
  60 minutes so the output actually demonstrates a skip.
- **A stray syntax slip** in `app.py` (`st.form_submit_button("Add pet") :`) that
  `py_compile` caught.
