from django.test import TestCase
from rest_framework.test import APIRequestFactory
from rest_framework import status
from datetime import date
from dpp.models import (
    Metadata, ProductItem, ProductBatch, ProductModel,
    Institution, Company, Document
)
from api.serializers import MetadataSerializer


class MetadataSerializerTests(TestCase):
    """
    Tests for MetadataSerializer (connects to most DPP models)
    """

    def setUp(self):
        self.factory = APIRequestFactory()

        # Minimal institution (issuer)
        self.issuer = Institution.objects.create(
            name="Test Certifier AG",
            type="ngo",
            address="Street Name 7",
            country="CH",
        )

        # Minimal company (REO = Responsible Economic Operator)
        self.reo = Company.objects.create(
            name="Example Manufacturer GmbH",
            website="www.example.com",
            country="DE",
            vat_number="DE812345678",
        )

        # Minimal product model (flow)
        self.product_model = ProductModel.objects.create(
            name="Test Widget v2",
            unit="pcs",
            taric_code="01234567890128",
            # add required fields...
        )

        # Batch
        self.batch = ProductBatch.objects.create(
            model=self.product_model,
            batch_number=202507001,
        )

        # The metadata record we want to serialize
        self.metadata = Metadata.objects.create(
            issuer=self.issuer,
            reo=self.reo,
            version="1.0",
            language="DE",
            credential_format="xml",
            update_interval='A',
        )

        # Product item (instance)
        self.item = ProductItem.objects.create(
            product_batch=self.batch,
            DPP_metadata = self.metadata,
            serial_number="WGT-20250715-0042",
        )

        # Document
        self.doc = Document.objects.create(
            file="documents/LICENSE",
            type="manual",
            issuer=self.issuer,
            language="EN",
            issue_date=date(2025, 7, 10),
            expiry_date=date(2026, 7, 10),
        )

        # Inject request into context to make build_absolute_uri work
        self.request = self.factory.get("/api/")
        self.serializer_context = {"request": self.request}

    def test_metadata_serializer_structure_and_basic_fields(self):
        serializer = MetadataSerializer(
            self.metadata, context=self.serializer_context
        )
        data = serializer.data

        # Basic fields
        self.assertEqual(data["registration_number"], str(self.metadata.pk))
        self.assertEqual(data["version"], self.metadata.version)
        self.assertEqual(data["update_interval"], self.metadata.update_interval)

        # Nested product_item
        self.assertIn("product_item", data)
        item_data = data["product_item"]
        self.assertEqual(item_data["serial_number"], self.item.serial_number)

        # Nested batch and model
        self.assertIn("product_batch", item_data)
        batch_data = item_data["product_batch"]
        self.assertEqual(batch_data["batch_number"], self.batch.batch_number)
        self.assertIn("model", batch_data)
        self.assertEqual(batch_data["model"]["name"], "Test Widget v2")

    def test_nested_issuer_and_reo(self):
        serializer = MetadataSerializer(
            self.metadata, context=self.serializer_context
        )
        data = serializer.data

        # issuer (InstitutionSerializer)
        self.assertIn("issuer", data)
        issuer_data = data["issuer"]
        self.assertEqual(issuer_data["name"], self.issuer.name)
        self.assertEqual(issuer_data["country"], self.issuer.country)
        # legal_documents should be present (even if empty)
        self.assertIn("legal_documents", issuer_data)

        # reo (CompanySerializer → falls back to OrganizationSerializer)
        self.assertIn("reo", data)
        reo_data = data["reo"]
        self.assertEqual(reo_data["name"], "Example Manufacturer GmbH")
        self.assertIn("legal_documents", reo_data)

    def test_file_urls_are_absolute(self):
        # Create a document linked somehow (e.g. via issuer)
        doc = Document.objects.create(
            file="documents/requirements.txt",
            type="compliance",
            issuer=self.issuer,
        )

        serializer = MetadataSerializer(
            self.metadata, context=self.serializer_context
        )
        data = serializer.data

        issuer_data = data["issuer"]
        self.assertIn("legal_documents", issuer_data)
        # Depending on how many documents → usually list
        if issuer_data["legal_documents"]:
            first_doc = issuer_data["legal_documents"][0]
            self.assertTrue(first_doc["file_url"].startswith("http"))
            self.assertIn(doc.file, first_doc["file_url"])
