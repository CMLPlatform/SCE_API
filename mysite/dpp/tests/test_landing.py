"""Tests for the public landing page at /."""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class LandingPageTests(TestCase):
    def test_public_page_renders(self):
        response = self.client.get(reverse("landing"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "landing.html")
        self.assertContains(response, "Sustainability and Cost Evaluator")
        self.assertContains(response, "css/landing.css")

    def test_anonymous_user_sees_sign_in_and_request_access(self):
        response = self.client.get(reverse("landing"))
        login = reverse("login") + "?next=" + reverse("dpp:home")
        self.assertContains(response, f'href="{login}"')
        self.assertContains(response, f'href="{reverse("accounts:signup")}"')
        self.assertNotContains(response, "Open the app")

    def test_logged_in_user_gets_link_to_the_app(self):
        user = User.objects.create_user("alice", password="pw-alice-123")
        self.client.force_login(user)
        response = self.client.get(reverse("landing"))
        self.assertContains(response, "Open the app")
        self.assertContains(response, f'href="{reverse("dpp:home")}"')
        self.assertNotContains(response, "Request access")

    def test_logout_returns_to_landing_page(self):
        user = User.objects.create_user("bob", password="pw-bob-123")
        self.client.force_login(user)
        response = self.client.post(reverse("logout"))
        self.assertRedirects(response, reverse("landing"), fetch_redirect_response=False)
