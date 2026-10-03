from datetime import datetime
from zoneinfo import ZoneInfo


JERUSALEM_TIMEZONE = ZoneInfo("Asia/Jerusalem")


def now_in_jerusalem() -> datetime:
    return datetime.now(JERUSALEM_TIMEZONE)


def humanize_status(status: str) -> str:
    return status.replace("_", " ")
