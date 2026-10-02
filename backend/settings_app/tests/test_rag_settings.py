import logging
from unittest import mock

import pytest

from common.exceptions import ApiError
from knowledge.models import KnowledgeChunk
from knowledge.tests.factories import make_company, make_product
from settings_app.models import SystemSetting

URL = "/api/admin/settings/rag"


@pytest.mark.django_db
class TestRagSettingsApi:
    def test_defaults(self, admin_client):
        body = admin_client.get(URL).json()

        assert body == {
            "embedding_model": "intfloat/multilingual-e5-small",
            "embedding_dim": 384,
            "chunk_max_chars": 500,
            "chunk_overlap_chars": 100,
            "retrieval_top_k": 5,
            "retrieval_max_distance": 0.6,
            "search_with_previous_question": True,
            "history_messages": 10,
            "max_sources": 3,
            "llm_max_output_tokens": 4096,
            "reindexed_chunks": None,
        }

    def test_update_without_reindex(self, admin_client):
        response = admin_client.patch(
            URL, {"retrieval_top_k": 8, "retrieval_max_distance": 0.25}, format="json"
        )

        assert response.status_code == 200
        assert response.json()["reindexed_chunks"] is None
        setting = SystemSetting.load()
        assert (setting.retrieval_top_k, setting.retrieval_max_distance) == (8, 0.25)

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("chunk_max_chars", 50),
            ("chunk_max_chars", 5000),
            ("retrieval_top_k", 0),
            ("retrieval_top_k", 21),
            ("retrieval_max_distance", 2.5),
            ("history_messages", 51),
            ("max_sources", 11),
            ("llm_max_output_tokens", 100),
            ("embedding_model", "bad model name"),
        ],
    )
    def test_out_of_range_values_are_field_errors(self, admin_client, field, value):
        response = admin_client.patch(URL, {field: value}, format="json")

        assert response.status_code == 400
        assert field in response.json()["error"]["details"]

    def test_overlap_must_be_smaller_than_max(self, admin_client):
        response = admin_client.patch(
            URL, {"chunk_max_chars": 200, "chunk_overlap_chars": 200}, format="json"
        )

        assert response.status_code == 400
        assert "chunk_overlap_chars" in response.json()["error"]["details"]

    def test_chunk_change_reindexes_everything(self, admin_client):
        long_text = " ".join(f"{i}번째 문장은 긴 제품 설명입니다." for i in range(80))
        product = make_product(make_company(), description=long_text)
        before = KnowledgeChunk.objects.filter(product=product).count()

        response = admin_client.patch(
            URL, {"chunk_max_chars": 200, "chunk_overlap_chars": 20}, format="json"
        )

        assert response.status_code == 200
        assert response.json()["reindexed_chunks"] == KnowledgeChunk.objects.count()
        after = KnowledgeChunk.objects.filter(product=product)
        assert after.count() > before
        assert all(len(c.content.split("\n", 1)[1]) <= 200 for c in after)

    def test_failed_reindex_rolls_back_the_change(self, admin_client):
        with mock.patch(
            "settings_app.rag.reindex_all",
            side_effect=ApiError("CONFLICT", "재색인이 이미 진행 중입니다.", 409),
        ):
            response = admin_client.patch(URL, {"chunk_max_chars": 300}, format="json")

        assert response.status_code == 409
        assert SystemSetting.load().chunk_max_chars == 500

    def test_embedding_model_with_wrong_dimension_is_rejected(self, admin_client, settings):
        settings.EMBEDDING_BACKEND = "sentence_transformers"
        model = mock.Mock(spec=["get_embedding_dimension", "encode"])
        model.get_embedding_dimension.return_value = 768
        with mock.patch("sentence_transformers.SentenceTransformer", return_value=model):
            response = admin_client.patch(
                URL, {"embedding_model": "intfloat/multilingual-e5-base"}, format="json"
            )

        assert response.status_code == 400
        assert "384차원" in response.json()["error"]["details"]["embedding_model"][0]
        assert SystemSetting.load().embedding_model == "intfloat/multilingual-e5-small"

    def test_unloadable_embedding_model_returns_embedding_error(self, admin_client, settings):
        settings.EMBEDDING_BACKEND = "sentence_transformers"
        with mock.patch("sentence_transformers.SentenceTransformer", side_effect=OSError("404")):
            response = admin_client.patch(URL, {"embedding_model": "no/such-model"}, format="json")

        assert response.status_code == 503
        assert response.json()["error"]["code"] == "EMBEDDING_ERROR"
        assert SystemSetting.load().embedding_model == "intfloat/multilingual-e5-small"

    def test_change_is_audited(self, admin_client, caplog):
        caplog.set_level(logging.INFO, logger="audit")

        admin_client.patch(URL, {"max_sources": 2, "retrieval_top_k": 5}, format="json")

        assert "event=rag_settings_updated user='manager' fields='max_sources'" in caplog.text
