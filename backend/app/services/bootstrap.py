from sqlalchemy.orm import Session

from app.core.config import Settings
from app.services.bootstrap_service import BootstrapService
from app.services.prompts.service import PromptTemplateService


def seed_default_data(session: Session, settings: Settings, prompt_service: PromptTemplateService) -> None:
    BootstrapService(settings, prompt_service).seed_default_data(session)
