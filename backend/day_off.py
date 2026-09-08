from datetime import date as date_type
from typing import Optional

from sqlalchemy.orm import Session

from models import VacationDay, VacationStatus
from holidays import czech_state_holiday_name


def day_off_reason(db: Session, user_id: int, day: date_type) -> tuple[bool, Optional[str], Optional[str]]:
    """Řekne, jestli je pro daného uživatele daný den volno (víkend, státní
    svátek nebo schválená dovolená) a proč. Sdílené mezi checklistem, formulářem
    výkonu a denní kontrolou neúplných checklistů - ať se stejná logika
    neduplikuje a nerozjede na dvou místech jinam."""
    if day.weekday() >= 5:
        return True, "weekend", None

    holiday_name = czech_state_holiday_name(day)
    if holiday_name:
        return True, "holiday", holiday_name

    on_vacation = db.query(VacationDay).filter(
        VacationDay.user_id == user_id,
        VacationDay.date == day,
        VacationDay.status == VacationStatus.approved,
    ).first() is not None
    if on_vacation:
        return True, "vacation", None

    return False, None, None
