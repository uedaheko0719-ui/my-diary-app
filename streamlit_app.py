from __future__ import annotations

import calendar
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st


NOTES_DIR = Path("notes")
NOTES_DIR.mkdir(exist_ok=True)

SECTION_NOTE = "文字笔记"
SECTION_DIET = "饮食规划"
SECTION_UI = "界面设置"
SECTION_TIME = "时间表"


def app_now() -> datetime:
    return datetime.now(ZoneInfo(st.session_state.get("tz", "Asia/Shanghai")))


def note_path(day: date) -> Path:
    return NOTES_DIR / f"{day:%Y-%m-%d}.txt"


def month_plan_path(year: int, month: int) -> Path:
    return NOTES_DIR / f"{year:04d}-{month:02d}-long_plan.json"


def read_sections(path: Path) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    if not path.exists():
        return sections

    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.rstrip("\n")
        if line.startswith("【") and line.endswith("】"):
            current = line[1:-1]
            sections.setdefault(current, [])
        elif current is not None:
            sections.setdefault(current, []).append(line)
    return sections


def read_day(day: date):
    sections = read_sections(note_path(day))
    note = "\n".join(sections.get(SECTION_NOTE, [])).strip()
    diet = "\n".join(sections.get(SECTION_DIET, [])).strip()
    time_map: dict[str, str] = {}
    ui: dict[str, str] = {}

    for line in sections.get(SECTION_TIME, []):
        if "::" in line:
            slot, text = line.split("::", 1)
            time_map[slot] = text

    for line in sections.get(SECTION_UI, []):
        if "::" in line:
            key, value = line.split("::", 1)
            ui[key.strip()] = value.strip()

    extras = {
        key: value
        for key, value in sections.items()
        if key not in {SECTION_NOTE, SECTION_DIET, SECTION_TIME, SECTION_UI}
    }
    return note, diet, time_map, ui, extras


def write_day(
    day: date,
    note: str,
    diet: str,
    time_map: dict[str, str],
    ui: dict[str, str] | None = None,
    extras: dict[str, list[str]] | None = None,
):
    ui = ui or {}
    extras = extras or {}
    lines = [
        f"【{SECTION_NOTE}】",
        note.strip(),
        "",
        f"【{SECTION_DIET}】",
        diet.strip(),
        "",
        f"【{SECTION_UI}】",
    ]
    lines.extend(f"{key}::{value}" for key, value in ui.items() if str(value).strip())
    lines.extend(["", f"【{SECTION_TIME}】"])
    for slot, text in time_map.items():
        if str(text).strip():
            lines.append(f"{slot}::{str(text).strip()}")

    for name, extra_lines in extras.items():
        lines.extend(["", f"【{name}】"])
        lines.extend(str(item).rstrip("\n") for item in extra_lines)

    note_path(day).write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def natural_time(hour: int) -> str:
    hour %= 24
    if hour == 0:
        return "12:00 AM"
    if hour < 12:
        return f"{hour}:00 AM"
    if hour == 12:
        return "12:00 PM"
    return f"{hour - 12}:00 PM"


def time_slots() -> list[str]:
    return [f"{natural_time(7 + i)} - {natural_time(8 + i)}" for i in range(24)]


def load_month_plan(year: int, month: int) -> list[dict]:
    path = month_plan_path(year, month)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_month_plan(year: int, month: int, blocks: list[dict]):
    month_plan_path(year, month).write_text(
        json.dumps(blocks, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def add_token(amount: float):
    st.session_state.token = min(1.0, max(0.0, st.session_state.get("token", 0.0) + amount))
    st.session_state.battery_flash = True


def save_token_to_day(day: date):
    note, diet, time_map, ui, extras = read_day(day)
    ui["TOKEN_LEVEL"] = f"{st.session_state.get('token', 0.0) * 16:.4f}"
    write_day(day, note, diet, time_map, ui, extras)


def sync_long_plan(year: int, month: int, blocks: list[dict]):
    slots = time_slots()
    last_day = calendar.monthrange(year, month)[1]
    for block in blocks:
        text = str(block.get("text", "")).strip()
        if not text:
            continue
        start = max(1, min(last_day, int(block.get("day", 1))))
        span = max(1, int(block.get("span", 1)))
        hour = max(0, min(23, int(block.get("hour", 22))))
        slot = slots[(hour - 7) % 24]

        for day_num in range(start, min(last_day, start + span - 1) + 1):
            current = date(year, month, day_num)
            note, diet, time_map, ui, extras = read_day(current)
            existing = time_map.get(slot, "").strip()
            parts = [item.strip() for item in existing.split("\n") if item.strip()]
            if text not in parts:
                parts.append(text)
            time_map[slot] = "\n".join(parts)
            write_day(current, note, diet, time_map, ui, extras)


def init_state():
    today = app_now().date()
    defaults = {
        "selected_day": today,
        "view_year": today.year,
        "view_month": today.month,
        "tz": "Asia/Shanghai",
        "token": 0.0,
        "battery_flash": False,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)

    if "token_loaded" not in st.session_state:
        _note, _diet, _time, ui, _extras = read_day(st.session_state.selected_day)
        try:
            st.session_state.token = min(1.0, float(ui.get("TOKEN_LEVEL", "0")) / 16.0)
        except ValueError:
            st.session_state.token = 0.0
        st.session_state.token_loaded = True


def render_css():
    flash = " battery-flash" if st.session_state.get("battery_flash") else ""
    st.markdown(
        f"""
        <style>
          :root {{
            --paper:#f8f3e7;
            --ink:#253027;
            --muted:#6f756f;
            --line:#ddd2bf;
            --accent:#278b57;
            --danger:#c94a3a;
          }}
          .stApp {{ background:var(--paper); color:var(--ink); }}
          .block-container {{ padding-top:1rem; max-width:1320px; }}
          button[kind="secondary"], .stButton>button {{
            border-radius:6px !important;
            border:1px solid var(--line) !important;
            background:#fffaf0 !important;
            transition:transform .12s ease, border-color .12s ease, background .12s ease;
          }}
          button[kind="secondary"]:hover, .stButton>button:hover {{
            transform:translateY(-1px);
            border-color:#9fbca9 !important;
            background:#ffffff !important;
          }}
          .browser-bar {{
            display:flex; align-items:center; justify-content:space-between;
            gap:16px; border-bottom:1px solid var(--line); padding:4px 0 12px;
            margin-bottom:10px;
          }}
          .app-title {{ font-size:28px; font-weight:700; letter-spacing:0; }}
          .battery-wrap {{ display:flex; align-items:center; gap:8px; justify-content:flex-end; }}
          .battery {{
            width:150px; height:24px; padding:3px; border:2px solid #28352c;
            background:#fff; position:relative; border-radius:4px;
          }}
          .battery:after {{
            content:""; position:absolute; width:7px; height:12px; right:-10px; top:4px;
            border:2px solid #28352c; border-left:0; border-radius:0 3px 3px 0;
          }}
          .battery-fill {{
            height:100%; width:{int(st.session_state.get("token", 0.0) * 100)}%;
            background:#38b86f; border-radius:2px; transition:width .16s ease;
          }}
          .battery-flash .battery-fill {{ animation:batteryPulse .28s ease; }}
          @keyframes batteryPulse {{
            0% {{ filter:brightness(1); }}
            50% {{ filter:brightness(1.8); }}
            100% {{ filter:brightness(1); }}
          }}
          .battery-label {{ font-size:12px; font-weight:700; color:#304137; min-width:72px; }}
          .day-card {{
            background:#fffaf0; border:1px solid var(--line); border-radius:8px;
            padding:12px; min-height:92px;
          }}
          .day-card.today {{ border-left:5px solid var(--danger); }}
          .now-row {{
            border-left:5px solid var(--danger); padding-left:10px;
            background:#fffdf7; border-radius:5px;
          }}
          .history-card {{
            background:#fffaf0; border:1px solid var(--line); border-radius:8px;
            padding:12px; margin:8px 0;
          }}
          .plan-block {{
            background:#e9f5eb; border-left:5px solid #38b86f;
            padding:10px 12px; border-radius:7px; margin:7px 0;
          }}
          .small-muted {{ color:var(--muted); font-size:13px; }}
          textarea {{ border-radius:7px !important; }}
        </style>
        <div class="browser-bar">
          <div class="app-title">My Diary</div>
          <div class="battery-wrap{flash}">
            <div class="battery"><div class="battery-fill"></div></div>
            <div class="battery-label">TOKEN {int(st.session_state.get("token", 0.0) * 100)}%</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.session_state.battery_flash = False


def render_month():
    c1, c2, c3 = st.columns([1, 3, 1])
    with c1:
        if st.button("Previous Month", use_container_width=True):
            base = date(st.session_state.view_year, st.session_state.view_month, 15) - timedelta(days=31)
            st.session_state.view_year, st.session_state.view_month = base.year, base.month
            add_token(0.01)
            st.rerun()
    with c2:
        st.subheader(f"{calendar.month_name[st.session_state.view_month]} {st.session_state.view_year}")
    with c3:
        if st.button("Next Month", use_container_width=True):
            base = date(st.session_state.view_year, st.session_state.view_month, 15) + timedelta(days=31)
            st.session_state.view_year, st.session_state.view_month = base.year, base.month
            add_token(0.01)
            st.rerun()

    st.caption("Click a date to open its day page.")
    headers = st.columns(7)
    for col, name in zip(headers, ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
        col.markdown(f"**{name}**")

    today = app_now().date()
    for week in calendar.monthcalendar(st.session_state.view_year, st.session_state.view_month):
        cols = st.columns(7)
        for idx, day_num in enumerate(week):
            with cols[idx]:
                if day_num == 0:
                    st.write("")
                    continue
                current = date(st.session_state.view_year, st.session_state.view_month, day_num)
                note, diet, time_map, _ui, _extras = read_day(current)
                marks = []
                if note:
                    marks.append("note")
                if diet:
                    marks.append("meal")
                if any(value.strip() for value in time_map.values()):
                    marks.append("plan")
                cls = "day-card today" if current == today else "day-card"
                st.markdown(
                    f"<div class='{cls}'><b>{day_num}</b><br><span class='small-muted'>{' / '.join(marks) or '&nbsp;'}</span></div>",
                    unsafe_allow_html=True,
                )
                if st.button("Open", key=f"open-{current}", use_container_width=True):
                    st.session_state.selected_day = current
                    add_token(0.01)
                    st.rerun()


def render_day():
    selected = st.session_state.selected_day
    note, diet, time_map, ui, extras = read_day(selected)
    st.subheader(f"{selected:%Y-%m-%d}  {selected.strftime('%A')}")

    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        if st.button("Yesterday", use_container_width=True):
            st.session_state.selected_day = selected - timedelta(days=1)
            add_token(0.01)
            st.rerun()
    with c2:
        if st.button("Tomorrow", use_container_width=True):
            st.session_state.selected_day = selected + timedelta(days=1)
            add_token(0.01)
            st.rerun()
    with c3:
        picked = st.date_input("Jump to date", value=selected)
        if picked != selected:
            st.session_state.selected_day = picked
            add_token(0.01)
            st.rerun()

    day_tabs = st.tabs(["Schedule", "Meal Plan", "Diary Note", "Token Settings"])

    with day_tabs[0]:
        slots = time_slots()
        now = app_now()
        current_slot = f"{natural_time(now.hour)} - {natural_time(now.hour + 1)}"
        new_time_map: dict[str, str] = {}
        filled = 0
        for slot in slots:
            row_class = "now-row" if selected == now.date() and slot == current_slot else ""
            if row_class:
                remaining = 100 - int(now.minute / 60 * 100)
                st.markdown(f"<div class='{row_class}'><b>{slot}</b> · {remaining}% left this hour</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"**{slot}**")
            value = st.text_area(
                label=f"Plan for {slot}",
                value=time_map.get(slot, ""),
                height=72,
                label_visibility="collapsed",
                key=f"time-{selected}-{slot}",
            )
            if value.strip():
                filled += 1
            new_time_map[slot] = value

        if st.button("Save Schedule", use_container_width=True):
            progress_bonus = 0.5 * min(1.0, filled / 24)
            add_token(progress_bonus)
            ui["TOKEN_LEVEL"] = f"{st.session_state.token * 16:.4f}"
            write_day(selected, note, diet, new_time_map, ui, extras)
            st.success("Schedule saved.")
            st.rerun()

    with day_tabs[1]:
        new_diet = st.text_area("Meal Plan", value=diet, height=260, key=f"diet-{selected}")
        if st.button("Save Meal Plan", use_container_width=True):
            add_token(max(0.01, len(new_diet) * 0.001))
            ui["TOKEN_LEVEL"] = f"{st.session_state.token * 16:.4f}"
            write_day(selected, note, new_diet, time_map, ui, extras)
            st.success("Meal plan saved.")
            st.rerun()

    with day_tabs[2]:
        new_note = st.text_area("Diary Note", value=note, height=340, key=f"note-{selected}")
        if st.button("Save Diary Note", use_container_width=True):
            add_token(max(0.01, len(new_note) * 0.001))
            ui["TOKEN_LEVEL"] = f"{st.session_state.token * 16:.4f}"
            write_day(selected, new_note, diet, time_map, ui, extras)
            st.success("Diary note saved.")
            st.rerun()

    with day_tabs[3]:
        st.write("Token battery rewards planning, typing, and action.")
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("+ Click token", use_container_width=True):
                add_token(0.01)
                save_token_to_day(selected)
                st.rerun()
        with c2:
            if st.button("+ Important task", use_container_width=True):
                add_token(0.1)
                save_token_to_day(selected)
                st.rerun()
        with c3:
            if st.button("Reset token", use_container_width=True):
                st.session_state.token = 0.0
                save_token_to_day(selected)
                st.rerun()


def render_meal_history():
    st.subheader("Meal History")
    anchor = st.session_state.selected_day
    count = 0
    for offset in range(0, 30):
        current = anchor - timedelta(days=offset)
        _note, diet, _time, _ui, _extras = read_day(current)
        if not diet:
            continue
        count += 1
        st.markdown(
            f"<div class='history-card'><b>{current:%Y-%m-%d}</b><br>{diet.replace(chr(10), '<br>')}</div>",
            unsafe_allow_html=True,
        )
    if count == 0:
        st.info("No meal history in the last 30 days.")


def render_long_plan():
    year = st.session_state.view_year
    month = st.session_state.view_month
    st.subheader(f"Long Plan · {calendar.month_name[month]} {year}")
    st.caption("This is the web-safe version of the desktop drag planner. Add blocks here, then sync them into daily 10 PM style schedule rows.")

    blocks = load_month_plan(year, month)
    last_day = calendar.monthrange(year, month)[1]

    with st.form("add-long-plan", clear_on_submit=True):
        task = st.text_input("Task", placeholder="Early sleep")
        c1, c2, c3 = st.columns(3)
        with c1:
            start_day = st.number_input("Start day", 1, last_day, min(app_now().day, last_day))
        with c2:
            hour = st.number_input("Hour", 0, 23, 22)
        with c3:
            span = st.number_input("Span days", 1, last_day, 7)
        submitted = st.form_submit_button("Add Block", use_container_width=True)
        if submitted and task.strip():
            blocks.append({"text": task.strip(), "day": int(start_day), "hour": int(hour), "span": int(span)})
            save_month_plan(year, month, blocks)
            add_token(0.05)
            st.rerun()

    if not blocks:
        st.info("No long-plan blocks yet.")
    else:
        for idx, block in enumerate(blocks):
            end_day = min(last_day, int(block.get("day", 1)) + int(block.get("span", 1)) - 1)
            st.markdown(
                f"<div class='plan-block'><b>{block.get('text', '')}</b><br>"
                f"Day {block.get('day', 1)} to {end_day}, {int(block.get('hour', 22)):02d}:00</div>",
                unsafe_allow_html=True,
            )
            if st.button("Delete", key=f"delete-block-{idx}"):
                blocks.pop(idx)
                save_month_plan(year, month, blocks)
                st.rerun()

    if st.button("Sync Long Plan to Daily Schedule", use_container_width=True):
        sync_long_plan(year, month, blocks)
        add_token(0.1)
        st.success("Synced into daily schedule.")
        st.rerun()


def main():
    st.set_page_config(page_title="My Diary", layout="wide")
    init_state()
    render_css()

    with st.sidebar:
        st.subheader("Settings")
        tz_label = "Beijing" if st.session_state.tz == "Asia/Shanghai" else "NYC"
        st.caption(f"Current timezone: {tz_label}")
        if st.button("Switch Beijing / NYC", use_container_width=True):
            st.session_state.tz = "America/New_York" if st.session_state.tz == "Asia/Shanghai" else "Asia/Shanghai"
            add_token(0.01)
            st.rerun()
        st.divider()
        st.write(f"Now: {app_now():%Y-%m-%d %H:%M}")
        st.write(f"Selected: {st.session_state.selected_day:%Y-%m-%d}")

    tabs = st.tabs(["Month Calendar", "Day Page", "Meal History", "Long Plan"])
    with tabs[0]:
        render_month()
    with tabs[1]:
        render_day()
    with tabs[2]:
        render_meal_history()
    with tabs[3]:
        render_long_plan()


if __name__ == "__main__":
    main()
