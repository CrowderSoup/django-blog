from django.urls import path

from .views import MicrosubView, WebSubCallbackView

urlpatterns = [
    path("microsub", MicrosubView.as_view(), name="microsub-endpoint"),
    path(
        "microsub/websub/callback/<int:subscription_id>/",
        WebSubCallbackView.as_view(),
        name="microsub-websub-callback",
    ),
]
