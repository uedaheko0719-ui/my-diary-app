from __future__ import annotations

import calendar
import json
from html import escape
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


def open_day(day: date):
    st.session_state.selected_day = day
    st.session_state.view_year = day.year
    st.session_state.view_month = day.month
    st.session_state.view = "day"


def add_token(amount: float):
    if amount == 0:
        return
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
    if not params.get("day") and not params.get("month") and not params.get("matrix_done"):
        st.session_state.view = "month"

    if params.get("matrix_done") and params.get("day"):
        try:
            picked = date.fromisoformat(params["day"])
            task_index = int(params["matrix_done"])
            note, diet, quadrant, time_map, ui, extras = read_day(picked)
            tasks = load_quadrant_tasks(quadrant)
            if 0 <= task_index < len(tasks):
                tasks.pop(task_index)
                add_token(st.session_state.important_token)
                ui["TOKEN_LEVEL"] = f"{st.session_state.token * 16:.4f}"
                write_day(picked, note, diet, dump_quadrant_tasks(tasks), time_map, ui, extras)
            st.session_state.selected_day = picked
            st.session_state.view_year = picked.year
            st.session_state.view_month = picked.month
            st.session_state.view = "day"
            st.session_state.matrix_open = True
            st.query_params.clear()
        except (ValueError, TypeError):
            st.query_params.clear()

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
            if params.get("matrix") == "open":
                st.session_state.matrix_open = True
            st.query_params.clear()
        except ValueError:
            st.query_params.clear()

    if "loaded_token" not in st.session_state:
        st.session_state.token = 0.0
        st.session_state.loaded_token = True


def css():
    battery_class = "battery-wrap flash" if st.session_state.flash_battery else "battery-wrap"
    st.markdown(
        f"""
        <style>
          :root {{
            --paper:#fbf4e4;
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
          .block-container {{ max-width:1220px; padding:8px 18px 12px; }}
          .simple-topbar {{
            display:flex; align-items:center; justify-content:space-between;
            gap:12px; min-height:34px;
          }}
          .month-link {{
            display:inline-flex; align-items:center; justify-content:center; min-height:30px;
            padding:0 12px; border:1px solid #e3d8c5; background:#fffdf8;
            color:#000; text-decoration:none; font-weight:700; box-shadow:none;
            font-size:13px; border-radius:2px;
          }}
          .month-link:hover {{
            background:#fff; border-color:#bca98c;
            transform:translateY(-2px);
            box-shadow:0 8px 18px rgba(60,50,35,.18);
          }}
          .month-link, .calendar-cell, div.stButton > button, [data-testid="stCheckbox"], textarea, input, .battery {{
            transition:background .14s ease, transform .14s ease, box-shadow .14s ease, border-color .14s ease, filter .14s ease;
          }}
          a, button, label, input, textarea,
          [role="button"], [data-baseweb="checkbox"], [data-baseweb="input"], [data-baseweb="textarea"],
          [data-testid="stCheckbox"], [data-testid="stTextInput"], [data-testid="stTextArea"],
          [data-testid="stFormSubmitButton"] button {{
            transition:background .14s ease, transform .14s ease, box-shadow .14s ease, border-color .14s ease, filter .14s ease !important;
          }}
          a:hover, button:hover, [role="button"]:hover,
          [data-baseweb="checkbox"]:hover, [data-testid="stCheckbox"]:hover,
          [data-testid="stFormSubmitButton"] button:hover {{
            transform:translateY(-2px) !important;
            filter:brightness(1.04) !important;
            box-shadow:0 7px 18px rgba(60,50,35,.18) !important;
            cursor:pointer !important;
          }}
          label:hover {{
            cursor:pointer !important;
          }}
          input:hover, textarea:hover,
          [data-baseweb="input"]:hover, [data-baseweb="textarea"]:hover,
          [data-testid="stTextInput"]:hover, [data-testid="stTextArea"]:hover {{
            filter:brightness(1.015) !important;
            box-shadow:0 1px 4px rgba(60,50,35,.06) !important;
            border-color:#c9bda6 !important;
          }}
          [data-testid="stButton"] button:hover,
          [data-testid="baseButton-secondary"]:hover,
          [data-testid="baseButton-primary"]:hover,
          [data-testid="stLinkButton"] a:hover {{
            background:#fff8eb !important;
            border-color:#c9bda6 !important;
            transform:translateY(-2px) scale(1.012) !important;
            box-shadow:0 8px 20px rgba(60,50,35,.20) !important;
          }}
          [data-testid="stCheckbox"] label:hover,
          [data-testid="stCheckbox"] label:hover div {{
            background:#fff8eb !important;
          }}
          [data-testid="stCheckbox"] label:hover span {{
            color:#000 !important;
          }}
          .topbar-right {{ display:flex; align-items:center; gap:14px; }}
          .compact-action-row [data-testid="stHorizontalBlock"] {{
            flex-wrap:nowrap !important;
            gap:8px !important;
          }}
          .compact-action-row [data-testid="column"] {{
            min-width:0 !important;
            flex:1 1 0 !important;
          }}
          .html-btn {{ display:flex; align-items:center; justify-content:center; min-height:38px; border:1px solid #e3d8c5; color:#000; text-decoration:none; font-weight:700; box-shadow:none; font-size:15px; white-space:nowrap; background:#fffdf8; }}
          .html-btn:hover {{
            filter:brightness(1.04); background:#fff;
            transform:translateY(-2px);
            border-color:#bca98c;
            box-shadow:0 8px 18px rgba(60,50,35,.18);
          }}
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
            border:1px solid #e3d8c5; background:#fffdf8; border-radius:2px;
            text-decoration:none; color:var(--ink); font-size:22px; transition:background .12s ease, border-color .12s ease;
          }}
          .month-arrow:hover {{
            background:#fff; border-color:#bca98c;
            transform:translateY(-2px);
            box-shadow:0 8px 18px rgba(60,50,35,.18);
          }}
          .calendar-grid {{
            display:grid; grid-template-columns:repeat(7, minmax(0, 1fr)); gap:8px;
          }}
          .week-label {{ color:#000; font-weight:700; text-align:center; padding-bottom:16px; font-size:18px; }}
          div.stButton > button {{
            border-radius:2px !important; border:1px solid #e3d8c5 !important; background:#fffdf8 !important;
            color:#000 !important; min-height:34px; transition:background .12s ease, border-color .12s ease, box-shadow .12s ease;
            font-weight:650; box-shadow:none; font-family:Arial, sans-serif;
            font-size:15px !important;
          }}
          div.stButton > button p, div.stButton > button span {{
            color:#000 !important;
          }}
          div.stButton > button:hover {{
            background:#fff !important; border-color:#bca98c !important;
            box-shadow:0 8px 20px rgba(60,50,35,.20) !important;
            transform:translateY(-2px) scale(1.012) !important;
          }}
          div.stButton > button:active {{
            border-style:inset !important; transform:translateY(1px); box-shadow:none;
          }}
          .calendar-cell {{
            display:flex; align-items:center; justify-content:center; gap:5px;
            min-height:88px; border:1px solid #eee4d3; background:#fffefa;
            border-radius:0; padding:9px; font-size:20px; font-weight:500;
            text-decoration:none; color:var(--ink); transition:background .12s ease, transform .12s ease, border-color .12s ease;
          }}
          .calendar-cell:hover {{
            background:#fff; border-color:#bca98c;
            transform:translateY(-2px);
            box-shadow:0 9px 20px rgba(60,50,35,.16);
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
          .calendar-button-empty {{
            min-height:88px;
            border:1px solid transparent;
            opacity:.15;
          }}
          [class*="st-key-day-cell-"] button {{
            min-height:88px !important;
            border:1px solid #eee4d3 !important;
            background:#fffefa !important;
            border-radius:0 !important;
            font-size:18px !important;
            font-weight:500 !important;
            color:#000 !important;
            white-space:pre-line !important;
            padding:4px !important;
          }}
          [class*="st-key-day-cell-"] button:hover {{
            background:#fff !important;
            border-color:#bca98c !important;
            transform:translateY(-2px) !important;
            box-shadow:0 9px 20px rgba(60,50,35,.16) !important;
          }}
          .calendar-date {{ display:block; }}
          .calendar-today-label {{ display:block; color:var(--red); font-size:11px; margin-top:4px; }}
          .day-top {{
            display:flex; align-items:center; justify-content:center;
            gap:8px; padding-bottom:0; margin-bottom:2px;
          }}
          .day-title {{ font-size:26px; font-weight:800; text-align:center; color:#000; margin:8px 0 10px; }}
          .right-tools {{ display:flex; align-items:center; gap:12px; }}
          .battery-wrap {{ display:flex; align-items:center; gap:8px; }}
          .battery {{
            width:168px; height:22px; border:1px solid #25372e; border-radius:0;
            background:#fffefa; padding:3px; position:relative; box-shadow:none;
            display:grid; grid-template-columns:repeat(4, 1fr); gap:3px;
          }}
          .battery:hover {{
            box-shadow:0 0 0 2px rgba(53,168,104,.16), 0 8px 18px rgba(53,168,104,.18);
            filter:brightness(1.05);
            transform:translateY(-2px);
          }}
          .battery:after {{
            content:""; position:absolute; right:-7px; top:6px; width:5px; height:9px;
            border:1px solid #25372e; border-left:0; border-radius:0; background:#fffefa;
          }}
          .battery-cell {{
            height:100%; background:linear-gradient(90deg, var(--green) 0 var(--fill, 0%), #fffefa var(--fill, 0%) 100%);
            border:1px solid rgba(37,55,46,.14);
            transition:background .16s ease, filter .14s ease;
          }}
          .flash .battery {{
            animation:batteryShellFlash .42s ease-out;
          }}
          .flash .battery-cell {{
            animation:batteryWhite .42s ease-out;
          }}
          @keyframes batteryShellFlash {{
            0% {{ box-shadow:0 0 0 0 rgba(53,168,104,.0); filter:brightness(1); }}
            35% {{ box-shadow:0 0 0 4px rgba(53,168,104,.35), 0 0 22px rgba(53,168,104,.42); filter:brightness(1.2); }}
            100% {{ box-shadow:none; filter:brightness(1); }}
          }}
          @keyframes batteryWhite {{
            0% {{ filter:brightness(1); }}
            35% {{ filter:brightness(1.65); }}
            100% {{ filter:brightness(1); }}
          }}
          .battery-label {{ min-width:32px; font-size:11px; font-weight:700; }}
          .tool-row {{ display:flex; gap:14px; margin:20px 0 14px; flex-wrap:wrap; }}
          .schedule-title {{ font-size:18px; font-weight:800; margin:14px 0 8px; color:#000; }}
          [data-testid="stVerticalBlock"] {{ gap:.55rem !important; }}
          [data-testid="stTextArea"] {{ margin:0 !important; }}
          .day-head {{
            position:relative; background:var(--paper);
            padding:2px 0 8px; border-bottom:1px solid rgba(238,231,218,.9);
            box-shadow:0 6px 14px rgba(80,70,48,.07);
          }}
          [data-testid="stElementContainer"]:has(.day-head),
          [data-testid="stMarkdown"]:has(.day-head) {{
            position:sticky !important;
            top:0 !important;
            z-index:1000 !important;
            background:var(--paper) !important;
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
            max-width:180px !important;
            margin:0 auto !important;
            background:#fffdf8 !important;
            border-color:#e3d8c5 !important;
          }}
          .action-btn {{ display:flex; align-items:center; justify-content:center; min-height:46px; border:1px solid #e3d8c5; background:#fffdf8; color:#000; text-decoration:none; font-weight:700; font-size:16px; box-shadow:none; }}
          .action-btn:hover {{
            background:#fff;
            transform:translateY(-2px);
            border-color:#bca98c;
            box-shadow:0 8px 18px rgba(60,50,35,.18);
          }}
          .action-btn:active {{ border-style:inset; box-shadow:none; transform:translateY(1px); }}
          .st-key-monthly-matrix button {{ font-size:15px !important; }}
          .panel-box {{
            border:1px solid #eee4d3; background:var(--softbox); border-radius:2px;
            padding:12px; margin:8px 0 12px;
            color:#000;
          }}
          .day-progress {{
            position:relative; height:76px; margin:0; overflow:visible;
          }}
          .timeline-sticky {{
            background:var(--paper);
            padding:3px 0 2px;
            border-bottom:0;
            box-shadow:none;
          }}
          .day-actions {{
            margin-top:30px;
          }}
          .action-link-grid {{
            display:grid;
            grid-template-columns:repeat(3, minmax(0, 1fr));
            gap:10px;
            margin-top:30px;
          }}
          .day-action-link {{
            display:flex;
            align-items:center;
            justify-content:center;
            min-height:36px;
            border:1px solid #e3d8c5;
            background:#fffdf8;
            color:#000 !important;
            text-decoration:none !important;
            font-size:15px;
            font-weight:650;
            box-sizing:border-box;
            white-space:nowrap;
          }}
          .day-action-link:hover {{
            background:#fff;
            border-color:#bca98c;
            transform:translateY(-2px);
            box-shadow:0 8px 20px rgba(60,50,35,.20);
          }}
          .progress-line {{
            display:none;
            position:absolute; left:0; right:0; top:34px; height:18px;
            background:#fffefa;
            border:1px solid rgba(37,55,46,.14);
            box-shadow:inset 0 0 0 1px rgba(255,255,255,.72), 0 7px 16px rgba(60,50,35,.07);
          }}
          .progress-fill {{
            display:none;
            position:absolute; left:0; top:35px; height:16px;
            background:var(--green);
            box-shadow:0 0 14px rgba(53,168,104,.25);
          }}
          .tick {{
            display:none;
          }}
          .time-battery {{
            position:absolute; left:0; right:0; top:34px; height:22px;
            display:grid; grid-template-columns:repeat(24, minmax(0, 1fr)); gap:3px;
            padding:3px; border:1px solid rgba(37,55,46,.16);
            background:#fffefa;
            box-shadow:inset 0 0 0 1px rgba(255,255,255,.72), 0 7px 16px rgba(60,50,35,.07);
          }}
          .timeline-scroll {{
            width:100%;
            overflow-x:auto;
            overflow-y:visible;
            scroll-snap-type:x mandatory;
            scrollbar-width:thin;
            overscroll-behavior-x:contain;
          }}
          .timeline-track {{
            display:grid;
            grid-template-columns:repeat(3, 100%);
            width:300%;
          }}
          .timeline-panel {{
            position:relative;
            scroll-snap-align:start;
            padding:0 1px;
          }}
          .timeline-panel-link {{
            display:block;
            color:inherit !important;
            text-decoration:none !important;
          }}
          .time-cell.yesterday {{
            background:linear-gradient(90deg, var(--red) 0 var(--fill, 0%), rgba(201,74,58,.10) var(--fill, 0%) 100%);
          }}
          .time-cell.tomorrow {{
            background:#fffefa;
          }}
          .time-cell {{
            position:relative;
            background:linear-gradient(90deg, var(--green) 0 var(--fill, 0%), rgba(53,168,104,.10) var(--fill, 0%) 100%);
            border:1px solid rgba(37,55,46,.10);
            min-width:0;
            transition:filter .14s ease, box-shadow .14s ease, transform .14s ease, border-color .14s ease;
          }}
          .time-cell:hover {{
            filter:brightness(1.05);
            transform:translateY(-2px);
            border-color:rgba(53,168,104,.38);
            box-shadow:0 0 0 1px rgba(53,168,104,.18), 0 7px 16px rgba(53,168,104,.16);
            z-index:3;
          }}
          .time-cell:hover .timeline-pop {{ display:block; }}
          .tick.major {{ display:block; position:absolute; top:26px; width:1px; height:38px; background:#222; opacity:.22; }}
          .tick-label {{
            position:absolute; top:0; transform:translateX(-50%); font-size:14px; font-weight:800; color:#000;
          }}
          .tick-label.end {{ transform:translateX(-100%); }}
          .tick.major.end {{ transform:translateX(-1px); }}
          .hour-zone {{
            display:none;
            position:absolute; top:24px; height:36px;
          }}
          .hour-zone:hover .timeline-pop {{ display:block; }}
          .hour-zone:hover {{
            background:rgba(53,168,104,.20);
            box-shadow:0 0 0 1px rgba(53,168,104,.24), 0 0 14px rgba(53,168,104,.15);
          }}
          .timeline-pop {{
            display:none; position:absolute; top:36px; left:50%; transform:translateX(-50%);
            width:190px; min-height:76px; background:#fffefa; border:1px solid #d8cbb6;
            padding:10px; z-index:50; font-size:15px; white-space:pre-wrap; color:#000;
            box-shadow:0 4px 12px rgba(80,70,48,.08);
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
          .schedule-time-cell:hover {{
            background:#fff8eb;
            transform:translateY(-1px);
            box-shadow:0 5px 12px rgba(60,50,35,.12);
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
            box-shadow:0 4px 12px rgba(47,42,34,.08); font-weight:500;
          }}
          .slot-time:hover .slot-task {{ display:block; }}
          .back-arrow {{
            display:inline-flex; align-items:center; justify-content:center; width:42px; height:38px;
            border:1px solid var(--line); border-radius:7px; background:var(--panel); font-size:22px;
          }}
          .matrix-dialog {{
            width:min(900px, 100%); overflow:auto; background:rgba(255,253,248,.42);
            border:1px solid rgba(216,203,182,.65); box-shadow:0 6px 16px rgba(60,50,35,.06);
            padding:12px; margin:14px auto 12px; color:#000; border-radius:2px;
          }}
          .matrix-header {{
            display:flex; align-items:center; justify-content:space-between;
            gap:10px; margin-bottom:8px;
          }}
          .matrix-title {{
            font-size:16px; font-weight:800; color:#000; margin:0;
            text-transform:lowercase; letter-spacing:0;
          }}
          .matrix-dialog [data-testid="stForm"] {{
            background:#fffefa !important;
            border:1px solid rgba(216,203,182,.72) !important;
            padding:8px 10px !important;
            border-radius:2px !important;
            margin-bottom:12px !important;
          }}
          .matrix-dialog [data-testid="stVerticalBlockBorderWrapper"] {{
            background:#fff !important;
            border:1px solid #d8cbb6 !important;
            box-shadow:0 4px 14px rgba(60,50,35,.08) !important;
            min-height:156px !important;
            border-radius:2px !important;
          }}
          .matrix-dialog [data-testid="stVerticalBlockBorderWrapper"]:hover {{
            border-color:#bba98d !important;
            box-shadow:0 9px 22px rgba(60,50,35,.16) !important;
            transform:translateY(-2px);
          }}
          .quadrant-title-bar {{
            font-size:15px; font-weight:800; color:#000;
            padding-bottom:8px; margin-bottom:8px;
            border-bottom:1px solid #eadfce;
          }}
          .matrix-dialog [data-testid="stCaptionContainer"] {{
            color:#6f6a60 !important;
          }}
          .matrix-form-panel {{
            padding:0;
            margin:0;
            background:transparent;
          }}
          .matrix-flags {{
            display:flex;
            gap:8px;
            margin:2px 0 8px;
          }}
          [data-testid="stVerticalBlockBorderWrapper"] {{
            background:#fff !important;
            border:1px solid #d8cbb6 !important;
            box-shadow:0 4px 14px rgba(60,50,35,.08) !important;
            border-radius:2px !important;
          }}
          [data-testid="stVerticalBlockBorderWrapper"]:hover {{
            border-color:#bba98d !important;
            box-shadow:0 9px 22px rgba(60,50,35,.16) !important;
            transform:translateY(-2px);
          }}
          [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stMarkdownContainer"],
          [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stMarkdownContainer"] * {{
            background:transparent !important;
          }}
          .quadrant-grid {{
            display:grid !important; grid-template-columns:repeat(2, minmax(0, 1fr)) !important; gap:12px;
            aspect-ratio:1.65 / 1; color:#000;
          }}
          .matrix-html-grid {{
            display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:12px;
            margin-top:8px;
          }}
          .matrix-html-box {{
            background:#fff;
            border:1px solid #d8cbb6;
            min-height:132px;
            padding:12px;
            box-shadow:0 3px 10px rgba(60,50,35,.06);
            border-radius:2px;
          }}
          .matrix-html-box:hover {{
            border-color:#bba98d;
            box-shadow:0 9px 22px rgba(60,50,35,.16);
            transform:translateY(-2px);
          }}
          .matrix-empty {{
            color:#6f6a60;
            font-size:13px;
            padding-top:2px;
          }}
          .matrix-task {{
            display:flex; align-items:center; gap:8px;
            background:#fff;
            border:1px solid #eadfce;
            padding:8px 9px;
            margin:6px 0;
            color:#000 !important;
            text-decoration:none !important;
            font-size:15px;
            line-height:1.25;
          }}
          .matrix-task:hover {{
            background:#fff8eb;
            border-color:#bca98c;
            box-shadow:0 7px 18px rgba(60,50,35,.16);
            transform:translateY(-2px);
          }}
          .matrix-task-check {{
            width:14px; min-width:14px; height:14px;
            border:1px solid #111;
            background:#fff;
            display:inline-block;
          }}
          .quadrant-box {{
            border:1px solid #eee4d3; background:#fff; border-radius:2px; padding:12px;
            min-height:150px; overflow:auto; color:#000;
          }}
          .quadrant-title {{ font-weight:800; margin-bottom:8px; color:#000; font-size:17px; line-height:1.1; }}
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
          [data-testid="stCheckbox"] {{
            background:#fff !important;
            border:1px solid #eadfce !important;
            padding:6px 8px !important;
            margin:4px 0 !important;
          }}
          [data-testid="stCheckbox"] label,
          [data-testid="stCheckbox"] label > div,
          [data-testid="stCheckbox"] label span,
          [data-testid="stCheckbox"] [data-testid="stMarkdownContainer"],
          [data-testid="stCheckbox"] [data-testid="stMarkdownContainer"] * {{
            background:#fff !important;
          }}
          [data-testid="stCheckbox"]:hover {{
            background:#fff8eb !important;
            border-color:#bca98c !important;
            box-shadow:0 7px 18px rgba(60,50,35,.16) !important;
            transform:translateY(-2px);
          }}
          [data-testid="stCheckbox"] svg {{
            color:#000 !important;
            fill:#000 !important;
          }}
          label, p, span, div {{
            color:inherit;
          }}
          .stTextArea textarea, .stTextInput input {{
            color:#000 !important;
            background:#fff !important;
          }}
          .stTextArea textarea:hover, .stTextInput input:hover,
          [data-baseweb="input"]:hover, [data-baseweb="textarea"]:hover {{
            border-color:#cfc1aa !important;
            box-shadow:0 1px 4px rgba(60,50,35,.06) !important;
          }}
          [data-testid="stFormSubmitButton"] button {{
            background:#fffdf8 !important;
            color:#000 !important;
            border:1px solid #e3d8c5 !important;
            box-shadow:none !important;
          }}
          [data-testid="stFormSubmitButton"] button p,
          [data-testid="stFormSubmitButton"] button span {{
            color:#000 !important;
          }}
          [data-testid="stForm"] {{
            background:transparent !important;
            border:1px solid #eadfce !important;
            padding:10px !important;
            border-radius:2px !important;
          }}
          @media (max-width: 760px) {{
            html, body, .stApp {{
              overflow-x:hidden !important;
            }}
            .block-container {{
              width:760px !important;
              max-width:760px !important;
              min-width:760px !important;
              padding:8px 14px 12px !important;
              transform:scale(.98);
              transform-origin:top left;
            }}
            .compact-action-row [data-testid="stHorizontalBlock"] {{ flex-wrap:nowrap !important; gap:4px !important; }}
            .compact-action-row [data-testid="column"] {{ min-width:0 !important; flex:1 1 0 !important; }}
            .html-btn {{ min-height:32px; font-size:11px; padding:0 3px; }}
            .compact-action-row [data-testid="stHorizontalBlock"] {{ gap:4px !important; }}
            .simple-topbar {{ min-height:24px; gap:6px; }}
            .day-head {{ top:0; padding:1px 0 5px; }}
            .schedule-scroll {{ height:calc(100vh - 172px); min-height:360px; }}
            .topbar-right {{ gap:8px; }}
            .battery {{ width:104px; height:16px; gap:2px; padding:2px; }}
            .battery:after {{ right:-6px; top:4px; width:4px; height:8px; }}
            .battery-label {{ font-size:9px; min-width:28px; }}
            .month-link {{ min-height:24px; padding:0 6px; font-size:10px; }}
            .calendar-grid {{ gap:4px; }}
            .calendar-cell {{ min-height:54px; padding:4px; font-size:14px; }}
            .content-mark {{ width:9px; height:13px; box-shadow:1px 1px 0 #c8bda7; }}
            .week-label {{ font-size:11px; }}
            .month-title {{ font-size:21px; }}
            .day-progress {{ height:42px; }}
            .timeline-sticky {{ padding:2px 0 3px; }}
            .time-battery {{ top:22px; height:16px; gap:1px; padding:2px; }}
            .tick.major {{ top:17px; height:26px; opacity:.22; }}
            .tick-label {{ top:0; font-size:10px; }}
            .day-actions {{ margin-top:12px; }}
            .st-key-notes-btn button,
            .st-key-meal-btn button,
            .st-key-monthly-matrix button {{
              min-height:30px !important;
              max-width:none !important;
              font-size:11px !important;
              padding:0 4px !important;
            }}
            .timeline-pop {{ width:150px; font-size:13px; }}
            .slot {{ grid-template-columns:86px minmax(0, 1fr); gap:6px; }}
            .slot-time {{ font-size:11px; }}
            .day-title {{ font-size:16px; margin:3px 0 3px; line-height:1.15; }}
            .day-top {{ align-items:center; flex-direction:row; }}
            .quadrant-grid {{ grid-template-columns:repeat(2, minmax(0, 1fr)) !important; gap:6px; aspect-ratio:1 / 1.08; }}
            .matrix-html-grid {{ grid-template-columns:repeat(2, minmax(0, 1fr)); gap:6px; }}
            .matrix-html-box {{ min-height:126px; padding:8px; }}
            .matrix-task {{ padding:6px; font-size:11px; }}
            .matrix-dialog {{ width:100%; padding:9px; }}
            .matrix-title {{ font-size:14px; }}
            .quadrant-box {{ padding:7px; font-size:11px; }}
            .quadrant-title {{ font-size:12px; }}
            .task-pill {{ padding:5px; font-size:11px; }}
          }}
          @media (max-width: 680px) {{
            .block-container {{ transform:scale(.89); }}
          }}
          @media (max-width: 600px) {{
            .block-container {{ transform:scale(.79); }}
          }}
          @media (max-width: 520px) {{
            .block-container {{ transform:scale(.68); }}
          }}
          @media (max-width: 430px) {{
            .block-container {{
              width:760px !important;
              max-width:760px !important;
              min-width:760px !important;
              padding:8px 14px 12px !important;
              transform:scale(.56);
              transform-origin:top left;
            }}
            .simple-topbar {{ min-height:22px; }}
            .month-link {{ min-height:22px; font-size:9px; padding:0 5px; }}
            .battery {{ width:82px; height:14px; gap:1px; padding:2px; }}
            .battery-label {{ font-size:8px; min-width:22px; }}
            .day-title {{ font-size:13px; margin:2px 0; }}
            .day-progress {{ height:34px; }}
            .time-battery {{ top:18px; height:13px; gap:1px; padding:1px; }}
            .tick.major {{ top:14px; height:20px; width:1px; }}
            .tick-label {{ font-size:8px; }}
            .day-actions {{ margin-top:8px; }}
            .st-key-notes-btn button,
            .st-key-meal-btn button,
            .st-key-monthly-matrix button {{
              min-height:26px !important;
              font-size:9px !important;
              padding:0 2px !important;
            }}
            .slot {{ grid-template-columns:70px minmax(0, 1fr); gap:4px; }}
            .schedule-time-cell {{ font-size:9px; padding:11px 3px 0 5px; }}
            .schedule-title {{ font-size:14px; margin:9px 0 5px; }}
            .matrix-title {{ font-size:12px; }}
            .matrix-dialog {{ padding:8px; }}
            .matrix-header {{ margin-bottom:6px; }}
            .matrix-flags {{ gap:5px; }}
            .quadrant-title-bar {{ font-size:11px; padding-bottom:5px; margin-bottom:5px; }}
            .matrix-html-box {{ min-height:96px; padding:6px; }}
            .matrix-task {{ font-size:9px; padding:5px; gap:5px; }}
            .matrix-task-check {{ width:11px; min-width:11px; height:11px; }}
          }}
          @media (max-width: 760px) {{
            .simple-topbar {{ min-height:34px; gap:12px; }}
            .day-head {{ padding:2px 0 8px; }}
            .battery {{ width:168px; height:22px; gap:3px; padding:3px; }}
            .battery:after {{ right:-7px; top:6px; width:5px; height:9px; }}
            .battery-label {{ font-size:11px; min-width:32px; }}
            .month-link {{ min-height:30px; padding:0 12px; font-size:13px; }}
            .day-title {{ font-size:26px; margin:8px 0 10px; line-height:normal; }}
            .day-progress {{ height:76px; }}
            .timeline-sticky {{ padding:3px 0 2px; }}
            .time-battery {{ top:34px; height:22px; gap:3px; padding:3px; }}
            .tick.major {{ top:26px; height:38px; width:1px; }}
            .tick-label {{ top:0; font-size:14px; }}
            .day-actions {{ margin-top:30px; }}
            .st-key-notes-btn button,
            .st-key-meal-btn button,
            .st-key-monthly-matrix button {{
              min-height:36px !important;
              max-width:180px !important;
              font-size:15px !important;
              padding:0 8px !important;
            }}
            .slot {{ grid-template-columns:190px 1fr; gap:12px; }}
            .schedule-time-cell {{ font-size:inherit; padding:14px 8px 0 10px; }}
            .schedule-title {{ font-size:15px; margin:10px 0 6px; }}
            .matrix-html-grid {{ grid-template-columns:repeat(2, minmax(0, 1fr)); gap:12px; }}
            .matrix-html-box {{ min-height:132px; padding:12px; }}
            .matrix-task {{ font-size:15px; padding:8px 9px; gap:8px; }}
            .matrix-task-check {{ width:14px; min-width:14px; height:14px; }}
          }}
          @media (max-width: 680px) {{
            .block-container {{ transform:scale(.89); }}
          }}
          @media (max-width: 600px) {{
            .block-container {{ transform:scale(.79); }}
          }}
          @media (max-width: 520px) {{
            .block-container {{ transform:scale(.68); }}
          }}
          @media (max-width: 430px) {{
            .block-container {{ transform:scale(.56); }}
          }}
          @media (max-width: 760px) {{
            html, body, .stApp {{
              overflow-x:hidden !important;
            }}
            .block-container {{
              width:100% !important;
              min-width:0 !important;
              max-width:100% !important;
              transform:none !important;
              transform-origin:initial !important;
              padding:8px 10px 12px !important;
              box-sizing:border-box !important;
            }}
            .month-wrap {{
              width:100% !important;
              max-width:100% !important;
              margin:0 auto !important;
              overflow:visible !important;
            }}
            .month-nav {{
              grid-template-columns:38px minmax(0, 1fr) 38px !important;
              gap:6px !important;
              margin:10px 0 10px !important;
              width:100% !important;
            }}
            .month-arrow {{
              height:34px !important;
              font-size:18px !important;
            }}
            .month-title {{
              font-size:20px !important;
              text-align:center !important;
              white-space:nowrap !important;
            }}
            .calendar-grid {{
              width:100% !important;
              grid-template-columns:repeat(7, minmax(0, 1fr)) !important;
              gap:3px !important;
            }}
            .week-label {{
              font-size:10px !important;
              padding-bottom:5px !important;
              min-width:0 !important;
            }}
            .calendar-cell {{
              min-height:0 !important;
              aspect-ratio:1 / 1 !important;
              padding:2px !important;
              font-size:12px !important;
              gap:2px !important;
              min-width:0 !important;
              overflow:hidden !important;
              box-sizing:border-box !important;
            }}
            .content-mark {{
              width:7px !important;
              height:10px !important;
              box-shadow:none !important;
            }}
            .calendar-today-label {{
              display:none !important;
            }}
            .calendar-button-empty {{
              min-height:0 !important;
              aspect-ratio:1 / 1 !important;
            }}
            [class*="st-key-day-cell-"] button {{
              min-height:0 !important;
              aspect-ratio:1 / 1 !important;
              font-size:10px !important;
              padding:1px !important;
              line-height:1.05 !important;
            }}
          }}
          @media (max-width: 760px) {{
            .block-container:has(.day-head) {{
              width:100% !important;
              min-width:0 !important;
              max-width:100% !important;
              padding:8px 10px 12px !important;
              transform:none !important;
              box-sizing:border-box !important;
            }}
            .block-container:has(.day-head) .simple-topbar {{
              min-height:26px !important;
              gap:6px !important;
            }}
            .block-container:has(.day-head) .month-link {{
              min-height:24px !important;
              padding:0 7px !important;
              font-size:11px !important;
            }}
            .block-container:has(.day-head) .battery {{
              width:116px !important;
              height:16px !important;
              gap:2px !important;
              padding:2px !important;
            }}
            .block-container:has(.day-head) .battery:after {{
              right:-6px !important;
              top:4px !important;
              width:4px !important;
              height:8px !important;
            }}
            .block-container:has(.day-head) .battery-label {{
              font-size:9px !important;
              min-width:24px !important;
            }}
            .block-container:has(.day-head) .day-title {{
              font-size:18px !important;
              margin:5px 0 4px !important;
              line-height:1.15 !important;
              white-space:nowrap !important;
            }}
            .block-container:has(.day-head) .day-progress {{
              height:44px !important;
            }}
            .block-container:has(.day-head) .time-battery {{
              top:23px !important;
              height:15px !important;
              gap:1px !important;
              padding:2px !important;
            }}
            .block-container:has(.day-head) .tick.major {{
              top:18px !important;
              height:24px !important;
              opacity:.2 !important;
            }}
            .block-container:has(.day-head) .tick-label {{
              font-size:10px !important;
            }}
            .block-container:has(.day-head) .day-actions {{
              margin-top:12px !important;
            }}
            .block-container:has(.day-head) .action-link-grid {{
              gap:5px !important;
              margin-top:12px !important;
            }}
            .block-container:has(.day-head) .day-action-link {{
              min-height:26px !important;
              font-size:10px !important;
              padding:0 2px !important;
            }}
            .block-container:has(.day-head) .st-key-notes-btn button,
            .block-container:has(.day-head) .st-key-meal-btn button,
            .block-container:has(.day-head) .st-key-monthly-matrix button {{
              min-height:26px !important;
              max-width:none !important;
              font-size:10px !important;
              padding:0 2px !important;
            }}
            .block-container:has(.day-head) .schedule-time-cell {{
              font-size:10px !important;
              padding:10px 3px 0 4px !important;
              min-height:54px !important;
              line-height:1.15 !important;
              overflow-wrap:anywhere !important;
            }}
            .block-container:has(.day-head) .schedule-title {{
              font-size:15px !important;
              margin:10px 0 5px !important;
              line-height:1.1 !important;
            }}
            .block-container:has(.day-head) textarea {{
              min-width:0 !important;
              height:52px !important;
              min-height:52px !important;
            }}
            .block-container:has(.day-head) [data-testid="stTextArea"] {{
              min-width:0 !important;
            }}
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
    delta = len(str(value)) - len(note)
    add_token(delta * st.session_state.type_token)
    ui["TOKEN_LEVEL"] = f"{st.session_state.token * 16:.4f}"
    write_day(day, value, diet, quadrant, time_map, ui, extras)
    st.session_state.last_saved = f"Auto-saved notes for {day:%Y-%m-%d}"


def save_diet_from_state(day: date):
    note, diet, quadrant, time_map, ui, extras = read_day(day)
    key = f"diet-text-{day.isoformat()}"
    value = st.session_state.get(key, diet)
    delta = len(str(value)) - len(diet)
    add_token(delta * st.session_state.type_token)
    ui["TOKEN_LEVEL"] = f"{st.session_state.token * 16:.4f}"
    write_day(day, note, value, quadrant, time_map, ui, extras)
    st.session_state.last_saved = f"Auto-saved meal plan for {day:%Y-%m-%d}"


def save_schedule_from_state(day: date):
    note, diet, quadrant, time_map, ui, extras = read_day(day)
    new_time_map: dict[str, str] = {}
    for slot in time_slots():
        key = f"slot-{day}-{slot}"
        new_time_map[slot] = st.session_state.get(key, time_map.get(slot, ""))
    old_chars = sum(len(str(value)) for value in time_map.values())
    new_chars = sum(len(str(value)) for value in new_time_map.values())
    add_token((new_chars - old_chars) * st.session_state.type_token)
    ui["TOKEN_LEVEL"] = f"{st.session_state.token * 16:.4f}"
    write_day(day, note, diet, quadrant, new_time_map, ui, extras)
    st.session_state.last_saved = f"Auto-saved schedule for {day:%Y-%m-%d}"


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

    html = [
        f"""
        <div class="month-wrap">
        <div class="month-nav">
          <a class="month-arrow" href="?month={prev_y:04d}-{prev_m:02d}">&lsaquo;</a>
          <div class="month-title">{calendar.month_name[month]} {year}</div>
          <a class="month-arrow" href="?month={next_y:04d}-{next_m:02d}">&rsaquo;</a>
        </div>
        <div class="calendar-grid">
        """
    ]
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
                f'<a class="{" ".join(classes)}" href="/?day={current.isoformat()}" target="_self">'
                f'<span class="calendar-date">{day_num}</span>{content_mark}{today_label}</a>'
            )
    html.append("</div>")
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


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


def simple_topbar_html(selected: date) -> str:
    pct = int(st.session_state.token * 100)
    battery_class = "battery-wrap flash" if st.session_state.flash_battery else "battery-wrap"
    token_pct = max(0.0, min(100.0, st.session_state.token * 100))
    cells = []
    for index in range(4):
        start = index * 25
        fill = max(0.0, min(25.0, token_pct - start)) / 25 * 100
        cells.append(f'<div class="battery-cell" style="--fill:{fill:.2f}%"></div>')
    return (
        f'<div class="simple-topbar">'
        f'<a class="month-link" href="?month={selected.year:04d}-{selected.month:02d}">&larr; Month</a>'
        f'<div class="topbar-right">'
        f'<div class="{battery_class}">'
        f'<div class="battery">{"".join(cells)}</div>'
        f'<div class="battery-label">{pct}%</div>'
        f'</div></div></div>'
    )


def render_simple_topbar(selected: date):
    st.markdown(simple_topbar_html(selected), unsafe_allow_html=True)


def day_progress_html(selected: date) -> str:
    _note, _diet, _quadrant, time_map, _ui, _extras = read_day(selected)
    current = now()
    if selected == current.date():
        pct = ((current.hour * 60) + current.minute) / (24 * 60) * 100
    elif selected < current.date():
        pct = 100
    else:
        pct = 0

    html = ['<div class="day-progress">']
    for hour in range(24):
        left = hour / 24 * 100
        if hour in {0, 6, 12, 18}:
            html.append(f'<div class="tick major" style="left:{left:.2f}%"></div>')
            html.append(f'<div class="tick-label" style="left:{left:.2f}%">{hour:02d}</div>')
    html.append('<div class="tick major end" style="left:100%"></div>')
    html.append('<div class="tick-label end" style="left:100%">24</div>')

    html.append('<div class="time-battery">')
    for hour in range(24):
        if selected < current.date():
            fill = 100
        elif selected > current.date():
            fill = 0
        elif hour < current.hour:
            fill = 100
        elif hour == current.hour:
            fill = current.minute / 60 * 100
        else:
            fill = 0
        slot = f"{natural_time(hour)} - {natural_time(hour + 1)}"
        text = escape(time_map.get(slot, "").strip() or "No task")
        pop_time = f"{hour:02d}:00 ~ {(hour + 1) % 24:02d}:00"
        html.append(
            f'<div class="time-cell" style="--fill:{fill:.2f}%">'
            f'<div class="timeline-pop"><b>{pop_time}</b>{text}</div></div>'
        )
    html.append("</div>")
    html.append("</div>")
    return "".join(html)


def render_day_progress(selected: date):
    st.markdown(day_progress_html(selected), unsafe_allow_html=True)


def render_text_panel(selected: date, panel: str):
    note, diet, quadrant, time_map, ui, extras = read_day(selected)
    if panel == "note":
        st.markdown('<div class="panel-box">', unsafe_allow_html=True)
        st.text_area(
            "Today's Notes",
            value=note,
            height=260,
            key=f"note-text-{selected.isoformat()}",
            on_change=save_note_from_state,
            args=(selected,),
        )
        st.markdown("</div>", unsafe_allow_html=True)
    elif panel == "diet":
        if not diet:
            diet = "First meal:\n\nSecond meal:\n\nThird meal:"
        st.markdown('<div class="panel-box">', unsafe_allow_html=True)
        st.text_area(
            "Meal Plan",
            value=diet,
            height=220,
            key=f"diet-text-{selected.isoformat()}",
            on_change=save_diet_from_state,
            args=(selected,),
        )
        st.markdown("</div>", unsafe_allow_html=True)
    elif panel == "quadrant":
        st.markdown('<div class="panel-box">', unsafe_allow_html=True)
        st.subheader("Today's Eisenhower Matrix")
        tasks = load_quadrant_tasks(quadrant)
        with st.form(f"quadrant-form-{selected}", clear_on_submit=True):
            task_text = st.text_input("Task", placeholder="Write one task")
            col_a, col_b = st.columns(2)
            important = col_a.checkbox("Important")
            urgent = col_b.checkbox("Urgent")
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
    st.markdown('<div class="matrix-dialog">', unsafe_allow_html=True)
    st.markdown(
        '<div class="matrix-header"><div class="matrix-title">monthly eisenhower matrix</div>',
        unsafe_allow_html=True,
    )
    st.markdown('</div>', unsafe_allow_html=True)

    with st.form(f"quadrant-dialog-form-{selected}", clear_on_submit=True):
        st.markdown('<div class="matrix-form-panel">', unsafe_allow_html=True)
        task_text = st.text_input("Task", placeholder="Write one task")
        st.markdown('<div class="matrix-flags">', unsafe_allow_html=True)
        important = st.checkbox("Important")
        urgent = st.checkbox("Urgent")
        st.markdown('</div>', unsafe_allow_html=True)
        submitted = st.form_submit_button("Add Task", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
    if st.button("Close matrix", key="close-matrix", use_container_width=True):
        st.session_state.matrix_open = False
        st.rerun()
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

    grid_html = ['<div class="matrix-html-grid">']
    for title, items in groups.items():
        grid_html.append('<div class="matrix-html-box">')
        grid_html.append(f'<div class="quadrant-title-bar">{escape(title)}</div>')
        if not items:
            grid_html.append('<div class="matrix-empty">No tasks yet</div>')
        for index, task in items:
            grid_html.append(
                f'<a class="matrix-task" href="?day={selected.isoformat()}&matrix_done={index}">'
                f'<span class="matrix-task-check"></span><span>{escape(task["text"])}</span></a>'
            )
        grid_html.append("</div>")
    grid_html.append("</div>")
    st.markdown("".join(grid_html), unsafe_allow_html=True)
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


def render_day():
    selected = st.session_state.selected_day
    sticky_html = (
        '<div class="day-head">'
        f'{simple_topbar_html(selected)}'
        '<div class="day-top">'
        f'<div class="day-title">{selected:%Y-%m-%d} {selected.strftime("%A")}</div>'
        '</div>'
        '<div class="timeline-sticky">'
        f'{day_progress_html(selected)}'
        '</div>'
        '</div>'
    )
    st.markdown(sticky_html, unsafe_allow_html=True)
    st.session_state.flash_battery = False

    if st.session_state.get("last_saved"):
        message = st.session_state.last_saved
        if str(message).startswith("Save failed"):
            st.error(message)
        else:
            st.success(message)

    st.markdown(
        f"""
        <div class="action-link-grid">
          <a class="day-action-link" href="/?day={selected.isoformat()}&matrix=open" target="_self">Matrix</a>
          <a class="day-action-link" href="/?day={selected.isoformat()}&panel=note" target="_self">Notes</a>
          <a class="day-action-link" href="/?day={selected.isoformat()}&panel=diet" target="_self">Meal</a>
        </div>
        """,
        unsafe_allow_html=True,
    )

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
        st.stop()
    else:
        render_day()


if __name__ == "__main__":
    main()
