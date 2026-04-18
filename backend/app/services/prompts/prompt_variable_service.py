from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PromptVariable
from app.services.prompts.registry import PROMPT_VARIABLES_BY_TYPE


class PromptVariableService:
    """Synchronizes registered prompt variables into persistent metadata."""

    def sync_registry_defaults(self, session: Session) -> None:
        for template_type, variables in PROMPT_VARIABLES_BY_TYPE.items():
            for variable_name, description in variables.items():
                existing = session.scalar(
                    select(PromptVariable).where(
                        PromptVariable.template_type == str(template_type),
                        PromptVariable.variable_name == variable_name,
                    )
                )
                if existing:
                    continue
                session.add(
                    PromptVariable(
                        template_type=str(template_type),
                        variable_name=variable_name,
                        description=description,
                        is_required=True,
                    )
                )
        session.flush()
