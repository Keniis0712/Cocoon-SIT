from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.services.bootstrap_access_seed_service import BootstrapAccessSeedService
from app.services.bootstrap_catalog_seed_service import BootstrapCatalogSeedService
from app.services.bootstrap_workspace_seed_service import BootstrapWorkspaceSeedService
from app.services.prompts.service import PromptTemplateService


class BootstrapService:
    """Coordinates default data seeding across access, catalog, and workspace domains."""

    def __init__(
        self,
        settings: Settings,
        prompt_service: PromptTemplateService,
        access_seed_service: BootstrapAccessSeedService | None = None,
        catalog_seed_service: BootstrapCatalogSeedService | None = None,
        workspace_seed_service: BootstrapWorkspaceSeedService | None = None,
    ) -> None:
        self.settings = settings
        self.prompt_service = prompt_service
        self.access_seed_service = access_seed_service or BootstrapAccessSeedService()
        self.catalog_seed_service = catalog_seed_service or BootstrapCatalogSeedService()
        self.workspace_seed_service = workspace_seed_service or BootstrapWorkspaceSeedService()

    def seed_default_data(self, session: Session) -> None:
        admin_user = self.access_seed_service.ensure_defaults(session, self.settings)
        self.catalog_seed_service.ensure_defaults(
            session,
            self.prompt_service,
            admin_user_id=admin_user.id,
        )
