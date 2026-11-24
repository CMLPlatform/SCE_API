"""Tests for login and ownership rules (dpp.permissions)."""
import uuid

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from ..models import (
    CircularityEvaluation, CircularityIndicator, CircularityScore,
    CircularityTracker, Company, Document, Facility, Flow, ImpactCategory,
    ImpactIndicator, Metadata, Process, ProductBatch, ProductExchange,
    ProductionLine, ProductModel, ProductProperties, SustainabilityEvaluation,
    SustainabilityScore,
)
from ..permissions import can_access, filter_owned


class OwnershipTestCase(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice", password="pw-alice-123")
        self.bob = User.objects.create_user("bob", password="pw-bob-123")
        operator = Company.objects.create(name="ACME", country="DE")
        self.facility = Facility.objects.create(
            operator=operator, country="NL", address="Industrieweg 1"
        )
        self.alice_line = self.make_line(self.alice, "Alice line")
        self.bob_line = self.make_line(self.bob, "Bob line")
        self.alice_process = Process.objects.get(production_line=self.alice_line)

    def make_line(self, user, name):
        product = ProductModel.objects.create(name=f"{name} product")
        line = ProductionLine.objects.create(
            name=name, final_product=product, facility=self.facility, created_by=user
        )
        Process.objects.create(
            name=f"{name} process", production_line=line, functional_flow=product
        )
        return line


class PermissionHelperTests(OwnershipTestCase):
    def test_owner_and_shared_access(self):
        self.assertTrue(can_access(self.alice, self.alice_line))
        self.assertFalse(can_access(self.bob, self.alice_line))
        self.assertFalse(can_access(self.bob, self.alice_process))
        self.assertTrue(can_access(self.bob, self.facility))  # shared data

    def test_exchange_belongs_to_process_owner(self):
        exchange = ProductExchange.objects.create(
            process=self.alice_process, product=self.bob_line.final_product,
            amount=1, direction="in", type="prod",
        )
        self.assertFalse(can_access(self.bob, exchange))
        self.assertEqual(
            list(filter_owned(ProductExchange.objects.all(), self.bob)), []
        )

    def test_filter_owned(self):
        lines = filter_owned(ProductionLine.objects.all(), self.bob)
        self.assertEqual(list(lines), [self.bob_line])
        self.assertEqual(filter_owned(ProductionLine.objects.all(), None).count(), 0)

    def test_staff_sees_everything(self):
        staff = User.objects.create_user("staff", password="pw-staff-123", is_staff=True)
        self.assertEqual(filter_owned(ProductionLine.objects.all(), staff).count(), 2)

    def test_product_belongs_to_line_owner(self):
        alice_product = self.alice_line.final_product
        shared = ProductModel.objects.create(name="Catalogue screw")
        self.assertTrue(can_access(self.alice, alice_product))
        self.assertFalse(can_access(self.bob, alice_product))
        self.assertTrue(can_access(self.bob, shared))
        bob_sees = set(filter_owned(Flow.objects.all(), self.bob))
        self.assertNotIn(alice_product.flow_ptr, bob_sees)
        self.assertIn(shared.flow_ptr, bob_sees)
        self.assertNotIn(alice_product, filter_owned(ProductModel.objects.all(), self.bob))

    def test_final_product_without_process_is_owned(self):
        model = ProductModel.objects.create(name="Batch model")
        batch = ProductBatch.objects.create(model=model, batch_number=1, GTIN="0000000000000")
        ProductionLine.objects.create(
            name="Alice batch line", final_product=batch, facility=self.facility,
            created_by=self.alice,
        )
        self.assertFalse(can_access(self.bob, batch))
        self.assertEqual(filter_owned(ProductBatch.objects.all(), self.bob).count(), 0)

    def test_product_data_belongs_to_product_owner(self):
        props = ProductProperties.objects.create(
            product=self.alice_line.final_product, weight=1, volume=1, density=1,
        )
        self.assertFalse(can_access(self.bob, props))
        self.assertTrue(can_access(self.alice, props))
        self.assertEqual(filter_owned(ProductProperties.objects.all(), self.bob).count(), 0)

    def test_scores_belong_to_product_owner(self):
        product = self.alice_line.final_product
        indicator = ImpactIndicator.objects.create(
            method="EF 3.0", unit="kg CO2 eq",
            impact_category=ImpactCategory.objects.create(name="Climate change"),
        )
        sustainability = SustainabilityScore.objects.create(
            impact_indicator=indicator, impact_value=1, scope_1_2_3=1,
            evaluation=SustainabilityEvaluation.objects.create(
                product=product, functional_amount=1,
            ),
        )
        evaluation = CircularityEvaluation.objects.create(product=product)
        circ = CircularityIndicator.objects.create(id="T01", name="Test", unit="%")
        circularity = CircularityScore.objects.create(evaluation=evaluation, indicator=circ, value=1)
        tracker = CircularityTracker.objects.create(
            evaluation=evaluation, indicator=circ, value=1, name="RFID tag",
        )
        for score in (sustainability, circularity, tracker):
            self.assertTrue(can_access(self.alice, score), score)
            self.assertFalse(can_access(self.bob, score), score)
        for model in (SustainabilityScore, CircularityScore, CircularityTracker):
            self.assertEqual(filter_owned(model.objects.all(), self.bob).count(), 0, model)
            self.assertEqual(filter_owned(model.objects.all(), self.alice).count(),
                             model.objects.count(), model)


class WebViewTests(OwnershipTestCase):
    def test_login_required(self):
        url = reverse("dpp:productionline_list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_list_only_shows_own_lines(self):
        self.client.force_login(self.bob)
        response = self.client.get(reverse("dpp:productionline_list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["object_list"]), [self.bob_line])

    def test_other_users_line_is_not_found(self):
        self.client.force_login(self.bob)
        for url in [
            reverse("dpp:production_line_detail", args=[self.alice_line.pk]),
            reverse("dpp:productionline_update", args=[self.alice_line.pk]),
            reverse("dpp:productionline_delete", args=[self.alice_line.pk]),
            reverse("dpp:process_detail", args=[self.alice_process.pk]),
            reverse("dpp:transport_subset", args=[self.alice_line.pk]),
            reverse("dpp:product_detail", args=[self.alice_line.final_product.pk]),
            reverse("dpp:productmodel_update", args=[self.alice_line.final_product.pk]),
        ]:
            self.assertEqual(self.client.get(url).status_code, 404, url)
        response = self.client.post(
            reverse("dpp:productionline_delete", args=[self.alice_line.pk])
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(ProductionLine.objects.filter(pk=self.alice_line.pk).exists())

    def test_cannot_recalculate_other_users_product(self):
        self.client.force_login(self.bob)
        url = reverse("dpp:product_detail", args=[self.alice_line.final_product.pk])
        self.assertEqual(self.client.post(url, {"recalculate": "1"}).status_code, 404)

    def test_owner_and_shared_products_open(self):
        shared = ProductModel.objects.create(name="Catalogue screw")
        self.client.force_login(self.alice)
        for pk in (self.alice_line.final_product.pk, shared.pk):
            url = reverse("dpp:product_detail", args=[pk])
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_cannot_add_process_to_other_users_line(self):
        self.client.force_login(self.bob)
        product = ProductModel.objects.create(name="Sneaky product")
        response = self.client.post(reverse("dpp:process_add"), {
            "name": "Sneaky process", "amount": 1,
            "production_line": self.alice_line.pk, "functional_flow": product.pk,
        })
        self.assertEqual(response.status_code, 200)  # form shown again with error
        self.assertIn("production_line", response.context["form"].errors)
        self.assertFalse(Process.objects.filter(name="Sneaky process").exists())

    def test_welcome_page_hides_lines_from_anonymous_users(self):
        response = self.client.get(reverse("dpp:home"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["latest_lines"]), [])

    def test_popup_response_escapes_names(self):
        self.client.force_login(self.bob)
        response = self.client.post(
            reverse("dpp:company_add") + "?_popup=1",
            {"name": '</script><script>alert(1)</script>', "country": "DE"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b"<script>alert(1)", response.content)


class ApiTests(OwnershipTestCase):
    def setUp(self):
        super().setUp()
        self.api = APIClient()

    def test_login_required(self):
        response = self.api.get("/api/productionline/")
        self.assertIn(response.status_code, (401, 403))
        response = self.api.post("/api/company/", {"name": "X", "country": "DE"})
        self.assertIn(response.status_code, (401, 403))

    def test_only_own_lines_listed(self):
        self.api.force_authenticate(self.bob)
        response = self.api.get("/api/productionline/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([line["name"] for line in response.data], ["Bob line"])
        response = self.api.get(f"/api/productionline/{self.alice_line.pk}/")
        self.assertEqual(response.status_code, 404)
        response = self.api.delete(f"/api/process/{self.alice_process.pk}/")
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Process.objects.filter(pk=self.alice_process.pk).exists())
        product = self.alice_line.final_product
        response = self.api.get(f"/api/productmodel/{product.pk}/")
        self.assertEqual(response.status_code, 404)

    def test_published_dpps_are_public_but_read_only(self):
        response = self.api.get("/api/metadata/")
        self.assertEqual(response.status_code, 200)
        self.api.force_authenticate(self.bob)
        response = self.api.delete(f"/api/metadata/{uuid.uuid4()}/")
        self.assertEqual(response.status_code, 403)


class UploadValidationTests(TestCase):
    def test_rejects_disallowed_file_type(self):
        doc = Document(file=SimpleUploadedFile("page.html", b"<script></script>"))
        with self.assertRaises(ValidationError) as ctx:
            doc.full_clean()
        self.assertIn("file", ctx.exception.message_dict)

    def test_accepts_pdf(self):
        doc = Document(file=SimpleUploadedFile("report.pdf", b"%PDF-1.4"))
        try:
            doc.full_clean()
        except ValidationError as e:
            self.assertNotIn("file", e.message_dict)
