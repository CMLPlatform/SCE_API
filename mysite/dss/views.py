import numpy as np
import pandas as pd

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render, reverse
from django.views.generic import DetailView
from rest_framework.views import APIView, View
from rest_framework.response import Response
from rest_framework import status

from .serializers import (
    ExperimentSerializer, ExperimentComparisonSerializer,
    WeldStationSerializer, WeldStationComparisonSerializer,
    McdaRequestSerializer,
)
from .mcda import McdaConfig, WeightConstraints, mcda, ranking_to_pairwise
from .models import McdaSession, DecisionMatrix, Criterion, CritGroup, Results
from .forms import KpiSelectionForm, BaseConfigForm, WeightsThresholdsForm, SamplingConfigForm
from .plot import fig_to_bytes


# -----------------------------------
# Results view construction functions
# -----------------------------------

PLOT_TIMEOUT = 3600  # Cache storage time for figures

# Define display order and labels
RESULT_NAMES = {
    "decision_matrix":     "Performance matrix",
    "pairwise_prefs":      "Pairwise preference matrix",
    "net_flow_scores":     "PROMETHEE flows & Net flow scores (NFS)",
    "outrank_probability": "Pairwise outranking probabilities (based on NFS)",
    "sampler_stats":       "Sampling diagnostics",
    "win_probability":     "Winning probabilities",
    "expected_rank":       "Expected rank (lower is better)",
    "rank_acceptability":  "Rank acceptability indices",
    "mean_net_flows":      "Mean net flow scores",
    "mean_weights":        "Mean sampled weights",
    "samples_used":        "Rejection sampling diagnostics",
}

def _format(value) -> str:
    """Normalise numpy scalars and round floats to 4 digits for display."""
    if isinstance(value, (np.floating, float)):
        return f"{float(value):.4f}"
    elif isinstance(value, (np.integer, int)):
        return str(int(value))
    return str(value)

def _df_to_ctx(df: pd.DataFrame) -> dict:
    return {
        "index_name": df.index.name or "",
        "headers": list(df.columns),
        "rows": [
            (str(idx), [_format(v) for v in row])
            for idx, row in zip(df.index, df.values)
        ],
    }

def _series_to_ctx(series: pd.Series) -> dict:
    return {
        "index_name": series.index.name or "",
        "value_name": series.name or "Value",
        "rows": [(str(idx), _format(v)) for idx, v in series.items()],
    }

def _build_sections(result: dict) -> list[dict]:
    """Convert the data in results to a list of sections"""
    sections = []
    for key, label in RESULT_NAMES.items():
        if key not in result:
            continue
        value = result[key]

        if isinstance(value, pd.DataFrame):
            sections.append({
                "label": label, "type": "dataframe", "data": _df_to_ctx(value)
            })
        elif isinstance(value, pd.Series):
            sections.append({
                "label": label, "type": "series", "data": _series_to_ctx(value)
            })
        else:
            sections.append({
                "label": label, "type": "scalar", "data": _format(value)
            })

    return sections

# -----------------------------------
# KPI calculation helper functions
# -----------------------------------

# wages, electricity carbon intensity, electricity price
country_data = pd.read_csv(settings.DATA_DIR / "country_data.csv", index_col="country")
# price, carbon footprint of consumables
material_data = pd.read_csv(settings.DATA_DIR / "material_data.csv", index_col="material")
MULTIPLIERS = {"h": 1/3600, "min": 1/60, "s": 1, "kg": 1, "g": 1/1000, "mg": 10**-6, "m3": 1, "L": 1/1000}

def lookup(info: str, country: str):
    """Find the info for country in country_data
    """
    if country in country_data.index:
        value = country_data.loc[country, info]
        if value:
            return value
    return country_data.loc["?", info]

def create_criteria(session: McdaSession, user_type: str="pd"):
    """Create default groups and criteria"""
    cost = CritGroup.objects.create(session=session, name="Economic")
    sust = CritGroup.objects.create(session=session, name="Sustainability")
    qual = CritGroup.objects.create(session=session, name="Technical quality")
    Criterion.objects.create(session=session, name="Operating costs", group=cost, direction="min")
    Criterion.objects.create(session=session, name="Process energy use", group=sust, direction="min")
    Criterion.objects.create(session=session, name="Process carbon footprint", group=sust, direction="min")
    if user_type == "kam":
        circ = CritGroup.objects.create(session=session, name="Circularity")
        oper = CritGroup.objects.create(session=session, name="Productivity")
        Criterion.objects.create(session=session, name="Total production costs", group=cost, direction="min")
        Criterion.objects.create(session=session, name="Maintenance costs", group=cost, direction="min")
        Criterion.objects.create(session=session, name="Production cycle time", group=oper, direction="min")
        Criterion.objects.create(session=session, name="Product carbon footprint", group=sust, direction="min")
        Criterion.objects.create(session=session, name="Scrap rate", group=circ, direction="min")
        Criterion.objects.create(session=session, name="Recyclability", group=circ, direction="max")
        return qual, oper
    return qual, None

def calculate_experiment_kpis(exp: dict, user_type: str) -> dict:
    """
    Compute the KPI values for a single experiment or alternative.

    Converts consumable flow rates to absolute usage, then derives cost,
    energy-use, and carbon-footprint KPIs shared by all users. For the
    KAM user, additionally accounts for scrap-adjusted yield, maintenance
    and material costs, amortized CAPEX, and operational-efficiency KPIs.

    Parameters:
        exp: A single experiment's raw data (one entry of `valid_data`),
            containing weld parameters, consumables, quality parameters,
            and for KAM: materials, operational efficiency data.
        user_type: Either "pd" or "kam". Determines the KPI set.

    Returns:
        dict: KPI name -> value, ready to store as a DecisionMatrix row.

    Raises:
        RuntimeError: If a consumable's quantity/time unit or material
            name is not recognised.
    """
    processing_time = exp["weldLength"] * exp["weldSpeed"]  #TODO: check units
    consumables_use = {}
    for cons in exp["consumables"]:
        qnt_unit, time_unit = cons["unit"].split("/")
        if qnt_unit not in MULTIPLIERS:
            raise RuntimeError(f"Cannot process unit '{qnt_unit}'")
        elif time_unit not in MULTIPLIERS:
            raise RuntimeError(f"Cannot process unit '{time_unit}'")
        elif cons["name"] not in material_data.index:
            raise RuntimeError(f"Material '{cons["name"]}' not recognised.")
        amount = MULTIPLIERS[qnt_unit] * cons["flowRate"] * \
                processing_time * MULTIPLIERS[time_unit]
        consumables_use[cons["name"]] = amount

    if user_type == "kam":
        cycle_time = exp["cycleTime"]
        yield_rate = 1 - exp["scrapRate"]
    else:  # Simplifications for the PD user
        cycle_time = processing_time
        yield_rate = 1
    consumables_costs = sum([
        amount * material_data.loc[cons, "price"]
        for cons, amount in consumables_use.items()
    ])
    labour_costs = cycle_time/3600 * lookup("wages", exp["country"]) * 3
    process_energy_use = (
        processing_time * exp["laserPowerkW"]
        + cycle_time * exp["weldingStationPowerkW"]
    ) / 3600 / yield_rate
    operating_costs = consumables_costs + labour_costs + (
        process_energy_use * lookup("electricity_price", exp["country"])
    )
    consumables_footprint = sum([
        amount * material_data.loc[cons, "CO2eq"]
        for cons, amount in consumables_use.items()
    ]) / yield_rate
    proc_carbon_footprint = consumables_footprint + (
        process_energy_use * lookup("electricity_CO2eq", exp["country"])
    )
    if user_type == "kam":
        annual_production = 240 * 16 * 3600 / cycle_time
        operating_costs += exp["maintenanceCosts"] / annual_production
        material_costs = sum([
            mat["weight"] * material_data.loc[mat["name"], "price"]
            for mat in exp["materials"]
        ])
        material_footprint = sum([
            mat["weight"] * material_data.loc[mat["name"], "CO2eq"]
            for mat in exp["materials"]
        ])
        service_life = 15
        CAPEX = 700000
        amortized_capex = CAPEX / (service_life * annual_production)
        total_production_costs = (
            operating_costs + material_costs + amortized_capex
        ) / yield_rate
        prod_carbon_footprint = (
            proc_carbon_footprint + material_footprint / yield_rate
        )

    # Create dict of KPIs
    kpi_dict = {
        "Process energy use": process_energy_use,
        "Operating costs": operating_costs,
        "Process carbon footprint": proc_carbon_footprint,
    }
    for kpi in exp["qualityParameters"]:
        kpi_dict[kpi["name"]] = kpi["value"]
    if user_type == "kam":
        kam_kpis = {
            "Maintenance costs": exp["maintenanceCosts"],
            "Scrap rate": exp["scrapRate"],
            "Recyclability": exp["recyclability"],
            "Production cycle time": cycle_time,
            "Total production costs": total_production_costs,
            "Product carbon footprint": prod_carbon_footprint,
        }
        kpi_dict.update(kam_kpis)
        for kpi in exp["productivity"]:
            kpi_dict[kpi["name"]] = kpi["value"]

    return kpi_dict

def calculate_kpis(valid_data: list, user: str="pd") -> McdaSession:
    """
    Calculate the KPIs (criteria) of interest for user (pd or kam)
    and attach these to a new McdaSession.

    Creates the session's criteria groups (via `create_criteria`),
    registers the dynamic quality parameters 
    and for KAM, operational efficiency criteria. 
    Then convert each experiment in `valid_data` to a DecisionMatrix row.

    Args:
        valid_data: List of validated expemcdariment dicts, as produced by
            the PD or KAM serializer. All entries are assumed to share
            the same set of quality parameters / operational-efficiency
            criteria as `valid_data[0]`.
        user: Either "pd" or "kam". Determines which criteria are
            created and which KPIs are calculated per experiment.

    Returns:
        McdaSession: The newly created session, with criteria, groups,
        and one DecisionMatrix row per experiment attached.
    """
    # Start a session and initiate groups and criteria
    session = McdaSession.objects.create()
    quality_group, oper_group = create_criteria(session, user_type=user)
    for kpi in valid_data[0]["qualityParameters"]:
        Criterion.objects.create(
            session=session, name=kpi["name"],
            group=quality_group, direction=kpi["target"],
        )
    if oper_group:
        for kpi in valid_data[0]["productivity"]:
            Criterion.objects.create(
                session=session, name=kpi["name"],
                group=oper_group, direction=kpi["target"],
            )
    
    # Extract data from all experiments, compute and store KPIs
    for experiment in valid_data:
        kpi_dict = calculate_experiment_kpis(experiment, user)
        name = "Experiment #" + str(experiment["experimentId"])
        DecisionMatrix.objects.create(
            session=session, name=name, values=kpi_dict
        )
    return session

# -----------------------------------
# Context definitions for forms
# -----------------------------------

def step1_context() -> dict:
    """
    Static context for step 1 form.
    Each option dict: {value, label, hint}.
    Hints help users who aren't MCDA experts.
    """
    return {
        "scenario_options": [
            {"value": "deterministic", "label": "Deterministic",
             "hint": "Criteria have a fixed importance (weight)."},
            {"value": "random",  "label": "Random",
            "hint": "Uncertain importance, without bounds or constraints."},
            {"value": "bounded", "label": "Bounded",
            "hint": "The importance of each criterion is within a range."},
            {"value": "ordered", "label": "Ordered",
            "hint": "The criteria can be ordered by level of importance."},
            {"value": "bounded_ordered", "label": "Bounded ordered",
            "hint": "Both lower and upper bounds, and an importance order apply."},
        ],
        "method_options": [
            {"value": "promethee_like", "label": "Simple",
             "hint": "Define the importance of criteria."},
            {"value": "promethee", "label": "Advanced",
             "hint": "Also define indifference and preference thresholds."},
        ],
        "weight_mode_options": [
            {"value": "flat", "label": "Flat",
             "hint": "One weight per criterion."},
            {"value": "group", "label": "Group",
             "hint": "Criteria are grouped; weights are equal within a group."},
            {"value": "hierarchical", "label": "Hierarchical",
             "hint": "Group weights × local criterion weights."},
        ],
        "veto_type_options": [
            {"value": "no",   "label": "None",  "hint": "No veto applied"},
            {"value": "hard", "label": "Hard",  "hint": "Disqualify alternatives"},
            {"value": "soft", "label": "Soft",  "hint": "Penalise alternatives"},
        ],
    }

def step2_context(session) -> dict:
    """
    Dynamic context for step 2 — depends on session choices.
    """
    directions = {crit.name: crit.direction for crit in session.criteria}
    group_names = list(session.groups.values_list("name", flat=True))

    threshold_hint = (
        "PROMETHEE requires an indifference and preference threshold per criterion "
        "(leave empty or enter a range: q, p)."
        if session.method == "promethee"
        else "Enter the threshold value for each criterion. (Optional)"
    )

    return {
        "criteria": directions,
        "groups": group_names,
        "threshold_hint": threshold_hint,
        "weight_range": session.scenario.startswith("bounded"),
    }

def step3_context(session) -> dict:
    """
    Dynamic context for step 3:
    - All active criteria and groups
    - Criteria in each group (dict)
    """
    criteria = session.criteria
    groups   = {crit.group for crit in criteria}

    if session.weight_mode == "hierarchical":
        criteria_by_group = {
            group.name: [c.name for c in group.criteria.filter(used=True)]
            for group in groups
        }
    else:
        criteria_by_group = {}
 
    return {
        "groups":            list(groups),
        "criteria":          list(criteria),
        "criteria_by_group": criteria_by_group,
    }

# -----------------------------------
# The actual views
# -----------------------------------

class ExperimentKpiView(APIView):
    """Receives an experiment, returns a KPI set."""
    def post(self, request):
        serializer = ExperimentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        kpi_dict = calculate_experiment_kpis(serializer.validated_data, "pd")
        return Response(kpi_dict, status=status.HTTP_200_OK)

class WeldStationKpiView(APIView):
    """Receives a weld station, returns a KPI set."""
    def post(self, request):
        serializer = WeldStationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        kpi_dict = calculate_experiment_kpis(serializer.validated_data, "kam")
        return Response(kpi_dict, status=status.HTTP_200_OK)

class ExperimentComparisonInitView(APIView):
    """Receives an experiment list, redirects to MCDA wizard."""
    def post(self, request):
        serializer = ExperimentComparisonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session = calculate_kpis(serializer.validated_data)

        return redirect(
            reverse("wizard", kwargs={"session_id": session.id, "step": 0})
        )
        return Response({"session_id": session.id}, status=status.HTTP_201_CREATED)

class KamComparisonInitView(APIView):
    """Receives a weld station list, returns an MCDA session ID."""
    def post(self, request):
        serializer = WeldStationComparisonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session = calculate_kpis(serializer.validated_data, user="kam")

        return Response({"session_id": session.id}, status=status.HTTP_201_CREATED)
        return redirect(
            reverse("wizard", kwargs={"session_id": session.id, "step": 0})
        )

class McdaWizardView(View):
    """View multiple forms, guiding the user in seting up MCDA configuration"""
    def _next_step(self, current_step: int, session: McdaSession) -> int | None:
        """Decision tree: select the next form"""
        if current_step < 2:  # Form 0 and 1 are always shown
            return current_step + 1
        if current_step == 2:
            if session.scenario != "deterministic":
                return 3
            return None  # deterministic: skip Form 3
        return None  # step 3 is always the last
    
    def get_form(self, step: int, session: McdaSession, data=None):
        """Returns the right form for the current step."""
        if step == 0:
            return KpiSelectionForm(session, data)
        elif step == 1:
            return BaseConfigForm(data)
        elif step == 2:
            return WeightsThresholdsForm(session, data)
        elif step == 3:
            return SamplingConfigForm(session, data)

    def get_context(self, step: int, session: McdaSession, **kwargs):
        if step == 0:
            context = {"groups": kwargs["form"].groups}
        elif step == 1:
            context = step1_context()
        elif step == 2:
            context = step2_context(session)
        elif step == 3:
            context = step3_context(session)
        context.update(kwargs)
        context["session"] = session
        return context

    def get(self, request, session_id: int, step: int):
        session = get_object_or_404(McdaSession, pk=session_id)
        form = self.get_form(step, session)
        context = self.get_context(step, session=session, form=form)
        return render(request, f"dss/step_{step}.html", context)

    def post(self, request, session_id: int, step: int):
        session = get_object_or_404(McdaSession, pk=session_id)
        form = self.get_form(step, session, data=request.POST)

        if not form.is_valid():
            context = self.get_context(step, session, form=form)
            return render(request, f"dss/step_{step}.html", context)

        form.save(session)

        next_step = self._next_step(step, session)
        if next_step:
            return redirect("wizard", session_id=session_id, step=next_step)

        # All steps done. Run the MCDA calculations
        config = session.build_config()
        try:
            results, plots, title = mcda(config)
        except RuntimeError as e:
            return render(request, "dss/error.html", {"error": e})

        # Cache the created figures
        for name, fig in plots.items():
            cache.set(
                f"mcda_plot_{session_id}_{name}",
                fig_to_bytes(fig),
                timeout=PLOT_TIMEOUT,
            )
        # Redirect to the results page with plots
        result, _ = Results.objects.update_or_create(
            session=session,
            defaults={
                'title': title.replace('_', ' ').title().replace("maa", "MAA"),
                'plots': list(plots.keys()),
                'sections': _build_sections(results),
            }
        )
        return redirect('results', pk=result.pk)
        return Response(response_data, status=status.HTTP_200_OK)


class McdaResultsView(DetailView):
    """View figures and tables of MCDA results"""
    model = Results
    template_name = "dss/results.html"
    context_object_name = 'result'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        result = self.object
        context.update({
            "session": result.session,
            "title": result.title + " MCDA results",
            "plot_names": result.plots,
            "sections": result.sections,
        })
        return context


def plot_view(request, session_id: int, plot_name: str) -> HttpResponse:
    """Plots a single figure (embedded in another page)"""
    fig_bytes = cache.get(f"mcda_plot_{session_id}_{plot_name}")
    if fig_bytes is None:
        return HttpResponse(
            "Plot not found or session expired.",
            status=404,
            content_type="text/plain",
        )
    return HttpResponse(fig_bytes, content_type="image/svg+xml")


class McdaCalculationView(APIView):
    """
    Receives: decision matrix & MCDA setttings.
    Returns: ranking and score of alternatives.
    """
    DEFAULT_GROUPS = {
        "Technical quality": {"Porosity", "Tensile strength", "Weld depth"},
        "Economic": {
            "Operating costs",
            "Total production costs",
            "Maintenance costs",
        },
        "Sustainability": {
            "Process energy use",
            "Process carbon footprint",
            "Product carbon footprint",
        },
        "Circularity": {"Scrap rate", "Recyclability"},
        "Productivity": {
            "Production cycle time",
            "Process automation level",
            "Operator specialisation level",
            "Process monitoring",
            "Production lead time",
            "Machine saturation",
        },
    }

    def serialize_results(self, data: dict):
        if "net_flow_scores" in data:
            df = data["net_flow_scores"][["NFS (phi)", "rank"]]
        else:
            df = pd.concat(
                [data["mean_net_flows"], data["expected_rank"]], axis=1
            )

        df.columns = ["score", "rank"]
        return df.to_dict('index')

    def post(self, request):
        request_serializer = McdaRequestSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        data = request_serializer.validated_data

        try:  # Convert decision matrix to a DataFrame
            decision_matrix = pd.DataFrame.from_dict(
                data["decision_matrix"], orient='index'
            )
        except BaseException as e:
            return Response({"Issue with decision matrix": str(e)},
                            status=status.HTTP_400_BAD_REQUEST)

        try:  # Compile a config object, run MCDA
            groups = data.get("groups", self.DEFAULT_GROUPS)
            constraints = WeightConstraints(
                group=data.get("group_weights"),
                local=data.get("local_weights"),
                criterion=data.get("crit_weights"),
                group_order=ranking_to_pairwise(data.get("group_ranks")),
                criterion_order=ranking_to_pairwise(data.get("crit_ranks")),
            )
            if local_ranks := data.get("local_ranks"):
                constraints.local_order = {
                    g: ranking_to_pairwise(local_ranks[g])
                    if g in local_ranks else []
                    for g in groups
                }

            config = McdaConfig(
                df              = decision_matrix,
                directions      = data["directions"],
                scenario        = data["scenario"],
                method          = data["method"],
                weight_mode     = data["weight_mode"],
                groups          = groups,
                thresholds      = data.get("thresholds"),
                # Veto settings
                veto_type       = data.get("veto_type", "no"),
                veto_thresholds = data.get("veto_thresholds"),
                penalty_factor  = data.get("penalty_factor", 0.5),
                # Sampling
                n_samples       = data.get("n_samples", 10000),
                alpha           = data.get("alpha", 1.0),
                alpha_group     = data.get("alpha_group", 1.0),
                alpha_local     = data.get("alpha_local", 1.0),
                # Weights & constraints
                constraints     = constraints,
            )
            result = mcda(config)[0]
        except ValueError as e:
            return Response({"Error": e}, status=status.HTTP_400_BAD_REQUEST)

        return Response(self.serialize_results(result), status=status.HTTP_200_OK)
