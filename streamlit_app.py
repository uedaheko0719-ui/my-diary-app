from __future__ import annotations

import calendar
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st


NOTES_DIR = Path("notes")
NOTES_DIR.mkdir(exist_ok=True)

SECTION_NOTE = "文字笔记"
SECTION_DIET = "饮食规划"
SECTION_UI = "界面设置"
SECTION_TIME = "时间表"
SECTION_QUADRANT = "四象限"


def now() -> datetime:
    return datetime.now(ZoneInfo("Asia/Shanghai"))


def note_path(day: date) -> Path:
    return NOTES_DIR / f"{day:%Y-%m-%d}.txt"


def read_sections(path: Path) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current = None
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
    quadrant = "\n".join(sections.get(SECTION_QUADRANT, [])).strip()
    ui: dict[str, str] = {}
    time_map: dict[str, str] = {}

    for line in sections.get(SECTION_UI, []):
        if "::" in line:
            key, value = line.split("::", 1)
            ui[key.strip()] = value.strip()

    for line in sections.get(SECTION_TIME, []):
        if "::" in line:
            slot, value = line.split("::", 1)
            time_map[slot] = value

    extras = {
        key: value
        for key, value in sections.items()
        if key not in {SECTION_NOTE, SECTION_DIET, SECTION_UI, SECTION_TIME, SECTION_QUADRANT}
    }
    return note, diet, quadrant, time_map, ui, extras


def write_day(
    day: date,
    note: str,
    diet: str,
    quadrant: str,
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
    for slot, value in time_map.items():
        if value.strip():
            lines.append(f"{slot}::{value.strip()}")
    lines.extend(["", f"【{SECTION_QUADRANT}】", quadrant.strip()])

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


def current_slot() -> str:
    current = now()
    return f"{natural_time(current.hour)} - {natural_time(current.hour + 1)}"


def add_token(amount: float):
    st.session_state.token = min(1.0, max(0.0, st.session_state.token + amount))
    st.session_state.flash_battery = True


def init_state():
    today = now().date()
    defaults = {
        "view": "month",
        "selected_day": today,
        "panel": "",
        "settings_open": False,
        "quadrant_open": False,
        "token": 0.0,
        "flash_battery": False,
        "click_token": 0.01,
        "type_token": 0.001,
        "important_token": 0.1,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)

    if "loaded_token" not in st.session_state:
        _note, _diet, _quad, _time_map, ui, _extras = read_day(today)
        try:
            st.session_state.token = min(1.0, float(ui.get("TOKEN_LEVEL", "0")) / 16.0)
        except ValueError:
            st.session_state.token = 0.0
        st.session_state.loaded_token = True


def css():
    battery_class = "battery-wrap flash" if st.session_state.flash_battery else "battery-wrap"
    st.markdown(
        f"""
        <style>
          :root {{
            --paper:#f8f3e7;
            --panel:#fffaf0;
            --line:#ded3c0;
            --ink:#263027;
            --muted:#7a7d74;
            --green:#35a868;
            --red:#c94a3a;
          }}
          .stApp {{ background:var(--paper); color:var(--ink); }}
          .block-container {{ max-width:1220px; padding-top:18px; }}
          .month-wrap {{ max-width:980px; margin:0 auto; }}
          .month-title {{ font-size:26px; font-weight:700; text-align:center; margin:0 0 18px; }}
          .week-label {{ color:var(--muted); font-weight:700; text-align:center; padding-bottom:8px; }}
          div.stButton > button {{
            border-radius:6px; border:1px solid var(--line); background:var(--panel);
            color:var(--ink); min-height:42px; transition:background .12s ease, transform .12s ease, border-color .12s ease;
          }}
          div.stButton > button:hover {{
            background:#fff; border-color:#96b79f; transform:translateY(-1px);
          }}
          .calendar-cell {{
            height:92px; border:1px solid var(--line); background:var(--panel);
            border-radius:6px; padding:9px; font-size:17px; font-weight:700;
          }}
          .calendar-cell.today {{
            border-left:6px solid var(--red); background:#fffdf8;
          }}
          .calendar-cell.empty {{ opacity:0; }}
          .day-top {{
            display:flex; align-items:center; justify-content:space-between;
            gap:12px; padding-bottom:12px; margin-bottom:12px; border-bottom:1px solid var(--line);
          }}
          .day-title {{ font-size:24px; font-weight:700; }}
          .right-tools {{ display:flex; align-items:center; gap:12px; }}
          .battery-wrap {{ display:flex; align-items:center; gap:8px; }}
          .battery {{
            width:150px; height:24px; border:2px solid #27352d; border-radius:4px;
            background:white; padding:3px; position:relative;
          }}
          .battery:after {{
            content:""; position:absolute; right:-10px; top:4px; width:7px; height:12px;
            border:2px solid #27352d; border-left:0; border-radius:0 3px 3px 0;
          }}
          .battery-fill {{
            height:100%; width:{int(st.session_state.token * 100)}%; background:var(--green);
            border-radius:2px; transition:width .16s ease;
          }}
          .flash .battery-fill {{ animation:batteryFlash .25s ease; }}
          @keyframes batteryFlash {{
            0% {{ filter:brightness(1); }}
            50% {{ filter:brightness(1.75); }}
            100% {{ filter:brightness(1); }}
          }}
          .battery-label {{ min-width:42px; font-size:12px; font-weight:800; }}
          .tool-row {{ display:flex; gap:8px; margin-bottom:14px; flex-wrap:wrap; }}
          .panel-box {{
            border:1px solid var(--line); background:var(--panel); border-radius:8px;
            padding:14px; margin:10px 0 16px;
          }}
          .slot {{
            display:grid; grid-template-columns:170px 1fr; gap:12px; align-items:start;
            padding:10px 0; border-bottom:1px solid rgba(222,211,192,.75);
          }}
          .slot.now {{ border-left:6px solid var(--green); padding-left:10px; background:#fffdf8; }}
          .slot-time {{ font-weight:700; color:#3d463f; padding-top:8px; }}
          textarea {{ border-radius:7px !important; }}
          @media (max-width: 760px) {{
            .slot {{ grid-template-columns:1fr; }}
            .day-top {{ align-items:flex-start; flex-direction:column; }}
          }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.session_state.flash_battery = False


def save_token(day: date):
    note, diet, quadrant, time_map, ui, extras = read_day(day)
    ui["TOKEN_LEVEL"] = f"{st.session_state.token * 16:.4f}"
    write_day(day, note, diet, quadrant, time_map, ui, extras)


def render_month():
    today = now().date()
    st.markdown('<div class="month-wrap">', unsafe_allow_html=True)
    st.markdown(f'<div class="month-title">{today:%B %Y}</div>', unsafe_allow_html=True)

    for col, label in zip(st.columns(7), ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
        col.markdown(f'<div class="week-label">{label}</div>', unsafe_allow_html=True)

    for week in calendar.monthcalendar(today.year, today.month):
        cols = st.columns(7)
        for index, day_num in enumerate(week):
            with cols[index]:
                if day_num == 0:
                    st.markdown('<div class="calendar-cell empty"></div>', unsafe_allow_html=True)
                    continue
                current = date(today.year, today.month, day_num)
                label = f"| {day_num}" if current == today else str(day_num)
                if st.button(label, key=f"open-{current}", use_container_width=True):
                    st.session_state.selected_day = current
                    st.session_state.view = "day"
                    st.session_state.panel = ""
                    add_token(st.session_state.click_token)
                    st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def render_day_header(selected: date):
    pct = int(st.session_state.token * 100)
    battery_class = "battery-wrap flash" if st.session_state.flash_battery else "battery-wrap"
    st.markdown(
        f"""
        <div class="day-top">
          <div class="day-title">{selected:%Y-%m-%d} · {selected.strftime('%A')}</div>
          <div class="right-tools">
            <div class="{battery_class}">
              <div class="battery"><div class="battery-fill"></div></div>
              <div class="battery-label">{pct}%</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_settings(selected: date):
    st.markdown('<div class="panel-box">', unsafe_allow_html=True)
    st.subheader("Battery Settings")
    c1, c2, c3 = st.columns(3)
    st.session_state.click_token = c1.number_input(
        "Click token", min_value=0.0, max_value=1.0, value=float(st.session_state.click_token), step=0.001, format="%.3f"
    )
    st.session_state.type_token = c2.number_input(
        "Type token / char", min_value=0.0, max_value=0.05, value=float(st.session_state.type_token), step=0.001, format="%.3f"
    )
    st.session_state.important_token = c3.number_input(
        "Important task token", min_value=0.0, max_value=1.0, value=float(st.session_state.important_token), step=0.01
    )
    if st.button("Reset Battery"):
        st.session_state.token = 0.0
        save_token(selected)
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def render_text_panel(selected: date, panel: str):
    note, diet, quadrant, time_map, ui, extras = read_day(selected)
    if panel == "note":
        st.markdown('<div class="panel-box">', unsafe_allow_html=True)
        value = st.text_area("Today's Notes", value=note, height=260)
        if st.button("Save Notes", use_container_width=True):
            add_token(max(st.session_state.click_token, len(value) * st.session_state.type_token))
            ui["TOKEN_LEVEL"] = f"{st.session_state.token * 16:.4f}"
            write_day(selected, value, diet, quadrant, time_map, ui, extras)
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    elif panel == "diet":
        st.markdown('<div class="panel-box">', unsafe_allow_html=True)
        value = st.text_area("Meal Plan", value=diet, height=220)
        if st.button("Save Meal Plan", use_container_width=True):
            add_token(max(st.session_state.click_token, len(value) * st.session_state.type_token))
            ui["TOKEN_LEVEL"] = f"{st.session_state.token * 16:.4f}"
            write_day(selected, note, value, quadrant, time_map, ui, extras)
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    elif panel == "quadrant":
        st.markdown('<div class="panel-box">', unsafe_allow_html=True)
        value = st.text_area("Eisenhower Matrix", value=quadrant, height=220, placeholder="Important / Urgent...")
        if st.button("Save Quadrant", use_container_width=True):
            add_token(st.session_state.important_token)
            ui["TOKEN_LEVEL"] = f"{st.session_state.token * 16:.4f}"
            write_day(selected, note, diet, value, time_map, ui, extras)
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


def render_schedule(selected: date):
    note, diet, quadrant, time_map, ui, extras = read_day(selected)
    slots = time_slots()
    active_slot = current_slot() if selected == now().date() else ""
    changed: dict[str, str] = {}
    filled = 0

    for slot in slots:
        cls = "slot now" if slot == active_slot else "slot"
        st.markdown(f'<div class="{cls}"><div class="slot-time">{slot}</div><div>', unsafe_allow_html=True)
        value = st.text_area(
            f"{slot} plan",
            value=time_map.get(slot, ""),
            key=f"slot-{selected}-{slot}",
            height=74,
            label_visibility="collapsed",
        )
        st.markdown("</div></div>", unsafe_allow_html=True)
        changed[slot] = value
        if value.strip():
            filled += 1

    if st.button("Save Schedule", use_container_width=True):
        add_token(0.5 * min(1.0, filled / 24))
        ui["TOKEN_LEVEL"] = f"{st.session_state.token * 16:.4f}"
        write_day(selected, note, diet, quadrant, changed, ui, extras)
        st.rerun()


def render_day():
    selected = st.session_state.selected_day
    render_day_header(selected)

    c1, c2, c3, c4, c5 = st.columns([1, 1, 1, 1, 1])
    if c1.button("Month", use_container_width=True):
        st.session_state.view = "month"
        add_token(st.session_state.click_token)
        st.rerun()
    if c2.button("Notes", use_container_width=True):
        st.session_state.panel = "" if st.session_state.panel == "note" else "note"
        add_token(st.session_state.click_token)
        st.rerun()
    if c3.button("Meal", use_container_width=True):
        st.session_state.panel = "" if st.session_state.panel == "diet" else "diet"
        add_token(st.session_state.click_token)
        st.rerun()
    if c4.button("Quadrant", use_container_width=True):
        st.session_state.panel = "" if st.session_state.panel == "quadrant" else "quadrant"
        add_token(st.session_state.click_token)
        st.rerun()
    if c5.button("Battery", use_container_width=True):
        st.session_state.settings_open = not st.session_state.settings_open
        add_token(st.session_state.click_token)
        st.rerun()

    if st.session_state.settings_open:
        render_settings(selected)
    if st.session_state.panel:
        render_text_panel(selected, st.session_state.panel)

    render_schedule(selected)


def main():
    st.set_page_config(page_title="My Diary", layout="wide")
    init_state()
    css()

    if st.session_state.view == "month":
        render_month()
    else:
        render_day()


if __name__ == "__main__":
    main()
