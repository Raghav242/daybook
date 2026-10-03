from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.infrastructure.database import get_session
from app.modules.settings.repository import SettingsRepository
from app.modules.settings.schemas import SettingsInput, SettingsOutput
from app.modules.settings.service import SettingsService

router = APIRouter(prefix="/settings", tags=["settings"])


def get_service(session: Session = Depends(get_session)):
    return SettingsService(SettingsRepository(session))


@router.get("", response_model=SettingsOutput)
def get_settings(service: SettingsService = Depends(get_service)):
    return service.get()


@router.put("", response_model=SettingsOutput)
def update_settings(data: SettingsInput, service: SettingsService = Depends(get_service)):
    return service.update(data)
