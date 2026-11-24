"""Tests for the synthetic demo data (seed_demo) and the example platform requests."""
import json
import re
from io import StringIO
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from dpp.management.commands.seed_demo import LINE_NAME, MANUFACTURER
from dpp.models import (
    Company, ManufacturingProcess, Metadata, Process, ProductBatch, ProductionLine, Publisher,
)
from dss.models import McdaSession

EXAMPLES = Path(settings.BASE_DIR) / "dss" / "examples"


def seed(*args):
    out = StringIO()
    call_command("seed_demo", *args, stdout=out)
    return out.getvalue()


class SeedDemoTests(TestCase):
    def test_loads_a_complete_production_line(self):
        output = seed("--password", "demo-pass-123")
        line = ProductionLine.objects.get(name=LINE_NAME)
        self.assertEqual(line.created_by.username, "demo")
        self.assertEqual(Process.objects.filter(production_line=line).count(), 3)
        self.assertEqual(line.transport.count(), 8)
        self.assertEqual(line.publisher.status, 4)  # steps 1-4 done; step 5 (LCA) needs Brightway
        self.assertTrue(Publisher.objects.filter(production_line=line).exists())
        self.assertEqual(Metadata.objects.filter(reo__name=MANUFACTURER).count(), 1)
        self.assertEqual(line.check_unused_outputs(), "")  # every intermediate product is used
        self.assertEqual(McdaSession.objects.count(), 2)  # PD and KAM examples
        self.assertIn("demo-pass-123", output)
        self.assertTrue(User.objects.get(username="demo").check_password("demo-pass-123"))

    def test_second_run_does_not_duplicate(self):
        seed("--no-dss")
        output = seed("--no-dss")
        self.assertIn("already loaded", output)
        self.assertEqual(ProductionLine.objects.filter(name=LINE_NAME).count(), 1)

    def test_reset_and_remove(self):
        seed("--no-dss")
        seed("--reset", "--no-dss")
        self.assertEqual(ProductionLine.objects.filter(name=LINE_NAME).count(), 1)
        seed("--remove")
        self.assertFalse(ProductionLine.objects.filter(name=LINE_NAME).exists())
        self.assertFalse(Company.objects.filter(name=MANUFACTURER).exists())

    def test_flowchart_shows_only_this_lines_processes(self):
        """After publishing step 2 an aggregated copy of the line exists;
        it must not appear in the line's flowchart."""
        seed("--no-dss")
        line = ProductionLine.objects.get(name=LINE_NAME)
        aggregated = ManufacturingProcess.objects.get(functional_flow=line.final_product, backgroundprocess__isnull=True)
        self.client.force_login(line.created_by)
        response = self.client.get(reverse("dpp:production_line_detail", args=[line.pk]))
        code = response.context["mermaid_code"]
        self.assertIsNone(re.search(rf"\ba{aggregated.pk}\b", code), code)
        for process in line.bop.all():
            self.assertIn(f"a{process.pk}({process.name})", code)

    def test_demo_pages_render(self):
        seed("--no-dss")
        line = ProductionLine.objects.get(name=LINE_NAME)
        self.client.force_login(line.created_by)
        welding = Process.objects.get(name="Dynamic beam laser welding")
        for url in [
            reverse("dpp:production_line_detail", args=[line.pk]),
            reverse("dpp:process_detail", args=[welding.pk]),
            reverse("dpp:product_detail", args=[line.final_product.pk]),
            reverse("dpp:publisher_detail", args=[line.publisher.pk]),
            reverse("dpp:sustainabilityevaluation_list"),
        ]:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        dpp = Metadata.objects.get(reo__name=MANUFACTURER)
        self.client.logout()
        response = self.client.get(reverse("dpp:dpp_full", args=[dpp.pk]))  # public page
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "DEMO-BCP-0001")

    def test_product_page_accepts_batch(self):
        """The product page also opens for a ProductBatch (a Flow that is
        not a ProductModel), e.g. when it is a final product."""
        seed("--no-dss")
        line = ProductionLine.objects.get(name=LINE_NAME)
        model = line.final_product.model
        batch = ProductBatch.objects.create(model=model, batch_number=1, GTIN="0000000000000")
        self.client.force_login(line.created_by)
        response = self.client.get(reverse("dpp:product_detail", args=[batch.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["opts"].model_name, "productbatch")


class ExampleRequestTests(TestCase):
    """The example requests in dss/examples/ are accepted by the API."""

    def post(self, endpoint, file):
        data = json.loads((EXAMPLES / file).read_text())
        return self.client.post(endpoint, data=json.dumps(data), content_type="application/json")

    def test_process_developer_examples(self):
        response = self.post("/dss/experiment/", "pd_experiment_single.json")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertGreater(response.json()["Process carbon footprint"], 0)
        response = self.post("/dss/experiments/", "pd_experiments.json")
        self.assertEqual(response.status_code, 302, response.content)
        self.assertIn("/step/0/", response["Location"])

    def test_key_account_manager_examples(self):
        response = self.post("/dss/welding-station/", "kam_welding_station_single.json")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertGreater(response.json()["Total production costs"], 0)
        response = self.post("/dss/welding-stations/", "kam_welding_stations.json")
        self.assertEqual(response.status_code, 201, response.content)
        self.assertIn("session_id", response.json())


class PublisherViewTests(TestCase):
    def setUp(self):
        seed("--no-dss")
        self.line = ProductionLine.objects.get(name=LINE_NAME)
        self.publisher = self.line.publisher
        self.client.force_login(self.line.created_by)

    def test_update_redirects_to_detail_page(self):
        from django.forms.models import model_to_dict
        data = {k: v for k, v in model_to_dict(self.publisher).items() if v is not None}
        data["amount"] = 7
        response = self.client.post(reverse("dpp:publisher_update", args=[self.publisher.pk]), data)
        self.assertRedirects(response, reverse("dpp:publisher_detail", args=[self.publisher.pk]))
        self.publisher.refresh_from_db()
        self.assertEqual(self.publisher.amount, 7)

    def test_detail_page_lists_problems_with_fix_links(self):
        self.line.final_product.details.delete()
        response = self.client.get(reverse("dpp:publisher_detail", args=[self.publisher.pk]))
        self.assertContains(response, "before you run the steps")
        self.assertContains(response, f"{reverse('dpp:dppdetails_add')}?product={self.line.final_product.pk}")

    def test_create_form_returns_to_next_url(self):
        product = self.line.final_product
        product.details.delete()
        back = reverse("dpp:publisher_detail", args=[self.publisher.pk])
        url = f"{reverse('dpp:dppdetails_add')}?product={product.pk}&next={back}"
        response = self.client.post(url, {"product": product.pk, "warranty_period": 0, "spare_parts_availability_duration": 0, "takeback_system": "no"})
        self.assertRedirects(response, back)

    def test_create_form_ignores_next_url_to_other_site(self):
        product = self.line.final_product
        product.details.delete()
        url = f"{reverse('dpp:dppdetails_add')}?next=https://evil.example/"
        response = self.client.post(url, {"product": product.pk, "warranty_period": 0, "spare_parts_availability_duration": 0, "takeback_system": "no"})
        self.assertRedirects(response, reverse("dpp:dppdetails_list"), fetch_redirect_response=False)

    def test_failed_run_shows_error_message(self):
        self.line.final_product.details.delete()
        url = reverse("dpp:publisher_detail", args=[self.publisher.pk])
        response = self.client.post(url, {"action": "run_all"}, follow=True)
        texts = [str(m) for m in response.context["messages"]]
        self.assertTrue(any("DPP details missing" in t for t in texts), texts)
        self.assertFalse(any("successfully" in t for t in texts), texts)
