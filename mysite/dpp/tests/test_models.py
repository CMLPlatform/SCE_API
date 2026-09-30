import uuid
from unittest.mock import patch

import pandas as pd

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.test import TestCase
from django.urls import reverse

from ..models import *
from .. import lca


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def grams(qty, unit="g"):
    """Value as produced by Flow.calc_composition (converted to grams)."""
    return qty * CONVERSIONS[unit] * 1000

def make_facility(name="ACME"):
    operator = Company.objects.create(
            name=name,
            website="www.example.com",
            country="DE",
            vat_number="DE812345678",
        )
    return Facility.objects.create(
        operator=operator, country="NL", address="Industrieweg 1"
    )

def make_product(name="Widget", **kwargs):
    return ProductModel.objects.create(name=name, **kwargs)

def make_line(final_product, facility=None, name="Line"):
    user, _ = User.objects.get_or_create(username="testuser", password="notsosecret")
    return ProductionLine.objects.create(
        name=name, final_product=final_product, facility=facility, created_by=user
    )

def make_process(line, output, amount=1, **kwargs):
    return Process.objects.create(
        name=f"make {output.name}", amount=amount,
        production_line=line, functional_flow=output, **kwargs
    )

def add_exchange(process, product, amount, direction="in", type_="prod"):
    return ProductExchange.objects.create(
        process=process, product=product, amount=amount,
        direction=direction, type=type_,
    )

def add_properties(product, weight=1.0, unit="kg", **kwargs):
    return ProductProperties.objects.create(
        product=product, weight=weight, weight_unit=unit,
        volume=1.0, density=1.0, **kwargs
    )

def make_batch(model, number=1, gtin="0000000000001"):
    return ProductBatch.objects.create(batch_number=number, model=model, GTIN=gtin)


class SupplyChainTestCase(TestCase):
    """
    Shared setup of a two-step production line

        raw --(2x)--> [P1] --> part --(3x)--> [P2] --> final
    """
    def setUp(self):
        self.facility = make_facility(name="Example manufacturer")
        self.raw = make_product("Raw")
        self.part = make_product("Part")
        self.final = make_product("Final", unit="bottles", brand="brand name")
        self.line = make_line(self.final, self.facility)
        self.p1 = make_process(self.line, self.part)
        self.p2 = make_process(self.line, self.final)
        add_exchange(self.p1, self.raw, 2)
        add_exchange(self.p2, self.part, 3)


# --------------------------------------------------------------------------
# Document
# --------------------------------------------------------------------------

class DocumentTest(TestCase):
    def setUp(self):
        self.instruction = Instruction.objects.create(label="Assembly")
        self.document = Document.objects.create(type="other", file="documents/test.pdf")
        self.manual = Document.objects.create(type="manual", file="documents/manual.pdf")

    # Test manuals type
    def test_manual_with_instruction_is_valid(self):
        """A manual with at least one instruction should not raise."""
        instruction2 = Instruction.objects.create(label="Maintenance")
        self.manual.instructions.add(instruction2)

    def test_manual_without_instruction_raises(self):
        """A manual must have at least one instruction."""
        self.manual.instructions.add(self.instruction)
        with self.assertRaises(ValidationError):
            self.manual.instructions.remove(self.instruction)

    def test_manual_after_clear_raises(self):
        """Clearing all instructions from a manual should raise."""
        self.manual.instructions.add(self.instruction)
        with self.assertRaises(ValidationError):
            self.manual.instructions.clear()

    # Test non-manual documents
    def test_non_manual_without_instruction_is_valid(self):
        """A non-manual without instructions should not raise."""
        self.document.instructions.count()

    def test_non_manual_with_instruction_raises(self):
        """Adding an instruction to a non-manual should raise."""
        with self.assertRaises(ValidationError):
            self.document.instructions.add(self.instruction)


# --------------------------------------------------------------------------
# Unknown-entity helpers
# --------------------------------------------------------------------------

class UnknownEntityTests(TestCase):
    def test_get_unknown_company_is_equal(self):
        first = get_unknown_company()
        second = get_unknown_company()
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Company.objects.filter(name="Unknown company").count(), 1)

    def test_get_unknown_servicer_sets_description(self):
        servicer = get_unknown_servicer()
        self.assertEqual(servicer.service_description, "Deleted service")
        self.assertEqual(get_unknown_servicer().pk, servicer.pk)

    def test_deleting_importer_reassigns_details_to_unknown_importer(self):
        product = make_product()
        importer = Importer.objects.create(name="Imp", country="NL", EORI_number="X1")
        details = DppDetails.objects.create(product=product, importer=importer)

        importer.delete()

        details.refresh_from_db()
        self.assertEqual(details.importer.name, "Unknown importer")
        self.assertEqual(details.importer.pk, get_unknown_importer().pk)


# --------------------------------------------------------------------------
# Flow
# --------------------------------------------------------------------------

class FlowBasicsTests(SupplyChainTestCase):
    def test_str_and_model_of_product_model(self):
        flow = Flow.objects.get(pk=self.final.pk)
        self.assertEqual(str(flow), "Final")
        self.assertEqual(flow.model, self.final)

    def test_model_of_product_batch_is_its_product_model(self):
        batch = make_batch(self.final)
        flow = Flow.objects.get(pk=batch.pk)
        self.assertEqual(flow.model, self.final)

    def test_plain_flow_str_and_model(self):
        flow = Flow.objects.create()
        self.assertEqual(str(flow), f"Unspecified flow #{flow.pk}")
        self.assertEqual(flow.model, flow)

    def test_manufacturer_is_operator_of_producing_facility(self):
        self.assertEqual(self.final.manufacturer, self.facility.operator)

    def test_manufacturer_is_none_without_producing_process(self):
        self.assertIsNone(self.raw.manufacturer)


class FlowCompositionTests(SupplyChainTestCase):
    def setUp(self):
        super().setUp()
        self.copper = Material.objects.create(name="Copper")
        Composition.objects.create(product=self.raw, material=self.copper, quantity=5, unit="g")

    def test_calc_composition_recurses_through_the_line(self):
        # final = 3 part = 3 * (2 raw) = 6 raw
        result = self.final.calc_composition(self.line)
        self.assertAlmostEqual(result[self.copper], 6 * grams(5))

    def test_calc_composition_of_background_product_uses_its_bom(self):
        result = self.raw.calc_composition(self.line)
        self.assertAlmostEqual(result[self.copper], grams(5))

    def test_calc_composition_subtracts_waste(self):
        scrap = make_product("Scrap")
        Composition.objects.create(product=scrap, material=self.copper, quantity=1, unit="g")
        add_exchange(self.p2, scrap, 1, direction="out", type_="waste")

        result = self.final.calc_composition(self.line)
        self.assertAlmostEqual(result[self.copper], 6 * grams(5) - grams(1))

    def test_get_composition_stores_rows_and_caches_them(self):
        rows = self.final.get_composition()
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(
            Composition.objects.get(product=self.final, material=self.copper).quantity,
            6 * grams(5),
        )
        # Changing the input does not change the cached result...
        Composition.objects.filter(product=self.raw).update(quantity=10)
        self.final.get_composition()
        self.assertAlmostEqual(
            Composition.objects.get(product=self.final).quantity, 6 * grams(5)
        )
        # ...unless a recalculation is requested.
        self.final.get_composition(recalculate=True)
        self.assertAlmostEqual(
            Composition.objects.get(product=self.final).quantity, 6 * grams(10)
        )

    def test_find_missing_bom_returns_components_without_composition(self):
        missing = self.final.find_missing_bom()   # `part` has no composition
        self.assertEqual([ex.product_id for ex in missing], [self.part.pk])
        self.assertEqual(self.part.find_missing_bom(), [])   # part has it
        self.assertEqual(self.raw.find_missing_bom(), [])    # no upstream

    def test_get_hazardous_concentrations_only_includes_hazardous_materials(self):
        lead = HazardousMaterial.objects.create(name="Lead", CAS_number="7439-92-1")
        Composition.objects.create(
            product=self.raw, material=Material.objects.get(pk=lead.pk), quantity=5, unit="g"
        )
        add_properties(self.final, weight=10, unit="kg")

        result = {m.name: v for m, v in self.final.get_hazardous_concentrations().items()}

        expected = 6 * grams(5) * CONVERSIONS["g"] / (10 * CONVERSIONS["kg"])
        self.assertEqual(set(result), {"Lead"})   # Copper is not hazardous
        self.assertAlmostEqual(result["Lead"], expected)

    def test_add_concentrations_creates_hazardous_rows(self):
        lead = HazardousMaterial.objects.create(name="Lead", CAS_number="7439-92-1")
        Composition.objects.create(
            product=self.raw, material=Material.objects.get(pk=lead.pk), quantity=5, unit="g"
        )
        add_properties(self.final, weight=10, unit="kg")

        self.final.add_concentrations()

        conc = Concentration.objects.get(product=self.final, material__name="Lead")
        self.assertAlmostEqual(
            conc.fraction, 6 * grams(5) * CONVERSIONS["g"] / (10 * CONVERSIONS["kg"])
        )

    def test_add_concentrations_adds_packaging_row(self):
        add_properties(self.final, weight=10, unit="kg")
        self.final.add_concentrations()
        conc = Concentration.objects.get(
            product=self.final, material__name="Total packaging material"
        )
        self.assertEqual(conc.fraction, 0)   # no packaging exchanges


class FlowComponentTests(SupplyChainTestCase):
    def test_add_components_uses_only_incoming_components(self):
        self.p2.amount = 1.5
        self.p2.save()
        add_exchange(self.p2, make_product("Glue"), 9, type_="cons")   # not a component

        self.final.add_components()

        self.assertEqual(Component.objects.filter(product=self.final).count(), 1)
        comp = Component.objects.get(product=self.final, component=self.part)
        self.assertEqual(comp.amount, 2)   # 3/1.5

    def test_add_subcomponents_raises_if_component_not_present(self):
        with self.assertRaises(Component.DoesNotExist):
            self.final.add_subcomponents(self.part)

    def test_add_subcomponents_replaces_component_by_its_parts(self):
        Component.objects.create(product=self.final, component=self.part, amount=2)
        Component.objects.create(product=self.part, component=self.raw, amount=3)

        self.final.add_subcomponents(self.part)

        self.assertFalse(Component.objects.filter(product=self.final, component=self.part).exists())
        self.assertEqual(Component.objects.get(product=self.final, component=self.raw).amount, 6)

    def test_add_subcomponents_sums_with_existing_entries(self):
        Component.objects.create(product=self.final, component=self.part, amount=2)
        Component.objects.create(product=self.final, component=self.raw, amount=1)
        Component.objects.create(product=self.part, component=self.raw, amount=3)

        self.final.add_subcomponents(self.part)

        self.assertEqual(Component.objects.get(product=self.final, component=self.raw).amount, 7)


# --------------------------------------------------------------------------
# ProductProperties / ProductItem / Component / Material
# --------------------------------------------------------------------------

class ProductPropertiesTests(SupplyChainTestCase):
    def test_zero_weight_gives_zero_packaging_ratio(self):
        props = add_properties(self.final, weight=0)
        self.assertEqual(props.packaging_ratio, 0)

    def test_net_weight_without_packaging_is_weight(self):
        props = add_properties(self.final, weight=10)
        self.assertEqual(props.net_weight, 10)

    def test_packaging_ratio_excluding_packaging(self):
        box = make_product("Box")
        add_properties(box, weight=1, unit="kg")
        add_exchange(self.p2, box, 1, type_="pack")
        props = add_properties(self.final, weight=10, unit="kg", includes_packaging=False)
        self.assertAlmostEqual(props.packaging_ratio, 0.1)

    def test_packaging_ratio_and_net_weight_including_packaging(self):
        box = make_product("Box")
        add_properties(box, weight=1, unit="kg")
        add_exchange(self.p2, box, 1, type_="pack")
        props = add_properties(self.final, weight=11, unit="kg", includes_packaging=True)
        self.assertAlmostEqual(props.packaging_ratio, 0.1)   # 1 / (11-1)
        self.assertAlmostEqual(props.net_weight, 10)


class ProductItemTests(TestCase):
    def setUp(self):
        self.item = ProductItem.objects.create(
            product_batch=make_batch(make_product()), serial_number="SN-1"
        )

    def test_update_circularity_appends_and_persists(self):
        self.item.update_circularity("R3")
        self.item.update_circularity("R8")
        self.item.refresh_from_db()
        self.assertEqual(self.item.circularity, "new,R3,R8")

    def test_update_circularity_rejects_unknown_code(self):
        with self.assertRaises(AssertionError):
            self.item.update_circularity("R99")
        self.item.refresh_from_db()
        self.assertEqual(self.item.circularity, "new")

    # NOTE: ProductItem.disassemble() is not tested: it uses `self.components`
    # and `GTIN_code`, neither of which exists on the model.


class ComponentTests(TestCase):
    def test_clean_rejects_self_containment(self):
        product = make_product()
        with self.assertRaises(ValidationError):
            Component(product=product, component=product, amount=1).clean()

    def test_clean_accepts_different_products(self):
        Component(product=make_product("A"), component=make_product("B"), amount=1).clean()


class MaterialTests(TestCase):
    def test_critical_material_needs_country(self):
        with self.assertRaises(ValidationError):
            Material.objects.create(name="Cobalt", criticality_level="c")

    def test_country_needs_criticality_level(self):
        with self.assertRaises(ValidationError):
            Material.objects.create(name="Cobalt", origin_country="CD")

    def test_valid_crm_and_str(self):
        mat = Material.objects.create(name="Cobalt", criticality_level="c", origin_country="CD")
        self.assertTrue(mat.is_critical)
        self.assertEqual(str(mat), "Cobalt (CD)")

    def test_plain_material_is_neither_critical_nor_hazardous(self):
        mat = Material.objects.create(name="Steel")
        self.assertFalse(mat.is_critical)
        self.assertFalse(mat.is_hazardous)
        self.assertEqual(str(mat), "Steel")

    def test_is_hazardous_for_hazardous_material(self):
        haz = HazardousMaterial.objects.create(name="Lead", CAS_number="7439-92-1")
        self.assertTrue(Material.objects.get(pk=haz.pk).is_hazardous)


# --------------------------------------------------------------------------
# Activities, exchanges
# --------------------------------------------------------------------------

class ActivityBiosphereTests(TestCase):
    def test_aggregate_biosphere_scales_and_sums_exchanges(self):
        p1 = Activity.objects.create(name="p1")
        p2 = Activity.objects.create(name="p2")
        target = Activity.objects.create(name="aggregated")
        co2 = Emission.objects.create(name="CO2")
        ch4 = Emission.objects.create(name="CH4")

        def env(process, substance, amount, compartment="air"):
            return EnvExchange.objects.create(
                process=process, substance=substance, compartment=compartment,
                direction="out", amount=amount,
            )
        env(p1, co2, 1)
        env(p1, ch4, 4)
        env(p2, co2, 2)
        env(target, ch4, 99, compartment="soil")   # stale, must be removed

        target.aggregate_biosphere(pd.Series({p1.id: 2.0, p2.id: 3.0}))

        result = {
            (e.substance.name, e.compartment): e.amount
            for e in EnvExchange.objects.filter(process=target)
        }
        self.assertEqual(set(result), {("CO2", "air"), ("CH4", "air")})
        self.assertAlmostEqual(result[("CO2", "air")], 2 * 1 + 3 * 2)
        self.assertAlmostEqual(result[("CH4", "air")], 2 * 4)
        # Source exchanges are untouched
        self.assertEqual(EnvExchange.objects.get(process=p1, substance=co2).amount, 1)


class ManufacturingProcessTests(TestCase):
    def test_save_requires_facility(self):
        mp = ManufacturingProcess(name="mp", functional_flow=make_product())
        with self.assertRaises(ValidationError) as cm:
            mp.save()
        self.assertIn("facility", cm.exception.message_dict)

    def test_save_with_facility_succeeds(self):
        mp = ManufacturingProcess(
            name="mp", functional_flow=make_product(), facility=make_facility()
        )
        mp.save()
        self.assertIsNotNone(mp.pk)


class ProcessSaveTests(TestCase):
    def setUp(self):
        self.facility = make_facility()
        self.product = make_product()
        self.line = make_line(self.product, self.facility)

    def test_facility_defaults_to_production_line_facility(self):
        proc = make_process(self.line, self.product)
        self.assertEqual(proc.facility, self.facility)
        self.assertFalse(proc.is_outsourced)

    def test_other_facility_marks_process_as_outsourced(self):
        proc = make_process(self.line, self.product, facility=make_facility("Other"))
        self.assertTrue(proc.is_outsourced)

    def test_functional_flow_is_required(self):
        proc = Process(name="p", production_line=self.line, functional_flow=None)
        with self.assertRaises(ValidationError):
            proc.save()


class ProductExchangeTests(TestCase):
    def setUp(self):
        self.process = Activity.objects.create(name="act")

    def test_type_defaults_from_direction(self):
        ex_in = ProductExchange.objects.create(
            process=self.process, product=make_product("a"), amount=1, direction="in")
        ex_out = ProductExchange.objects.create(
            process=self.process, product=make_product("b"), amount=1, direction="out")
        self.assertEqual(ex_in.type, "prod")
        self.assertEqual(ex_out.type, "waste")

    def test_output_must_be_waste(self):
        with self.assertRaises(ValidationError):
            ProductExchange.objects.create(
                process=self.process, product=make_product(), amount=1,
                direction="out", type="cons")


class EnvExchangeTests(TestCase):
    def setUp(self):
        self.process = Activity.objects.create(name="act")
        self.substance = Emission.objects.create(name="CO2")

    def test_functional_flow_direction_is_rejected(self):
        with self.assertRaises(ValidationError):
            EnvExchange.objects.create(
                process=self.process, substance=self.substance,
                compartment="air", direction="ff", amount=1)

    def test_direction_defaults_to_out(self):
        ex = EnvExchange.objects.create(
            process=self.process, substance=self.substance,
            compartment="air", direction="", amount=1)
        self.assertEqual(ex.direction, "out")


# --------------------------------------------------------------------------
# ProductionLine
# --------------------------------------------------------------------------

class ProductionLineTest(SupplyChainTestCase):
    def test_check_unused_outputs_ok_for_linked_chain(self):
        self.assertEqual(self.line.check_unused_outputs(), "")

    def test_check_unused_outputs_warns_about_dangling_product(self):
        make_process(self.line, make_product("Byproduct"))
        msg = self.line.check_unused_outputs()
        self.assertIn("Byproduct", msg)
        self.assertNotIn("Final", msg)   # the final product is allowed to be unused

    def test_check_missing_origins_warns_about_unproduced_input(self):
        msg = self.line.check_missing_origins()
        self.assertIn("Raw", msg)
        self.assertNotIn("Part", msg)    # produced by P1

    def test_check_missing_origins_accepts_manufacturing_process_as_origin(self):
        ManufacturingProcess.objects.create(
            name="Raw production", facility=self.facility, functional_flow=self.raw)
        self.assertEqual(self.line.check_missing_origins(), "")

    def test_create_transport_only_for_inputs_from_outside_the_line(self):
        self.line.create_transport()
        transports = Transport.objects.filter(production_line=self.line)
        self.assertEqual([t.product_id for t in transports], [self.raw.pk])
        self.assertEqual(transports[0].distance, 150)

    def test_create_transport_is_idempotent_and_keeps_edits(self):
        self.line.create_transport()
        Transport.objects.filter(production_line=self.line).update(distance=400)
        self.line.create_transport()
        transport = Transport.objects.get(production_line=self.line)
        self.assertEqual(transport.distance, 400)

    def test_production_line_list(self):
        response = self.client.get(reverse("dpp:productionline_list"))
        response = self.client.get(
            reverse("dpp:production_line_detail", args=(self.line.id,))
        )

class AggregateProductionTests(SupplyChainTestCase):
    """
    Scaling for 1 unit of `final`:  P2 = 1, P1 = 3 (3 part per final),
    raw supplier = 6 (2 raw per part).
    """
    def setUp(self):
        super().setUp()
        ManufacturingProcess.objects.create(
            name="Raw production", amount=1, facility=self.facility,
            functional_flow=self.raw)
        self.co2 = Emission.objects.create(name="CO2")
        for proc, amount in [(self.p1, 1), (self.p2, 2)]:
            EnvExchange.objects.create(
                process=proc, substance=self.co2, compartment="air",
                direction="out", amount=amount)

    def test_aggregate_production_creates_manufacturing_process(self):
        agg = self.line.aggregate_production()

        self.assertEqual(agg.name, "Final production")
        self.assertEqual(agg.functional_flow_id, self.final.pk)
        self.assertEqual(agg.facility_id, self.facility.pk)
        self.assertAlmostEqual(agg.amount, 1)

    def test_aggregate_production_creates_scaled_product_exchanges(self):
        agg = self.line.aggregate_production()

        ex = ProductExchange.objects.get(process=agg)
        self.assertEqual(ex.product_id, self.raw.pk)
        self.assertEqual(ex.direction, "in")
        self.assertEqual(ex.type, "prod")
        self.assertAlmostEqual(ex.amount, 6)

    def test_aggregate_production_aggregates_biosphere(self):
        agg = self.line.aggregate_production()

        co2 = EnvExchange.objects.get(process=agg, substance=self.co2)
        self.assertAlmostEqual(co2.amount, 3 * 1 + 1 * 2)

    def test_aggregate_production_is_repeatable(self):
        first = self.line.aggregate_production()
        second = self.line.aggregate_production()

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(ProductExchange.objects.filter(process=second).count(), 1)
        self.assertEqual(EnvExchange.objects.filter(process=second).count(), 1)
        self.assertAlmostEqual(
            EnvExchange.objects.get(process=second).amount, 5)


# --------------------------------------------------------------------------
# Publisher
# --------------------------------------------------------------------------

class PublisherTests(SupplyChainTestCase):
    def setUp(self):
        super().setUp()
        self.issuer = Organization.objects.create(name="Issuer", country="NL")
        self.reo = Company.objects.create(name="REO", country="NL")
        self.publisher = Publisher.objects.create(
            production_line=self.line,
            amount=2,
            gtin="11111",
            issuer=self.issuer,
            reo=self.reo,
            credential_format="json_ld",
            access_link_base="https://dpp.example/",
        )

    # -- small helpers ----------------------------------------------------
    def test_show_status(self):
        self.assertEqual(self.publisher.show_status(), "Not started")
        self.publisher.status = 5
        self.assertEqual(self.publisher.show_status(), "Do Life Cycle Assessment")
        self.publisher.status = 42
        self.assertEqual(self.publisher.show_status(), "Unknown")

    def test_can_publish_requires_final_step_and_no_error(self):
        self.assertFalse(self.publisher.can_publish())
        self.publisher.status = 5
        self.assertTrue(self.publisher.can_publish())
        self.publisher.error_message = "boom"
        self.assertFalse(self.publisher.can_publish())

    def test_get_registration_nrs_unpacks_and_strips(self):
        self.publisher.registration_numbers = " a, b ,c"
        self.assertEqual(self.publisher.get_registration_nrs(), ["a", "b", "c"])

    def test_get_registration_nrs_generates_unique_numbers(self):
        numbers = self.publisher.get_registration_nrs()
        self.assertEqual(len(numbers), 2)
        self.assertEqual(len(set(numbers)), 2)

    # -- check_details ------------------------------------------------------
    def test_check_details_reports_missing_details_and_properties(self):
        msg = self.publisher.check_details(self.line.final_product)
        self.assertIn("DPP details missing", msg)
        self.assertIn("Product Properties missing", msg)

    def test_check_details_ok_when_complete(self):
        DppDetails.objects.create(product=self.final)
        add_properties(self.final)
        fresh = Flow.objects.get(pk=self.final.pk)   # avoid cached "missing" relations
        self.assertEqual(self.publisher.check_details(fresh), "")

    def test_check_details_warns_about_too_few_registration_numbers(self):
        DppDetails.objects.create(product=self.final)
        add_properties(self.final)
        fresh = Flow.objects.get(pk=self.final.pk)
        publisher = Publisher(amount=3, registration_numbers="a,b")
        self.assertIn("Insufficient registration numbers", publisher.check_details(fresh))

    # -- run_from_step ------------------------------------------------------
    def patch_pipeline(self):
        """Mock every step of the pipeline; returns {name: mock}."""
        targets = {
            "origins": patch.object(ProductionLine, "check_missing_origins", return_value=""),
            "outputs": patch.object(ProductionLine, "check_unused_outputs", return_value=""),
            "details": patch.object(Publisher, "check_details", return_value=""),
            "aggregate": patch.object(ProductionLine, "aggregate_production"),
            "concentrations": patch.object(ProductModel, "add_concentrations"),
            "components": patch.object(ProductModel, "add_components"),
            "transport": patch.object(ProductionLine, "create_transport"),
            "lca": patch.object(lca, "create_supply_chain_lca"),
        }
        mocks = {}
        for name, patcher in targets.items():
            mocks[name] = patcher.start()
            self.addCleanup(patcher.stop)
        return mocks

    def test_run_from_step_full_run(self):
        mocks = self.patch_pipeline()

        had_error = self.publisher.run_from_step(1)

        self.assertFalse(had_error)
        self.assertEqual(self.publisher.status, 5)
        self.assertEqual(self.publisher.error_message, "")
        self.assertTrue(self.publisher.can_publish())
        for name, mock in mocks.items():
            mock.assert_called_once()

    def test_run_from_step_stops_when_validation_fails(self):
        mocks = self.patch_pipeline()
        mocks["origins"].return_value = "Warning: Production process missing for ['Raw']"

        had_error = self.publisher.run_from_step(1)

        self.assertTrue(had_error)
        self.assertEqual(self.publisher.status, 0)
        self.assertTrue(self.publisher.error_message.startswith("Error at step 1"))
        mocks["aggregate"].assert_not_called()

    def test_run_from_step_records_failure_of_later_step(self):
        mocks = self.patch_pipeline()
        mocks["aggregate"].side_effect = RuntimeError("boom")

        had_error = self.publisher.run_from_step(1)

        self.assertTrue(had_error)
        self.assertEqual(self.publisher.status, 1)
        self.assertEqual(self.publisher.error_message, "Error at step 2: boom")
        mocks["transport"].assert_not_called()
        self.assertFalse(self.publisher.can_publish())

    def test_run_from_step_resumes_after_last_completed_step(self):
        mocks = self.patch_pipeline()
        self.publisher.status = 2
        self.publisher.save()

        self.assertFalse(self.publisher.run_from_step(3))

        mocks["origins"].assert_not_called()
        mocks["aggregate"].assert_not_called()
        mocks["concentrations"].assert_called_once()
        self.assertEqual(self.publisher.status, 5)

    def test_run_from_step_cannot_skip_uncompleted_steps(self):
        mocks = self.patch_pipeline()
        self.publisher.status = 1
        self.publisher.save()

        self.publisher.run_from_step(4)   # is clamped to step 2

        mocks["origins"].assert_not_called()
        mocks["aggregate"].assert_called_once()
        self.assertEqual(self.publisher.status, 5)

    # -- create_dpps --------------------------------------------------------
    def test_create_dpps_creates_item_and_metadata_per_registration_number(self):
        numbers = [str(uuid.uuid4()), str(uuid.uuid4())]
        self.publisher.registration_numbers = ",".join(numbers)
        self.publisher.status = 5

        self.publisher.create_dpps()

        self.assertEqual(ProductItem.objects.count(), 2)
        for nr in numbers:
            md = Metadata.objects.get(registration_number=nr)
            self.assertEqual(md.access_link, "https://dpp.example/" + nr)
            self.assertEqual(md.issuer_id, self.issuer.pk)
            self.assertEqual(md.reo_id, self.reo.pk)

    def test_create_dpps_does_nothing_when_pipeline_incomplete(self):
        self.publisher.registration_numbers = ",".join(str(uuid.uuid4()) for _ in range(2))
        self.publisher.status = 3

        self.publisher.create_dpps()

        self.assertEqual(ProductItem.objects.count(), 0)
        self.assertEqual(Metadata.objects.count(), 0)
