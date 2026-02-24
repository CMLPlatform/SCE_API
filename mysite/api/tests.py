from django.test import TestCase
from rest_framework.test import APIRequestFactory
from rest_framework import status
from datetime import date
from dpp.models import (
    Metadata, ProductItem, ProductBatch, ProductModel,
    Institution, Company, ServiceOperator, Document, DppDetails,
    Component, Concentration, Material,
    InspectionEvent, DisassemblyEvent, MaintenanceEvent, ItemExchange,
    ManufacturingProcess, Facility, ProductExchange,
)
from api.serializers import MetadataSerializer, ProductItemSerializer


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

        # Documents
        self.doc1 = Document.objects.create(
            file="documents/LICENSE",
            type="manual",
            issuer=self.issuer,
            language="EN",
            issue_date=date(2025, 7, 10),
            expiry_date=date(2026, 7, 10),
        )
        self.doc2 = Document.objects.create(
            file="documents/requirements.txt",
            type="compliance",
            issuer=self.issuer,
        )

        # Minimal product model (flow)
        self.product_model = ProductModel.objects.create(
            name="Test Widget v2",
            unit="pcs",
            taric_code="01234567890128",
        )
        self.details = DppDetails.objects.create(
            product=self.product_model,
            warranty_period=10,
        )
        self.details.compliance_documents.set([self.doc1, self.doc2])
        self.details.save()

        # Batch
        self.batch = ProductBatch.objects.create(
            model=self.product_model,
            batch_number=202507001,
        )

        # Product item (instance)
        self.item = ProductItem.objects.create(
            product_batch=self.batch,
            serial_number="WGT-20250715-0042",
        )

        # The metadata record we want to serialize
        self.metadata = Metadata.objects.create(
            product_item = self.item,
            issuer=self.issuer,
            reo=self.reo,
            version="1.0",
            language="DE",
            credential_format="xml",
            update_interval='A',
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
        model_data = batch_data["model"]
        self.assertEqual(model_data["name"], "Test Widget v2")

        # Check DppDetails
        expected_details = {
            'compliance_documents': {
                'manual': ['/documents/LICENSE'],
                'compliance': ['/documents/requirements.txt']
            },
            'CPV_code': '',
            'GS1_GPC_code': '',
            'warranty_period': '10.0',
            'spare_parts_availability_duration': '0.0',
            'takeback_system': 'no',
            'importer': None,
        }
        self.assertDictEqual(model_data['details'], expected_details)

    def test_nested_issuer_and_reo(self):
        serializer = MetadataSerializer(
            self.metadata, context=self.serializer_context
        )
        data = serializer.data
        print(data)

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

class LifeCycleEventSerializerTests(TestCase):
    """
    Tests for LifeCycleEventSerializer and its child classes
    """

    def setUp(self):
        self.api_factory = APIRequestFactory()

        # Create test objects
        self.electricity = ProductModel.objects.create(
            name="Electricity, low voltage, grid mix NL",
            unit="kWh",
        )
        self.product_model = ProductModel.objects.create(
            name="Smartphone model W",
            unit="pcs",
            taric_code="012345678901",
        )
        self.batch = ProductBatch.objects.create(
            model=self.product_model,
            batch_number=202507001,
        )
        self.screen_model = ProductModel.objects.create(
            name="Screen model W",
            unit="pcs",
            taric_code="012345678902",
        )
        self.screen_batch = ProductBatch.objects.create(
            model=self.screen_model,
            batch_number=202507002,
        )
        self.component = Component.objects.create(
            product=self.product_model,
            component=self.screen_model,
            amount=1,
        )
        self.glass = Material.objects.create(
            name="Glass",
            density=3,
        )
        self.concentration = Concentration.objects.create(
            product=self.screen_model,
            material=self.glass,
            fraction=1,
        )
        self.company = Company.objects.create(
            name="Example Manufacturer GmbH",
            website="www.example.com",
            country="DE",
            vat_number="DE812345678",
        )
        self.issuer = Institution.objects.create(
            name="Test Certifier AG",
            type="ngo",
            address="Street Name 7",
            country="CH",
        )
        self.phone = ProductItem.objects.create(
            product_batch=self.batch,
            serial_number="PTT-20250715-0043",
        )
        self.screen = ProductItem.objects.create(
            product_batch=self.screen_batch,
            serial_number="PTT-20250715-0041",
        )
        self.metadata1 = Metadata.objects.create(
            product_item=self.phone,
            issuer=self.issuer,
            reo=self.company,
            version="1.0",
        )
        self.metadata2 = Metadata.objects.create(
            product_item=self.screen,
            issuer=self.issuer,
            reo=self.company,
            version="1.0",
        )
        self.operator = ServiceOperator.objects.create(
            name="Repair Shop BV",
            website="www.example.nl",
            country="NL",
            vat_number="NL012345678",
            service_description="Repair of electronics, except computers."
        )
        self.factory = Facility.objects.create(
            operator=self.operator,
            country='NL',
            address="Industrieweg 1, Utrecht",
        )
        self.service = ProductModel.objects.create(
            name="Repair service",
            unit="pcs",
        )
        self.process = ManufacturingProcess.objects.create(
            name="Maintenance process",
            amount=1,
            facility=self.factory,
            functional_flow=self.service,
        )
        self.energy_use = ProductExchange.objects.create(
            process=self.process,
            product=self.electricity,
            amount=2.4,
            direction='in',
            is_observed=True,
            type='ener',
        )
        self.doc = Document.objects.create(
            file="documents/Maintenance_plan.pdf",
            type="maintenance",
            issuer=self.operator,
            language="EN",
            issue_date=date(2025, 7, 10),
            expiry_date=date(2026, 7, 10),
        )
        self.inspection_event = InspectionEvent.objects.create(
            operator=self.operator,
            product=self.phone,
            type='test',
            activity_data=self.process,
        )
        self.maintenance_event = MaintenanceEvent.objects.create(
            operator=self.operator,
            product=self.phone,
            type='corrective',
            activity_data=self.process,
            maintenance_plan=self.doc,
            description="Replacement of broken screen.",
            software_or_hardware=False,
        )
        self.exchange = ItemExchange.objects.create(
            event=self.maintenance_event,
            item=self.screen,
            amount=1,
        )

        # Inject request into context to make build_absolute_uri work
        self.request = self.api_factory.get("/api/")
        self.serializer_context = {"request": self.request}

    def test_item_serializer_structure_and_basic_fields(self):
        serializer = ProductItemSerializer(
            self.phone, context=self.serializer_context
        )
        data = serializer.data
        print(data) #FIXME: remove

        # Basic fields
        self.assertEqual(data["serial_number"], self.phone.serial_number)

        # Nested service events
        self.assertIn("service_events", data)
        service_data = data["service_events"]
        self.assertEqual(len(service_data), 2)
        self.assertIn("activity_data", service_data[0])
        self.assertEqual(service_data[0]['date'], str(date.today()))
        # self.assertDictEqual(service_data, self.phone.serial_number)
    
    def test_attached_documents_serializer(self):
        serializer = ProductItemSerializer(
            self.phone, context=self.serializer_context
        )
        data = serializer.data



class SustainabilityEvaluationSerializerTests(TestCase):
    """
    Tests for SustainabilityEvaluationSerializer,
    CircularityEvaluationSerializer, and associated classes
    """

    def setUp(self):
        self.factory = APIRequestFactory()

        # Minimal institution (issuer)
        self.issuer = Institution.objects.create()
