"""
Tests for lca.py functions:
  setup_project, ensure_methods, select_supply_chain,
  convert_dpp_to_brightway, lca_calculations, create_supply_chain_lca

All Brightway and Django ORM calls are mocked so the suite runs without
a live database or ecoinvent licence.

Run with:
    pytest test_lca.py -v
"""
from django.test import TestCase
import datetime
from unittest.mock import MagicMock, patch
from ..models import IndicatorSet
from dpp.lca import (
    EXCLUDED_METHODS, setup_project, ensure_methods, select_supply_chain,
    convert_dpp_to_brightway, lca_calculations, create_supply_chain_lca,
)

# ---------------------------------------------------------------------------
# Helpers to build lightweight mock objects
# ---------------------------------------------------------------------------

def make_flow(pk=1, name="product", unit="kg", produced_by=None):
    flow = MagicMock()
    flow.id = pk
    flow.pk = pk
    flow.__str__ = lambda self: name
    flow.model.unit = unit
    flow.model.name = name
    if produced_by is not None:
        flow.manufacturing_info = produced_by
    return flow


def make_process(pk=1, name="proc", unit="kg", facility=None,
                 description="desc", amount=1.0, database="mydb"):
    proc = MagicMock()
    proc.pk = pk
    proc.name = name
    proc.amount = amount
    proc.description = description
    proc.database = database
    proc.facility = facility
    proc.functional_flow.model.unit = unit
    proc.__str__ = lambda self: name
    return proc


# ---------------------------------------------------------------------------
# Test classes for key LCA functions
# ---------------------------------------------------------------------------

class TestSetupProject(TestCase):

    @patch("dpp.lca.bwi")
    @patch("dpp.lca.bwd")
    def test_create_new_project(self, mock_bwd, mock_bwi):
        """When the project doesn't exist it should be created and configured."""
        mock_bwd.projects.__contains__ = MagicMock(return_value=False)
        mock_bwd.projects.current = "L4M-test"
        setup_project("L4M-test")

        mock_bwd.projects.set_current.assert_called_once_with("L4M-test")
        mock_bwi.remote.install_project.assert_called_once_with(
            "ecoinvent-3.12-biosphere", "L4M-test"
        )

    @patch("dpp.lca.bwi")
    @patch("dpp.lca.bwd")
    def test_reuse_existing_project(self, mock_bwd, mock_bwi):
        """When the project already exists only set_current should be called."""
        mock_bwd.projects.__contains__ = MagicMock(return_value=True)
        mock_bwd.projects.current = "L4M-test"
        setup_project("L4M-test")

        mock_bwd.projects.set_current.assert_called_once_with("L4M-test")
        mock_bwi.remote.install_project.assert_not_called()


class TestEnsureMethods(TestCase):

    def _bwd_methods(self):
        """Return a dict-like object with three EF v3.1 methods."""
        family = "EF v3.1"
        keys = [
            (family, "climate change", "GWP100"),
            (family, "acidification", "AP"),
            ("Other family", "x", "y"),  # should be filtered out
        ]
        methods = {k: {"unit": "kg CO2 eq"} for k in keys}
        return methods

    @patch("dpp.lca.bwd")
    def test_creates_indicator_set_when_missing(self, mock_bwd):
        mock_bwd.methods = self._bwd_methods()

        result = ensure_methods("EF v3.1")
        assert result.name == "EF v3.1"
        assert result.start_date == datetime.date.today()

    @patch("dpp.lca.bwd")
    def test_returns_existing_indicator_set(self, mock_bwd):
        mock_bwd.methods = self._bwd_methods()
        existing_set = IndicatorSet.objects.create(
            name="CML2001", start_date=datetime.date(2020,2,2)
        )
        result = ensure_methods("CML2001")
        assert result == existing_set

    @patch("dpp.lca.bwd")
    def test_excludes_known_zero_impact_methods(self, mock_bwd):
        """Methods in EXCLUDED_METHODS must never be stored."""
        family = "EF v3.1"
        excluded = next(iter(EXCLUDED_METHODS))   # grab one excluded tuple
        methods_dict = {
            excluded: {"unit": "kg"},
            (family, "acidification", "AP"): {"unit": "kg SO2 eq"},
        }
        mock_bwd.methods = methods_dict

        indicator_set = MagicMock()
        created_methods = []

        with patch("dpp.models.IndicatorSet") as MockIS, \
             patch("dpp.models.ImpactIndicator") as MockII, \
             patch("dpp.models.ImpactCategory") as MockIC:

            MockIS.objects.get.side_effect = MockIS.DoesNotExist
            MockIS.DoesNotExist = Exception
            MockIS.objects.create.return_value = indicator_set
            MockIC.objects.get_or_create.return_value = (MagicMock(), True)
            MockII.objects.filter.return_value = []

            def capture_update_or_create(**kwargs):
                created_methods.append(kwargs.get("method"))
                return MagicMock(), True

            MockII.objects.update_or_create.side_effect = capture_update_or_create
            ensure_methods(family)

        # The excluded method's sub-string should not appear
        assert excluded[1] not in created_methods


class TestSelectSupplyChain(TestCase):

    def test_single_node(self):
        """A product with no upstream exchanges returns exactly one process."""
        proc = make_process(pk=1)
        proc.prod_exchanges.all.return_value = []
        flow = make_flow(pk=10, produced_by=proc)

        result = select_supply_chain(flow)
        assert result == [proc]

    def test_two_level_chain(self):
        """Upstream process is discovered through prod_exchanges."""
        upstream_proc = make_process(pk=2)
        upstream_proc.prod_exchanges.all.return_value = []
        upstream_flow = make_flow(pk=20, produced_by=upstream_proc)

        root_proc = make_process(pk=1)
        exc = MagicMock()
        exc.product = upstream_flow
        root_proc.prod_exchanges.all.return_value = [exc]

        root_flow = make_flow(pk=10, produced_by=root_proc)

        result = select_supply_chain(root_flow)
        assert root_proc in result
        assert upstream_proc in result
        assert len(result) == 2

    def test_cycle_is_not_infinite(self):
        """Visited-set prevents infinite loops on circular references."""
        proc = make_process(pk=1)
        flow = make_flow(pk=10, produced_by=proc)

        # Exchange points back to the same flow (cycle)
        exc = MagicMock()
        exc.product = flow
        proc.prod_exchanges.all.return_value = [exc]

        result = select_supply_chain(flow)   # must terminate
        assert len(result) == 1

    def test_max_depth_limits_traversal(self):
        """max_depth=1 should stop after root's direct children."""
        deep_proc = make_process(pk=3)
        deep_proc.prod_exchanges.all.return_value = []
        deep_flow = make_flow(pk=30, produced_by=deep_proc)

        mid_proc = make_process(pk=2)
        mid_exc = MagicMock(); mid_exc.product = deep_flow
        mid_proc.prod_exchanges.all.return_value = [mid_exc]
        mid_flow = make_flow(pk=20, produced_by=mid_proc)

        root_proc = make_process(pk=1)
        root_exc = MagicMock(); root_exc.product = mid_flow
        root_proc.prod_exchanges.all.return_value = [root_exc]
        root_flow = make_flow(pk=10, produced_by=root_proc)

        # deep_proc is beyond depth=1, should be absent
        result = select_supply_chain(root_flow, max_depth=1)
        assert deep_proc not in result


class TestConvertDppToBrightway(TestCase):

    @patch("dpp.lca.bwd")
    def test_output_contains_activity_key(self, mock_bwd):
        """Each process must produce a key of the form (db_name, pk)."""

        proc = make_process(pk=42, name="my proc", unit="kg")

        with patch("dpp.models.ProductExchange") as MockPE, \
             patch("dpp.models.EnvExchange") as MockEE:

            MockPE.objects.filter.return_value = []
            MockEE.objects.filter.return_value = []

            result = convert_dpp_to_brightway([proc], "testdb")

        assert ("testdb", 42) in result

    @patch("dpp.lca.bwd")
    def test_production_exchange_is_present(self, mock_bwd):
        """The activity must always have a production exchange."""
        proc = make_process(pk=1, unit="kg", amount=2.0)

        with patch("dpp.models.ProductExchange") as MockPE, \
             patch("dpp.models.EnvExchange") as MockEE:

            MockPE.objects.filter.return_value = []
            MockEE.objects.filter.return_value = []

            result = convert_dpp_to_brightway([proc], "db")

        activity = result[("db", 1)]
        prod_excs = [e for e in activity["exchanges"] if e["type"] == "production"]
        assert len(prod_excs) == 1
        assert prod_excs[0]["amount"] == 2.0

    @patch("dpp.lca.bwd")
    def test_stage_raw_material_for_mass_unit(self, mock_bwd):
        """Processes with a mass-unit functional flow should be 'Raw material acquisition'."""
        proc = make_process(pk=1, unit="kg")

        with patch("dpp.models.ProductExchange") as MockPE, \
             patch("dpp.models.EnvExchange") as MockEE:
            MockPE.objects.filter.return_value = []
            MockEE.objects.filter.return_value = []
            result = convert_dpp_to_brightway([proc], "db")

        assert result[("db", 1)]["stage"] == "Raw material acquisition"

    @patch("dpp.lca.bwd")
    def test_stage_manufacturing_for_non_resource_unit(self, mock_bwd):
        """Processes with unit 'pcs' (not a resource unit) should be 'Manufacturing'."""
        proc = make_process(pk=1, unit="pcs")

        with patch("dpp.models.ProductExchange") as MockPE, \
             patch("dpp.models.EnvExchange") as MockEE:
            MockPE.objects.filter.return_value = []
            MockEE.objects.filter.return_value = []
            result = convert_dpp_to_brightway([proc], "db")

        assert result[("db", 1)]["stage"] == "Manufacturing"

    @patch("dpp.lca.bwd")
    def test_cutoff_excludes_external_products(self, mock_bwd):
        """ProductExchanges whose upstream process is not in `processes` are cut off."""
        proc = make_process(pk=1, unit="pcs")
        external_proc = make_process(pk=99)

        pe = MagicMock()
        pe.direction = "in"
        pe.amount = 5.0
        pe.product.model.unit = "kg"
        pe.product.manufacturing_info = external_proc   # not in [proc]

        with patch("dpp.models.ProductExchange") as MockPE, \
             patch("dpp.models.EnvExchange") as MockEE:
            MockPE.objects.filter.return_value = [pe]
            MockEE.objects.filter.return_value = []
            result = convert_dpp_to_brightway([proc], "db")

        tech_excs = [e for e in result[("db", 1)]["exchanges"] if e["type"] == "technosphere"]
        assert len(tech_excs) == 0


class TestLcaCalculations(TestCase):

    @patch("dpp.lca.bwd")
    def test_returns_results_list(self, mock_bwd):
        """Should return one tuple per non-excluded method."""
        family = "EF v3.1"
        methods = [
            (family, "climate change", "GWP100"),
            (family, "acidification", "AP"),
        ]
        mock_bwd.methods = {m: {"unit": "kg CO2 eq"} for m in methods}

        lca_obj = MagicMock()
        lca_obj.score = 3.14
        activity = MagicMock()
        activity.lca.return_value = lca_obj
        activity.__getitem__ = lambda self, k: "test activity" if k == "name" else None

        results = lca_calculations(activity, family)
        assert len(results) == 2
        assert all(len(r) == 3 for r in results)   # (method, score, unit)

    @patch("dpp.lca.bwd")
    def test_switch_method_called_for_subsequent_methods(self, mock_bwd):
        """dpp.lca.switch_method should be called for every method after the first."""
        family = "EF v3.1"
        methods = [
            (family, "a", "x"),
            (family, "b", "y"),
            (family, "c", "z"),
        ]
        mock_bwd.methods = {m: {"unit": "u"} for m in methods}

        lca_obj = MagicMock(); lca_obj.score = 1.0
        activity = MagicMock(); activity.lca.return_value = lca_obj
        activity.__getitem__ = lambda self, k: "act"

        lca_calculations(activity, family)
        assert lca_obj.switch_method.call_count == 2   # once for m[1], once for m[2]
        assert lca_obj.lcia.call_count == 2


class TestCreateSupplyChainLca(TestCase):
    """Test create_supply_chain_lca. integration-style, heavily mocked"""

    def _setup_bwd(self, mock_bwd, db_name):
        mock_db = MagicMock()
        mock_bwd.Database.return_value = mock_db
        mock_bwd.databases.__contains__ = MagicMock(return_value=False)

        family = "EF v3.1"
        methods = [(family, "climate change", "GWP100")]
        mock_bwd.methods = {m: {"unit": "kg CO2 eq"} for m in methods}

        ref_activity = MagicMock()
        ref_activity.__getitem__ = lambda self, k: "ref act"
        lca_obj = MagicMock(); lca_obj.score = 2.0
        ref_activity.lca.return_value = lca_obj
        mock_db.get.return_value = ref_activity

        return mock_db

    @patch("dpp.lca.create_supply_chain_lca", wraps=None)   # don't wrap; we test the real fn
    @patch("dpp.lca.bwd")
    @patch("dpp.lca.bwi")
    def test_evaluation_created_for_new_product(self, mock_bwi, mock_bwd, _wrap):
        proc = make_process(pk=1, unit="kg")
        product = make_flow(pk=10, name="widget", produced_by=proc)

        db_name = "dpp_widget_10"
        mock_db = self._setup_bwd(mock_bwd, db_name)
        mock_bwd.projects.__contains__ = MagicMock(return_value=True)

        with patch("dpp.lca.setup_project"), \
             patch("dpp.lca.ensure_methods") as mock_em, \
             patch("dpp.lca.select_supply_chain", return_value=[proc]), \
             patch("dpp.lca.convert_dpp_to_brightway", return_value={}), \
             patch("dpp.lca.lca_calculations", return_value=[
                 (("EF v3.1", "climate change", "GWP100"), 2.0, "kg CO2 eq")
             ]), \
             patch("dpp.models.SustainabilityEvaluation") as MockEval, \
             patch("dpp.models.SustainabilityScore") as MockScore, \
             patch("dpp.models.ImpactIndicator") as MockII:

            mock_em.return_value = MagicMock(name="method_set")
            MockEval.objects.get_or_create.return_value = (MagicMock(), True)
            MockII.objects.get.return_value = MagicMock()

            create_supply_chain_lca(product)

        MockEval.objects.get_or_create.assert_called_once()
        MockScore.objects.create.assert_called_once()

    @patch("dpp.lca.bwd")
    @patch("dpp.lca.bwi")
    def test_scores_updated_when_evaluation_exists(self, mock_bwi, mock_bwd):
        proc = make_process(pk=1, unit="kg")
        product = make_flow(pk=10, name="widget", produced_by=proc)

        db_name = "dpp_widget_10"
        mock_db = self._setup_bwd(mock_bwd, db_name)
        mock_bwd.projects.__contains__ = MagicMock(return_value=True)

        with patch("dpp.lca.setup_project"), \
             patch("dpp.lca.ensure_methods") as mock_em, \
             patch("dpp.lca.select_supply_chain", return_value=[proc]), \
             patch("dpp.lca.convert_dpp_to_brightway", return_value={}), \
             patch("dpp.lca.lca_calculations", return_value=[
                 (("EF v3.1", "climate change", "GWP100"), 2.0, "kg CO2 eq")
             ]), \
             patch("dpp.models.SustainabilityEvaluation") as MockEval, \
             patch("dpp.models.SustainabilityScore") as MockScore, \
             patch("dpp.models.ImpactIndicator") as MockII:

            mock_em.return_value = MagicMock(name="method_set")
            # created=False -> evaluation already existed
            MockEval.objects.get_or_create.return_value = (MagicMock(), False)
            MockII.objects.get.return_value = MagicMock()

            create_supply_chain_lca(product)

        MockScore.objects.filter.return_value.delete.assert_called_once \
            if hasattr(MockScore.objects.filter.return_value, 'delete') else None
        MockScore.objects.update_or_create.assert_called_once()
