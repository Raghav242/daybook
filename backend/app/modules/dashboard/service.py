from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.modules.dashboard.repository import DashboardRepository
from app.modules.settings.service import SettingsService


class DashboardService:
    def __init__(self, repository: DashboardRepository, settings: SettingsService):
        self.repository = repository
        self.settings = settings
        if repository.user_id != settings.repository.user_id:
            raise ValueError("Dashboard and settings must use the same authenticated owner.")

    def get(self, now: datetime | None = None):
        settings = self.settings.get()
        zone = ZoneInfo(settings.timezone)
        today = (now or datetime.now(timezone.utc)).astimezone(zone).date()
        start = datetime.combine(today, time.min, zone).astimezone(timezone.utc)
        end = datetime.combine(today + timedelta(days=1), time.min, zone).astimezone(timezone.utc)
        horizon = today + timedelta(days=30)
        return {
            "today": today,
            "timezone": settings.timezone,
            "bill_horizon": horizon,
            **self.repository.summary(today, start, end, horizon),
        }
