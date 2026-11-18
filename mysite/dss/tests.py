import logging
import pytest
from unittest.mock import patch

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status

from dpp.models import (
    Company,
    Facility,
    Process,
    ProductExchange,
    ProductModel,
    ProductionLine,
    Transport,
)
from .models import CritGroup, DecisionMatrix, Criterion, McdaSession
from .lca import build_supply_chain
from .mcda import (
    McdaConfig,
    WeightConstraints,
    has_uncertain_performances,
    mcda,
    sample_performance_matrix,
    set_fixed_weights,
)
from .serializers import (
    McdaRequestSerializer,
    SupplyChainRequestSerializer,
    WeldStationSerializer,
)
from .views import lookup, calculate_experiment_kpis, calculate_kpis
from mysite.utils import UncertainValue

logger = logging.getLogger(__name__)
logger.setLevel('DEBUG')
logging.getLogger('django.db.backends').setLevel(logging.WARNING)


def uncertain_mapping(values):
    return {
        key: value if isinstance(value, UncertainValue)
        else UncertainValue(*value) if isinstance(value, (tuple, list))
        else UncertainValue(value)
        for key, value in values.items()
    }


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def material_data_df():
    return pd.DataFrame(
        {"price": [10.0, 5.0], "CO2eq": [2.0, 1.0]},
        index=pd.Index(["Argon", "Steel"], name="material"),
    )

@pytest.fixture(autouse=True)
def patched_material_data(material_data_df):
    """Auto-applied so every test sees a controlled material_data table."""
    with patch("dss.views.material_data", material_data_df):
        yield material_data_df

@pytest.fixture
def country_data_df():
    return pd.DataFrame(
        {
            "wages": [30.0, 0.0, 20.0],
            "electricity_price": [0.25, 0.23, 0.15],
            "electricity_CO2eq": [0.4, 0.4, 0.6],
        },
        index=pd.Index(["NL", "DE", "?"], name="country"),
    )

@pytest.fixture(autouse=True)
def patched_country_data(country_data_df):
    """Auto-applied so every test sees a controlled country_data table."""
    with patch("dss.views.country_data", country_data_df):
        yield country_data_df

@pytest.fixture
def pd_experiment():
    return {
        "experimentId": 1,
        "country": "NL",
        "weldLength": 600,
        "weldSpeed": 3.0,
        "laserPowerkW": 5.0,
        "weldingStationPowerkW": 1.0,
        "nOperators": 3,
        "consumables": [
            {"name": "Argon", "unit": "L/min", "flowRate": 10.0},
        ],
        "qualityParameters": [
            {"name": "Tensile strength", "value": 450, "target": "max"},
        ],
    }

@pytest.fixture
def kam_experiment(pd_experiment):
    exp = pd_experiment
    exp.update({
        "cycleTime": 250.0,
        "scrapRate": 0.1,
        "maintenanceCosts": 1000.0,
        "recyclability": 0.8,
        "capex": 1000000,
        "materials": [
            {"name": "Steel", "weight": 4.0},
        ],
        "productivity": [
            {"name": "Machine saturation", "value": 0.7, "target": "max"},
            {"name": "Process automation level", "value": "medium", "target": "max"},
        ],
    })
    return exp


class TestLookup:

    def test_returns_value_for_known_country(self, country_data_df):
        assert lookup("wages", "NL") == 30.0

    def test_falls_back_to_default_for_unknown_country(self, country_data_df):
        assert lookup("wages", "XX") == 20.0

    def test_falls_back_to_default_when_value_is_false(self, country_data_df):
        assert lookup("wages", "DE") == 20.0

# ---------------------------------------------------------------------------
# test serializers
# ---------------------------------------------------------------------------
class TestSerializers(TestCase):

    def test_supply_chain_process_lists(self):
        serializer = SupplyChainRequestSerializer(data={
            "material": "steel",
            "preprocesses": [{"name": "alkaline_degreasing", "time": 12.5}],
            "postprocesses": [{"name": "pickling", "time": 8}],
        })

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(
            serializer.validated_data["preprocesses"],
            [{"name": "alkaline_degreasing", "time": UncertainValue(12.5)}],
        )
        self.assertEqual(
            serializer.validated_data["postprocesses"],
            [{"name": "pickling", "time": UncertainValue(8)}],
        )

    def test_supply_chain_process_fields_are_validated(self):
        for process in ({"name": "unknown_process", "time": 12},
                        {"name": "pickling", "time": [30, 10]},
                        {"name": "pickling", "time": -1}):
            with self.subTest(process=process):
                serializer = SupplyChainRequestSerializer(data={
                    "material": "steel",
                    "preprocesses": [process],
                })
                self.assertFalse(serializer.is_valid())

    def test_supply_chain_process_time_accepts_ranges(self):
        serializer = SupplyChainRequestSerializer(data={
            "material": "steel",
            "preprocesses": [{"name": "pickling", "time": [10, 30]}],
        })

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(
            serializer.validated_data["preprocesses"][0]["time"],
            UncertainValue(10, 30),
        )

    def test_supply_chain_process_lists_default_to_empty(self):
        serializer = SupplyChainRequestSerializer(data={"material": "steel"})

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["preprocesses"], [])
        self.assertEqual(serializer.validated_data["postprocesses"], [])

    def test_decision_matrix_scalars_are_normalized_to_uncertain_values(self):
        serializer = McdaRequestSerializer(data={
            "decision_matrix": {"a": {"criterion": 1}, "b": {"criterion": [2, 4]}},
            "directions": {"criterion": "max"},
            "scenario": "deterministic",
            "method": "promethee_like",
            "weight_mode": "equal",
            "groups": {"group": ["criterion"]},
            "group_weights": {"group": 1},
        })

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(
            serializer.validated_data["decision_matrix"]["a"]["criterion"],
            UncertainValue(1),
        )
        self.assertEqual(
            serializer.validated_data["decision_matrix"]["b"]["criterion"],
            UncertainValue(2, 4),
        )

    def test_promethee_requires_pair_thresholds(self):
        serializer = McdaRequestSerializer(data={
            "decision_matrix": {"a": {"criterion": 1}, "b": {"criterion": 2}},
            "directions": {"criterion": "max"},
            "scenario": "deterministic",
            "method": "promethee",
            "weight_mode": "equal",
            "groups": {"group": ["criterion"]},
            "thresholds": {"criterion": 1},
        })

        self.assertFalse(serializer.is_valid())

    def test_weld_station_serializer(self):
        input = {
            "experimentId": 402,
            "weldLength": 1300,
            "weldSpeed": 100,
            "country": "NL",
            "laserPowerkW": 50,
            "weldingStationPowerkW": 8.5,
            "maintenanceCosts": 26.40,
            "cycleTime": 21,
            "scrapRate": 0.05,
            "recyclability": "high",
            "consumables": [
                {"name": "Steel wire", "flowRate": 5.5, "unit": "g/h", "transport_km": 250},
                {"name": "Argon", "flowRate": 1, "unit": "l/min", "transport_km": 100},
            ],
            "qualityParameters": [
                {"name": "cost", "value": 200, "target": "min"},
                {"name": "depth", "value": 5, "target": 3.9},
            ],
            "materials": [{"name": "Steel sheets", "weight": 3, "transport_km": 200}],
            "productivity": [
                {"name": "expertise", "value": "medium", "target": "max"},
            ],
            "manufacturer": {
                "name": "Example Manufacturer GmbH", "country": "DE",
                "website": "https://www.example.com", "vat_number": "DE812345678",
                "legal_documents": {},
            },
        }
        # Create expected output based on input data
        expected_output = input.copy()
        for i, kpi in enumerate(expected_output["qualityParameters"]):
            expected_output["qualityParameters"][i]["value"] = float(kpi["value"])
        for key in ["consumables", "materials"]:
            for i in range(len(expected_output[key])):
                expected_output[key][i]["transport_mode"] = "NA"
        
        result = WeldStationSerializer(data=input)
        result.is_valid(raise_exception=True)
        for key in expected_output:
            self.assertEqual(expected_output[key], result.validated_data[key], key)


class TestMcdaUncertainValues(TestCase):

    def test_performance_sampling_uses_uncertain_value_bounds(self):
        df = pd.DataFrame(
            {"criterion": [UncertainValue(2), UncertainValue(4, 8)]},
            index=["certain", "uncertain"],
        )

        self.assertTrue(has_uncertain_performances(df))
        sampled = sample_performance_matrix(df, np.random.default_rng(42))
        self.assertEqual(sampled.loc["certain", "criterion"], 2)
        self.assertGreaterEqual(sampled.loc["uncertain", "criterion"], 4)
        self.assertLessEqual(sampled.loc["uncertain", "criterion"], 8)

    def test_fixed_weights_use_uncertain_value_means(self):
        config = McdaConfig(
            df=pd.DataFrame({"first": [1], "second": [2]}),
            directions={"first": "max", "second": "max"},
            scenario="deterministic",
            method="simple",
            weight_mode="flat",
            criteria=["first", "second"],
            constraints=WeightConstraints(
                criterion={
                    "first": UncertainValue(1, 3),
                    "second": UncertainValue(1),
                }
            ),
        )

        set_fixed_weights(config)

        self.assertAlmostEqual(config._weights["first"], 2 / 3)
        self.assertAlmostEqual(config._weights["second"], 1 / 3)

    def test_certain_performances_do_not_activate_uncertainty(self):
        df = pd.DataFrame(
            {"criterion": [UncertainValue(4), UncertainValue(8)]},
            index=["first", "second"],
        )

        self.assertFalse(has_uncertain_performances(df))

    def test_session_config_converts_json_values_to_uncertain_values(self):
        session = McdaSession.objects.create(
            scenario="bounded",
            method="promethee",
            weight_mode="hierarchical",
            veto_type="no",
            group_weights={"group": [0.2, 0.8]},
            local_weights={"group": {"criterion": 1.0}},
            thresholds={"criterion": [0.0, 1.0]},
            n_samples=10,
        )
        group = CritGroup.objects.create(session=session, name="group")
        Criterion.objects.create(
            session=session,
            name="criterion",
            group=group,
            direction="max",
        )
        DecisionMatrix.objects.create(
            session=session,
            name="first",
            values={"criterion": 2.0},
        )
        DecisionMatrix.objects.create(
            session=session,
            name="second",
            values={"criterion": [3.0, 5.0]},
        )

        config = session.build_config()

        self.assertEqual(config.df.loc["first", "criterion"], UncertainValue(2.0))
        self.assertEqual(config.df.loc["second", "criterion"], UncertainValue(3.0, 5.0))
        assert(config.constraints.group["group"] == UncertainValue(0.2, 0.8))
        self.assertEqual(
            config.constraints.local["group"]["criterion"], UncertainValue(1.0)
        )
        self.assertEqual(config.thresholds["criterion"], UncertainValue(0.0, 1.0))


class TestBuildSupplyChain(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username="supply-chain-test")
        self.input = {
            "experimentId": 402,
            "weldLength": 600,
            "weldSpeed": 3,
            "country": "NL",
            "laserPowerkW": 5,
            "weldingStationPowerkW": 1,
            "maintenanceCosts": 100,
            "cycleTime": 250,
            "scrapRate": 0.1,
            "recyclability": "high",
            "consumables": [
                {
                    "name": "Argon",
                    "flowRate": 10,
                    "unit": "L/min",
                    "transport_km": 100,
                },
            ],
            "qualityParameters": [
                {"name": "strength", "value": 10, "target": "max"},
            ],
            "materials": [
                {
                    "name": "Steel sheets",
                    "weight": 4,
                    "transport_km": 200,
                },
            ],
            "productivity": [
                {"name": "efficiency", "value": "high", "target": "max"},
            ],
            "manufacturer": {
                "name": "Example Manufacturer GmbH",
                "country": "DE",
                "address": "Industrieweg 1",
                "website": "https://example.com",
                "vat_number": "DE812345678",
                "legal_documents": {},
            },
        }

    def validated_data(self, **overrides):
        payload = {**self.input, **overrides}
        serializer = WeldStationSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    def test_builds_weld_station_line_and_input_exchanges(self):
        chain_id = build_supply_chain(self.validated_data(), self.user)

        line = ProductionLine.objects.get(pk=chain_id)
        self.assertEqual(line.created_by, self.user)
        self.assertEqual(line.facility.operator.name, "Example Manufacturer GmbH")
        self.assertEqual(line.facility.country, "NL")
        self.assertEqual(line.final_product.model.unit, "pcs")

        process = Process.objects.get(production_line=line)
        self.assertEqual(process.functional_flow, line.final_product)
        self.assertAlmostEqual(process.amount, 0.9)
        exchanges = {
            (exchange.product.model.name, exchange.type): exchange
            for exchange in ProductExchange.objects.filter(process=process)
        }
        self.assertEqual(exchanges[("Steel sheets", "prod")].amount, 4)
        self.assertEqual(exchanges[("Argon", "cons")].product.model.unit, "m3")
        self.assertAlmostEqual(exchanges[("Argon", "cons")].amount, 1 / 30)
        self.assertAlmostEqual(
            exchanges[("Electricity, low voltage, grid mix NL", "ener")].amount,
            (200 * 5 + 250) / 3600,
        )

        transports = {
            transport.product.model.name: transport
            for transport in Transport.objects.filter(production_line=line)
        }
        self.assertEqual(transports["Steel sheets"].distance, 200)
        self.assertEqual(transports["Argon"].distance, 100)

    def test_process_service_exchanges_preserve_time_ranges(self):
        validated = self.validated_data(
            preprocesses=[
                {"name": "alkaline_degreasing", "time": [10, 20]},
            ],
            postprocesses=[
                {"name": "pickling", "time": 5},
            ],
        )

        line_id = build_supply_chain(validated, self.user)
        process = Process.objects.get(production_line_id=line_id)
        exchanges = {
            exchange.product.model.name: exchange
            for exchange in ProductExchange.objects.filter(
                process=process, type="serv"
            )
        }

        ranged = exchanges["alkaline_degreasing service"]
        self.assertEqual(ranged.amount, 15)
        self.assertEqual(ranged.uncertainty_type, "interval")
        self.assertEqual(ranged.minimum, 10)
        self.assertEqual(ranged.maximum, 20)
        certain = exchanges["pickling service"]
        self.assertEqual(certain.amount, 5)
        self.assertEqual(certain.uncertainty_type, "none")
        self.assertIsNone(certain.minimum)
        self.assertIsNone(certain.maximum)

    def test_creation_rolls_back_when_an_exchange_fails(self):
        with patch(
            "dss.lca.ProductExchange.save",
            side_effect=RuntimeError("exchange failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "exchange failed"):
                build_supply_chain(self.validated_data(), self.user)

        self.assertEqual(Company.objects.count(), 0)
        self.assertEqual(Facility.objects.count(), 0)
        self.assertEqual(ProductModel.objects.count(), 0)
        self.assertEqual(ProductionLine.objects.count(), 0)

    def test_supply_chain_requires_an_authenticated_owner(self):
        with self.assertRaises(PermissionDenied):
            build_supply_chain(self.validated_data())

    def test_weld_station_endpoint_rejects_anonymous_requests(self):
        response = APIClient().post(
            "/dss/welding-station/", {}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


# ---------------------------------------------------------------------------
# calculate_experiment_kpis
# ---------------------------------------------------------------------------

class TestCalculateExperimentKpisPd:

    def test_pd_kpi_results(self, pd_experiment):
        result = calculate_experiment_kpis(pd_experiment, "pd")

        assert set(result.keys()) == {
            "Process energy use",
            "Operating costs",
            "Process carbon footprint",
            "Tensile strength",
        }

        assert result["Tensile strength"] == 450
        assert result["Operating costs"] > 0
        assert result["Process energy use"] > 0
        assert result["Process carbon footprint"] > 0

        # PD yield_rate == 1, cycle_time == processing_time, so process energy
        # use should equal (processing_time * (laser + welding station kW)) / 3600.
        processing_time = pd_experiment["weldLength"] / pd_experiment["weldSpeed"]
        expected_energy = (
            pd_experiment["laserPowerkW"] + pd_experiment["weldingStationPowerkW"]
        ) * processing_time / 3600
        assert result["Process energy use"] == pytest.approx(expected_energy)

    def test_unrecognised_consumable_unit_raises(self, pd_experiment):
        pd_experiment["consumables"][0]["unit"] = "bogus/min"

        with pytest.raises(RuntimeError, match="Cannot process unit 'bogus'"):
            calculate_experiment_kpis(pd_experiment, "pd")

    def test_unrecognised_material_raises(self, pd_experiment):
        pd_experiment["consumables"][0]["name"] = "Unobtainium"

        with pytest.raises(RuntimeError, match="Material 'Unobtainium' not recognised"):
            calculate_experiment_kpis(pd_experiment, "pd")


class TestCalculateExperimentKpisKam:

    def test_returns_expected_keys(self, kam_experiment):
        result = calculate_experiment_kpis(kam_experiment, "kam")

        expected = {
            "Process energy use", "Operating costs", "Process carbon footprint",
            "Tensile strength", "Maintenance costs", "Scrap rate",
            "Recyclability", "Production cycle time", "Total production costs",
            "Product carbon footprint", "Machine saturation",
            "Process automation level",
        }
        assert set(result.keys()) == expected

        assert result["Maintenance costs"] == kam_experiment["maintenanceCosts"]
        assert result["Scrap rate"] == kam_experiment["scrapRate"]
        assert result["Recyclability"] == kam_experiment["recyclability"]
        assert result["Production cycle time"] == kam_experiment["cycleTime"]
        assert result["Machine saturation"] == 0.7

    def test_calculation_result(self, pd_experiment, kam_experiment):
        # KAM's process energy use (using cycleTime) should exceed the PD figure
        # computed from the same underlying weld parameters.
        pd_result = calculate_experiment_kpis(pd_experiment, "pd")
        result = calculate_experiment_kpis(kam_experiment, "kam")

        assert result["Process energy use"] > pd_result["Process energy use"]
        assert result["Total production costs"] > result["Operating costs"]

    def test_scrap_rate_of_one_raises_zero_division(self, kam_experiment):
        # yield_rate = 1 - scrapRate; a scrapRate of 1 means yield_rate = 0,
        # which should surface as a ZeroDivisionError rather than silently
        # producing inf/NaN KPIs.
        kam_experiment["scrapRate"] = 1

        with pytest.raises(ZeroDivisionError):
            calculate_experiment_kpis(kam_experiment, "kam")


# ---------------------------------------------------------------------------
# calculate_kpis
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_calculate_kpis_propagates_unrecognised_unit_error(pd_experiment):
    pd_experiment["consumables"][0]["unit"] = "something/min"

    with pytest.raises(RuntimeError, match="Cannot process unit 'something'"):
        calculate_kpis([pd_experiment], user="pd")


@pytest.mark.django_db
class TestCalculateKpis:
    def test_creates_session_and_matrix(self, pd_experiment):
        exp2 = dict(pd_experiment, experimentId=2)
        valid_data = [pd_experiment, exp2]

        session = calculate_kpis(valid_data, user="pd")
        rows = DecisionMatrix.objects.filter(session=session)
        assert rows.count() == 2
        assert {row.name for row in rows} == {"Experiment #1", "Experiment #2"}

    def test_pd_decision_matrix(self, pd_experiment):
        session = calculate_kpis([pd_experiment], user="pd")

        names = set(Criterion.objects.filter(session=session).values_list("name", flat=True))
        assert "Tensile strength" in names

        row = DecisionMatrix.objects.get(session=session, name="Experiment #1")
        nrg = 600/3 * (5+1) / 3600
        expected = {
            'Process energy use': nrg,
            'Operating costs': 600/3/60*10*10/1000 + 600/3/3600*30*3 + nrg*0.25,
            'Process carbon footprint': 0.2,
            'Tensile strength': 450
        }
        assert row.values == expected

    def test_kam_decision_matrix(self, kam_experiment):
        exp2 = dict(kam_experiment, experimentId=2, scrapRate=0.2)
        session = calculate_kpis([kam_experiment, exp2], user="kam")

        names = set(Criterion.objects.filter(session=session).values_list("name", flat=True))
        assert "Machine saturation" in names

        row = DecisionMatrix.objects.get(session=session, name="Welding station #1")
        expected = {
            'Process energy use': 0.3472222222222222,
            'Operating costs': 6.688223379629629,
            'Process carbon footprint': 0.20555555555555555,
            'Tensile strength': 450,
            'Maintenance costs': 1000.0,
            'Scrap rate': 0.1,
            'Recyclability': 0.8,
            'Production cycle time': 250.0,
            'Total production costs': 30.993173439643346,
            'Product carbon footprint': 4.672839506172839,
            'Machine saturation': 0.7,
            'Process automation level': 0.5,
        }
        assert row.values == expected

        matrix = DecisionMatrix.objects.filter(session=session)
        rows = {row.name: row.values for row in matrix}
        assert rows["Welding station #1"]["Scrap rate"] == 0.1
        assert rows["Welding station #2"]["Scrap rate"] == 0.2


class McdaTest(TestCase):
    """
    Class for testing an MCDA request,
    including decision matrix and weighting preferences.
    """
    # ============================================================
    # DECISION MATRIX
    # ============================================================

    def test_mcda(self):
        df = pd.DataFrame(
            data=[
                [9.3, 0.0,   0.0, 0.0, 0.0, 1, 0.551, 0.19108, 4.95, 0.0282, 0.00500, 0.000000439, 26.9, 1.91, 0.298],
                [9.3, 0.0,   0.0, 0.0, 0.0, 2, 0.551, 0.19108, 4.63, 0.0265, 0.00501, 0.000000412, 26.5, 1.94, 0.397],
                [0.0, 0.027, 0.2, 0.3, 3.3, 2, 0.396, 0.01072, 15.0, 0.1160, 0.01020, 0.000001270, 52.7, 3.34, 0.592],
                [0.0, 0.027, 0.2, 0.3, 3.3, 3, 0.396, 0.01072, 8.43, 0.0807, 0.00756, 0.000000774, 17.8, 9.38, 0.297],
            ],
            index=["Steel RoW", "Steel RER", "AlLi RoW", "AlLi Canada"],
            columns=[
                "Ni concentration (%)",
                "Li concentration (%)",
                "Mg concentration (%)",
                "Ti concentration (%)",
                "Cu concentration (%)",
                "Operator",
                "Recycled input (kg/kg)",
                "Waste output (kg/kg)",
                "Climate change (GWP100)",
                "Acidification (AE)",
                "Eutrophication Freshwater (P)",
                "Particulate Matter (human health)",
                "LandUse (soil quality index)",
                "WaterUse (m³ world eq deprived)",
                "Ionising radiation (kBq U-235 eq)",
            ],
        )
        df = df.map(UncertainValue)

        # ============================================================
        # CRITERION ORIENTATION
        # ============================================================

        directions = {
            "Ni concentration (%)": "min",
            "Li concentration (%)": "min",
            "Mg concentration (%)": "min",
            "Ti concentration (%)": "min",
            "Cu concentration (%)": "min",
            "Operator": "max",
            "Recycled input (kg/kg)": "max",
            "Waste output (kg/kg)": "min",
            "Climate change (GWP100)": "min",
            "Acidification (AE)": "min",
            "Eutrophication Freshwater (P)": "min",
            "Particulate Matter (human health)": "min",
            "LandUse (soil quality index)": "min",
            "WaterUse (m³ world eq deprived)": "min",
            "Ionising radiation (kBq U-235 eq)": "min",
        }

        # ============================================================
        # CRITERION GROUPS
        # ============================================================

        groups = {
            "CRM": [
                "Ni concentration (%)",
                "Li concentration (%)",
                "Mg concentration (%)",
                "Ti concentration (%)",
                "Cu concentration (%)",
            ],
            "Circularity": [
                "Recycled input (kg/kg)",
                "Waste output (kg/kg)",
            ],
            "Environmental": [
                "Climate change (GWP100)",
                "Acidification (AE)",
                "Eutrophication Freshwater (P)",
                "Particulate Matter (human health)",
                "LandUse (soil quality index)",
                "WaterUse (m³ world eq deprived)",
                "Ionising radiation (kBq U-235 eq)",
            ],
            "Manufacturer": [
                "Operator",
            ]
        }

        # ============================================================
        # CRITERION WEIGHTS
        # ============================================================

        group_weights = {
            "CRM": 0.25,
            "Circularity": 0.25,
            "Environmental": 0.40,
            "Manufacturer": 0.10
        }

        local_weights = {
            "CRM":{
                "Ni concentration (%)": 0.30,
                "Li concentration (%)": 0.20,
                "Mg concentration (%)": 0.15,
                "Ti concentration (%)": 0.15,
                "Cu concentration (%)": 0.20
            },
            "Circularity":{
                "Recycled input (kg/kg)": 0.70,
                "Waste output (kg/kg)": 0.30
            },
            "Environmental":{
                "Climate change (GWP100)": 0.30,
                "Acidification (AE)": 0.10,
                "Eutrophication Freshwater (P)": 0.10,
                "Particulate Matter (human health)": 0.10,
                "LandUse (soil quality index)": 0.10,
                "WaterUse (m³ world eq deprived)": 0.20,
                "Ionising radiation (kBq U-235 eq)": 0.10
            },
            "Manufacturer":{
                "Operator": 1.0
            }
        }

        # ============================================================
        # PROMETHEE SETTINGS
        # ============================================================

        thresholds = {
            "Ni concentration (%)": (0.0, 2.0),
            "Li concentration (%)": (0.0, 0.01),
            "Mg concentration (%)": (0.0, 0.05),
            "Ti concentration (%)": (0.0, 0.05),
            "Cu concentration (%)": (0.0, 1.0),
            "Operator": (0.0, 1.0),
            "Recycled input (kg/kg)": (0.0, 0.10),
            "Waste output (kg/kg)": (0.0, 0.05),
            "Climate change (GWP100)": (0.0, 5.0),
            "Acidification (AE)": (0.0, 0.05),
            "Eutrophication Freshwater (P)": (0.0, 0.003),
            "Particulate Matter (human health)": (0.0, 0.0000005),
            "LandUse (soil quality index)": (0.0, 20.0),
            "WaterUse (m³ world eq deprived)": (0.0, 3.0),
            "Ionising radiation (kBq U-235 eq)": (0.0, 0.2),
        }

        # Veto thresholds: if alternative a is worse than b by more than v,
        # then S(a,b) is penalized.
        veto_thresholds = {
            "Climate change (GWP100)": 8.0,
            "WaterUse (m³ world eq deprived)": 5.0,
            "Ni concentration (%)": 5.0,
            "Cu concentration (%)": 2.0,
        }

        # ============================================================
        # GROUP-LEVEL WEIGHT UNCERTAINTY
        # ============================================================
        """
        Group-level weights represent the relative importance of the
        main dimensions of the decision problem:
        - CRM
        - Circularity
        - Environmental
        - Manufacturer

        These weights are denoted as:
            W_g
        and must satisfy:
            W_g >= 0
            sum_g W_g = 1

        In the "bounded" sampling mode, lower and upper bounds are
        imposed on each group weight.
        In the "ordered" sampling mode, ordinal constraints are imposed.
        These can also include preference intensities.
        """
        # ============================================================

        group_bounds = {
            "CRM": (0.10,0.40),
            "Circularity": (0.10,0.40),
            "Environmental": (0.20,0.60),
            "Manufacturer": (0.05,0.25),
        }

        group_order_constraints = [
            ("Environmental", "Manufacturer", 1.5),
            ("CRM", "Manufacturer", 1.2),
            ("Circularity", "Manufacturer", 1.0),
        ]

        # ============================================================
        # LOCAL CRITERION-LEVEL WEIGHT UNCERTAINTY
        # ============================================================
        """
        Local weights represent the importance of criteria within
        each group.

        For a criterion j belonging to group g, the local weight is:
            w_{j|g}
        and must satisfy, within each group:
            w_{j|g} >= 0
            sum_{j in G_g} w_{j|g} = 1

        In the hierarchical model, the final global criterion weight is:
            w_j = W_g × w_{j|g}

        where:
            W_g       = sampled group weight
            w_{j|g}   = sampled local weight of criterion j within group g

        In the "bounded" sampling mode, local lower and upper bounds
        are imposed.
        In the "ordered" sampling mode, local ordinal constraints and
        preference intensities are imposed.

        A local ordinal constraint can be specified as:
        ("A", "B")
        meaning:
            w_A >= w_B
        or as:
        ("A", "B", intensity)
        meaning:
            w_A >= intensity × w_B
        """

        local_bounds = {
            "CRM": {
                "Ni concentration (%)": (0.10,0.40),
                "Li concentration (%)": (0.05,0.30),
                "Mg concentration (%)": (0.05,0.25),
                "Ti concentration (%)": (0.05,0.25),
                "Cu concentration (%)": (0.10,0.40),
            },
            "Circularity": {
                "Recycled input (kg/kg)": (0.40,0.80),
                "Waste output (kg/kg)": (0.20,0.60),
            },
            "Environmental": {
                "Climate change (GWP100)": (0.15,0.35),
                "Acidification (AE)": (0.05,0.20),
                "Eutrophication Freshwater (P)": (0.05,0.20),
                "Particulate Matter (human health)": (0.05,0.20),
                "LandUse (soil quality index)": (0.05,0.20),
                "WaterUse (m³ world eq deprived)": (0.10,0.30),
                "Ionising radiation (kBq U-235 eq)": (0.05,0.20),
            },
            "Manufacturer": {
                "Operator": (1.00,1.00),
            }
        }

        local_order_constraints = {
            "CRM": [
                ("Ni concentration (%)", "Li concentration (%)"),
                ("Ni concentration (%)", "Mg concentration (%)"),
                ("Cu concentration (%)", "Mg concentration (%)"),
                ("Cu concentration (%)", "Ti concentration (%)"),
            ],
            "Circularity": [
                ("Recycled input (kg/kg)", "Waste output (kg/kg)"),
            ],
            "Environmental": [
                ("Climate change (GWP100)", "Acidification (AE)"),
                ("Climate change (GWP100)", "Eutrophication Freshwater (P)"),
                ("Climate change (GWP100)", "Particulate Matter (human health)"),
                ("Climate change (GWP100)", "LandUse (soil quality index)"),
                ("Climate change (GWP100)", "Ionising radiation (kBq U-235 eq)"),
                ("WaterUse (m³ world eq deprived)", "Ionising radiation (kBq U-235 eq)"),
            ],
            "Manufacturer": []
        }

        criterion_bounds = {
            "Ni concentration (%)": (0.0,0.20),
            "Li concentration (%)": (0.0,0.15),
            "Mg concentration (%)": (0.0,0.12),
            "Ti concentration (%)": (0.0,0.12),
            "Cu concentration (%)": (0.0,0.20),
            "Recycled input (kg/kg)": (0.1,0.40),
            "Waste output (kg/kg)": (0.0,0.30),
            "Climate change (GWP100)": (0.1,0.25),
            "Acidification (AE)": (0.05,0.20),
            "Eutrophication Freshwater (P)": (0.05,0.20),
            "Particulate Matter (human health)": (0.05,0.20),
            "LandUse (soil quality index)": (0.05,0.20),
            "WaterUse (m³ world eq deprived)": (0.0,0.30),
            "Ionising radiation (kBq U-235 eq)": (0.05,0.20),
            "Operator": (0.05,0.25),
        }

        group_bounds = uncertain_mapping(group_bounds)
        local_bounds = {
            group: uncertain_mapping(bounds)
            for group, bounds in local_bounds.items()
        }
        criterion_bounds = uncertain_mapping(criterion_bounds)
        thresholds = uncertain_mapping(thresholds)

        constraints = WeightConstraints(
            group_bounds, local_bounds, criterion_bounds,
            group_order_constraints, local_order_constraints,
        )

        # ============================================================
        # COMPOSING ALMOST ALL COMBINATIONS OF PARAMETERS
        # ============================================================

        # "scenario", "method", "weight", "veto"
        test_cases = [
            ["deterministic", "promethee", "flat", "no"],
            ["deterministic", "promethee", "flat", "soft"],
            ["deterministic", "promethee", "flat", "hard"],
            ["deterministic", "promethee", "group", "no"],
            ["deterministic", "promethee", "hierarchical", "no"],
            ["random", "promethee", "flat", "no"],
            ["random", "promethee", "group", "no"],
            ["random", "promethee", "hierarchical", "no"],
            ["bounded", "promethee", "group", "no"],
            ["bounded", "promethee", "hierarchical", "no"],
            ["ordered", "promethee", "group", "no"],
            ["ordered", "promethee", "hierarchical", "no"],
            ["deterministic", "promethee_like", "group", "no"],
            ["deterministic", "promethee_like", "hierarchical", "no"],
        ]
        for settings in test_cases:
            logger.debug(f"Testing case: {settings}")
            config = McdaConfig(
                df=df,
                directions=directions,
                scenario=settings[0],
                method=settings[1],
                weight_mode=settings[2],
                groups=groups,
                thresholds=thresholds,
                veto_type=settings[3],
                veto_thresholds=veto_thresholds,
                n_samples=10,
                constraints=constraints,
            )
            results, plots, title = mcda(config)
            plt.close()  # Close plots to clear memory
        assert set(results.keys()) == {"net_flow_scores", "pairwise_prefs", "decision_matrix"}
        assert set(plots.keys()) == {"Net Flow Score", "Pairwise Preference Matrix"}
        assert title == "deterministic"
        return


class McdaCalculationViewTest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse('mcda')  # Access to McdaCalculationView
        self.valid_payload = {
            "decision_matrix": {
                "alt1": {"crit1": 10,     "crit2": 20},
                "alt2": {"crit1": (8, 9), "crit2": 25},
            },
            "directions": {"crit1": "max", "crit2": "min"},
            "scenario": "ordered",
            "method": "promethee",
            "weight_mode": "hierarchical",
            "groups": {"group1": ["crit1", "crit2"]},
            "group_weights": {"group1": 1.0},
            "local_weights": {"group1": {"crit1": 0.4, "crit2": 0.6}},
            "crit_weights": {"crit1": 0.6, "crit2": 0.4},
            "thresholds": {"crit1": (0.5, 5), "crit2": (1, 6)},
            "veto_type": "soft",
            "veto_thresholds": {"crit1": 6, "crit2": 7},
            "penalty_factor": 0.5,
            "n_samples": 100,
            "alpha": 0.5,
            "alpha_group": 1,
            "alpha_local": 1.5,
            "group_ranks": {"group1": 1},
            "local_ranks": {"group1": {"crit1": 2, "crit2": 1}},
            "crit_ranks": {"crit1": 1, "crit2": 2},
        }
        self.invalid_payload = {
            "decision_matrix": {
                "alt1": {"crit1": 10,     "crit2": 20},
                "alt2": {"crit1": (8, 9), "crit3": 25},
            },
            "directions": {"crit1": 12, "crit2": "low"},
            "scenario": "bounded",
            "method": "promethee",
            "weight_mode": "hierarchical",
            "groups": {"group1": ["crit1", "crit2"], "group2": ["crit3"]},
            "group_weights": {"group1": 0.7},
            "local_weights": {"group1": {"crit1": 0.8, "crit2": 0.6}},
            "crit_weights": {"crit1": 0.6, "crit2": 0.4},
            "thresholds": {"crit1": (5, 0.5), "crit2": (1, 6)},
            "veto_type": "true",
            "veto_thresholds": {"crit1": 6, "crit2": 7},
            "group_ranks": {"group1": "1"},
            "local_ranks": {"group1": {"crit1": ["nonsense"]}},
            "crit_ranks": {"crit1": 1, "crit2": 2},
        }
        self.expected_result = {
            'alt1': {'score': 0.6347775757345835, 'rank': 1.0},
            'alt2': {'score': -0.6347775757345835, 'rank': 2.0},
   }

    def test_valid_post_request(self):
        response = self.client.post(
            self.url, data=self.valid_payload, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertListEqual(list(response.data.keys()), ["alt1", "alt2"])
        self.assertDictEqual(response.data, self.expected_result)

    def test_invalid_post_request(self):
        response = self.client.post(
            self.url, data=self.invalid_payload, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertListEqual(
            list(response.data.keys()),
            ["directions", "thresholds", "veto_type", "local_ranks"]
        )
        # print(response.data)

class Explanations():
    # ============================================================
    # ANALYSIS SCENARIO SELECTION
    # ============================================================
    """
    The variable `scenario` controls what weights and constraints are used:
    deterministic:
        Fixed weights
    random:
        No bounds and no ordinal constraints are imposed.
    bounded:
        Lower and upper bounds are imposed, but no ordinal
        constraints are imposed.
    ordered:
        Ordinal constraints and preference intensities are imposed,
        but specific lower/upper bounds are not imposed.
    bounded_ordered:
        Lower/upper bounds and ordinal/intensity constraints are
        imposed simultaneously.

    If `scenario` is not deterministic, uncertain weights are 
    sampled through SMAA during weight sampling.
    ------------------------------------------------------------

    The uncertainty on the performances is not selected manually.
    It is detected automatically by checking whether the decision
    matrix contains interval values, represented as UncertainValue
    instances with lower and upper bounds.

    Therefore, the final analysis type is determined by combining:
    - scenario
    - presence/absence of uncertain performances in df

    This generates four analysis_type cases:
    1. deterministic: Fixed weights + deterministic performance values
    2. performance_uncertainty: Fixed weights + uncertain performance values
    3. smaa_weights: Uncertain weights + deterministic performance values
    4. full_smaa: Uncertain weights + uncertain performance values
    """

    scenario = "bounded"

    # ============================================================
    # DETERMINISTIC WEIGHT MODE
    # ============================================================
    """
    This parameter is used only when the analysis relies on fixed
    criterion weights, namely in:
    - deterministic
    - performance_uncertainty

    Available options:
    "flat": All final criteria receive the same weight.
    "group": Group weights are fixed, and each group weight is distributed
            equally among the criteria belonging to that group.
    "hierarchical": Final criterion weights are obtained as:
                    final weight = group weight × local criterion weight
        This allows criteria within a group to have different relative importance.
    """

    weight_mode = "flat"

    # ============================================================
    # METHOD SELECTION
    # ============================================================
    """
    method = "promethee_like"

    If q = 0: Type I / usual criterion
    If q > 0: Type II / U-shape criterion

    In both cases, preference is binary:
        P(a,b) = 1 if d(a,b) > q
               = 0 otherwise

    method = "promethee"

    If q = 0 and p > 0: Type III / V-shape criterion
    If q > 0 and p > q: Type V / linear preference with indifference area
    """

    method = "promethee_like"

    # ============================================================
    # VETO SETTINGS
    # ============================================================

    use_veto = False

    # Type of veto:
    # "hard" => set S(a,b) to 0
    # "soft" => multiply S(a,b) by a penalty factor
    veto_type = "soft"

    penalty_factor = 0.5


    # ============================================================
    # WEIGHT UNCERTAINTY MODEL
    # ============================================================
    """
    This section defines how criterion weights are generated in
    the SMAA analysis.

    The model supports three alternative weighting structures:

    1) flat
        Final criterion weights are sampled directly.
        No group structure is imposed.
            w = (w_1, ..., w_m)
            sum_j w_j = 1

    2) group
        Only group-level weights are sampled.
        Each sampled group weight is then uniformly distributed
        among the criteria belonging to that group.
            w_j = W_g / |G_g|
    where criterion j belongs to group g.

    3) hierarchical
    Both group-level weights and local within-group weights
    are sampled.
        w_j = W_g × w_{j|g}
    This allows criteria in the same group to have different
    local importance.
    """

    weight_mode = "flat"
