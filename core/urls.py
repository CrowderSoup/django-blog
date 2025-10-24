from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("page/<slug:slug>/", views.page, name="page"),
]
