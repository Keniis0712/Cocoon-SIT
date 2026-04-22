from app.services.jobs.chat_dispatch_codec import ChatDispatchCodec
from app.services.jobs.chat_dispatch_types import ChatDispatchEnvelope, ChatDispatchQueue
from app.services.jobs.in_memory_chat_dispatch_queue import InMemoryChatDispatchQueue
from app.services.jobs.redis_chat_dispatch_queue import RedisChatDispatchQueue


class _FakeRedis:
    def __init__(self) -> None:
        self.messages: list[tuple[str, dict]] = []
        self.acked: list[tuple[str, str, str]] = []
        self.group_created = False

    def xgroup_create(self, name: str, groupname: str, id: str, mkstream: bool) -> None:
        self.group_created = True

    def xadd(self, stream_name: str, payload: dict) -> None:
        self.messages.append((stream_name, payload))

    def xlen(self, stream_name: str) -> int:
        return len(self.messages)

    def xreadgroup(self, groupname: str, consumername: str, streams: dict, count: int, block: int):
        if not self.messages:
            return []
        stream_name, payload = self.messages[0]
        return [(stream_name, [("1-0", payload)])]

    def xack(self, stream_name: str, group_name: str, stream_id: str) -> None:
        self.acked.append((stream_name, group_name, stream_id))


def test_chat_dispatch_codec_round_trips_payload():
    codec = ChatDispatchCodec()

    payload = {"message_id": "msg-1", "timezone": "UTC", "nested": {"x": 1}}
    encoded = codec.encode_payload(payload)

    assert codec.decode_payload(encoded) == payload


def test_chat_dispatch_codec_handles_empty_bytes_and_non_dict_payloads():
    codec = ChatDispatchCodec()

    assert codec.decode_payload(None) == {}
    assert codec.decode_payload(b"") == {}
    assert codec.decode_payload(b'{"kind":"ok"}') == {"kind": "ok"}
    assert codec.decode_payload('["not", "a", "dict"]') == {}


def test_chat_dispatch_envelope_and_base_queue_methods():
    envelope = ChatDispatchEnvelope(
        stream_id="1-0",
        action_id="action-1",
        target_type="cocoon",
        target_id="cocoon-1",
        event_type="chat",
        payload={"message_id": "msg-1"},
    )

    assert envelope.stream_id == "1-0"
    assert envelope.payload == {"message_id": "msg-1"}

    class _BaseQueue(ChatDispatchQueue):
        def enqueue(self, action_id: str, **kwargs) -> int:
            return super().enqueue(action_id, **kwargs)

        def consume_next(self):
            return super().consume_next()

        def ack(self, envelope):
            super().ack(envelope)

    queue = _BaseQueue()

    try:
        queue.enqueue("action-1", event_type="chat", cocoon_id="cocoon-1", payload={})
        raise AssertionError("expected NotImplementedError")
    except NotImplementedError:
        pass
    try:
        queue.consume_next()
        raise AssertionError("expected NotImplementedError")
    except NotImplementedError:
        pass
    try:
        queue.ack(envelope)
        raise AssertionError("expected NotImplementedError")
    except NotImplementedError:
        pass


def test_in_memory_chat_dispatch_queue_preserves_payload():
    queue = InMemoryChatDispatchQueue()

    queue.enqueue("action-1", event_type="chat", cocoon_id="cocoon-1", payload={"message_id": "msg-1"})
    envelope = queue.consume_next()

    assert envelope is not None
    assert envelope.action_id == "action-1"
    assert envelope.target_type == "cocoon"
    assert envelope.target_id == "cocoon-1"
    assert envelope.payload == {"message_id": "msg-1"}


def test_redis_chat_dispatch_queue_serializes_payload(monkeypatch):
    fake_redis = _FakeRedis()
    monkeypatch.setattr(
        "app.services.jobs.redis_chat_dispatch_queue.Redis.from_url",
        lambda *args, **kwargs: fake_redis,
    )

    queue = RedisChatDispatchQueue(
        redis_url="redis://unused",
        stream_name="cocoon:dispatch:chat",
        group_name="workers",
        consumer_name="worker-1",
    )

    queue.enqueue(
        "action-1",
        event_type="edit",
        cocoon_id="cocoon-1",
        payload={"message_id": "msg-1", "retry": False},
    )
    envelope = queue.consume_next()

    assert fake_redis.group_created is True
    assert envelope is not None
    assert envelope.event_type == "edit"
    assert envelope.target_type == "cocoon"
    assert envelope.target_id == "cocoon-1"
    assert envelope.payload == {"message_id": "msg-1", "retry": False}

    queue.ack(envelope)
    assert fake_redis.acked == [("cocoon:dispatch:chat", "workers", "1-0")]
