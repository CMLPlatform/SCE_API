"""Tests for the published DPPs page: ownership, grouping by batch, bulk delete."""
import uuid

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from ..models import (
    Company, Facility, Metadata, Process, ProductBatch, ProductionLine,
    ProductItem, ProductModel,
)
from ..permissions import can_access, filter_owned

LIST_URL = reverse("dpp:metadata_list")
DELETE_URL = reverse("dpp:metadata_bulk_delete")


class PublishedDppTestCase(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice", password="pw-alice-123")
        self.bob = User.objects.create_user("bob", password="pw-bob-123")
        self.reo = Company.objects.create(name="ACME", country="DE")
        self.facility = Facility.objects.create(
            operator=self.reo, country="NL", address="Industrieweg 1"
        )
        self.alice_model = self.make_line(self.alice, "Alice")
        self.bob_model = self.make_line(self.bob, "Bob")
        # Publishing a product model makes a batch that no line makes
        self.alice_batch_1 = self.make_batch(self.alice_model, 1)
        self.alice_batch_2 = self.make_batch(self.alice_model, 2)
        self.bob_batch = self.make_batch(self.bob_model, 1)
        self.alice_dpps = (
            self.make_dpps(self.alice_batch_1, 3) + self.make_dpps(self.alice_batch_2, 2)
        )
        self.bob_dpps = self.make_dpps(self.bob_batch, 2)

    def make_line(self, user, name):
        product = ProductModel.objects.create(name=f"{name} product")
        line = ProductionLine.objects.create(
            name=f"{name} line", final_product=product, facility=self.facility,
            created_by=user,
        )
        Process.objects.create(
            name=f"{name} process", production_line=line, functional_flow=product
        )
        return product

    def make_batch(self, model, number):
        return ProductBatch.objects.create(model=model, batch_number=number, GTIN="0000000000000")

    def make_dpps(self, batch, amount):
        dpps = []
        for i in range(amount):
            item = ProductItem.objects.create(
                product_batch=batch,
                serial_number=f"{batch.model.pk}-{batch.batch_number}-{i}",
            )
            dpps.append(Metadata.objects.create(
                product_item=item, issuer=self.reo, reo=self.reo,
                version="1.0", credential_format="json_ld",
            ))
        return dpps

    def pks(self, dpps):
        return [str(dpp.pk) for dpp in dpps]


class DppOwnershipTests(PublishedDppTestCase):
    def test_dpp_belongs_to_owner_of_product_model(self):
        self.assertTrue(can_access(self.alice, self.alice_dpps[0]))
        self.assertFalse(can_access(self.bob, self.alice_dpps[0]))
        self.assertEqual(
            set(filter_owned(Metadata.objects.all(), self.bob)), set(self.bob_dpps)
        )

    def test_dpp_belongs_to_owner_of_batch_line(self):
        # Bob's line makes a batch of Alice's model: the DPPs are Bob's
        batch = self.make_batch(self.alice_model, 3)
        ProductionLine.objects.create(
            name="Bob batch line", final_product=batch, facility=self.facility,
            created_by=self.bob,
        )
        dpp = self.make_dpps(batch, 1)[0]
        self.assertTrue(can_access(self.bob, dpp))
        self.assertFalse(can_access(self.alice, dpp))
        self.assertNotIn(dpp, filter_owned(Metadata.objects.all(), self.alice))

    def test_dpp_of_unowned_product_is_shared(self):
        shared = self.make_batch(ProductModel.objects.create(name="Catalogue screw"), 1)
        dpp = self.make_dpps(shared, 1)[0]
        self.assertTrue(can_access(self.bob, dpp))
        self.assertIn(dpp, filter_owned(Metadata.objects.all(), self.bob))

    def test_other_users_dpp_pages_return_404(self):
        self.client.force_login(self.bob)
        pk = self.alice_dpps[0].pk
        for name in ("metadata_detail", "metadata_update", "metadata_delete"):
            response = self.client.get(reverse(f"dpp:{name}", args=[pk]))
            self.assertEqual(response.status_code, 404, name)

    def test_api_still_shows_every_dpp(self):
        # The public DPP page (DppFullView) does not use filter_owned either
        pk = self.alice_dpps[0].pk
        api = APIClient()
        response = api.get("/api/metadata/")
        self.assertEqual(len(response.data), len(self.alice_dpps) + len(self.bob_dpps))
        api.force_authenticate(self.bob)
        self.assertEqual(api.get(f"/api/metadata/{pk}/").status_code, 200)


class DppListTests(PublishedDppTestCase):
    def test_login_required(self):
        response = self.client.get(LIST_URL)
        self.assertEqual(response.status_code, 302)

    def test_lists_own_dpps_grouped_by_batch(self):
        self.client.force_login(self.alice)
        response = self.client.get(LIST_URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["object_list"]), self.alice_dpps)
        self.assertContains(response, "5 DPPs in 2 batches")
        self.assertContains(response, 'data-group="batch-1"')
        self.assertContains(response, 'data-group="batch-2"')
        self.assertNotContains(response, 'data-group="batch-3"')
        self.assertContains(response, "data-select-group", count=2)
        self.assertContains(response, "data-select-row", count=5)
        self.assertContains(response, "data-select-all")
        for dpp in self.bob_dpps:
            self.assertNotContains(response, str(dpp.pk))

    def test_groups_are_collapsed(self):
        self.client.force_login(self.alice)
        response = self.client.get(LIST_URL)
        self.assertContains(response, 'class="group-rows" hidden', count=2)
        self.assertContains(response, 'aria-expanded="false"', count=2)

    def test_empty_list(self):
        Metadata.objects.all().delete()
        self.client.force_login(self.alice)
        response = self.client.get(LIST_URL)
        self.assertContains(response, "No published DPPs yet.")
        self.assertNotContains(response, "data-delete-selected")


class DppBulkDeleteTests(PublishedDppTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.alice)

    def test_first_post_asks_for_confirmation(self):
        selected = self.alice_dpps[:2]
        response = self.client.post(DELETE_URL, {"pk": self.pks(selected)})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dpp/metadata_confirm_bulk_delete.html")
        self.assertContains(response, "Delete 2 DPPs")
        self.assertEqual(Metadata.objects.count(), 7)

    def test_confirm_deletes_selected_dpps_only(self):
        selected = self.alice_dpps[:2]
        response = self.client.post(DELETE_URL, {"pk": self.pks(selected), "confirm": "1"})
        self.assertRedirects(response, LIST_URL)
        remaining = set(Metadata.objects.all())
        self.assertEqual(remaining, set(self.alice_dpps[2:] + self.bob_dpps))
        # The product items stay
        self.assertEqual(ProductItem.objects.count(), 7)

    def test_delete_all(self):
        response = self.client.post(DELETE_URL, {"pk": self.pks(self.alice_dpps), "confirm": "1"})
        self.assertRedirects(response, LIST_URL)
        self.assertEqual(set(Metadata.objects.all()), set(self.bob_dpps))
        messages = [str(m) for m in response.wsgi_request._messages]
        self.assertEqual(messages, ["5 DPPs deleted."])

    def test_ignores_other_users_dpps(self):
        selected = self.pks(self.bob_dpps) + self.pks(self.alice_dpps[:1])
        self.client.post(DELETE_URL, {"pk": selected, "confirm": "1"})
        self.assertEqual(set(Metadata.objects.all()), set(self.alice_dpps[1:] + self.bob_dpps))

    def test_only_other_users_dpps_deletes_nothing(self):
        response = self.client.post(DELETE_URL, {"pk": self.pks(self.bob_dpps), "confirm": "1"})
        self.assertRedirects(response, LIST_URL)
        self.assertEqual(Metadata.objects.count(), 7)

    def test_nothing_or_invalid_selected(self):
        for data in ({}, {"pk": ["not-a-uuid", str(uuid.uuid4())], "confirm": "1"}):
            response = self.client.post(DELETE_URL, data)
            self.assertRedirects(response, LIST_URL)
        self.assertEqual(Metadata.objects.count(), 7)

    def test_get_not_allowed(self):
        self.assertEqual(self.client.get(DELETE_URL).status_code, 405)

    def test_login_required(self):
        self.client.logout()
        response = self.client.post(DELETE_URL, {"pk": self.pks(self.alice_dpps), "confirm": "1"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Metadata.objects.count(), 7)
