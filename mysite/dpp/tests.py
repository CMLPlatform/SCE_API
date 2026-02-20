from django.test import TestCase
from django.urls import reverse
from .models import *

def create_production_system():
    fprod = ProductModel(
        name="final product", unit="bottles", brand="brand name"
    )
    fprod.save()
    pl = ProductionLine(
        name="Production line",
        description="text",
        final_product=fprod,
        operator=get_unknown_company(),
        facility = "facility id"
    )
    pl.save()
    return pl

# Test create a 
class ProductionLineTest(TestCase):
    def test_create_transport(self):
        pl = create_production_system()
        pl.create_transport()
        transport = Transport.objects.all()
        self.assertIsNotNone(transport)

class ViewTest(TestCase):
    def test_production_line_list(self):
        pl = create_production_system()
        response = self.client.get(reverse("dpp:productionline_list"))
        response = self.client.get(reverse("dpp:production_line_detail", args=(pl.id,)))

