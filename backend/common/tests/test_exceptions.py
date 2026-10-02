import pytest
from rest_framework import exceptions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.test import APIRequestFactory

from common.exceptions import ApiError
from common.permissions import IsAdminRole

factory = APIRequestFactory()


def _call(exc):
    @api_view(["GET"])
    @permission_classes([AllowAny])
    def view(request):
        raise exc

    return view(factory.get("/"))


def test_validation_error_uses_common_format_with_details():
    response = _call(exceptions.ValidationError({"name": ["이 필드는 필수입니다."]}))

    assert response.status_code == 400
    assert response.data == {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "입력값을 확인해 주세요.",
            "details": {"name": ["이 필드는 필수입니다."]},
        }
    }


def test_api_error_keeps_custom_code_and_status():
    response = _call(ApiError("CHATBOT_DISABLED", "준비 중", status_code=503))

    assert response.status_code == 503
    assert response.data == {"error": {"code": "CHATBOT_DISABLED", "message": "준비 중"}}


@pytest.mark.django_db
def test_default_permission_rejects_anonymous_with_401():
    @api_view(["GET"])
    def admin_only(request):
        return None

    response = admin_only(factory.get("/"))

    assert response.status_code in (401, 403)
    assert response.data["error"]["code"] in ("NOT_AUTHENTICATED", "PERMISSION_DENIED")


@pytest.mark.django_db
def test_is_admin_role_permission(django_user_model):
    admin = django_user_model.objects.create_user("boss", password="x", role="ADMIN")
    user = django_user_model.objects.create_user("guest", password="x")
    request = factory.get("/")
    perm = IsAdminRole()

    request.user = admin
    assert perm.has_permission(request, None) is True
    request.user = user
    assert perm.has_permission(request, None) is False
    admin.is_active = False
    request.user = admin
    assert perm.has_permission(request, None) is False
