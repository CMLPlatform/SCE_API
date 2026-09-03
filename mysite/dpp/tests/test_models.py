from django.test import TestCase
from django.urls import reverse
from ..models import *

# Test creating a production line and transport
class ProductionLineTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            username="test_user", password="notsosecret"
        )
        self.fprod = ProductModel.objects.create(
            name="final product", unit="bottles", brand="brand name"
        )
        self.operator = Company.objects.create(
            name="Example Manufacturer GmbH",
            website="www.example.com",
            country="DE",
            vat_number="DE812345678",
        )
        facility = Facility.objects.create(
            operator=self.operator,
            country='NL',
            address="Industrieweg 1, Utrecht",
        )
        self.pl = ProductionLine.objects.create(
            name="Production line",
            description="text",
            final_product=self.fprod,
            facility=facility,
            created_by=self.user,
        )

    def test_create_transport(self):
        self.pl.create_transport()
        transport = Transport.objects.all()
        self.assertIsNotNone(transport)

    def test_production_line_list(self):
        response = self.client.get(reverse("dpp:productionline_list"))
        response = self.client.get(reverse("dpp:production_line_detail", args=(self.pl.id,)))

