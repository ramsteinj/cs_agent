from django.urls import path

from . import views

urlpatterns = [
    path("status", views.status, name="chat-status"),
    path("sessions", views.create_session, name="chat-sessions"),
    path(
        "sessions/<uuid:session_id>/messages", views.session_messages, name="chat-session-messages"
    ),
    path("messages", views.send_message, name="chat-messages"),
]
