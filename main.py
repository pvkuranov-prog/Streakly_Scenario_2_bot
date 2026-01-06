from __future__ import annotations

import calendar
from datetime import datetime
from typing import List, Dict, Set, Tuple

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="Telegram Calendar API", version="1.0.0")

WEEKDAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


class CalendarRequest(BaseModel):
    dates: List[str] = Field(
        ...,
        description='Array of dates in "DD-MM-YYYY", e.g. ["14-03-2025","20-03-2025"]',
        examples=[["14-03-2025", "20-03-2025", "27-03-2025"]],
    )
    emoji: str = Field("✅", description="Emoji to replace marked dates")


class CalendarResponse(BaseModel):
    month: str
    message: str


def _parse_dates(date_strs: List[str]) -> List[datetime]:
    out: List[datetime] = []
    for s in date_strs:
        try:
            out.append(datetime.strptime(s, "%d-%m-%Y"))
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f'Invalid date "{s}". Expected format: DD-MM-YYYY (e.g. 14-03-2025)',
            )
    return out


def _group_by_month(dts: List[datetime]) -> Dict[Tuple[int, int], Set[int]]:
    grouped: Dict[Tuple[int, int], Set[int]] = {}
    for dt in dts:
        grouped.setdefault((dt.year, dt.month), set()).add(dt.day)
    return grouped


def _build_calendar_message(year: int, month: int, marked_days: Set[int], emoji: str) -> str:
    # Неделя начинается с понедельника как в вашем примере
    cal = calendar.Calendar(firstweekday=calendar.MONDAY)
    weeks = cal.monthdayscalendar(year, month)  # list[list[int]] 0 = пустая клетка

    # Форматирование клетки: либо ✅, либо число; пустые клетки — пусто
    def cell(d: int) -> str:
        if d == 0:
            return ""  # важно: пусто, чтобы строки выглядели как у вас
        if d in marked_days:
            return emoji
        return str(d)

    lines: List[str] = []
    lines.append(f"Календарь активностей для {year:04d}-{month:02d}:")
    lines.append(" ".join(WEEKDAYS_RU))
    lines.append("")  # пустая строка как в примере
    lines.append("")  # ещё одна пустая строка как в примере

    for week in weeks:
        # Собираем строку с разделителем пробел
        row = " ".join(cell(d) for d in week).strip()
        # Убираем многопробельность из-за пустых клеток слева
        # (оставляем аккуратное визуальное форматирование)
        row = " ".join(part for part in row.split(" ") if part != "")
        if row:
            lines.append(row)

    # Telegram monospace
    return "```text\n" + "\n".join(lines) + "\n```"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/calendar", response_model=CalendarResponse)
def make_calendar(req: CalendarRequest):
    dts = _parse_dates(req.dates)
    grouped = _group_by_month(dts)

    if not grouped:
        raise HTTPException(status_code=400, detail="No dates provided")

    # Чтобы формат был однозначный — один месяц на запрос
    if len(grouped) > 1:
        months = [f"{y:04d}-{m:02d}" for (y, m) in grouped.keys()]
        raise HTTPException(
            status_code=400,
            detail=f"Dates span multiple months: {months}. Send dates for one month per request.",
        )

    (year, month), marked = next(iter(grouped.items()))
    message = _build_calendar_message(year, month, marked, req.emoji)
    return CalendarResponse(month=f"{year:04d}-{month:02d}", message=message)
