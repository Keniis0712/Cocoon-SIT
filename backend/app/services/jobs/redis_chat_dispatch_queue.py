from __future__ import annotations

from redis import Redis

from app.services.jobs.chat_dispatch_codec import ChatDispatchCodec
from app.services.jobs.chat_dispatch_types import ChatDispatchEnvelope, ChatDispatchQueue
from app.services.workspace.targets import resolve_target_type


class RedisChatDispatchQueue(ChatDispatchQueue):
    """Redis Streams-backed queue used for multi-worker deployments."""

    def __init__(
        self,
        redis_url: str,
        stream_name: str,
        group_name: str,
        consumer_name: str,
        codec: ChatDispatchCodec | None = None,
    ):
        self.redis = Redis.from_url(redis_url, decode_responses=True)
        self.stream_name = stream_name
        self.group_name = group_name
        self.consumer_name = consumer_name
        self.codec = codec or ChatDispatchCodec()
        try:
            self.redis.xgroup_create(name=stream_name, groupname=group_name, id="0", mkstream=True)
        except Exception:
            pass

    def enqueue(
        self,
        action_id: str,
        *,
        event_type: str,
        cocoon_id: str | None = None,
        chat_group_id: str | None = None,
        payload: dict,
    ) -> int:
        target_type, target_id = resolve_target_type(cocoon_id=cocoon_id, chat_group_id=chat_group_id)
        self.redis.xadd(
            self.stream_name,
            {
                "action_id": action_id,
                "target_type": target_type,
                "target_id": target_id,
                "event_type": event_type,
                "payload": self.codec.encode_payload(payload),
            },
        )
        return self.redis.xlen(self.stream_name)

    def consume_next(self) -> ChatDispatchEnvelope | None:
        result = self.redis.xreadgroup(
            groupname=self.group_name,
            consumername=self.consumer_name,
            streams={self.stream_name: ">"},
            count=1,
            block=250,
        )
        if not result:
            return None
        _, messages = result[0]
        stream_id, payload = messages[0]
        return ChatDispatchEnvelope(
            stream_id=stream_id,
            action_id=payload["action_id"],
            target_type=payload["target_type"],
            target_id=payload["target_id"],
            event_type=payload["event_type"],
            payload=self.codec.decode_payload(payload.get("payload")),
        )

    def ack(self, envelope: ChatDispatchEnvelope) -> None:
        self.redis.xack(self.stream_name, self.group_name, envelope.stream_id)
