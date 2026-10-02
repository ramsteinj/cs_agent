import json
import uuid
from unittest import mock

import pytest

import llm
from chat import services
from chat.models import ChatMessage, ChatSession
from knowledge.models import KnowledgeChunk
from knowledge.tests.factories import make_company, make_product
from settings_app.models import LLMProviderConfig, SystemSetting

URL = "/api/chat/messages"


def _fake_reply(deltas, final_text=None, refused=False, error=None):
    """Replacement for llm.stream_reply recording its inputs."""
    calls = []

    def stream_reply(provider, api_key, model, system, messages, max_output_tokens, temperature):
        calls.append(
            {
                "provider": provider,
                "api_key": api_key,
                "model": model,
                "system": system,
                "messages": messages,
                "max_output_tokens": max_output_tokens,
                "temperature": temperature,
            }
        )
        yield from deltas
        if error:
            raise error
        return llm.FinalReply(
            text=final_text if final_text is not None else "".join(deltas),
            model=model,
            stop_reason="refusal" if refused else "end_turn",
            input_tokens=10,
            output_tokens=5,
            refused=refused,
        )

    return stream_reply, calls


def _events(response):
    body = b"".join(response.streaming_content).decode()
    return [json.loads(part[len("data: ") :]) for part in body.split("\n\n") if part.strip()]


@pytest.fixture
def enabled(db):
    LLMProviderConfig.get("anthropic").set_api_key("sk-ant-api03-test-secret-WXYZ")
    return SystemSetting.load()


def _set(**fields):
    SystemSetting.load()  # make sure the singleton row exists before updating it
    SystemSetting.objects.filter(pk=1).update(**fields)


@pytest.fixture
def loose_retrieval(enabled):
    # Fake hashing embeddings are not calibrated like e5; accept any distance.
    _set(retrieval_max_distance=2.0)


@pytest.fixture
def session(db):
    return ChatSession.objects.create()


def _send(client, session, message="오케이드라이브 가격이 얼마예요?"):
    return client.post(
        URL, {"session_id": str(session.id), "message": message}, content_type="application/json"
    )


@pytest.mark.django_db
class TestPreStreamErrors:
    def test_disabled_without_api_key_returns_503(self, client, session):
        response = _send(client, session)

        assert response.status_code == 503
        assert response.json()["error"]["code"] == "CHATBOT_DISABLED"

    def test_validation_errors(self, client, enabled, session):
        empty = _send(client, session, "   ")
        too_long = _send(client, session, "가" * 1001)
        bad_json = client.post(URL, "not json", content_type="application/json")

        assert empty.status_code == too_long.status_code == bad_json.status_code == 400
        assert "message" in empty.json()["error"]["details"]
        assert "message" in too_long.json()["error"]["details"]

    def test_unknown_session_returns_404(self, client, enabled):
        response = client.post(
            URL,
            {"session_id": str(uuid.uuid4()), "message": "hi"},
            content_type="application/json",
        )

        assert response.status_code == 404

    def test_get_not_allowed(self, client):
        assert client.get(URL).status_code == 405

    def test_ip_rate_limit(self, client, enabled, session, settings):
        settings.CHAT_IP_RATE_PER_MINUTE = 2
        reply, _ = _fake_reply(["ok"])
        with mock.patch("chat.services.llm.stream_reply", reply):
            for _ in range(2):
                response = _send(client, session)
                assert response.status_code == 200
                _events(response)

            response = _send(client, session)

        assert response.status_code == 429
        assert response.json()["error"]["code"] == "RATE_LIMITED"

    def test_session_message_cap(self, client, enabled, session, settings):
        settings.CHAT_SESSION_MAX_MESSAGES = 1
        ChatMessage.objects.create(session=session, role="user", content="q")

        assert _send(client, session).status_code == 429


@pytest.mark.django_db
class TestStreaming:
    def test_event_order_and_persistence(self, client, enabled, session, loose_retrieval):
        product = make_product(make_company(), name="오케이드라이브", price="월 5,000원")
        reply, calls = _fake_reply(["월 5,000원", "입니다."])

        with mock.patch("chat.services.llm.stream_reply", reply):
            response = _send(client, session)
            events = _events(response)  # the body is generated lazily: consume inside the patch

        assert response.status_code == 200
        assert response["Content-Type"].startswith("text/event-stream")
        assert [e["type"] for e in events] == ["start", "delta", "delta", "done"]
        assert [e["text"] for e in events[1:3]] == ["월 5,000원", "입니다."]
        assert {"type": "product", "id": product.pk, "title": "오케이드라이브"} in events[-1][
            "sources"
        ]
        assert "replace_text" not in events[-1]

        assistant = ChatMessage.objects.get(pk=events[0]["message_id"])
        assert assistant.content == "월 5,000원입니다."
        assert assistant.status == "ok"
        assert assistant.retrieved_chunk_ids
        assert (assistant.input_tokens, assistant.output_tokens) == (10, 5)

        call = calls[0]
        assert call["provider"] == "anthropic"
        assert call["api_key"] == "sk-ant-api03-test-secret-WXYZ"
        assert call["model"] == "claude-opus-5-5"
        assert call["max_output_tokens"] == 4096
        assert call["messages"][-1]["role"] == "user"
        assert call["messages"][-1]["content"].startswith("<context>")
        assert "고객 질문: 오케이드라이브 가격이 얼마예요?" in call["messages"][-1]["content"]

    def test_uses_configured_model_bot_name_and_extra_instructions(self, client, enabled, session):
        claude = LLMProviderConfig.get("anthropic")
        claude.model = "claude-haiku-4-5"
        claude.save()
        enabled.bot_name = "OK봇"
        enabled.extra_instructions = "반말 금지"
        enabled.save()
        reply, calls = _fake_reply(["네"])

        with mock.patch("chat.services.llm.stream_reply", reply):
            _events(_send(client, session))

        assert calls[0]["model"] == "claude-haiku-4-5"
        assert '"OK봇"' in calls[0]["system"]
        assert calls[0]["system"].endswith("반말 금지")

    def test_history_is_plain_text_and_limited(self, client, enabled, session):
        _set(history_messages=4)
        for i in range(4):
            ChatMessage.objects.create(session=session, role="user", content=f"질문{i}")
            ChatMessage.objects.create(session=session, role="assistant", content=f"답변{i}")
        reply, calls = _fake_reply(["네"])

        with mock.patch("chat.services.llm.stream_reply", reply):
            _events(_send(client, session, "그거 가격은?"))

        messages = calls[0]["messages"]
        assert [m["content"] for m in messages[:-1]] == ["질문2", "답변2", "질문3", "답변3"]
        assert [m["role"] for m in messages] == ["user", "assistant", "user", "assistant", "user"]

    def test_failed_turns_are_excluded_from_history(self, client, enabled, session):
        ChatMessage.objects.create(session=session, role="user", content="실패질문", status="error")
        ChatMessage.objects.create(session=session, role="assistant", content="", status="error")
        reply, calls = _fake_reply(["네"])

        with mock.patch("chat.services.llm.stream_reply", reply):
            _events(_send(client, session))

        assert len(calls[0]["messages"]) == 1

    def test_follow_up_search_uses_previous_question(self, client, enabled, session):
        ChatMessage.objects.create(session=session, role="user", content="오케이드라이브 알려줘")
        ChatMessage.objects.create(session=session, role="assistant", content="...")
        reply, _ = _fake_reply(["네"])

        with (
            mock.patch("chat.services.llm.stream_reply", reply),
            mock.patch("chat.services.search", return_value=[]) as search,
        ):
            _events(_send(client, session, "그거 가격은?"))

        assert search.call_args.args[0] == "오케이드라이브 알려줘\n그거 가격은?"

    def test_llm_error_emits_error_event_and_marks_turn_failed(self, client, enabled, session):
        reply, _ = _fake_reply(["부분"], error=llm.LLMError("boom"))

        with mock.patch("chat.services.llm.stream_reply", reply):
            events = _events(_send(client, session))

        assert [e["type"] for e in events] == ["start", "delta", "error"]
        assert events[-1]["code"] == "LLM_ERROR"
        assert "일시적인 오류" in events[-1]["message"]
        statuses = list(session.messages.values_list("role", "status"))
        assert statuses == [("user", "error"), ("assistant", "error")]

    def test_refusal_after_partial_output_replaces_text(self, client, enabled, session):
        reply, _ = _fake_reply(["부분 답"], final_text=llm.REFUSAL_MESSAGE, refused=True)

        with mock.patch("chat.services.llm.stream_reply", reply):
            events = _events(_send(client, session))

        assert events[-1]["replace_text"] == llm.REFUSAL_MESSAGE
        assert events[-1]["sources"] == []

    def test_client_disconnect_marks_turn_failed(self, enabled, session):
        reply, _ = _fake_reply(["하나", "둘"])

        with mock.patch("chat.services.llm.stream_reply", reply):
            events = services.answer_stream(session, "질문")
            next(events)  # start
            next(events)  # first delta
            events.close()  # what happens when the client goes away mid-stream

        assistant = session.messages.get(role="assistant")
        assert assistant.status == "error"
        assert assistant.content == "하나"
        assert session.messages.get(role="user").status == "error"


@pytest.mark.django_db
class TestSessions:
    def test_create_session(self, client):
        response = client.post("/api/chat/sessions")

        assert response.status_code == 201
        session = ChatSession.objects.get(pk=response.json()["session_id"])
        assert len(session.client_ip_hash) == 64
        assert "127.0.0.1" not in session.client_ip_hash

    def test_session_messages_for_restore(self, client, enabled, session, loose_retrieval):
        product = make_product(make_company(), name="오케이드라이브")
        reply, _ = _fake_reply(["답변"])
        with mock.patch("chat.services.llm.stream_reply", reply):
            _events(_send(client, session, "오케이드라이브 문서 저장"))

        body = client.get(f"/api/chat/sessions/{session.id}/messages").json()

        assert [(m["role"], m["content"]) for m in body] == [
            ("user", "오케이드라이브 문서 저장"),
            ("assistant", "답변"),
        ]
        assert body[1]["sources"][0]["id"] == product.pk

    def test_unknown_session_messages_404(self, client):
        assert client.get(f"/api/chat/sessions/{uuid.uuid4()}/messages").status_code == 404


@pytest.mark.django_db
class TestRagSettingsApplied:
    """RAG tuning values are read from the DB on every turn (specs/05 §1.1)."""

    def test_history_disabled_and_output_tokens(self, client, enabled, session):
        _set(history_messages=0, llm_max_output_tokens=1000)
        ChatMessage.objects.create(session=session, role="user", content="이전")
        ChatMessage.objects.create(session=session, role="assistant", content="답")
        reply, calls = _fake_reply(["네"])

        with mock.patch("chat.services.llm.stream_reply", reply):
            _events(_send(client, session))

        assert len(calls[0]["messages"]) == 1
        assert calls[0]["max_output_tokens"] == 1000

    def test_search_without_previous_question(self, client, enabled, session):
        _set(search_with_previous_question=False)
        ChatMessage.objects.create(session=session, role="user", content="오케이드라이브")
        ChatMessage.objects.create(session=session, role="assistant", content="...")
        reply, _ = _fake_reply(["네"])

        with (
            mock.patch("chat.services.llm.stream_reply", reply),
            mock.patch("chat.services.search", return_value=[]) as search,
        ):
            _events(_send(client, session, "가격은?"))

        assert search.call_args.args[0] == "가격은?"

    def test_max_sources(self, client, enabled, session, loose_retrieval):
        company = make_company()
        for i in range(3):
            make_product(company, name=f"제품{i}", description="오케이드라이브 가격 안내")
        _set(max_sources=1)
        reply, _ = _fake_reply(["네"])

        with mock.patch("chat.services.llm.stream_reply", reply):
            events = _events(_send(client, session, "오케이드라이브 가격"))

        assert len(events[-1]["sources"]) == 1


@pytest.mark.django_db
def test_selected_provider_is_used(client, session):
    gemini = LLMProviderConfig.get("gemini")
    gemini.set_api_key("AIzaSyTestSecret1234")
    gemini.model = "gemini-test-pro"
    gemini.save()
    _set(llm_provider="gemini")
    reply, calls = _fake_reply(["네"])

    with mock.patch("chat.services.llm.stream_reply", reply):
        events = _events(_send(client, session))

    assert events[-1]["type"] == "done"
    assert (calls[0]["provider"], calls[0]["model"], calls[0]["api_key"]) == (
        "gemini",
        "gemini-test-pro",
        "AIzaSyTestSecret1234",
    )
    assert session.messages.get(role="assistant").model == "gemini-test-pro"


@pytest.mark.django_db
def test_llm_failure_is_logged_with_provider_error_summary(client, enabled, session, caplog):
    summary = "status=400 type=invalid_request_error request_id=req_011credit"
    reply, _ = _fake_reply([], error=llm.LLMError(summary))

    with mock.patch("chat.services.llm.stream_reply", reply):
        _events(_send(client, session))

    assert f"LLM call failed (provider=anthropic, model=claude-opus-5-5): {summary}" in caplog.text
    assert "sk-ant-api03-test-secret-WXYZ" not in caplog.text


@pytest.mark.django_db
def test_configured_temperature_is_passed_to_the_provider(client, enabled, session):
    claude = LLMProviderConfig.get("anthropic")
    claude.model = "claude-haiku-4-5"
    claude.temperature = 0.2
    claude.save()
    reply, calls = _fake_reply(["네"])

    with mock.patch("chat.services.llm.stream_reply", reply):
        _events(_send(client, session))

    assert calls[0]["temperature"] == 0.2


@pytest.mark.django_db
def test_ambiguous_product_names_are_detected(enabled):
    company = make_company()
    tv = make_product(company, name="SC95A", category="TV")
    make_product(company, name="SC95A", category="모니터")
    unique = make_product(company, name="오케이드라이브")
    chunks = list(KnowledgeChunk.objects.filter(product__isnull=False).select_related("product"))

    ids = services.ambiguous_product_ids(chunks)

    assert tv.pk in ids
    assert unique.pk not in ids


@pytest.mark.django_db
def test_custom_system_prompt_is_sent_to_the_llm(client, enabled, session):
    _set(
        system_prompt="당신은 {bot_name}입니다. 항상 존댓말로 답하세요.",
        bot_name="OK봇",
        extra_instructions="짧게",
    )
    reply, calls = _fake_reply(["네"])

    with mock.patch("chat.services.llm.stream_reply", reply):
        _events(_send(client, session))

    assert calls[0]["system"] == (
        "당신은 OK봇입니다. 항상 존댓말로 답하세요.\n\n운영자 추가 지시:\n짧게"
    )
