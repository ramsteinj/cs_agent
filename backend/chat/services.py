"""RAG orchestration: history + retrieval + Claude streaming (specs/05-rag-pipeline.md)."""

import hashlib
import logging

from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework.throttling import BaseThrottle

import llm
from knowledge.models import KnowledgeChunk, Product
from knowledge.retrieval import search
from settings_app.models import SystemSetting

from .models import ChatMessage, ChatSession
from .prompts import build_system_prompt, build_user_content
from .sources import select_sources

logger = logging.getLogger(__name__)

ERROR_MESSAGE = "일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."


def hash_ip(ip):
    return hashlib.sha256(f"{settings.SECRET_KEY}:{ip or ''}".encode()).hexdigest()


def client_ip(request):
    """Same rule as the DRF throttles: X-Forwarded-For only via NUM_PROXIES trusted hops."""
    return BaseThrottle().get_ident(request)


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


def history_messages(session, before_id, limit):
    """Last N successful messages before the current turn, as Claude message params.

    Failed turns are stored with status=error on both sides and skipped, so roles
    alternate. The list always starts with a user turn.
    """
    if limit <= 0:
        return []
    recent = list(
        session.messages.filter(status=ChatMessage.Status.OK, id__lt=before_id).order_by("-id")[
            :limit
        ]
    )
    recent.reverse()
    while recent and recent[0].role != ChatMessage.Role.USER:
        recent.pop(0)
    return [{"role": m.role, "content": m.content} for m in recent if m.content]


def search_query(session, question, before_id, with_previous=True):
    """Current question (+ the previous user question, so follow-ups keep context)."""
    if not with_previous:
        return question
    previous = (
        session.messages.filter(role=ChatMessage.Role.USER, id__lt=before_id)
        .order_by("-id")
        .values_list("content", flat=True)
        .first()
    )
    return f"{previous}\n{question}" if previous else question


def ambiguous_product_ids(chunks):
    """Products in `chunks` whose name is shared by another product of the same company."""
    keys = {(c.company_id, c.product.name) for c in chunks if c.product_id}
    if not keys:
        return frozenset()
    query = Q()
    for company_id, name in keys:
        query |= Q(company_id=company_id, name=name)
    shared = {
        (row["company_id"], row["name"])
        for row in Product.objects.filter(query)
        .values("company_id", "name")
        .annotate(n=Count("id"))
        .filter(n__gt=1)
    }
    return frozenset(
        c.product_id for c in chunks if c.product_id and (c.company_id, c.product.name) in shared
    )


def sources_from_ids(chunk_ids, answer_text, limit):
    """Rebuild sources for stored messages; chunks re-created by later edits are skipped."""
    chunks = {
        c.pk: c
        for c in KnowledgeChunk.objects.filter(pk__in=chunk_ids).select_related(
            "company", "product", "document"
        )
    }
    found = [chunks[i] for i in chunk_ids if i in chunks]
    return select_sources(found, answer_text, limit, ambiguous_product_ids(found))


# --- Turn --------------------------------------------------------------------


def answer_stream(session, question):
    """Generator of SSE event dicts for one question (start -> delta* -> done | error).

    The caller has already checked the chatbot is enabled and rate limits.
    """
    setting = SystemSetting.load()
    provider = setting.active_provider_config
    api_key = provider.get_api_key()

    user_message = ChatMessage.objects.create(
        session=session, role=ChatMessage.Role.USER, content=question
    )
    assistant = ChatMessage.objects.create(
        session=session, role=ChatMessage.Role.ASSISTANT, model=provider.model
    )
    session.last_activity_at = timezone.now()
    session.save(update_fields=["last_activity_at", "updated_at"])
    yield {"type": "start", "message_id": assistant.pk}

    streamed = []
    try:
        query = search_query(
            session, question, user_message.pk, setting.search_with_previous_question
        )
        chunks = search(query)
        assistant.retrieved_chunk_ids = [c.pk for c in chunks]
        messages = history_messages(session, user_message.pk, setting.history_messages)
        messages.append({"role": "user", "content": build_user_content(question, chunks)})
        system = build_system_prompt(setting.bot_name, setting.extra_instructions)

        replies = llm.stream_reply(
            provider.provider,
            api_key,
            provider.model,
            system,
            messages,
            setting.llm_max_output_tokens,
            provider.temperature,
        )
        while True:
            try:
                text = next(replies)
            except StopIteration as stop:
                final = stop.value
                break
            streamed.append(text)
            yield {"type": "delta", "text": text}
    except Exception as exc:  # LLMError, embedding failures, DB errors...
        if isinstance(exc, llm.LLMError):
            # str(exc) is the provider's safe summary: status / error type / request ID.
            logger.warning(
                "LLM call failed (provider=%s, model=%s): %s",
                provider.provider,
                provider.model,
                exc,
            )
        else:
            logger.exception("Chat turn failed")
        _mark_failed(user_message, assistant, "".join(streamed))
        yield {"type": "error", "code": "LLM_ERROR", "message": ERROR_MESSAGE}
        return
    except GeneratorExit:
        # Client disconnected mid-stream: keep what we have, exclude it from history.
        _mark_failed(user_message, assistant, "".join(streamed))
        raise

    assistant.content = final.text
    assistant.model = final.model or provider.model
    assistant.input_tokens = final.input_tokens
    assistant.output_tokens = final.output_tokens
    assistant.save()

    sources = (
        []
        if final.refused
        else select_sources(chunks, final.text, setting.max_sources, ambiguous_product_ids(chunks))
    )
    done = {"type": "done", "sources": sources}
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
    limit = SystemSetting.load().max_sources
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
            item["sources"] = sources_from_ids(message.retrieved_chunk_ids, message.content, limit)
        result.append(item)
    return result
