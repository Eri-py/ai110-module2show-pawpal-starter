# PawPal+ Project Reflection

## 0. System Design (three core user actions)

In plain language, a PawPal+ user should be able to:

1. **Add a pet** to the household, with its species and age.
2. **Schedule a care task** for a specific pet — what it is, when it starts, how long it
   takes, how urgent it is, and whether it repeats daily or weekly.
3. **See today's plan** — every task in time order, with warnings when two tasks clash,
   and a generated plan that fits the care time actually available today.

Marking a task complete (and having a recurring task reappear tomorrow) came out of
action 3 once I started writing the demo script.

---

## 1. System Design

**a. Initial design**

Four classes, drafted as Mermaid in `diagrams/uml_draft.mmd` before any code:

- **`Task`** — one care activity: description, start time (`"HH:MM"`), duration,
  priority, frequency, completion flag. Owns only its own state (`mark_complete()`,
  `next_occurrence()`).
- **`Pet`** — identity (name, species, age) plus the list of tasks that belong to it.
  The pet is the only place a task lives, which keeps ownership unambiguous.
- **`Owner`** — the household: name, the list of pets, and (added during
  implementation) how many minutes of care time they have per day. Provides lookups
  (`get_pet()`, `all_tasks()`).
- **`Scheduler`** — the brain. It holds a reference to an `Owner` and does all the
  cross-pet work: sorting, filtering, conflict detection, recurrence, daily planning.

The deliberate rule was that `Scheduler` stores **no task data of its own**. It always
reads through `owner.all_tasks()`, so there is exactly one source of truth and no
chance of the UI and the scheduler disagreeing about what exists.

**b. Design changes**

Three changes came out of implementation:

1. **`Task` gained a `due_date`.** The draft only had a time of day, which made
   recurrence impossible to express — "tomorrow's walk" and "today's walk" would have
   been indistinguishable. Adding `due_date: date` (defaulting to today) made
   `next_occurrence()` a one-line `due_date + timedelta(...)` and let the whole system
   answer "what's on for tomorrow?".
2. **`Task` gained `pet_name`, stamped by `Pet.add_task()`.** Conflict warnings and the
   UI table both need to say *whose* task is clashing, and walking back up from a task to
   its pet on every render was wasteful. `Owner.pet_for_task()` still exists as the
   authoritative lookup; `pet_name` is the display label.
3. **`Owner` gained `daily_minutes_available`.** The brief asks for a plan built against
   constraints, and time available is the owner's constraint, not the pet's or the task's,
   so it belongs on `Owner`. That is what made `build_daily_plan()` possible.

---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

`build_daily_plan()` considers, in order:

1. **Completion status** — finished tasks never consume budget.
2. **Priority** (high → medium → low) — the ranking that decides what survives a short
   day. Meds and walks beat coat brushing.
3. **Duration vs. remaining time budget** — `Owner.daily_minutes_available` is a hard
   cap; a task that does not fit is skipped and reported, not silently dropped.
4. **Time of day** — used for presentation order and for conflict detection, not for
   selection.

I ranked priority above time because the realistic failure mode for a busy owner is
running out of day, not running out of clock slots: when something has to give, it should
be the enrichment, never the medication. Time still matters for *reading* the plan, so the
planner chooses by priority and then presents chronologically.

**b. Tradeoffs**

- **Greedy, not optimal.** The planner takes tasks in priority order and keeps whatever
  fits in the remaining budget. That is not the best possible use of the minutes — a
  skipped 20-minute medium task may be followed by a kept 15-minute low task, which is
  exactly what happens in the sample output. A knapsack-style optimiser would pack
  better, but it would be harder to explain, and an explanation ("why is brushing in my
  plan and playtime out?") is worth more here than five reclaimed minutes.
- **Conflicts are detected but not resolved.** `find_conflicts()` returns warnings and the
  plan is still produced. A pet owner can judge whether two overlapping tasks are a real
  problem (meds while eating breakfast is fine; two walks is not) far better than my
  heuristic could.
- **Overlap is interval-based, but durations are assumed accurate.** I chose true interval
  overlap (`start < other_end and other_start < end`) over the simpler exact-time match,
  so a 07:30 breakfast and 07:35 meds are caught. The cost is that conflict quality now
  depends on the owner's duration estimates, and there is no notion of travel or
  transition time between tasks.
- **Pairwise conflict scan is O(n²) in the worst case**, with an early `break` once the
  sorted list passes the current task's end time. For a household's daily task list
  (tens of items) that is irrelevant, and the loop stays readable.

---

## 3. AI Collaboration

**a. How you used AI**

I built this with Claude Code (Opus) as a paired assistant, and kept the phases in
separate contexts so the design conversation didn't bleed into the algorithm work:

- **Design**: described the four classes in prose and had it produce the Mermaid class
  diagram and then the matching skeleton (dataclasses, empty method bodies). Fastest part
  of the project — the diagram and the stubs stayed in sync for free.
- **Implementation**: asked for the `Scheduler` methods one concern at a time (sorting,
  then filtering, then recurrence, then planning), which kept each method reviewable.
- **Tests**: the most valuable use. I asked for edge cases a pet scheduler would hit
  rather than tests for the code I had written, which is how the "back-to-back tasks must
  *not* conflict", "same time on different days must not conflict" and "recurrence must
  not compound" cases got in. Two of those three are the ones I'd most likely have broken
  later.
- **UI**: asked specifically how to keep an object alive across Streamlit reruns, which
  is what produced the `get_owner()` / `st.session_state` pattern instead of rebuilding
  the `Owner` on every click.

The prompts that worked best named the constraint rather than the code: "the scheduler
must not own task data, it reads through the Owner" produced better results than "write
a scheduler class".

**b. Judgment and verification**

Things I pushed back on:

- **Sorting by the raw time string.** The first suggestion was
  `sorted(tasks, key=lambda t: t.time)`, which is correct only as long as every time is
  zero-padded — `"9:00"` sorts *after* `"10:00"` alphabetically. I replaced it with a
  `parse_time()` helper that converts to minutes past midnight, and wrote
  `test_sort_by_time_handles_single_digit_hours` to pin the behaviour down.
- **Exact-match conflict detection.** The lightweight version compared start times for
  equality. Mochi's 07:30 breakfast and 07:35 meds would have passed clean, which is the
  single most likely real clash in the sample data, so I moved to interval overlap.
- **A `Plan` dataclass for `build_daily_plan()`.** Cleaner in principle, but the plan is
  consumed once by the UI and once by the CLI and never stored, so a dict with documented
  keys was less machinery for the same result. I kept the dict and documented the keys in
  the docstring — a judgment call I'd revisit if anything ever needed to persist a plan.

How I verified: `python main.py` after every behaviour (the CLI demo was built before the
UI precisely so I could see the logic working in plain text), `python -m pytest` after
every change, and a scripted run of the Streamlit app through `AppTest` to confirm the
page renders, the conflict warning appears, and *Generate plan* produces the metric and
reasoning without raising.

---

## 4. Testing and Verification

**a. What you tested**

20 tests in `tests/test_pawpal.py`, grouped by concern:

- **Core object behaviour** — `mark_complete()` flips status; `add_task()` grows the
  pet's list and stamps `pet_name`; `Owner.all_tasks()` spans pets.
- **Sorting** — chronological order from an out-of-order list; `"9:00"` before
  `"10:00"`; priority beating an earlier start time.
- **Filtering** — by pet, by completion status, by priority; unknown pet returns empty;
  today's schedule excludes other days.
- **Recurrence** — daily rolls to tomorrow, weekly to +7 days, `once` returns `None`, and
  completing a generated copy adds exactly one further instance (no compounding).
- **Conflicts** — identical times flagged; partial overlap flagged; back-to-back tasks
  not flagged; same time on different days not flagged.
- **Planning** — budget respected with the overflow reported as skipped; output in time
  order; completed tasks don't consume budget; empty household doesn't crash.

The negative tests matter most. Any sloppy overlap check will flag a real conflict; what
separates a useful warning from noise is *not* flagging an 08:00–08:30 walk against an
08:30 feed, and a scheduler that cries wolf gets ignored.

**b. Confidence**

★★★★☆ — four of five. The logic layer behaves under every case I tested, and the CLI
demo exercises the same paths end to end. What I would test next:

1. **Malformed input.** `parse_time()` trusts its input; `"25:00"`, `"7"` or `""` would
   raise or silently produce nonsense. The UI's `st.time_input` makes this hard to hit
   today, but JSON persistence or a CSV import would.
2. **Tasks crossing midnight.** A 23:30 task of 45 minutes gets `end_minutes = 1455`,
   which is past the end of the day; it will never conflict with a 00:10 task tomorrow.
3. **The UI layer itself.** My `AppTest` run was a manual smoke check, not a committed
   test. The filter/complete/rerun cycle deserves a real test.
4. **Duplicate recurrence.** Nothing stops a user adding two identical daily tasks, and
   each would then generate its own forward copies.

---

## 5. Reflection

**a. What went well**

Keeping `pawpal_system.py` free of any Streamlit import. Because the logic layer has no
UI dependency, `main.py` could drive it from the terminal, the tests could instantiate it
directly with no harness, and `app.py` ended up being almost entirely presentation —
collecting inputs and rendering what the `Scheduler` returned. The "CLI-first" order in
the instructions is what forced this, and it paid for itself: every bug I hit was visible
in plain text before the UI existed.

**b. What you would improve**

Persistence. Everything lives in `st.session_state`, so restarting the app wipes the
household — the one thing that stops this being genuinely usable. Next iteration:
`save_to_json`/`load_from_json` on `Owner`, with `Task.due_date` serialised as ISO
strings. Second on the list is making conflicts actionable — offering "move this task 30
minutes later" instead of only warning — which would need a "next free slot" search over
the day's occupied intervals.

**c. Key takeaway**

Deciding *where state lives* was the whole design, and it was the one decision no
assistant could make for me. Once I'd committed to "a task belongs to exactly one pet,
the scheduler owns nothing", every later question had an obvious answer — where does
recurrence attach the new task, what does the UI mutate, what do the tests construct. The
AI was fastest at the parts I could already specify precisely, and most useful where I
asked it to attack my assumptions (the edge-case test plan) rather than write code. My
job as the lead architect was holding the invariants and knowing which suggestions to
turn down: the string sort and the exact-time conflict check were both plausible, both
would have passed a casual read, and both were wrong for this system.
