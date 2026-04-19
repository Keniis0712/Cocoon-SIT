from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import ActionDispatch, AuditRun, Message
from app.services.audit.service import AuditService
from app.services.realtime.hub import RealtimeHub
from app.services.runtime.side_effects import SideEffects
from app.services.runtime.types import ContextPackage, GenerationOutput


class ReplyDeliveryService:
    """Streams generated replies, persists them, and records audit artifacts."""

    def __init__(
        self,
        side_effects: SideEffects,
        audit_service: AuditService,
        realtime_hub: RealtimeHub,
    ) -> None:
        self.side_effects = side_effects
        self.audit_service = audit_service
        self.realtime_hub = realtime_hub

    def deliver(
        self,
        session: Session,
        context: ContextPackage,
        action: ActionDispatch,
        audit_run: AuditRun,
        generator_step,
        generation: GenerationOutput,
    ) -> Message:
        self.realtime_hub.publish(
            context.channel_key,
            {
                "type": "reply_started",
                "action_id": action.id,
                "cocoon_id": context.runtime_event.cocoon_id,
                "chat_group_id": context.runtime_event.chat_group_id,
            },
        )
        for chunk in generation.chunks:
            self.realtime_hub.publish(
                context.channel_key,
                {
                    "type": "reply_chunk",
                    "action_id": action.id,
                    "text": chunk,
                    "cocoon_id": context.runtime_event.cocoon_id,
                "chat_group_id": context.runtime_event.chat_group_id,
            },
        )
        message = self.side_effects.persist_generated_message(session, context, action, generation)
        self.realtime_hub.publish(
            context.channel_key,
            {
                "type": "reply_done",
                "action_id": action.id,
                "final_message_id": message.id,
                "cocoon_id": context.runtime_event.cocoon_id,
                "chat_group_id": context.runtime_event.chat_group_id,
            },
        )
        output_artifact = self.audit_service.record_json_artifact(
            session,
            audit_run,
            generator_step,
            "generator_output",
            {
                "final_message_id": message.id,
                "content": generation.reply_text,
                "structured_output": generation.structured_output,
            },
            summary="Assistant reply snapshot",
            metadata_json={
                "provider_kind": generation.provider_kind,
                "model_name": generation.model_name,
                **generation.usage,
            },
        )
        self.audit_service.record_link(
            session,
            audit_run,
            "produced_by",
            source_step_id=generator_step.id,
            target_artifact_id=output_artifact.id,
        )
        return message
