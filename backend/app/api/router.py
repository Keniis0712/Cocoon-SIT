"""Top-level API router composed from function-oriented route subpackages."""

from fastapi import APIRouter

from app.api.routes.admin import plugins as admin_plugins
from app.api.routes.access import auth, groups, invites, roles, users
from app.api.routes.catalog import (
    characters,
    embedding_providers,
    models,
    prompt_templates,
    provider_credentials,
    providers,
    settings,
    tags,
)
from app.api.routes.observability import admin_artifacts, audits, health, insights
from app.api.routes.workspace import (
    chat_groups,
    checkpoints,
    cocoons,
    memory,
    merges,
    messages,
    pulls,
    realtime,
    rollback,
    tags as workspace_tags,
)


api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(roles.router, prefix="/roles", tags=["roles"])
api_router.include_router(invites.router, prefix="/invites", tags=["invites"])
api_router.include_router(groups.router, prefix="/groups", tags=["groups"])
api_router.include_router(characters.router, prefix="/characters", tags=["characters"])
api_router.include_router(providers.router, prefix="/providers", tags=["providers"])
api_router.include_router(provider_credentials.router, prefix="/providers", tags=["providers"])
api_router.include_router(models.router, prefix="/providers", tags=["providers"])
api_router.include_router(embedding_providers.router, prefix="/providers", tags=["providers"])
api_router.include_router(tags.router, prefix="/tags", tags=["tags"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])
api_router.include_router(prompt_templates.router, prefix="/prompt-templates", tags=["prompt-templates"])
api_router.include_router(cocoons.router, prefix="/cocoons", tags=["cocoons"])
api_router.include_router(chat_groups.router, prefix="/chat-groups", tags=["chat-groups"])
api_router.include_router(messages.router, prefix="/cocoons", tags=["cocoons"])
api_router.include_router(workspace_tags.router, prefix="/cocoons", tags=["cocoons"])
api_router.include_router(rollback.router, prefix="/cocoons", tags=["cocoons"])
api_router.include_router(realtime.router, prefix="/cocoons", tags=["cocoons"])
api_router.include_router(memory.router, prefix="/memory", tags=["memory"])
api_router.include_router(pulls.router, prefix="/pulls", tags=["pulls"])
api_router.include_router(merges.router, prefix="/merges", tags=["merges"])
api_router.include_router(checkpoints.router, prefix="/checkpoints", tags=["checkpoints"])
api_router.include_router(audits.router, prefix="/audits", tags=["audits"])
api_router.include_router(insights.router, prefix="/insights", tags=["insights"])
api_router.include_router(admin_artifacts.router, prefix="/admin/artifacts", tags=["admin"])
api_router.include_router(admin_plugins.router, prefix="/admin/plugins", tags=["admin"])
