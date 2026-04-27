from __future__ import annotations

import calendar
import json
import os
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


def now_display() -> datetime:
    return datetime.now(ZoneInfo(st.session_state.get("tz", "Asia/Shanghai")))


def note_path(day: date) -> Path:
    return NOTES_DIR / f"{day:%Y-%m-%d}.txt"


def read_all_sections(path: Path) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    mode = None
    if not path.exists():
        return sections
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.rstrip("\n")
        if line.startswith("【") and line.endswith("】"):
            mode = line[1:-1]
            sections.setdefault(mode, [])
        elif mode is not None:
            sections.setdefault(mode, []).append(line)
    return sections


def read_day(day: date):
    sections = read_all_sections(note_path(day))
    note = "\n".join(sections.get(SECTION_NOTE, [])).strip()
    diet = "\n".join(sections.get(SECTION_DIET, [])).strip()
    time_map = {}
    ui = {}
    for line in sections.get(SECTION_TIME, []):
        if "::" in line:
            k, v = line.split("::", 1)
            time_map[k] = v
    for line in sections.get(SECTION_UI, []):
        if "::" in line:
            k, v = line.split("::", 1)
            ui[k.strip()] = v.strip()
    extras = {
        k: v
        for k, v in sections.items()
        if k not in {SECTION_NOTE, SECTION_DIET, SECTION_UI, SECTION_TIME}
    }
    return note, diet, time_map, ui, extras


def write_day(day: date, note: str, diet: str, time_map: dict[str, str], ui: dict[str, str] | None = None, extras=None):
    ui = ui or {}
    extras = extras or {}
    out = [
        f"【{SECTION_NOTE}】",
        note.strip(),
        "",
        f"【{SECTION_DIET}】",
        diet.strip(),
        "",
        f"【{SECTION_UI}】",
    ]
    out.extend(f"{k}::{v}" for k, v in ui.items())
    out.extend(["", f"【{SECTION_TIME}】"])
    for slot, text in time_map.items():
        if str(text).strip():
            out.append(f"{slot}::{str(text).strip()}")
    for name, lines in extras.items():
        out.extend(["", f"【{name}】"])
        out.extend(str(x).rstrip("\n") for x in lines)
    note_path(day).write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")


def generate_time_slots() -> list[str]:
    def natural_time(hour: int) -> str:
        if hour == 0:
            return "12:00 AM"
        if hour < 12:
            return f"{hour}:00 AM"
        if hour == 12:
            return "12:00 PM"
        return f"{hour - 12}:00 PM"

    return [
        f"{natural_time((7 + i) % 24)} - {natural_time((8 + i) % 24)}"
        for i in range(24)
    ]


def recent_diet_history(anchor: date, days=30):
    items = []
    for offset in range(1, days + 1):
        d = anchor - timedelta(days=offset)
        _note, diet, _time, _ui, _extras = read_day(d)
        if diet:
            items.append((d, diet))
    return items


def token_charge(amount: float):
    st.session_state.token = min(1.0, st.session_state.get("token", 0.0) + amount)


def render_battery():
    pct = int(st.session_state.get("token", 0.0) * 100)
    st.markdown(
        f"""
        <div class="battery-wrap">
          <div class="battery"><div class="battery-fill" style="width:{pct}%"></div></div>
          <div class="battery-cap"></div>
          <span class="battery-label">TOKEN {pct}%</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def month_plan_path(year: int, month: int) -> Path:
    return NOTES_DIR / f"{year:04d}-{month:02d}-long_plan.json"


def load_month_plan(year: int, month: int):
    path = month_plan_path(year, month)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_month_plan(year: int, month: int, blocks):
    month_plan_path(year, month).write_text(json.dumps(blocks, ensure_ascii=False, indent=2), encoding="utf-8")


def sync_plan_to_days(year: int, month: int, blocks):
    slots = generate_time_slots()
    days_in_month = calendar.monthrange(year, month)[1]
    for block in blocks:
        text = str(block.get("text", "")).strip()
        if not text:
            continue
        start_day = max(1, min(days_in_month, int(block.get("day", 1))))
        span = max(1, int(block.get("span", 1)))
        hour = max(0, min(23, int(block.get("hour", 22))))
        slot = slots[(hour - 7) % 24]
        for dd in range(start_day, min(days_in_month, start_day + span - 1) + 1):
            current = date(year, month, dd)
            note, diet, time_map, ui, extras = read_day(current)
            existing = time_map.get(slot, "").strip()
            if text not in existing.split("\n"):
                time_map[slot] = f"{existing}\n{text}".strip() if existing else text
            write_day(current, note, diet, time_map, ui, extras)


st.set_page_config(page_title="My Diary", layout="wide")

st.markdown(
    """
    <style>
      .block-container { padding-top: 1.2rem; }
      .battery-wrap { display:flex; align-items:center; gap:4px; justify-content:flex-end; }
      .battery { width:170px; height:22px; border:2px solid #223129; background:#fff; position:relative; }
      .battery-fill { height:100%; background:#39d98a; transition:width .15s ease; }
      .battery-cap { width:7px; height:12px; border:2px solid #223129; border-left:0; }
      .battery-label { font-size:12px; font-weight:700; margin-left:8px; color:#223129; }
      .calendar-day button { width:100%; min-height:3.2rem; }
      .time-now { border-left:6px solid #c94a3a; padding-left:.5rem; }
      .history-card { border:1px solid #ddd0b8; padding:.75rem; margin:.5rem 0; background:#fffaf0; }
    </style>
    """,
    unsafe_allow_html=True,
)

if "tz" not in st.session_state:
    st.session_state.tz = "Asia/Shanghai"
if "selected_day" not in st.session_state:
    st.session_state.selected_day = now_display().date()
if "view_year" not in st.session_state:
    today = now_display().date()
    st.session_state.view_year = today.year
    st.session_state.view_month = today.month
if "token" not in st.session_state:
    _n, _d, _t, ui, _e = read_day(st.session_state.selected_day)
    st.session_state.token = min(1.0, float(ui.get("TOKEN_LEVEL", "0") or 0) / 16.0)


top_l, top_r = st.columns([3, 2])
with top_l:
    st.title("My Diary")
with top_r:
    render_battery()

with st.sidebar:
    st.subheader("Settings")
    if st.button("Switch Beijing / NYC"):
        st.session_state.tz = "America/New_York" if st.session_state.tz == "Asia/Shanghai" else "Asia/Shanghai"
        st.rerun()
    st.caption(f"Timezone: {'Beijing' if st.session_state.tz == 'Asia/Shanghai' else 'NYC'}")
    click_token = st.number_input("Click token", value=0.01, min_value=0.0, max_value=1.0, step=0.001, format="%.3f")
    type_token = st.number_input("Type token / char", value=0.001, min_value=0.0, max_value=0.05, step=0.0005, format="%.4f")
    important_token = st.number_input("Important task token", value=0.1, min_value=0.0, max_value=4.0, step=0.01)
    progress_token = st.number_input("Full plan token", value=0.5, min_value=0.0, max_value=1.0, step=0.05)


tabs = st.tabs(["Month", "Day", "Meal History", "Long Plan"])

with tabs[0]:
    c1, c2, c3 = st.columns([1, 2, 1])
    with c1:
        if st.button("Previous"):
            base = date(st.session_state.view_year, st.session_state.view_month, 15) - timedelta(days=31)
            st.session_state.view_year, st.session_state.view_month = base.year, base.month
            st.rerun()
    with c2:
        st.header(f"{calendar.month_name[st.session_state.view_month]} {st.session_state.view_year}")
    with c3:
        if st.button("Next"):
            base = date(st.session_state.view_year, st.session_state.view_month, 15) + timedelta(days=31)
            st.session_state.view_year, st.session_state.view_month = base.year, base.month
            st.rerun()

    weeks = calendar.monthcalendar(st.session_state.view_year, st.session_state.view_month)
    st.write("Mon Tue Wed Thu Fri Sat Sun")
    for week in weeks:
        cols = st.columns(7)
        for idx, day_num in enumerate(week):
            with cols[idx]:
                if day_num == 0:
                    st.write("")
                else:
                    d = date(st.session_state.view_year, st.session_state.view_month, day_num)
                    marker = "📘" if note_path(d).exists() and note_path(d).stat().st_size > 40 else ""
                    if st.button(f"{day_num} {marker}", key=f"cal-{d}"):
                        st.session_state.selected_day = d
                        token_charge(click_token)
                        st.rerun()

with tabs[1]:
    selected = st.session_state.selected_day
    note, diet, time_map, ui, extras = read_day(selected)
    st.header(f"{selected:%Y-%m-%d} {selected.strftime('%A')}")

    note_tab, diet_tab, schedule_tab = st.tabs(["Notes", "Meal Plan", "Schedule"])
    with note_tab:
        new_note = st.text_area("Today notes", note, height=220)
        if new_note != note:
            token_charge(max(0, len(new_note) - len(note)) * type_token)
            write_day(selected, new_note, diet, time_map, ui, extras)
            st.rerun()
    with diet_tab:
        new_diet = st.text_area("Today meal plan", diet, height=180)
        if new_diet != diet:
            token_charge(max(0, len(new_diet) - len(diet)) * type_token)
            write_day(selected, note, new_diet, time_map, ui, extras)
            st.rerun()
    with schedule_tab:
        slots = generate_time_slots()
        now = now_display()
        current_slot = None
        start = datetime(selected.year, selected.month, selected.day, 7, tzinfo=ZoneInfo(st.session_state.tz))
        if now.date() == selected and now.hour < 7:
            start -= timedelta(days=1)
        if start <= now < start + timedelta(hours=24):
            current_slot = int((now - start).total_seconds() // 3600)

        new_time_map = dict(time_map)
        for i, slot in enumerate(slots):
            label = f"**{slot}**"
            if i == current_slot:
                st.markdown(f'<div class="time-now">{label}</div>', unsafe_allow_html=True)
            else:
                st.markdown(label)
            val = st.text_area(slot, time_map.get(slot, ""), height=80, label_visibility="collapsed", key=f"time-{selected}-{slot}")
            if val != time_map.get(slot, ""):
                new_time_map[slot] = val
        if st.button("Save schedule"):
            filled_before = sum(1 for x in time_map.values() if x.strip())
            filled_after = sum(1 for x in new_time_map.values() if x.strip())
            token_charge(max(0, filled_after - filled_before) * (progress_token / 24.0))
            write_day(selected, note, diet, new_time_map, ui, extras)
            st.success("Saved.")

with tabs[2]:
    st.header("Past 30 Days Meal History")
    for d, text in recent_diet_history(st.session_state.selected_day, 30):
        st.markdown(f'<div class="history-card"><b>{d:%Y-%m-%d} {d:%A}</b><br>{text.replace(chr(10), "<br>")}</div>', unsafe_allow_html=True)

with tabs[3]:
    year = st.session_state.view_year
    month = st.session_state.view_month
    st.header(f"Long Plan: {calendar.month_name[month]} {year}")
    blocks = load_month_plan(year, month)
    days_in_month = calendar.monthrange(year, month)[1]
    with st.form("add_long_plan"):
        text = st.text_input("Task, e.g. sleep early")
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            start_day = st.number_input("Start day", 1, days_in_month, 1)
        with col_b:
            hour = st.number_input("Hour (0-23)", 0, 23, 22)
        with col_c:
            span = st.number_input("Span days", 1, days_in_month, days_in_month)
        submitted = st.form_submit_button("Add block")
        if submitted and text.strip():
            blocks.append({"id": str(int(datetime.now().timestamp() * 1000)), "text": text.strip(), "day": int(start_day), "hour": int(hour), "span": int(span)})
            save_month_plan(year, month, blocks)
            st.rerun()

    if blocks:
        st.dataframe(blocks, use_container_width=True)
        if st.button("Sync to Days"):
            sync_plan_to_days(year, month, blocks)
            token_charge(progress_token)
            st.success("Synced to daily schedules.")
        if st.button("Clear Long Plan"):
            save_month_plan(year, month, [])
            st.rerun()
    else:
        st.info("No long plan blocks yet.")

