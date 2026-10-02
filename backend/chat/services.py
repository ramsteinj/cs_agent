"""RAG orchestration: history + retrieval + Claude streaming (specs/05-rag-pipeline.md)."""

import hashlib
import logging

from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone

from knowledge.models import KnowledgeChunk
from knowledge.retrieval import search
from settings_app.models import SystemSetting

from . import llm
from .models import ChatMessage, ChatSession
from .prompts import build_system_prompt, build_user_content

logger = logging.getLogger(__name__)

ERROR_MESSAGE = "일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."


def hash_ip(ip):
    return hashlib.sha256(f"{settings.SECRET_KEY}:{ip or ''}".encode()).hexdigest()


def client_ip(request):
    # REMOTE_ADDR only: X-Forwarded-For is client-controlled unless a trusted proxy sets it.
    return request.META.get("REMOTE_ADDR", "")


def create_session(ip):
    return ChatSession.objects.create(client_ip_hash=hash_ip(ip))


# --- Rate limits (specs/07 §4) ---------------------------------------------


def ip_rate_limited(ip):
    """Fixed one-minute window per hashed IP. Returns True when over the limit."""
    key = f"chat-rate:{hash_ip(ip)}:{int(timezone.now().timestamp() // 60)}"
    added = cache.add(key, 1, timeout=60)
    count = 1 if added else cache.incr(key)
    return count > settings.CHAT_IP_RATE_PER_MINUTE


def session_full(session):
    count = session.messages.filter(role=ChatMessage.Role.USER).count()
    return count >= settings.CHAT_SESSION_MAX_MESSAGES


# --- Prompt inputs -----------------------------------------------------------


def history_messages(session, before_id):
    """Last N successful messages before the current turn, as Claude message params.

    Failed turns are stored with status=error on both sides and skipped, so roles
    alternate. The list always starts with a user turn.
    """
    recent = list(
        session.messages.filter(status=ChatMessage.Status.OK, id__lt=before_id).order_by("-id")[
            : settings.CHAT_HISTORY_MESSAGES
        ]
    )
    recent.reverse()
    while recent and recent[0].role != ChatMessage.Role.USER:
        recent.pop(0)
    return [{"role": m.role, "content": m.content} for m in recent if m.content]


def search_query(session, question, before_id):
    """Current question + the previous user question, so follow-ups keep context."""
    previous = (
        session.messages.filter(role=ChatMessage.Role.USER, id__lt=before_id)
        .order_by("-id")
        .values_list("content", flat=True)
        .first()
    )
    return f"{previous}\n{question}" if previous else question


def sources_for(chunks):
    """Unique sources in relevance order, at most CHAT_MAX_SOURCES."""
    sources, seen = [], set()
    for chunk in chunks:
        key = (chunk.source_type, chunk.source_id)
        if key in seen:
            continue
        seen.add(key)
        title = chunk.product.name if chunk.product_id else chunk.company.name
        sources.append({"type": chunk.source_type, "id": chunk.source_id, "title": title})
        if len(sources) == settings.CHAT_MAX_SOURCES:
            break
    return sources


def sources_from_ids(chunk_ids):
    """Rebuild sources for stored messages; chunks re-created by later edits are skipped."""
    chunks = {
        c.pk: c
        for c in KnowledgeChunk.objects.filter(pk__in=chunk_ids).select_related(
            "company", "product"
        )
    }
    return sources_for([chunks[i] for i in chunk_ids if i in chunks])


# --- Turn --------------------------------------------------------------------


def answer_stream(session, question):
    """Generator of SSE event dicts for one question (start -> delta* -> done | error).

    The caller has already checked the chatbot is enabled and rate limits.
    """
    setting = SystemSetting.load()
    api_key = setting.get_api_key()

    user_message = ChatMessage.objects.create(
        session=session, role=ChatMessage.Role.USER, content=question
    )
    assistant = ChatMessage.objects.create(
        session=session, role=ChatMessage.Role.ASSISTANT, model=setting.claude_model
    )
    session.last_activity_at = timezone.now()
    session.save(update_fields=["last_activity_at", "updated_at"])
    yield {"type": "start", "message_id": assistant.pk}

    streamed = []
    try:
        chunks = search(search_query(session, question, user_message.pk))
        assistant.retrieved_chunk_ids = [c.pk for c in chunks]
        messages = history_messages(session, user_message.pk)
        messages.append({"role": "user", "content": build_user_content(question, chunks)})
        system = build_system_prompt(setting.bot_name, setting.extra_instructions)

        replies = llm.stream_reply(api_key, setting.claude_model, system, messages)
        while True:
            try:
                text = next(replies)
            except StopIteration as stop:
                final = stop.value
                break
            streamed.append(text)
            yield {"type": "delta", "text": text}
    except Exception as exc:  # LLMError, embedding failures, DB errors...
        if not isinstance(exc, llm.LLMError):
            logger.exception("Chat turn failed")
        _mark_failed(user_message, assistant, "".join(streamed))
        yield {"type": "error", "code": "LLM_ERROR", "message": ERROR_MESSAGE}
        return
    except GeneratorExit:
        # Client disconnected mid-stream: keep what we have, exclude it from history.
        _mark_failed(user_message, assistant, "".join(streamed))
        raise

    assistant.content = final.text
    assistant.model = final.model or setting.claude_model
    assistant.input_tokens = final.input_tokens
    assistant.output_tokens = final.output_tokens
    assistant.save()

    done = {"type": "done", "sources": [] if final.refused else sources_for(chunks)}
    if final.text != "".join(streamed):
        # e.g. refusal after partial output: the client must replace what it showed.
        done["replace_text"] = final.text
    yield done


def _mark_failed(user_message, assistant, partial_text):
    assistant.content = partial_text
    assistant.status = ChatMessage.Status.ERROR
    assistant.save()
    user_message.status = ChatMessage.Status.ERROR
    user_message.save(update_fields=["status", "updated_at"])


def public_messages(session):
    """Messages for restoring the chat after a page reload."""
    result = []
    for message in session.messages.filter(~Q(content="") | Q(status=ChatMessage.Status.ERROR)):
        item = {
            "id": message.pk,
            "role": message.role,
            "content": message.content,
            "status": message.status,
            "created_at": message.created_at,
        }
        if message.role == ChatMessage.Role.ASSISTANT:
            item["sources"] = sources_from_ids(message.retrieved_chunk_ids)
        result.append(item)
    return result
