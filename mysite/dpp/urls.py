from django.urls import path

from . import views

app_name = "dpp"

urlpatterns = [
    path("home", views.start, name="Welcome Page"),
    path("production-lines/create/", views.production_line_create, name="production_line_create"),
    path("production-lines/<int:pk>/edit/", views.production_line_edit, name="production_line_edit"),
]