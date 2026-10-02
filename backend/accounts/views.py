from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from . import services
from .serializers import ChangePasswordSerializer, LoginSerializer, UserSerializer


class LoginRateThrottle(SimpleRateThrottle):
    """10/min per client IP (specs/07-security.md §2)."""

    scope = "login"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([LoginRateThrottle])
def login(request):
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user, token = services.login_admin(**serializer.validated_data)
    return Response({"token": token, "user": UserSerializer(user).data})


@api_view(["POST"])
def logout(request):
    services.logout(request.user)
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
def me(request):
    return Response(UserSerializer(request.user).data)


@api_view(["POST"])
def change_password(request):
    serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    token = services.change_password(request.user, serializer.validated_data["new_password"])
    return Response({"token": token, "user": UserSerializer(request.user).data})
