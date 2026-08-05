import pandas as pd

from django.shortcuts import get_object_or_404, redirect, render, reverse
from django.views.generic import DetailView
from rest_framework.views import APIView, View
from rest_framework.response import Response
from rest_framework import status

from .serializers import ExperimentComparisonSerializer, McdaRequestSerializer, McdaResultSerializer
from .mcda import mcda, McdaConfig, WeightConstraints
from .models import McdaSession, DecisionMatrix, Criterion, CritGroup
from .forms import KpiSelectionForm, BaseConfigForm, WeightsThresholdsForm, SamplingConfigForm, GroupOrderFormSet, LocalOrderFormSet

# wages, electricity carbon intensity, electricity price
country_data = pd.read_csv("init_data/country_data.csv", index_col="country")
# price, carbon footprint of consumables
material_data = pd.read_csv("init_data/material_data.csv", index_col="material")

# Helper functions

def lookup(info: str, country: str):
    """Find the info for country in country_data
    """
    if country in country_data.index:
        value = country_data.loc[country, info]
        if value:
            return value
    return country_data.loc["?", info]

def create_default_criteria(session: McdaSession):
    """Create default groups and criteria"""
    cost = CritGroup.objects.create(session=session, name="Economic")
    sust = CritGroup.objects.create(session=session, name="Sustainability")
    circ = CritGroup.objects.create(session=session, name="Circularity", weight=0)
    qual = CritGroup.objects.create(session=session, name="Technical quality")
    Criterion.objects.create(session=session, name="Operating costs", group=cost, direction="min")
    Criterion.objects.create(session=session, name="Process energy use", group=sust, direction="min")
    Criterion.objects.create(session=session, name="Process carbon footprint", group=sust, direction="min")
    return qual

def calculate_kpis(valid_data: list) -> McdaSession:
    # Start a session and initiate groups and criteria
    session = McdaSession.objects.create()
    quality_group = create_default_criteria(session)
    for kpi in valid_data[0]["qualityParameters"]:
        if not Criterion.objects.filter(name=kpi["name"]).exists():
            Criterion.objects.create(
                session=session, name=kpi["name"],
                group=quality_group, direction=kpi["target"],
            )
    
    # Extract data from all experiments
    for exp in valid_data:
        multipliers = {"h": 1/3600, "min": 1/60, "s": 1, "kg": 1, "g": 1/1000, "mg": 10**-6, "m3": 1, "L": 1/1000}
        processing_time = exp["weldLength"] * exp["weldSpeed"]  #TODO: check units
        consumables_use = {}
        for cons in exp["consumables"]:
            qnt_unit, time_unit = cons["unit"].split("/")
            if qnt_unit not in multipliers:
                raise RuntimeError(f"Cannot process unit '{qnt_unit}'")
            elif time_unit not in multipliers:
                raise RuntimeError(f"Cannot process unit '{time_unit}'")
            elif cons["name"] not in material_data.index:
                raise RuntimeError(f"Material '{cons["name"]}' not recognised.")
            amount = multipliers[qnt_unit] * cons["flowRate"] * \
                    processing_time * multipliers[time_unit]
            consumables_use[cons["name"]] = amount
        
        consumables_costs = sum([
            amount * material_data.loc[cons, "price"]
            for cons, amount in consumables_use.items()
        ])
        labour_costs = processing_time/3600 * lookup("wages", exp["country"]) * 3
        process_energy_use = processing_time/3600 * (
            exp["laserPowerkW"] + exp["weldingStationPowerkW"]
        )
        operating_costs = consumables_costs + labour_costs + (
            process_energy_use * lookup("electricity_price", exp["country"])
        )
        consumables_footprint = sum([
            amount * material_data.loc[cons, "CO2eq"]
            for cons, amount in consumables_use.items()
        ])
        carbon_footprint = consumables_footprint + (
            process_energy_use * lookup("electricity_CO2eq", exp["country"])
        )

        # Create decision matrix
        kpi_dict = {
            "Process energy use": process_energy_use,
	        "Operating costs": operating_costs,
            "Process carbon footprint": carbon_footprint,
        }
        for kpi in exp["qualityParameters"]:
            kpi_dict[kpi["name"]] = kpi["value"]
        DecisionMatrix.objects.create(
            session=session, name=exp["experimentId"], values=kpi_dict
        )
    return session


def step1_context() -> dict:
    """
    Static context for step 1 form.
    Each option dict: {value, label, hint}.
    Hints help users who aren't MCDA experts.
    """
    return {
        "scenario_options": [
            {"value": "deterministic", "label": "Deterministic",
             "hint": "Criteria have a fixed importance."},
            {"value": "uncertain", "label": "Uncertain",
             "hint": "Criteria weights are given as ranges."},
            # {"value": "stochastic",  "label": "Stochastic",
            #  "hint": "Weights drawn from distributions."},
        ],
        "method_options": [
            {"value": "promethee", "label": "PROMETHEE",
             "hint": "Define indifference and preference thresholds."},
            {"value": "promethee_like", "label": "PROMETHEE-like",
             "hint": "Define the preference of criteria."},
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
    criteria = session.criteria.all()
    directions = {crit.name: crit.direction for crit in criteria}
    group_names = list(session.groups.values_list("name", flat=True))

    threshold_hint = (
        "PROMETHEE requires an indifference and preference threshold per criterion "
        "(enter as a range: q, p)."
        if session.method == "promethee"
        else "Enter the threshold value for each criterion."
    )

    sampling_mode_options = [
        {"value": "random",  "label": "Random",
         "hint": "No bounds or constraints are imposed."},
        {"value": "bounded", "label": "Bounded",
         "hint": "Lower and upper bounds are imposed."},
        {"value": "ordered", "label": "Ordered",
         "hint": "A preference order of the importance of groups is imposed."},
        {"value": "bounded_ordered", "label": "Bounded ordered",
         "hint": "Both lower and upper bounds, and a preference order imposed."},
    ]

    return {
        "criteria":              directions,
        "groups":                group_names,
        "threshold_hint":        threshold_hint,
        "sampling_mode_options": sampling_mode_options,
    }

class ExperimentComparisonInitView(APIView):
    def post(self, request):
        serializer = ExperimentComparisonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session = calculate_kpis(serializer.validated_data)

        return redirect(
            reverse("wizard", kwargs={"session_id": session.id, "step": 0})
        )
        return Response({"session_id": session.id}, status=status.HTTP_201_CREATED)

class McdaWizardView(View):
    def _next_step(self, current_step: int, session: McdaSession) -> int | None:
        """Decision tree: select the next form"""
        if current_step < 2:  # Form 0 and 1 are always shown
            return current_step + 1
        if current_step == 2:
            if session.scenario != "deterministic":
                return 3
            return None  # deterministic: skip Form 3
        return None  # step 3 is always the last
    
    def _ask_for_orders(self, session: McdaSession) -> bool:
        return (
            session.scenario == "uncertain" and
            session.sampling_mode in ["ordered", "bounded_ordered"]
        )

    def _get_order_formsets(self, session, data=None):
        """Instantiate both formsets with querysets scoped to this session."""
        session_groups    = CritGroup.objects.filter(session=session)
        session_criteria  = Criterion.objects.filter(session=session)

        group_formset = GroupOrderFormSet(data, instance=session, prefix="gfs")
        for form in group_formset.forms:
            form.fields["group1"].queryset = session_groups
            form.fields["group2"].queryset = session_groups

        local_formset = LocalOrderFormSet(data, instance=session, prefix="lfs")
        for form in local_formset.forms:
            form.fields["criterion1"].queryset = session_criteria
            form.fields["criterion2"].queryset = session_criteria

        return group_formset, local_formset
    
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
            if self._ask_for_orders(session):
                context = dict(zip(
                    ["group_order_formset", "local_order_formset"],
                    self._get_order_formsets(session),
                ))
                for formset in  ["group_order_formset", "local_order_formset"]:
                    if formset in kwargs:
                        context[formset] = kwargs[formset]
            else:
                context = {}
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

        if step == 3 and self._ask_for_orders(session):
            group_order, local_order = self._get_order_formsets(
                session, data=request.POST
            )
        else:
            group_order = local_order = None

        formsets_valid = (
            (group_order is None or group_order.is_valid()) and
            (local_order is None or local_order.is_valid())
        )
        if not form.is_valid() or not formsets_valid:
            context = self.get_context(
                step, session, form=form, group_order_formset=group_order, local_order_formset=local_order
            )
            return render(request, f"dss/step_{step}.html", context)

        # Save the form and GroupOrder + LocalOrder formsets to tables
        form.save(session)
        if group_order:
            group_order.save()
        if local_order:
            local_order.save()

        next_step = self._next_step(step, session)
        if next_step:
            return redirect("wizard", session_id=session_id, step=next_step)

        # All steps done. Run the MCDA calculations
        config = session.build_config()
        result = mcda(config)
        response_data = McdaResultSerializer(result).data
        return redirect("results", session_id=session_id)
        return Response(response_data, status=status.HTTP_200_OK)

class ExperimentResultsView(DetailView):
    model = "ExperimentResults"

def parse_request(valid_data: dict) -> McdaSession:
    """
    Converts validated serializer output → ORM models.
    Called once when the initial API request comes in.
    """
    session = McdaSession.objects.create()

    if valid_data["groups"] is not None:
        for criterion_name, direction in valid_data["directions"].items():
            Criterion(session, name=criterion_name, direction=direction).save()
        for group_name, criteria in valid_data["groups"].items():
            group = CritGroup(session, name=group_name)
            group.save()
            Criterion.objects.filter(name__in=criteria).update(group=group)

    quality_grp = create_default_criteria(session)

    for alt_name, values in valid_data["decision_matrix"].items():
        DecisionMatrix(session=session, name=alt_name, values=values).save()

    for criterion_name, direction in valid_data["directions"].items():
        if not Criterion.objects.filter(name=criterion_name).exists():
            Criterion(
                session, name=criterion_name, group=quality_grp, direction=direction
            ).save()

    return session

class McdaInitView(APIView):
    def post(self, request):
        serializer = McdaRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session = parse_request(serializer.validated_data)

        return Response({"session_id": session.id}, status=status.HTTP_201_CREATED)


#TODO: remove this View
class McdaCalculationView(APIView):
    def post(self, request):
        request_serializer = McdaRequestSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        data = request_serializer.validated_data

        # Convert some raw data to read-to-use data types
        try:
            decision_matrix = pd.DataFrame(data["decision_matrix"])
        except BaseException as e:
            return Response({"Issue with decision matrix": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        try:
            constraints = WeightConstraints(
                group=data.get("group_weights"),
                group_order=data.get("group_order_constraints"),
                local=data.get("local_weights"),
                local_order=data.get("local_order_constraints"),
            )
            config = McdaConfig(
                df=decision_matrix,
                directions=data["directions"],
                scenario=data["scenario"],
                method=data["method"],
                weight_mode=data["weight_mode"],
                groups=data.get("groups"),
                thresholds=data.get("thresholds"),

                # Veto settings
                veto_type=data["veto_type"],
                veto_thresholds=data.get("veto_thresholds"),
                penalty_factor=data.get("penalty_factor"),

                # Sampling
                sampling_mode=data.get("sampling_mode"),
                n_samples=data.get("n_samples"),
                alpha=data.get("alpha"),
                alpha_group=data.get("alpha_group"),
                alpha_local=data.get("alpha_local"),

                # Weight structure settings (group-level and local)
                constraints=constraints,
            )
            result = mcda(config)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        results = McdaResultSerializer(result)
        return Response(results.data, status=status.HTTP_200_OK)
