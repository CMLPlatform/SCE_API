from django import forms
from django.forms import inlineformset_factory
from .models import McdaSession, GroupOrder, LocalOrder


# ------------------------------------------------------------------
# Custom fields                                                     
# ------------------------------------------------------------------

class WeightField(forms.Field):
    """
    Accepts a single positive float ("0.5") or a range ("0.2, 0.8").
    Returns float | tuple[float, float].
    """
    widget = forms.TextInput(attrs={"placeholder": "e.g. 0.5 or 0.2, 0.8"})

    def to_python(self, value):
        if not value:
            return None
        value = value.strip()

        if "," in value:
            parts = value.split(",")
            if len(parts) != 2:
                raise forms.ValidationError("Range must be exactly two values.")
            try:
                lo, hi = float(parts[0].strip()), float(parts[1].strip())
            except ValueError:
                raise forms.ValidationError("Range values must be numbers.")
            if lo < 0 or hi < 0:
                raise forms.ValidationError("Values must be positive.")
            if lo > hi:
                raise forms.ValidationError("min must be ≤ max.")
            return (lo, hi)

        try:
            v = float(value)
        except ValueError:
            raise forms.ValidationError("Must be a positive number or range 'min, max'.")
        if v < 0:
            raise forms.ValidationError("Value must be positive.")
        return v


class PositiveFloatField(forms.FloatField):
    def validate(self, value):
        super().validate(value)
        if value is not None and value < 0:
            raise forms.ValidationError("Value must be positive.")


class OrderingEntryField(forms.Field):
    """
    Represents a single ordering constraint: "A > B, 0.8"
    Returns tuple[str, str, float].
    Rendered as a set of rows via OrderingWidget (see below).
    """
    def to_python(self, value):
        if not value:
            return None
        try:
            parts = [p.strip() for p in value.split(",")]
            if len(parts) != 3:
                raise ValueError
            a, b, intensity = parts[0], parts[1], float(parts[2])
            if intensity < 0:
                raise forms.ValidationError("Strength must be positive.")
            return (a, b, intensity)
        except ValueError:
            raise forms.ValidationError("Format must be 'A, B, intensity'.")


# ------------------------------------------------------------------
# Form 1: basic settings (always shown)
# ------------------------------------------------------------------

class BaseConfigForm(forms.Form):
    """
    Collects the top-level choices that drive which fields appear in Forms 2 and 3.
    Saved to: session.scenario, .method, .weight_mode, .veto_type
    """
    scenario = forms.ChoiceField(
        choices=McdaSession.Scenario.choices, widget=forms.RadioSelect,
    )
    method = forms.ChoiceField(
        choices=McdaSession.Method.choices, widget=forms.RadioSelect,
    )
    weight_mode = forms.ChoiceField(
        choices=McdaSession.WeightMode.choices, widget=forms.RadioSelect,
    )
    veto_type = forms.ChoiceField(
        choices=McdaSession.VetoType.choices, widget=forms.RadioSelect,
    )

    def save(self, session: McdaSession) -> None:
        data = self.cleaned_data
        session.scenario    = data["scenario"]
        session.method      = data["method"]
        session.weight_mode = data["weight_mode"]
        session.veto_type   = data["veto_type"]
        session.save()


# ------------------------------------------------------------------
# Form 2: conditional fields, dynamically built from session state
# ------------------------------------------------------------------

class WeightsThresholdsForm(forms.Form):
    """
    Fields are added dynamically in __init__ based on Form 1 choices.
    All fields are optional at the Django level; required-ness is
    enforced in clean() based on the session context.

    Saved to: session.group_weights, .local_weights, .thresholds,
              .veto_thresholds, .penalty_factor, .sampling_mode
    """

    def __init__(self, session: McdaSession, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = session
        criteria = list(session.criteria.values_list("name", flat=True))
        self.groups = list(session.groups.values_list("name", flat=True))

        # -- group_weights: weight_mode in {group, hierarchical} -----
        if session.weight_mode in ("group", "hierarchical"):
            for group in self.groups:
                self.fields[f"group_weight_{group}"] = WeightField(
                    label=f"Weight — {group.title()}", required=False
                )

        # -- local_weights: weight_mode == hierarchical ---------------
        if session.weight_mode == "hierarchical":
            for criterion in criteria:
                self.fields[f"local_weight_{criterion}"] = WeightField(
                    label=f"Local weight — {criterion}", required=False,
                )

        # -- thresholds: always, shape depends on method --------------
        for criterion in criteria:
            if session.method == "promethee":
                self.fields[f"threshold_{criterion}"] = WeightField(
                    label=f"Threshold — {criterion} (indifference, preference)",
                    required=False,
                )
            else:
                self.fields[f"threshold_{criterion}"] = PositiveFloatField(
                    label=f"Threshold — {criterion}", required=False
                )

        # -- veto_thresholds: veto_type != "no" -----------------------
        if session.veto_type != "no":
            for criterion in criteria:
                self.fields[f"veto_{criterion}"] = PositiveFloatField(
                    label=f"Veto threshold — {criterion}", required=False
                )

        # -- penalty_factor: veto_type == "soft" ----------------------
        if session.veto_type == "soft":
            self.fields["penalty_factor"] = PositiveFloatField(
                label="Penalty factor", required=False
            )

        # -- sampling_mode: weight_mode == "group" --------------------
        if session.weight_mode == "group":
            self.fields["sampling_mode"] = forms.ChoiceField(
                choices=McdaSession.SamplingMode.choices,
                widget=forms.RadioSelect,
            )

    def clean(self):
        cleaned = super().clean()
        session = self.session

        if session.weight_mode in ("group", "hierarchical"):
            for group in self.groups:
                if not cleaned.get(f"group_weight_{group}"):
                    self.add_error(
                        f"group_weight_{group}",
                        "Required when weight mode is group or hierarchical."
                    )

        if session.weight_mode == "hierarchical":
            for name in session.criteria.values_list("name", flat=True):
                if not cleaned.get(f"local_weight_{name}"):
                    self.add_error(f"local_weight_{name}", "Required for hierarchical weighting.")

        if session.veto_type != "no":
            for name in session.criteria.values_list("name", flat=True):
                if cleaned.get(f"veto_{name}") is None:
                    self.add_error(f"veto_{name}", "Required when veto is active.")

        if session.veto_type == "soft" and cleaned.get("penalty_factor") is None:
            self.add_error("penalty_factor", "Required for soft veto.")

        if session.weight_mode == "group" and not cleaned.get("sampling_mode"):
            self.add_error("sampling_mode", "Required when weight mode is group.")

        return cleaned

    def save(self, session: McdaSession) -> None:
        d = self.cleaned_data
        criteria = list(session.criteria.values_list("name", flat=True))

        if session.weight_mode in ("group", "hierarchical"):
            session.group_weights = {g: d[f"group_weight_{g}"] for g in self.groups}

        if session.weight_mode == "hierarchical":
            session.local_weights = {c: d[f"local_weight_{c}"] for c in criteria}
        elif session.weight_mode == "group":
            session.sampling_mode = d["sampling_mode"]

        session.thresholds = {c: d[f"threshold_{c}"] for c in criteria}

        if session.veto_type != "no":
            session.veto_thresholds = {c: d[f"veto_{c}"] for c in criteria}

        if session.veto_type == "soft":
            session.penalty_factor = d["penalty_factor"]

        session.save()


# ------------------------------------------------------------------
# Form 3: sampling & uncertainty parameters
# ------------------------------------------------------------------

class SamplingConfigForm(forms.Form):
    """
    Only shown when scenario == "uncertain".
    Fields are added dynamically based on scenario, weight_mode, and sampling_mode.

    Saved to: session.n_samples, .alpha, .alpha_group, .alpha_local,
              .group_order, .local_order
    """

    def __init__(self, session: McdaSession, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = session

        # -- n_samples: scenario != deterministic
        self.fields["n_samples"] = forms.IntegerField(
            label="Number of samples", min_value=1, required=False
        )

        self.fields["alpha"] = PositiveFloatField(
            label="Alpha (global confidence level)", required=False
        )
        if session.weight_mode in ("group", "hierarchical"):
            self.fields["alpha_group"] = PositiveFloatField(
                label="Alpha for group level", required=False
            )
        if session.weight_mode == "hierarchical":
            self.fields["alpha_local"] = PositiveFloatField(
                label="Alpha for local level", required=False
            )

    def _parse_order_lines(self, raw: str, valid_names: list[str]) -> list[tuple]:
        """Parses multi-line ordering constraints into list of (a, b, intensity) tuples."""
        result = []
        for i, line in enumerate(raw.strip().splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) != 3:
                raise forms.ValidationError(f"Line {i}: expected 'A, B, intensity'.")
            a, b = parts[0], parts[1]
            for name in (a, b):
                if name not in valid_names:
                    raise forms.ValidationError(
                        f"Line {i}: '{name}' is not a recognised name."
                    )
            try:
                intensity = float(parts[2])
            except ValueError:
                raise forms.ValidationError(f"Line {i}: intensity must be a number.")
            if intensity < 0:
                raise forms.ValidationError(f"Line {i}: intensity must be positive.")
            result.append((a, b, intensity))
        return result

    def clean(self):
        cleaned = super().clean()
        session = self.session

        if not cleaned.get("n_samples"):
            self.add_error("n_samples", "Required for non-deterministic scenarios.")

        if session.scenario == "uncertain":
            if cleaned.get("alpha") is None:
                self.add_error("alpha", "Required for uncertain scenario.")
            if session.weight_mode in ("group", "hierarchical") and cleaned.get("alpha_group") is None:
                self.add_error("alpha_group", "Required for uncertain + group/hierarchical weighting.")
            if session.weight_mode == "hierarchical" and cleaned.get("alpha_local") is None:
                self.add_error("alpha_local", "Required for uncertain + hierarchical weighting.")

        return cleaned

    def save(self, session: McdaSession) -> None:
        data = self.cleaned_data
        session.n_samples   = data.get("n_samples")
        session.alpha       = data.get("alpha")
        session.alpha_group = data.get("alpha_group")
        session.alpha_local = data.get("alpha_local")
        # session.group_order = data.get("group_order")
        # session.local_order = data.get("local_order")
        session.save()


class GroupOrderForm(forms.ModelForm):
    class Meta:
        model  = GroupOrder
        fields = ["group1", "group2", "intensity"]
        widgets = {
            "group1":    forms.Select(),
            "group2":    forms.Select(),
            "intensity": forms.NumberInput(attrs={"min": 0, "step": "0.01"}),
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("group1") == cleaned.get("group2"):
            raise forms.ValidationError("Choose two different groups.")
        return cleaned


class LocalOrderForm(forms.ModelForm):
    class Meta:
        model  = LocalOrder
        fields = ["criterion1", "criterion2", "intensity"]
        widgets = {
            "criterion1": forms.Select(),
            "criterion2": forms.Select(),
            "intensity":  forms.NumberInput(attrs={"min": 0, "step": "0.01"}),
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("criterion1") == cleaned.get("criterion2"):
            raise forms.ValidationError("Choose two different criteria.")
        return cleaned


# Formsets
# extra=1 shows one blank row by default; can_delete=True adds a remove checkbox
GroupOrderFormSet = inlineformset_factory(
    parent_model = McdaSession,
    model        = GroupOrder,
    form         = GroupOrderForm,
    extra        = 1,
    can_delete   = True,
)

LocalOrderFormSet = inlineformset_factory(
    parent_model = McdaSession,
    model        = LocalOrder,
    form         = LocalOrderForm,
    extra        = 1,
    can_delete   = True,
)
