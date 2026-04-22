from types import SimpleNamespace

import pytest

from app.services.realtime.backplane import (
    InMemoryRealtimeBackplane,
    RealtimeBackplane,
    RedisRealtimeBackplane,
)


class _FakePubSub:
    def __init__(self, messages):
        self.messages = list(messages)
        self.patterns = []
        self.closed = False

    def psubscribe(self, pattern):
        self.patterns.append(pattern)

    def get_message(self, timeout):
        if self.messages:
            return self.messages.pop(0)
        return None

    def close(self):
        self.closed = True


class _FakeRedis:
    def __init__(self, pubsub):
        self.pubsub_instance = pubsub
        self.published = []

    def publish(self, channel, payload):
        self.published.append((channel, payload))

    def pubsub(self, ignore_subscribe_messages=True):
        return self.pubsub_instance


def test_realtime_backplane_abstract_methods_raise():
    with pytest.raises(NotImplementedError):
        RealtimeBackplane.publish(object(), "cocoon-1", {})
    with pytest.raises(NotImplementedError):
        RealtimeBackplane.subscribe(object(), lambda *_: None)
    with pytest.raises(NotImplementedError):
        RealtimeBackplane.start(object())
    with pytest.raises(NotImplementedError):
        RealtimeBackplane.stop(object())


def test_in_memory_realtime_backplane_publishes_to_subscribers():
    backplane = InMemoryRealtimeBackplane()
    received = []

    backplane.subscribe(lambda cocoon_id, event: received.append((cocoon_id, event)))
    backplane.start()
    backplane.publish("cocoon-1", {"type": "ping"})
    backplane.stop()

    assert received == [("cocoon-1", {"type": "ping"})]


def test_redis_realtime_backplane_publishes_and_listens(monkeypatch):
    pubsub = _FakePubSub(
        [
            {"type": "ignore", "data": "{}"},
            {"type": "pmessage", "data": '{"cocoon_id":"cocoon-1","event":{"type":"reply_done"}}'},
        ]
    )
    fake_redis = _FakeRedis(pubsub)
    monkeypatch.setattr(
        "app.services.realtime.backplane.Redis.from_url",
        lambda *args, **kwargs: fake_redis,
    )

    backplane = RedisRealtimeBackplane("redis://unused", "cocoon:events")
    received = []
    backplane.subscribe(lambda cocoon_id, event: received.append((cocoon_id, event)))

    assert backplane.channel_name() == "cocoon:events:*"

    backplane.publish("cocoon-1", {"type": "queued"})
    backplane._stop_event.set()
    backplane._listen()

    assert fake_redis.published == [
        ("cocoon:events:cocoon-1", '{"cocoon_id": "cocoon-1", "event": {"type": "queued"}}')
    ]
    assert pubsub.patterns == ["cocoon:events:*"]
    assert received == []
    assert pubsub.closed is True


def test_redis_realtime_backplane_listen_dispatches_messages_to_handlers(monkeypatch):
    pubsub = _FakePubSub(
        [
            {"type": "pmessage", "data": '{"cocoon_id":"cocoon-2","event":{"type":"reply_done"}}'},
        ]
    )
    fake_redis = _FakeRedis(pubsub)
    monkeypatch.setattr(
        "app.services.realtime.backplane.Redis.from_url",
        lambda *args, **kwargs: fake_redis,
    )

    backplane = RedisRealtimeBackplane("redis://unused", "cocoon:events")
    received = []

    def handler(cocoon_id, event):
        received.append((cocoon_id, event))
        backplane._stop_event.set()

    backplane.subscribe(handler)
    backplane._listen()

    assert received == [("cocoon-2", {"type": "reply_done"})]
    assert pubsub.closed is True


def test_redis_realtime_backplane_start_and_stop_manage_thread(monkeypatch):
    pubsub = _FakePubSub([])
    fake_redis = _FakeRedis(pubsub)
    monkeypatch.setattr(
        "app.services.realtime.backplane.Redis.from_url",
        lambda *args, **kwargs: fake_redis,
    )

    started = []

    class _FakeThread:
        def __init__(self, target, daemon):
            self.target = target
            self.daemon = daemon

        def start(self):
            started.append("started")

        def join(self, timeout):
            started.append(("joined", timeout))

    monkeypatch.setattr("app.services.realtime.backplane.threading.Thread", _FakeThread)

    backplane = RedisRealtimeBackplane("redis://unused", "cocoon:events")
    backplane.start()
    backplane.start()
    backplane.stop()

    assert started == ["started", ("joined", 2)]
    assert backplane._thread is None
