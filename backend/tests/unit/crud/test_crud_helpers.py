from app.crud.catalog.prompts import list_prompt_templates
from app.crud.catalog.providers import list_model_providers
from app.crud.jobs.durable_jobs import enqueue_durable_job
from app.crud.workspace.action_dispatch import get_action_by_client_request_id
from app.crud.workspace.cocoons import get_session_state, list_cocoons, list_messages
from app.models import ActionDispatch, Cocoon, Message, ModelProvider, PromptTemplate, SessionState
from tests.sqlite_helpers import make_sqlite_session_factory


def _session_factory():
    return make_sqlite_session_factory()


def test_catalog_and_workspace_crud_helpers_return_ordered_records():
    session_factory = _session_factory()

    with session_factory() as session:
        session.add_all(
            [
                PromptTemplate(template_type="zeta", name="Zeta"),
                PromptTemplate(template_type="alpha", name="Alpha"),
                ModelProvider(name="provider-b", kind="mock", capabilities_json={}),
                ModelProvider(name="provider-a", kind="mock", capabilities_json={}),
            ]
        )
        session.flush()
        cocoon = Cocoon(
            name="crud-cocoon",
            owner_user_id="user-1",
            character_id="character-1",
            selected_model_id="model-1",
        )
        session.add(cocoon)
        session.flush()
        session.add(SessionState(cocoon_id=cocoon.id, persona_json={}, active_tags_json=[]))
        session.add_all(
            [
                Message(cocoon_id=cocoon.id, role="user", content="first"),
                Message(cocoon_id=cocoon.id, role="assistant", content="second"),
            ]
        )
        session.add(ActionDispatch(cocoon_id=cocoon.id, event_type="chat", client_request_id="req-1", payload_json={}))
        session.commit()

        assert [item.template_type for item in list_prompt_templates(session)] == ["alpha", "zeta"]
        assert [item.name for item in list_model_providers(session)] == ["provider-b", "provider-a"]
        assert [item.id for item in list_cocoons(session)] == [cocoon.id]
        assert [item.content for item in list_messages(session, cocoon.id)] == ["first", "second"]
        assert get_session_state(session, cocoon.id).cocoon_id == cocoon.id
        assert get_action_by_client_request_id(session, "req-1").client_request_id == "req-1"


def test_enqueue_durable_job_delegates_to_service():
    calls = []

    class _Service:
        def enqueue(self, session, job_type, lock_key, payload_json, cocoon_id):
            calls.append((session, job_type, lock_key, payload_json, cocoon_id))
            return "job"

    session = object()
    result = enqueue_durable_job(session, _Service(), "merge", "lock-key", {"x": 1}, "cocoon-1")

    assert result == "job"
    assert calls == [(session, "merge", "lock-key", {"x": 1}, "cocoon-1")]
