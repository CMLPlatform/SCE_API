"""Tests for the form card: add and edit forms shown in a dialog (FormCardMixin)."""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from ..models import Company


class FormCardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("carol", password="pw-carol-123")
        self.client.force_login(self.user)
        self.company = Company.objects.create(name="ACME", country="DE")

    def test_card_sends_only_the_form(self):
        response = self.client.get(reverse("dpp:company_add") + "?_card=1")
        self.assertTemplateUsed(response, "dpp/partials/form_card.html")
        self.assertTemplateNotUsed(response, "base.html")
        self.assertContains(response, 'data-card-title="New company"')
        self.assertContains(response, "data-card-cancel")

    def test_full_page_still_works(self):
        response = self.client.get(reverse("dpp:company_add"))
        self.assertTemplateUsed(response, "dpp/generic_form.html")
        self.assertContains(response, 'id="form-card"')

    def test_form_page_does_not_load_admin_scripts(self):
        # /admin/jsi18n/ sends users who are not staff to the admin log-in page
        response = self.client.get(reverse("dpp:company_update", args=[self.company.pk]))
        self.assertNotContains(response, "jsi18n")
        self.assertNotContains(response, "RelatedObjectLookups")

    def test_invalid_post_shows_the_form_again_with_errors(self):
        response = self.client.post(reverse("dpp:company_add") + "?_card=1", {"name": ""})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dpp/partials/form_card.html")
        self.assertContains(response, "Not saved.")

    def test_edit_in_card_returns_json(self):
        response = self.client.post(
            reverse("dpp:company_update", args=[self.company.pk]) + "?_card=1",
            {"name": "ACME Europe", "country": "DE"},
        )
        self.assertEqual(response.json(), {"pk": str(self.company.pk), "name": "ACME Europe"})
        self.company.refresh_from_db()
        self.assertEqual(self.company.name, "ACME Europe")

    def test_full_page_save_still_redirects(self):
        response = self.client.post(
            reverse("dpp:company_update", args=[self.company.pk]) + "?next=/dpp/welcome/",
            {"name": "ACME Europe", "country": "DE"},
        )
        self.assertRedirects(response, "/dpp/welcome/", fetch_redirect_response=False)

    def test_new_product_choice_in_card(self):
        response = self.client.get(reverse("dpp:flow_add") + "?_card=1")
        self.assertTemplateUsed(response, "dpp/partials/create_flow_card.html")
        self.assertContains(response, "data-card-link")
