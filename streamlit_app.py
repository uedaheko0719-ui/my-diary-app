from __future__ import annotations

import calendar
import json
from html import escape
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st
import streamlit.components.v1 as components


NOTES_DIR = Path("notes")
NOTES_DIR.mkdir(exist_ok=True)

SECTION_NOTE = "文字笔记"
SECTION_DIET = "饮食规划"
SECTION_UI = "界面设置"
SECTION_TIME = "时间表"
SECTION_QUADRANT = "四象限"


def now() -> datetime:
    return datetime.now(ZoneInfo("America/New_York"))


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
    return [f"{natural_time(i)} - {natural_time(i + 1)}" for i in range(24)]


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
        "view_year": today.year,
        "view_month": today.month,
        "selected_day": today,
        "panel": "",
        "matrix_open": False,
        "token": 0.0,
        "flash_battery": False,
        "click_token": 0.01,
        "type_token": 0.001,
        "important_token": 0.1,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)

    params = st.query_params
    if params.get("month"):
        try:
            year_text, month_text = params["month"].split("-", 1)
            st.session_state.view_year = int(year_text)
            st.session_state.view_month = int(month_text)
            st.session_state.view = "month"
            st.query_params.clear()
        except ValueError:
            st.query_params.clear()
    if params.get("day"):
        try:
            picked = date.fromisoformat(params["day"])
            st.session_state.selected_day = picked
            st.session_state.view_year = picked.year
            st.session_state.view_month = picked.month
            st.session_state.view = "day"
            panel = params.get("panel")
            if panel in {"note", "diet"}:
                st.session_state.panel = "" if st.session_state.panel == panel else panel
            st.query_params.clear()
        except ValueError:
            st.query_params.clear()

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
            --paper:#f8efd9;
            --panel:#fffefa;
            --softbox:#fffefa;
            --line:#eee7da;
            --ink:#263027;
            --muted:#7a7d74;
            --green:#35a868;
            --red:#c94a3a;
            --blue:#c9e2f5;
            --pink:#f5caca;
            --today:#ffe9a9;
          }}
          [data-testid="stHeader"], [data-testid="stToolbar"], #MainMenu, footer {{
            display:none !important;
          }}
          .stApp {{ background:var(--paper); color:var(--ink); }}
          .stApp, .stApp *, [data-testid="stMarkdownContainer"], [data-testid="stMarkdownContainer"] * {{
            color:#000;
          }}
          .block-container {{ max-width:1220px; padding:10px 18px 14px; }}
          .simple-topbar {{
            display:flex; align-items:center; justify-content:space-between;
            gap:10px; min-height:26px;
          }}
          .month-link {{
            display:inline-flex; align-items:center; justify-content:center; min-height:30px;
            padding:0 12px; border:1px solid #d8cbb6; background:#fffdf8;
            color:#000; text-decoration:none; font-weight:800; box-shadow:0 1px 3px rgba(60,50,35,.18);
            font-size:13px; border-radius:2px;
          }}
          .month-link:hover {{ background:#fff8eb; transform:translateY(-1px); }}
          .topbar-right {{ display:flex; align-items:center; gap:14px; }}
          .compact-action-row [data-testid="stHorizontalBlock"],
          [data-testid="stHorizontalBlock"] {{
            flex-wrap:nowrap !important;
            gap:8px !important;
          }}
          .compact-action-row [data-testid="column"],
          [data-testid="column"] {{
            min-width:0 !important;
            flex:1 1 0 !important;
          }}
          .html-btn {{ display:flex; align-items:center; justify-content:center; min-height:42px; border:1px solid #fff; color:#000; text-decoration:none; font-weight:800; box-shadow:0 1px 3px rgba(60,50,35,.18); font-size:16px; white-space:nowrap; background:#fff; }}
          .html-btn:hover {{ filter:brightness(1.04); transform:translateY(-1px); }}
          .html-btn:active {{ border-style:inset; box-shadow:none; transform:translateY(1px); }}
          .html-note {{ background:#e8f2ff; }}
          .html-meal {{ background:#fff4e4; }}
          .html-now {{ background:#e8f6ea; }}
          .html-spacer {{ min-width:0; }}
          .month-wrap {{ max-width:980px; margin:0 auto; }}
          .month-nav {{
            display:grid; grid-template-columns:54px 1fr 54px; align-items:center;
            gap:10px; margin:26px 0 18px;
          }}
          .month-title {{ font-size:26px; font-weight:700; text-align:center; }}
          .month-arrow {{
            display:flex; align-items:center; justify-content:center; height:44px;
            border:1px solid #fff; background:#fff; border-radius:2px;
            text-decoration:none; color:var(--ink); font-size:24px; transition:background .12s ease, transform .12s ease;
          }}
          .month-arrow:hover {{ background:#fff; transform:translateY(-1px); }}
          .calendar-grid {{
            display:grid; grid-template-columns:repeat(7, minmax(0, 1fr)); gap:8px;
          }}
          .week-label {{ color:#000; font-weight:800; text-align:center; padding-bottom:20px; font-size:20px; }}
          div.stButton > button {{
            border-radius:2px !important; border:1px solid #d8cbb6 !important; background:#fffdf8 !important;
            color:#000 !important; min-height:34px; transition:background .12s ease, transform .08s ease, border-color .12s ease;
            font-weight:700; box-shadow:0 1px 3px rgba(60,50,35,.18); font-family:Arial, sans-serif;
            font-size:15px !important;
          }}
          div.stButton > button p, div.stButton > button span {{
            color:#000 !important;
          }}
          div.stButton > button:hover {{
            background:#fff8eb !important; border-color:#fff !important; transform:translateY(-1px);
          }}
          div.stButton > button:active {{
            border-style:inset !important; transform:translateY(1px); box-shadow:none;
          }}
          .calendar-cell {{
            display:flex; align-items:center; justify-content:center; gap:5px;
            min-height:92px; border:1px solid #fff; background:#fffefa;
            border-radius:0; padding:9px; font-size:20px; font-weight:500;
            text-decoration:none; color:var(--ink); transition:background .12s ease, transform .12s ease, border-color .12s ease;
          }}
          .calendar-cell:hover {{
            background:#fff; border-color:#99b8a1; transform:translateY(-1px);
          }}
          .calendar-cell.today {{
            border-color:#bfa24e; background:var(--today); font-weight:900;
          }}
          .calendar-cell.sat {{ background:var(--blue); }}
          .calendar-cell.sun {{ background:var(--pink); }}
          .calendar-cell.today.sat, .calendar-cell.today.sun {{ background:var(--today); }}
          .content-mark {{
            width:12px; height:16px; border:1px solid #7d745f; display:inline-block;
            background:repeating-linear-gradient(45deg, #7d745f 0, #7d745f 2px, #4aa3df 2px, #4aa3df 4px, #f2df66 4px, #f2df66 6px);
            box-shadow:1px 1px 0 #c8bda7;
          }}
          .calendar-cell.empty {{ opacity:.15; pointer-events:none; }}
          .calendar-date {{ display:block; }}
          .calendar-today-label {{ display:block; color:var(--red); font-size:11px; margin-top:4px; }}
          .day-top {{
            display:flex; align-items:center; justify-content:center;
            gap:8px; padding-bottom:0; margin-bottom:2px;
          }}
          .day-title {{ font-size:24px; font-weight:900; text-align:center; color:#000; }}
          .right-tools {{ display:flex; align-items:center; gap:12px; }}
          .battery-wrap {{ display:flex; align-items:center; gap:8px; }}
          .battery {{
            width:160px; height:18px; border:2px solid #fff; border-radius:0;
            background:white; padding:2px; position:relative; box-shadow:0 1px 3px rgba(60,50,35,.18);
          }}
          .battery:after {{
            content:""; position:absolute; right:-8px; top:3px; width:6px; height:8px;
            border:2px solid #fff; border-left:0; border-radius:0; background:#fff;
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
          .battery-label {{ min-width:36px; font-size:11px; font-weight:800; }}
          .tool-row {{ display:flex; gap:14px; margin:20px 0 14px; flex-wrap:wrap; }}
          .schedule-title {{ font-size:19px; font-weight:900; margin:14px 0 8px; color:#000; }}
          [data-testid="stVerticalBlock"] {{ gap:.55rem !important; }}
          [data-testid="stTextArea"] {{ margin:0 !important; }}
          .day-head {{
            position:sticky; top:0; z-index:1000; background:var(--paper);
            padding:2px 0 7px; border-bottom:1px solid rgba(238,231,218,.9);
            box-shadow:0 4px 10px rgba(80,70,48,.04);
          }}
          .schedule-scroll {{
            height:calc(100vh - 190px); min-height:430px; overflow-y:auto; padding-right:12px;
            overscroll-behavior:contain; scroll-behavior:smooth;
          }}
          .st-key-now-btn button {{ background:#e8f6ea !important; font-size:20px; min-height:58px; border-color:#f8fff9 !important; }}
          .st-key-notes-btn button,
          .st-key-meal-btn button,
          .st-key-monthly-matrix button {{
            min-height:36px !important;
            max-width:220px !important;
            margin:0 auto !important;
            background:#fffdf8 !important;
            border-color:#d8cbb6 !important;
          }}
          .action-btn {{ display:flex; align-items:center; justify-content:center; min-height:58px; border:1px solid #fff; background:#fff; color:#000; text-decoration:none; font-weight:800; font-size:20px; box-shadow:0 1px 3px rgba(60,50,35,.18); }}
          .action-btn:hover {{ background:#f8fff9; transform:translateY(-1px); }}
          .action-btn:active {{ border-style:inset; box-shadow:none; transform:translateY(1px); }}
          .st-key-monthly-matrix button {{ font-size:15px !important; }}
          .panel-box {{
            border:1px solid #fff; background:var(--softbox); border-radius:2px;
            padding:12px; margin:8px 0 12px;
            color:#000;
          }}
          .day-progress {{
            position:relative; height:54px; margin:0; overflow:visible;
          }}
          .progress-line {{
            position:absolute; left:0; right:0; top:33px; height:6px; background:#d8d8d8;
          }}
          .progress-fill {{
            position:absolute; left:0; top:33px; height:6px; background:#4a90e2; border-radius:8px;
          }}
          .tick {{
            position:absolute; top:24px; width:2px; height:20px; background:#5c5c5c;
          }}
          .tick.major {{ top:13px; height:31px; }}
          .tick-label {{
            position:absolute; top:0; transform:translateX(-50%); font-size:15px; font-weight:900; color:#000;
          }}
          .hour-zone {{
            position:absolute; top:16px; height:34px;
          }}
          .hour-zone:hover .timeline-pop {{ display:block; }}
          .timeline-pop {{
            display:none; position:absolute; top:36px; left:50%; transform:translateX(-50%);
            width:190px; min-height:76px; background:#fffdf7; border:1px solid #c8bda7;
            padding:10px; z-index:50; font-size:15px; white-space:pre-wrap; color:#000;
            box-shadow:0 8px 20px rgba(80,70,48,.12);
          }}
          .timeline-pop b {{ display:block; margin-bottom:12px; font-weight:500; }}
          .slot {{
            display:grid; grid-template-columns:190px 1fr; gap:12px; align-items:start;
            padding:6px 0; border-bottom:1px solid rgba(255,255,255,.95);
          }}
          .schedule-time-cell {{
            font-weight:800; padding:14px 8px 0 10px; min-height:74px; position:relative;
            background:transparent; color:#000;
          }}
          .schedule-time-cell.now {{
            border-left:7px solid var(--red); background:#fffefa;
          }}
          .slot.now {{ border-left:7px solid var(--red); padding-left:10px; background:#fffdf8; }}
          .slot-time {{
            font-weight:700; color:#3d463f; padding-top:8px; position:relative; cursor:default;
          }}
          .slot-task {{
            position:absolute; z-index:20; left:0; top:32px; width:260px; max-width:70vw;
            display:none; white-space:pre-wrap; border:1px solid #fff;
            background:#fff; border-radius:7px; padding:10px; color:#000;
            box-shadow:0 8px 22px rgba(47,42,34,.13); font-weight:500;
          }}
          .slot-time:hover .slot-task {{ display:block; }}
          .back-arrow {{
            display:inline-flex; align-items:center; justify-content:center; width:42px; height:38px;
            border:1px solid var(--line); border-radius:7px; background:var(--panel); font-size:22px;
          }}
          .matrix-dialog {{
            width:min(900px, 100%); overflow:auto; background:#fff;
            border:1px solid #eadfce; box-shadow:0 8px 20px rgba(80,70,48,.10); padding:12px;
            margin:14px auto 12px; color:#000; border-radius:2px;
          }}
          .matrix-head {{ display:flex; align-items:center; justify-content:space-between; gap:12px; }}
          .matrix-title {{ font-size:22px; font-weight:900; color:#000; margin:0 0 8px; }}
          .quadrant-grid {{
            display:grid !important; grid-template-columns:repeat(2, minmax(0, 1fr)) !important; gap:12px;
            aspect-ratio:1.65 / 1; color:#000;
          }}
          .quadrant-box {{
            border:1px solid #fff; background:#fff; border-radius:2px; padding:12px;
            min-height:0; overflow:auto; color:#000;
          }}
          .quadrant-title {{ font-weight:900; margin-bottom:8px; color:#000; font-size:18px; line-height:1.1; }}
          .task-pill {{ border:1px solid #fff; background:#fff; border-radius:2px; padding:8px; margin:6px 0; color:#000; }}
          textarea, input, [data-baseweb="textarea"], [data-baseweb="input"],
          [data-baseweb="select"] > div {{
            border-radius:4px !important;
            color:#000 !important;
            background:#fff !important;
            border-color:#d8cbb6 !important;
          }}
          input::placeholder, textarea::placeholder {{
            color:#787878 !important;
            opacity:1 !important;
          }}
          [data-baseweb="textarea"] textarea,
          [data-baseweb="input"] input,
          [data-baseweb="select"] span,
          [data-baseweb="select"] div {{
            color:#000 !important;
          }}
          [data-testid="stTextArea"] label,
          [data-testid="stTextInput"] label,
          [data-testid="stSelectbox"] label,
          [data-testid="stCheckbox"] label {{
            color:#000 !important;
          }}
          label, p, span, div {{
            color:inherit;
          }}
          .stTextArea textarea, .stTextInput input {{
            color:#000 !important;
            background:#fff !important;
          }}
          [data-testid="stFormSubmitButton"] button {{
            background:#fffdf8 !important;
            color:#000 !important;
            border:1px solid #d8cbb6 !important;
            box-shadow:0 1px 3px rgba(60,50,35,.18) !important;
          }}
          [data-testid="stFormSubmitButton"] button p,
          [data-testid="stFormSubmitButton"] button span {{
            color:#000 !important;
          }}
          [data-testid="stForm"] {{
            background:#fff !important;
            border:1px solid #eadfce !important;
            padding:10px !important;
            border-radius:2px !important;
          }}
          @media (max-width: 760px) {{
            .block-container {{ padding:8px 7px 12px; }}
            .html-btn {{ min-height:32px; font-size:11px; padding:0 3px; }}
            .compact-action-row [data-testid="stHorizontalBlock"] {{ gap:4px !important; }}
            .day-head {{ top:0; padding-top:2px; }}
            .schedule-scroll {{ height:calc(100vh - 172px); min-height:360px; }}
            .topbar-right {{ gap:8px; }}
            .battery {{ width:92px; }}
            .battery-label {{ font-size:9px; min-width:28px; }}
            .month-link {{ min-height:26px; padding:0 6px; font-size:10px; }}
            .calendar-grid {{ gap:4px; }}
            .calendar-cell {{ min-height:54px; padding:4px; font-size:14px; }}
            .content-mark {{ width:9px; height:13px; box-shadow:1px 1px 0 #c8bda7; }}
            .week-label {{ font-size:11px; }}
            .month-title {{ font-size:21px; }}
            .day-progress {{ height:48px; }}
            .tick-label {{ font-size:12px; }}
            .timeline-pop {{ width:150px; font-size:13px; }}
            .slot {{ grid-template-columns:86px minmax(0, 1fr); gap:6px; }}
            .slot-time {{ font-size:11px; }}
            .day-title {{ font-size:17px; }}
            .day-top {{ align-items:center; flex-direction:row; }}
            .quadrant-grid {{ grid-template-columns:repeat(2, minmax(0, 1fr)) !important; gap:6px; aspect-ratio:1 / 1.08; }}
            .matrix-dialog {{ width:100%; padding:9px; }}
            .matrix-title {{ font-size:17px; }}
            .quadrant-box {{ padding:7px; font-size:11px; }}
            .quadrant-title {{ font-size:12px; }}
            .task-pill {{ padding:5px; font-size:11px; }}
          }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def save_token(day: date):
    note, diet, quadrant, time_map, ui, extras = read_day(day)
    ui["TOKEN_LEVEL"] = f"{st.session_state.token * 16:.4f}"
    write_day(day, note, diet, quadrant, time_map, ui, extras)


def save_note_from_state(day: date):
    note, diet, quadrant, time_map, ui, extras = read_day(day)
    key = f"note-text-{day.isoformat()}"
    value = st.session_state.get(key, note)
    added = max(0, len(str(value)) - len(note))
    if added:
        add_token(added * st.session_state.type_token)
    ui["TOKEN_LEVEL"] = f"{st.session_state.token * 16:.4f}"
    write_day(day, value, diet, quadrant, time_map, ui, extras)
    st.session_state.last_saved = f"Auto-saved notes for {day:%Y-%m-%d}"


def save_diet_from_state(day: date):
    note, diet, quadrant, time_map, ui, extras = read_day(day)
    key = f"diet-text-{day.isoformat()}"
    value = st.session_state.get(key, diet)
    added = max(0, len(str(value)) - len(diet))
    if added:
        add_token(added * st.session_state.type_token)
    ui["TOKEN_LEVEL"] = f"{st.session_state.token * 16:.4f}"
    write_day(day, note, value, quadrant, time_map, ui, extras)
    st.session_state.last_saved = f"Auto-saved meal plan for {day:%Y-%m-%d}"


def save_schedule_from_state(day: date):
    note, diet, quadrant, time_map, ui, extras = read_day(day)
    new_time_map: dict[str, str] = {}
    for slot in time_slots():
        key = f"slot-{day}-{slot}"
        new_time_map[slot] = st.session_state.get(key, time_map.get(slot, ""))
    filled = sum(1 for value in new_time_map.values() if str(value).strip())
    ui["TOKEN_LEVEL"] = f"{st.session_state.token * 16:.4f}"
    write_day(day, note, diet, quadrant, new_time_map, ui, extras)
    st.session_state.last_saved = f"Auto-saved schedule for {day:%Y-%m-%d}"
    if filled:
        add_token(0.5 * min(1.0, filled / 24))


def set_panel(panel: str):
    st.session_state.panel = "" if st.session_state.panel == panel else panel
    add_token(st.session_state.click_token)


def load_quadrant_tasks(raw: str) -> list[dict]:
    if not raw.strip():
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [
                {
                    "text": str(item.get("text", "")).strip(),
                    "important": bool(item.get("important")),
                    "urgent": bool(item.get("urgent")),
                }
                for item in data
                if str(item.get("text", "")).strip()
            ]
    except json.JSONDecodeError:
        pass
    return [{"text": line.strip(), "important": False, "urgent": False} for line in raw.splitlines() if line.strip()]


def dump_quadrant_tasks(tasks: list[dict]) -> str:
    return json.dumps(tasks, ensure_ascii=False, indent=2)


def quadrant_name(task: dict) -> str:
    important = bool(task.get("important"))
    urgent = bool(task.get("urgent"))
    if important and urgent:
        return "Important and Urgent"
    if important and not urgent:
        return "Important, Not Urgent"
    if urgent and not important:
        return "Urgent, Not Important"
    return "Not Important or Urgent"


def render_month():
    today = now().date()
    year = int(st.session_state.view_year)
    month = int(st.session_state.view_month)
    if month == 1:
        prev_y, prev_m = year - 1, 12
    else:
        prev_y, prev_m = year, month - 1
    if month == 12:
        next_y, next_m = year + 1, 1
    else:
        next_y, next_m = year, month + 1

    st.markdown('<div class="month-wrap">', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="month-nav">
          <a class="month-arrow" href="?month={prev_y:04d}-{prev_m:02d}">&lsaquo;</a>
          <div class="month-title">{calendar.month_name[month]} {year}</div>
          <a class="month-arrow" href="?month={next_y:04d}-{next_m:02d}">&rsaquo;</a>
        </div>
        """,
        unsafe_allow_html=True,
    )

    html = ['<div class="calendar-grid">']
    for label in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
        html.append(f'<div class="week-label">{label}</div>')
    for week in calendar.monthcalendar(year, month):
        for day_num in week:
            if day_num == 0:
                html.append('<div class="calendar-cell empty"></div>')
                continue
            current = date(year, month, day_num)
            note, diet, quadrant, time_map, _ui, _extras = read_day(current)
            has_content = bool(note or diet or quadrant or any(value.strip() for value in time_map.values()))
            classes = ["calendar-cell"]
            if current == today:
                classes.append("today")
            if current.weekday() == 5:
                classes.append("sat")
            if current.weekday() == 6:
                classes.append("sun")
            if has_content:
                classes.append("has-content")
            today_label = '<span class="calendar-today-label">Today</span>' if current == today else ""
            content_mark = '<span class="content-mark"></span>' if has_content else ""
            html.append(
                f'<a class="{" ".join(classes)}" href="?day={current.isoformat()}">'
                f'<span class="calendar-date">{day_num}</span>{content_mark}{today_label}</a>'
            )
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def render_day_header(selected: date):
    st.markdown(
        f"""
        <div class="day-top">
          <div class="day-title">{selected:%Y-%m-%d} · {selected.strftime('%A')}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_day_header_clean(selected: date):
    st.markdown(
        f"""
        <div class="day-top">
          <div class="day-title">{selected:%Y-%m-%d} {selected.strftime('%A')}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_simple_topbar(selected: date):
    pct = int(st.session_state.token * 100)
    battery_class = "battery-wrap flash" if st.session_state.flash_battery else "battery-wrap"
    st.markdown(
        f"""
        <div class="simple-topbar">
          <a class="month-link" href="?month={selected.year:04d}-{selected.month:02d}">&larr; Month</a>
          <div class="topbar-right">
            <div class="{battery_class}">
              <div class="battery"><div class="battery-fill"></div></div>
              <div class="battery-label">{pct}%</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_day_progress(selected: date):
    _note, _diet, _quadrant, time_map, _ui, _extras = read_day(selected)
    current = now()
    if selected == current.date():
        pct = ((current.hour * 60) + current.minute) / (24 * 60) * 100
    elif selected < current.date():
        pct = 100
    else:
        pct = 0

    html = ['<div class="day-progress">']
    html.append('<div class="progress-line"></div>')
    html.append(f'<div class="progress-fill" style="width:{pct:.2f}%"></div>')
    for hour in range(24):
        left = hour / 24 * 100
        major = hour in {0, 6, 12, 18}
        html.append(f'<div class="tick {"major" if major else ""}" style="left:{left:.2f}%"></div>')
        if major:
            html.append(f'<div class="tick-label" style="left:{left:.2f}%">{hour:02d}</div>')

        slot = f"{natural_time(hour)} - {natural_time(hour + 1)}"
        text = escape(time_map.get(slot, "").strip() or "No task")
        pop_time = f"{hour:02d}:00 ~ {(hour + 1) % 24:02d}:00"
        html.append(
            f'<div class="hour-zone" style="left:{left:.2f}%; width:{100/24:.4f}%">'
            f'<div class="timeline-pop"><b>{pop_time}</b>{text}</div></div>'
        )
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def render_text_panel(selected: date, panel: str):
    note, diet, quadrant, time_map, ui, extras = read_day(selected)
    if panel == "note":
        st.markdown('<div class="panel-box">', unsafe_allow_html=True)
        value = st.text_area(
            "Today's Notes",
            value=note,
            height=260,
            key=f"note-text-{selected.isoformat()}",
            on_change=save_note_from_state,
            args=(selected,),
        )
        if st.button("Save Notes Now", key=f"save-note-{selected}", use_container_width=True):
            add_token(max(st.session_state.click_token, len(value) * st.session_state.type_token))
            ui["TOKEN_LEVEL"] = f"{st.session_state.token * 16:.4f}"
            write_day(selected, value, diet, quadrant, time_map, ui, extras)
            saved_note, _diet, _quad, _time, _ui, _extras = read_day(selected)
            if saved_note.strip() == value.strip():
                st.session_state.last_saved = f"Notes saved for {selected:%Y-%m-%d}"
            else:
                st.session_state.last_saved = "Save failed: notes were not written."
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    elif panel == "diet":
        st.markdown('<div class="panel-box">', unsafe_allow_html=True)
        value = st.text_area(
            "Meal Plan",
            value=diet,
            height=220,
            key=f"diet-text-{selected.isoformat()}",
            on_change=save_diet_from_state,
            args=(selected,),
        )
        if st.button("Save Meal Plan Now", key=f"save-diet-{selected}", use_container_width=True):
            add_token(max(st.session_state.click_token, len(value) * st.session_state.type_token))
            ui["TOKEN_LEVEL"] = f"{st.session_state.token * 16:.4f}"
            write_day(selected, note, value, quadrant, time_map, ui, extras)
            _note, saved_diet, _quad, _time, _ui, _extras = read_day(selected)
            if saved_diet.strip() == value.strip():
                st.session_state.last_saved = f"Meal plan saved for {selected:%Y-%m-%d}"
            else:
                st.session_state.last_saved = "Save failed: meal plan was not written."
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    elif panel == "quadrant":
        st.markdown('<div class="panel-box">', unsafe_allow_html=True)
        st.subheader("Today's Eisenhower Matrix")
        tasks = load_quadrant_tasks(quadrant)
        with st.form(f"quadrant-form-{selected}", clear_on_submit=True):
            task_text = st.text_input("Task", placeholder="Write one task")
            col_a, col_b = st.columns(2)
            important = col_a.toggle("Important")
            urgent = col_b.toggle("Urgent")
            submitted = st.form_submit_button("Add Task", use_container_width=True)
        if submitted and task_text.strip():
            tasks.append({"text": task_text.strip(), "important": important, "urgent": urgent})
            add_token(st.session_state.important_token)
            ui["TOKEN_LEVEL"] = f"{st.session_state.token * 16:.4f}"
            write_day(selected, note, diet, dump_quadrant_tasks(tasks), time_map, ui, extras)
            st.rerun()

        groups = {
            "Important and Urgent": [],
            "Important, Not Urgent": [],
            "Urgent, Not Important": [],
            "Not Important or Urgent": [],
        }
        for index, task in enumerate(tasks):
            groups[quadrant_name(task)].append((index, task))

        st.markdown('<div class="quadrant-grid">', unsafe_allow_html=True)
        for title, items in groups.items():
            st.markdown(f'<div class="quadrant-box"><div class="quadrant-title">{escape(title)}</div>', unsafe_allow_html=True)
            if not items:
                st.caption("Empty")
            for index, task in items:
                st.markdown(f'<div class="task-pill">{escape(task["text"])}</div>', unsafe_allow_html=True)
                if st.button("Done", key=f"done-{selected}-{index}", use_container_width=True):
                    tasks.pop(index)
                    add_token(st.session_state.important_token)
                    ui["TOKEN_LEVEL"] = f"{st.session_state.token * 16:.4f}"
                    write_day(selected, note, diet, dump_quadrant_tasks(tasks), time_map, ui, extras)
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)


def render_quadrant_dialog(selected: date):
    note, diet, quadrant, time_map, ui, extras = read_day(selected)
    tasks = load_quadrant_tasks(quadrant)
    groups = {
        "Important and Urgent": [],
        "Important, Not Urgent": [],
        "Urgent, Not Important": [],
        "Not Important or Urgent": [],
    }
    for index, task in enumerate(tasks):
        groups[quadrant_name(task)].append((index, task))

    cells = []
    for title, items in groups.items():
        task_html = "".join(
            f'<div class="task">? {escape(task["text"])}</div>' for _index, task in items
        ) or '<div class="empty">No tasks yet</div>'
        cells.append(f'<section><h3>{escape(title)}</h3>{task_html}</section>')

    components.html(
        f"""
        <div id="matrixModal">
          <div id="matrixHandle">
            <strong>Monthly Eisenhower Matrix</strong>
            <button id="hideMatrix" type="button">x</button>
          </div>
          <div class="matrixGrid">{''.join(cells)}</div>
        </div>
        <style>
          body {{ margin:0; background:transparent; font-family:Arial, sans-serif; color:#000; }}
          #matrixModal {{
            position:absolute; left:18px; top:8px; width:min(820px, calc(100vw - 36px));
            background:#fff; border:1px solid #fff; box-shadow:0 12px 28px rgba(60,50,35,.18);
            padding:12px; resize:both; overflow:auto; min-width:320px; min-height:260px;
          }}
          #matrixHandle {{
            display:flex; align-items:center; justify-content:space-between; cursor:move;
            padding:2px 0 10px; color:#000; user-select:none;
          }}
          #hideMatrix {{
            border:1px solid #eee; background:#fff; color:#000; width:30px; height:28px;
            cursor:pointer; font-weight:700;
          }}
          .matrixGrid {{
            display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:10px;
            aspect-ratio:1.6 / 1;
          }}
          section {{
            background:#fff; border:1px solid #f2f2f2; padding:12px; overflow:auto; color:#000;
          }}
          h3 {{ margin:0 0 10px; font-size:18px; line-height:1.1; color:#000; }}
          .task, .empty {{
            color:#000; background:#fff; border:1px solid #f4f4f4; padding:7px; margin:6px 0;
            font-size:15px;
          }}
          .empty {{ color:#555; }}
          @media (max-width: 640px) {{
            #matrixModal {{ left:6px; width:calc(100vw - 12px); min-width:280px; }}
            .matrixGrid {{ gap:6px; aspect-ratio:1 / 1.12; }}
            h3 {{ font-size:12px; }}
            .task, .empty {{ font-size:11px; padding:5px; }}
            section {{ padding:7px; }}
          }}
        </style>
        <script>
          const modal = document.getElementById('matrixModal');
          const handle = document.getElementById('matrixHandle');
          const hide = document.getElementById('hideMatrix');
          let drag = false, dx = 0, dy = 0;
          handle.addEventListener('pointerdown', (event) => {{
            drag = true;
            dx = event.clientX - modal.offsetLeft;
            dy = event.clientY - modal.offsetTop;
            handle.setPointerCapture(event.pointerId);
          }});
          handle.addEventListener('pointermove', (event) => {{
            if (!drag) return;
            modal.style.left = Math.max(0, event.clientX - dx) + 'px';
            modal.style.top = Math.max(0, event.clientY - dy) + 'px';
          }});
          handle.addEventListener('pointerup', () => drag = false);
          hide.addEventListener('click', () => modal.style.display = 'none');
        </script>
        """,
        height=430,
    )

    st.markdown('<div class="matrix-dialog">', unsafe_allow_html=True)
    head_cols = st.columns([0.9, 0.1])
    with head_cols[0]:
        st.markdown('<div class="matrix-title">Matrix Controls</div>', unsafe_allow_html=True)
    with head_cols[1]:
        if st.button("x", key="close-matrix", use_container_width=True):
            st.session_state.matrix_open = False
            st.rerun()
    with st.form(f"quadrant-dialog-form-{selected}", clear_on_submit=True):
        col_task, col_kind, col_add = st.columns([2.2, 1.25, 0.8])
        task_text = col_task.text_input("Task", placeholder="Write one task")
        quadrant_choice = col_kind.selectbox(
            "Quadrant",
            [
                "Important and Urgent",
                "Important, Not Urgent",
                "Urgent, Not Important",
                "Not Important or Urgent",
            ],
        )
        submitted = col_add.form_submit_button("Add Task", use_container_width=True)
    if submitted and task_text.strip():
        important = quadrant_choice in {"Important and Urgent", "Important, Not Urgent"}
        urgent = quadrant_choice in {"Important and Urgent", "Urgent, Not Important"}
        tasks.append({"text": task_text.strip(), "important": important, "urgent": urgent})
        add_token(st.session_state.important_token)
        ui["TOKEN_LEVEL"] = f"{st.session_state.token * 16:.4f}"
        write_day(selected, note, diet, dump_quadrant_tasks(tasks), time_map, ui, extras)
        st.rerun()

    task_options = [f'{idx + 1}. {task["text"]}' for idx, task in enumerate(tasks)]
    if task_options:
        done_choice = st.selectbox("Mark task done", task_options, key=f"done-choice-{selected}")
        if st.button("Done Selected Task", key=f"dialog-done-selected-{selected}", use_container_width=True):
            done_index = task_options.index(done_choice)
            tasks.pop(done_index)
            add_token(st.session_state.important_token)
            ui["TOKEN_LEVEL"] = f"{st.session_state.token * 16:.4f}"
            write_day(selected, note, diet, dump_quadrant_tasks(tasks), time_map, ui, extras)
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

def render_schedule(selected: date):
    note, diet, quadrant, time_map, ui, extras = read_day(selected)
    slots = time_slots()
    active_slot = current_slot() if selected == now().date() else ""
    changed: dict[str, str] = {}
    filled = 0

    for slot in slots:
        task_hint = time_map.get(slot, "").strip() or "No task in this time block."
        marker = " now" if slot == active_slot else ""
        slot_id = ' id="now-slot"' if slot == active_slot else ""
        row = st.columns([0.22, 0.78], gap="small")
        with row[0]:
            st.markdown(
                f'<div class="schedule-time-cell{marker}"{slot_id} title="{escape(task_hint)}">{escape(slot)}</div>',
                unsafe_allow_html=True,
            )
        with row[1]:
            value = st.text_area(
                f"{slot} plan",
                value=time_map.get(slot, ""),
                key=f"slot-{selected}-{slot}",
                height=68,
                label_visibility="collapsed",
                on_change=save_schedule_from_state,
                args=(selected,),
            )
        changed[slot] = value
        if value.strip():
            filled += 1

    if st.button("Save Schedule Now", use_container_width=True):
        add_token(0.5 * min(1.0, filled / 24))
        ui["TOKEN_LEVEL"] = f"{st.session_state.token * 16:.4f}"
        write_day(selected, note, diet, quadrant, changed, ui, extras)
        _note, _diet, _quad, saved_time, _ui, _extras = read_day(selected)
        expected = {slot: value for slot, value in changed.items() if value.strip()}
        actual = {slot: value for slot, value in saved_time.items() if value.strip()}
        if actual == expected:
            st.session_state.last_saved = f"Schedule saved for {selected:%Y-%m-%d}"
        else:
            st.session_state.last_saved = "Save failed: schedule was not written."
        st.rerun()


def render_day():
    selected = st.session_state.selected_day
    render_simple_topbar(selected)
    render_day_header_clean(selected)
    st.session_state.flash_battery = False

    render_day_progress(selected)

    if st.session_state.get("last_saved"):
        message = st.session_state.last_saved
        if str(message).startswith("Save failed"):
            st.error(message)
        else:
            st.success(message)

    cols = st.columns([1, 1, 1])
    if cols[0].button("Today's Notes", key="notes-btn", use_container_width=True):
        set_panel("note")
        st.rerun()
    if cols[1].button("Meal Plan", key="meal-btn", use_container_width=True):
        set_panel("diet")
        st.rerun()
    if cols[2].button("Monthly Matrix", key="monthly-matrix", use_container_width=True):
        st.session_state.matrix_open = True
        add_token(st.session_state.click_token)
        st.rerun()

    if st.session_state.matrix_open:
        render_quadrant_dialog(selected)

    if st.session_state.panel:
        render_text_panel(selected, st.session_state.panel)

    st.markdown('<div class="schedule-title">Daily Schedule (0:00 - 24:00)</div>', unsafe_allow_html=True)
    with st.container(height=610, border=False):
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
