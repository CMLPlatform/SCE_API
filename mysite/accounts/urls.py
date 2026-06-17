from django.urls import path

from .views import SignUpView, ProfileView

app_name = "accounts"

urlpatterns = [
    path("signup/", SignUpView.as_view(), name="signup"),
    path('profile/', ProfileView.as_view(), name="profile"),
]
