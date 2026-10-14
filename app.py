"""PawPal+ Streamlit UI -- a thin shell over the Scheduler in pawpal_system.py."""

from datetime import date, timedelta

import streamlit as st

from pawpal_system import PRIORITIES, Owner, Pet, Scheduler, Task, format_time

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")


# --------------------------------------------------------------------------
# Session state: Streamlit reruns this file top to bottom on every click, so
# the Owner lives in st.session_state and is only built once per session.
# --------------------------------------------------------------------------
def get_owner() -> Owner:
    """Return the session's Owner, seeding a starter household on first run."""
    if "owner" not in st.session_state:
        owner = Owner(name="Jordan", daily_minutes_available=90)
        biscuit = owner.add_pet(Pet(name="Biscuit", species="dog", age=4))
        mochi = owner.add_pet(Pet(name="Mochi", species="cat", age=2))
        biscuit.add_task(
            Task(description="Morning walk", time="08:00", duration_minutes=30,
                 priority="high", frequency="daily")
        )
        biscuit.add_task(
            Task(description="Evening walk", time="18:30", duration_minutes=30,
                 priority="medium", frequency="daily")
        )
        mochi.add_task(
            Task(description="Breakfast", time="07:30", duration_minutes=10,
                 priority="high", frequency="daily")
        )
        mochi.add_task(
            Task(description="Thyroid meds", time="07:35", duration_minutes=5,
                 priority="high", frequency="daily")
        )
        st.session_state.owner = owner
    return st.session_state.owner


owner = get_owner()
scheduler = Scheduler(owner)

PRIORITY_ICON = {"high": "🔴", "medium": "🟠", "low": "🟢"}


def task_rows(tasks: list[Task]) -> list[dict]:
    """Turn Task objects into table rows for st.table/st.dataframe."""
    return [
        {
            "Time": f"{task.time}-{format_time(task.end_minutes)}",
            "Pet": task.pet_name,
            "Task": task.description,
            "Min": task.duration_minutes,
            "Priority": f"{PRIORITY_ICON.get(task.priority, '')} {task.priority}",
            "Repeats": task.frequency,
            "Done": "✅" if task.completed else "⬜",
        }
        for task in tasks
    ]


# --------------------------------------------------------------------------
# Sidebar: owner details and pet management
# --------------------------------------------------------------------------
with st.sidebar:
    st.header("🏠 Household")
    owner.name = st.text_input("Owner name", value=owner.name)
    owner.daily_minutes_available = st.slider(
        "Care time available today (min)", 15, 480, owner.daily_minutes_available, step=15
    )

    st.subheader("Add a pet")
    with st.form("add_pet", clear_on_submit=True):
        new_pet_name = st.text_input("Pet name")
        new_species = st.selectbox("Species", ["dog", "cat", "other"])
        new_age = st.number_input("Age (years)", min_value=0, max_value=30, value=1)
        if st.form_submit_button("Add pet"):
            if not new_pet_name.strip():
                st.warning("Give the pet a name first.")
            elif owner.get_pet(new_pet_name):
                st.warning(f"{new_pet_name} is already in the household.")
            else:
                owner.add_pet(Pet(name=new_pet_name.strip(), species=new_species, age=int(new_age)))
                st.success(f"Added {new_pet_name.strip()}.")

    st.subheader("Pets")
    for pet in owner.pets:
        st.write(f"- {pet} — {len(pet.pending_tasks())} pending today")


st.title("🐾 PawPal+")
st.caption(f"Pet care planning for {owner.name} — {date.today():%A %d %B %Y}")

if not owner.pets:
    st.info("Add a pet in the sidebar to get started.")
    st.stop()


# --------------------------------------------------------------------------
# Add a task
# --------------------------------------------------------------------------
st.subheader("➕ Schedule a task")
with st.form("add_task", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        pet_choice = st.selectbox("Pet", [pet.name for pet in owner.pets])
        description = st.text_input("Task", value="")
        due = st.date_input("Date", value=date.today())
    with col2:
        task_time = st.time_input("Start time", value=None)
        duration = st.number_input("Duration (minutes)", min_value=1, max_value=240, value=20)
        priority = st.selectbox("Priority", list(PRIORITIES))
    frequency = st.radio("Repeats", ["once", "daily", "weekly"], horizontal=True)

    if st.form_submit_button("Add task"):
        if not description.strip():
            st.warning("Describe the task first.")
        elif task_time is None:
            st.warning("Pick a start time.")
        else:
            task = Task(
                description=description.strip(),
                time=task_time.strftime("%H:%M"),
                duration_minutes=int(duration),
                priority=priority,
                frequency=frequency,
                due_date=due,
            )
            owner.get_pet(pet_choice).add_task(task)
            clash = scheduler.find_conflicts(scheduler.tasks_for_date(due))
            st.success(f"Added '{task.description}' for {pet_choice} at {task.time}.")
            for warning in clash:
                st.warning(f"⚠️ {warning}")

st.divider()


# --------------------------------------------------------------------------
# Today's schedule: sorted, filterable, completable
# --------------------------------------------------------------------------
st.subheader("📅 Schedule")
view_col, pet_col, status_col = st.columns(3)
with view_col:
    day_label = st.selectbox("Day", ["Today", "Tomorrow"])
with pet_col:
    pet_filter = st.selectbox("Pet", ["All pets"] + [pet.name for pet in owner.pets])
with status_col:
    status_filter = st.selectbox("Status", ["All", "Pending", "Completed"])

view_day = date.today() if day_label == "Today" else date.today() + timedelta(days=1)
completed_filter = {"All": None, "Pending": False, "Completed": True}[status_filter]
visible = scheduler.filter_tasks(
    scheduler.tasks_for_date(view_day),
    pet_name=None if pet_filter == "All pets" else pet_filter,
    completed=completed_filter,
)

conflicts = scheduler.find_conflicts(scheduler.tasks_for_date(view_day))
if conflicts:
    for warning in conflicts:
        st.warning(f"⚠️ {warning}")
else:
    st.success("✅ No scheduling conflicts for this day.")

if visible:
    st.table(task_rows(visible))
else:
    st.info("Nothing matches these filters.")

pending = [task for task in visible if not task.completed]
if pending:
    st.markdown("**Mark a task complete** (recurring tasks reappear on their next date)")
    labels = {f"{t.time} — {t.pet_name}: {t.description}": t for t in pending}
    done_label = st.selectbox("Task", list(labels))
    if st.button("Mark complete ✅"):
        follow_up = scheduler.mark_task_complete(labels[done_label])
        st.success(f"Completed '{labels[done_label].description}'.")
        if follow_up:
            st.info(
                f"🔁 Next '{follow_up.description}' queued for "
                f"{follow_up.due_date:%a %d %b} at {follow_up.time}."
            )
        st.rerun()

st.divider()


# --------------------------------------------------------------------------
# Daily plan: priority-first packing into the owner's time budget
# --------------------------------------------------------------------------
st.subheader("🧠 Generate daily plan")
st.caption(
    "Picks the highest-priority pending tasks that fit today's care-time budget, "
    "then shows them in time order with the reasoning behind each choice."
)

if st.button("Generate plan"):
    plan = scheduler.build_daily_plan(day=view_day)
    used, budget = plan["minutes_used"], plan["available_minutes"]
    st.metric("Care time used", f"{used} / {budget} min", f"{plan['minutes_left']} min spare")
    st.progress(min(used / budget, 1.0) if budget else 0.0)

    if plan["scheduled"]:
        st.table(task_rows(plan["scheduled"]))
    else:
        st.info("Nothing left to schedule for this day.")

    if plan["skipped"]:
        st.warning("These tasks did not fit the time budget:")
        st.table(task_rows(plan["skipped"]))

    for warning in plan["conflicts"]:
        st.warning(f"⚠️ {warning}")

    with st.expander("Why this plan?", expanded=True):
        for reason in plan["reasons"]:
            st.write(f"- {reason}")
