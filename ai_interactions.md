# AI Interactions Log

> Log of the AI-assisted work on PawPal+, including the stretch features
> (free-slot search, persistence, priority scheduling, output formatting, and a
> two-model comparison).

---

## Agent Workflow (SF7)

> Two agent runs are logged: the core algorithmic layer (Phase 4) and the stretch
> features.

### Run 1 — algorithmic layer (Phase 4)

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

### Run 2 — stretch features (free slot, persistence, formatting)

**What task did you give the agent?**

"Add three things: (1) a next-available-slot search that merges the day's busy intervals
and turns each conflict warning into a concrete 'move it to HH:MM' suggestion; (2) JSON
persistence so the household survives a restart, wired into the Streamlit UI with
autosave; (3) nicer output — `tabulate` tables and priority/status icons in the CLI,
matching icons in the UI. Keep `pawpal_system.py` free of Streamlit imports, and add
tests for all of it."

**What did the agent do?**

Files modified:

- `pawpal_system.py` — `DATA_FILE`; `to_dict()` / `from_dict()` on `Task`, `Pet` and
  `Owner`; `Owner.save_to_json()` / `load_from_json()`; `Scheduler.busy_intervals()`,
  `next_free_slot()`, `suggest_reschedule()`, `resolve_conflicts()`; an `after` argument
  on `Task.next_occurrence()` and a `catch_up` argument on
  `Scheduler.mark_task_complete()` (see the model comparison below).
- `app.py` — load from `data.json` at session start, `autosave()` after every mutation,
  sidebar *Saved data* controls (autosave checkbox, *Save now*, *Reload*, provenance
  caption), 💡 reschedule suggestions under conflict warnings, and a *Find a free slot*
  panel.
- `main.py` — `tabulate` tables with 🔴/🟠/🟢 and ✅/⬜ icons, a late high-priority task so
  priority sorting visibly differs from time sorting, a stale-task catch-up demo, and a
  closing save/reload round trip.
- `requirements.txt` — added `tabulate>=0.9`.
- `tests/test_pawpal.py` — 15 further tests (interval merging, free-slot search,
  reschedule suggestions, stale catch-up for daily and weekly, clock-independence of the
  default, save/load round trip, missing file).

Commands run: `python main.py`, `python -m pytest` (35 passed), `python -m py_compile`,
and an `AppTest` run of `app.py` in both states — with and without `data.json` present.

**What did you have to verify or fix manually?**

- **Reschedule direction.** The first `suggest_reschedule()` searched the whole day from
  `earliest="07:00"`, so its advice for a 07:35 clash was "move it to 07:00" — technically
  free, useless as advice. Changed the search to start at the task's own time, which turns
  the same case into "move it to 07:40".
- **Console encoding.** `tabulate`'s box-drawing borders and the emoji icons crashed
  `python main.py` outright on Windows (`UnicodeEncodeError`, cp1252). Added
  `sys.stdout.reconfigure(encoding="utf-8", errors="replace")`, and a plain-text fallback
  in `task_table()` for when `tabulate` is not installed.
- **A missing import** (`format_time` in `main.py`) and a first draft of `task_table()`
  that recomputed the end time by hand instead of reusing `Task.end_minutes`.
- **Pet lookup after a load.** Worth checking that `from_dict()` goes through
  `Pet.add_task()` rather than assigning the list directly, so `pet_name` is re-stamped
  and `Scheduler` still works on a reloaded household — there is now a test for exactly
  that.

---

## Prompt Comparison (SF11)

**The task both models were given:** make recurring-task rescheduling handle *stale*
tasks. If the app is not opened for weeks, a daily or weekly task's `due_date` can be
several periods in the past, and completing it should produce the next occurrence
strictly in the future — preserving the weekday for weekly tasks — without looping once
per missed period. Both were given the same `Task` dataclass and the existing
`next_occurrence()`.

| | Option A | Option B |
|-|----------|----------|
| **Model / tool used** | Claude Opus 5 (Claude Code, main session) | Claude Haiku 4.5 (Claude Code subagent, no repo access) |
| **Prompt** | Same spec as Option B, asked in the context of the live repo | Same spec, pasted as a self-contained snippet with the `Task` dataclass |
| **Response summary** | Add an optional `after: date \| None` argument to `next_occurrence()`: `due = due_date + step`, and if `after` is given and `due <= after`, advance by `((after - due) // step + 1) * step`. Caller (`mark_task_complete(catch_up=True)`) decides whether to pass `date.today()`. | Rewrite `next_occurrence()` to call `date.today()` internally: step once, then if the result is still past, branch on frequency and add `(today - due).days + 1` days for daily or `(today - due).days // 7 + 1` weeks for weekly. |
| **What was useful** | Keeps the method pure — the default result does not depend on the clock, so tests can assert exact dates. One arithmetic expression covers both frequencies. | The catch-up idea itself, which I had not implemented at all, and the insight that whole-period arithmetic preserves the weekday "for free". Correctly identified that the comparison must be `<= today`, not `< today`, to avoid landing on today. |
| **Problems noticed** | Needs a second argument threaded through the caller — slightly more API surface, and a caller that forgets `after` silently gets the old behaviour. | Reads `date.today()` inside the method, which makes every result clock-dependent and the unit tests time-sensitive. Duplicates the `"once"` check (`frequency == "once"` *and* `step is None`). Branches per frequency where one `timedelta // timedelta` division handles both. Its explanation claimed Python "handles DST automatically" — irrelevant here, since `date` arithmetic has no DST at all, and a sign that the justification was partly boilerplate. |
| **Decision** | **Shipped, merged with B's idea.** | Idea adopted, implementation not. |

**Which approach did you use in your final implementation and why?**

A merge, and the comparison is what produced it. Haiku found a real gap in my version —
a one-step roll-forward puts a month-stale weekly task back in the past, where it stays
invisible. But its fix buried `date.today()` inside a dataclass method, which would have
made `next_occurrence()` untestable without freezing the clock. The shipped version keeps
Haiku's whole-period arithmetic (generalised to `((after - due) // step + 1) * step`, so
one line serves daily and weekly) while leaving the clock read to the caller:
`Task.next_occurrence()` stays pure, `Scheduler.mark_task_complete(catch_up=True)` passes
`date.today()` by default, and `catch_up=False` recovers the old behaviour.

Four tests pin this down: stale weekly keeps its weekday and lands within the next seven
days, stale daily resumes tomorrow, `catch_up=False` advances exactly one step, and
`next_occurrence()` with no argument returns `2020-01-08` for a task dated `2020-01-01` —
i.e. provably clock-independent.
