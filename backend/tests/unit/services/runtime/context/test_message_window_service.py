from types import SimpleNamespace

from app.services.runtime.context.message_window_service import MessageWindowService


class _ScalarResult:
    def __init__(self, items):
        self._items = items

    def all(self):
        return list(self._items)


def test_message_window_service_returns_reversed_messages_when_no_active_tags():
    messages = [
        SimpleNamespace(id="m3", tags_json=["focus"]),
        SimpleNamespace(id="m2", tags_json=[]),
        SimpleNamespace(id="m1", tags_json=None),
    ]

    class _Session:
        def __init__(self):
            self.calls = 0

        def scalars(self, query):
            self.calls += 1
            return _ScalarResult(messages)

    service = MessageWindowService()
    result = service.list_visible_messages(_Session(), 10, [], cocoon_id="cocoon-1")

    assert [item.id for item in result] == ["m1", "m2", "m3"]


def test_message_window_service_filters_by_tagged_ids_and_falls_back_when_empty():
    messages = [
        SimpleNamespace(id="m3", tags_json=["focus"]),
        SimpleNamespace(id="m2", tags_json=["other"]),
        SimpleNamespace(id="m1", tags_json=[]),
    ]
    tagged_records = [SimpleNamespace(message_id="m3")]

    class _Session:
        def __init__(self, tag_items):
            self.calls = 0
            self.tag_items = tag_items

        def scalars(self, query):
            self.calls += 1
            if self.calls == 1:
                return _ScalarResult(messages)
            return _ScalarResult(self.tag_items)

    service = MessageWindowService()
    filtered = service.list_visible_messages(_Session(tagged_records), 10, ["focus"], cocoon_id="cocoon-1")
    fallback = service.list_visible_messages(_Session([]), 10, ["missing"], cocoon_id="cocoon-1")

    assert [item.id for item in filtered] == ["m1", "m3"]
    assert [item.id for item in fallback] == ["m1"]
