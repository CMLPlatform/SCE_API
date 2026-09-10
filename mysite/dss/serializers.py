from rest_framework import serializers
from .models import Criterion, CritGroup, GroupOrder, LocalOrder
from rest_framework.serializers import ValidationError

# Validation helpers

def _validate_range(v, positive: bool=False) -> float | tuple:
    """
    Positive float or [lo, hi] with 0 ≤ lo ≤ hi.
    Used for measurements, weights, thresholds.
    """
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        result = float(v)
    elif isinstance(v, (list, tuple)) and len(v) == 2:
        result = (float(v[0]), float(v[1]))
    else:
        raise ValueError("Must be a number or a (min, max) pair.")

    if isinstance(result, float):
        if positive and result < 0:
            raise ValueError("Value must be positive.")
    else:
        lo, hi = result
        if positive and lo < 0:
            raise ValueError(f"First value {lo} must be positive.")
        if lo > hi:
            raise ValueError(f"First {lo} must be ≤ second value {hi}.")
    return result

# Serializers for input data (API requests)
#TODO: configure https://github.com/vbabiy/djangorestframework-camel-case

class ConsumableSerializer(serializers.Serializer):
    name = serializers.CharField()
    flowRate = serializers.FloatField()
    unit = serializers.CharField()

class MaterialSerializer(serializers.Serializer):
    name = serializers.CharField()
    weight = serializers.FloatField()

class KpiSerializer(serializers.Serializer):
    name = serializers.CharField()
    value = serializers.FloatField()
    target = serializers.CharField()  # Can be "min", "max", or a float value

    def validate(self, data):
        t = data["target"]
        if t not in ["min", "max"]:
            try:
                float(t.strip())
            except ValueError:
                raise serializers.ValidationError(f"Target not recognized: {t}")
        return data

class ExperimentSerializer(serializers.Serializer):
    experimentId = serializers.IntegerField()
    weldLength = serializers.FloatField()
    weldSpeed = serializers.FloatField()
    country = serializers.CharField()
    laserPowerkW = serializers.FloatField()
    weldingStationPowerkW = serializers.FloatField()
    consumables = ConsumableSerializer(many=True)
    qualityParameters = KpiSerializer(many=True)

class ExperimentComparisonSerializer(serializers.ListSerializer):
    child = ExperimentSerializer()

    def validate(self, data):
        """
        Validate that all experiments in the list have the same set of quality parameter names.
        """
        if not data:
            return data

        # Collect all quality parameter names from the first experiment
        first_experiment = data[0]
        first_kpis = {
            qp['name'] for qp in first_experiment['qualityParameters']
        }

        # Check all other experiments
        for i, experiment in enumerate(data[1:], start=1):
            current_kpis = {
                qp['name'] for qp in experiment['qualityParameters']
            }
            if current_kpis != first_kpis:
                raise serializers.ValidationError(
                    f"Experiment {experiment['experimentId']} has different "
                    "quality parameters than the first experiment. Expected: "
                    f"{first_kpis}, Got: {current_kpis}"
                )

        # Check ID uniqueness
        ids = set([exp["experimentId"] for exp in data])
        if len(ids) != len(data):
            raise serializers.ValidationError("Duplicate experiment IDs found")

        return data

class WeldStationSerializer(ExperimentSerializer):
    maintenanceCosts = serializers.FloatField()
    cycleTime = serializers.FloatField(min_value=0.1)
    scrapRate = serializers.FloatField(min_value=0, max_value=0.99)
    recyclability = serializers.FloatField(min_value=0, max_value=1)
    materials = MaterialSerializer(many=True)
    productivity = KpiSerializer(many=True)

class WeldStationComparisonSerializer(serializers.ListSerializer):
    child = WeldStationSerializer()

class McdaRequestSerializer(serializers.Serializer):
    SCENARIO_CHOICES = ["deterministic", "random", "bounded", "ordered", "bounded_ordered"]
    METHOD_CHOICES = ["promethee", "promethee_like"]
    WEIGHT_CHOICES = ["flat", "group", "hierarchical"]
    VETO_CHOICES = ["no", "soft", "hard"]

    decision_matrix = serializers.DictField()  # {"alternative": {"criterion": value|(min, max)},}
    directions = serializers.DictField()  # {"criterion": "min"|"max"|value}

    scenario = serializers.ChoiceField(choices=SCENARIO_CHOICES)
    method = serializers.ChoiceField(choices=METHOD_CHOICES, default=METHOD_CHOICES[1])
    weight_mode = serializers.ChoiceField(choices=WEIGHT_CHOICES, default=WEIGHT_CHOICES[0])

    groups = serializers.DictField(required=False)  # {"group": ["criterion",]}
    group_weights = serializers.DictField(required=False)  # {"group": weight|(min, max)}
    local_weights = serializers.DictField(required=False)  # {"group": {"criterion": weight|(min, max)}}
    crit_weights = serializers.DictField(required=False)   # {"criterion": weight|(min, max)}

    thresholds = serializers.DictField(required=False)  # Promethee parameters: {"criterion": (q, p)} or {"criterion": q}, where q=indifference, p=preference
    veto_type = serializers.ChoiceField(choices=VETO_CHOICES, default="no")
    veto_thresholds = serializers.DictField(required=False)  # {"criterion": value}
    penalty_factor = serializers.FloatField(min_value=0, default=0.5)  # used if veto_type=="soft"

    n_samples = serializers.IntegerField(min_value=1, required=False)
    alpha = serializers.FloatField(min_value=0, required=False)
    alpha_group = serializers.FloatField(min_value=0, required=False)
    alpha_local = serializers.FloatField(min_value=0, required=False)
    group_ranks = serializers.DictField(required=False)  # {"group": rank}
    local_ranks = serializers.DictField(required=False)  # {"group": {"criterion": rank}}
    crit_ranks  = serializers.DictField(required=False)  # {"criterion": rank}

    # Validators for specific fields

    def validate_decision_matrix(self, value):
        for alt, criteria in value.items():
            if not isinstance(criteria, dict):
                raise ValidationError(
                    f"'{alt}': expected a dict of {{criterion: value}}."
                )
            for crit, v in criteria.items():
                try:
                    value[alt][crit] = _validate_range(v)
                except (ValueError, TypeError) as e:
                    raise ValidationError(f"['{alt}']['{crit}']: {e}")
        return value

    def validate_directions(self, value):
        for crit, v in value.items():
            if v in ("min", "max"):
                continue
            try:
                value[crit] = float(v)
            except (ValueError, TypeError):
                raise ValidationError(
                    f"['{crit}']: must be 'min', 'max', or a numeric target value."
                )
        return value

    def validate_groups(self, value):
        for group, criteria in value.items():
            if not isinstance(criteria, list):
                raise ValidationError(
                    f"['{group}']: expected a list of criterion names."
                )
            for i, c in enumerate(criteria):
                if not isinstance(c, str):
                    raise ValidationError(
                        f"['{group}'][{i}]: criterion name must be a string."
                    )
        return value

    def validate_group_weights(self, value):
        for group, v in value.items():
            try:
                value[group] = _validate_range(v, True)
            except (ValueError, TypeError) as e:
                raise ValidationError(f"['{group}']: {e}")
        return value

    def validate_local_weights(self, value):
        for group, criteria in value.items():
            if not isinstance(criteria, dict):
                raise ValidationError(
                    f"['{group}']: expected a dict of {{criterion: weight}}."
                )
            for crit, v in criteria.items():
                try:
                    value[group][crit] = _validate_range(v, True)
                except (ValueError, TypeError) as e:
                    raise ValidationError(f"['{group}']['{crit}']: {e}")
        return value

    def validate_crit_weights(self, value):
        for crit, v in value.items():
            try:
                value[crit] = _validate_range(v, True)
            except (ValueError, TypeError) as e:
                raise ValidationError(f"['{crit}']: {e}")
        return value

    def validate_thresholds(self, value):
        for crit, v in value.items():
            try:
                value[crit] = _validate_range(v, True)
            except (ValueError, TypeError) as e:
                raise ValidationError(f"['{crit}']: {e}")
        return value

    def validate_veto_thresholds(self, value):
        for crit, v in value.items():
            try:
                fv = float(v)
                if fv <= 0:
                    raise ValueError("Veto threshold must be > 0.")
                value[crit] = fv
            except (ValueError, TypeError) as e:
                raise ValidationError(f"['{crit}']: {e}")
        return value

    def _validate_rank_dict(self, value: dict, field_name: str):
        """Shared logic for rank dicts, containing positive integers."""
        for key, v in value.items():
            try:
                iv = int(v)
                if iv < 1:
                    raise ValueError("Rank must be ≥ 1.")
                value[key] = iv
            except (ValueError, TypeError) as e:
                raise ValidationError(f"{field_name}['{key}']: {e}")
        return value

    def validate_group_ranks(self, value):
        return self._validate_rank_dict(value, "group_ranks")

    def validate_crit_ranks(self, value):
        return self._validate_rank_dict(value, "crit_ranks")

    def validate_local_ranks(self, value):
        for group, criteria in value.items():
            if not isinstance(criteria, dict):
                raise ValidationError(
                    f"local_ranks['{group}']: expected a dict of {{criterion: rank}}."
                )
            value[group] = self._validate_rank_dict(criteria, "local_ranks")
        return value

    def validate(self, data):
        # Check that criteria in decision_matrix are in directions
        matrix_criteria = set(
            criterion
            for values in data["decision_matrix"].values()
            for criterion in values.keys()
        )
        direction_criteria = set(data["directions"].keys())
        missing = matrix_criteria - direction_criteria
        if missing:
            raise serializers.ValidationError(
                "Criteria found in matrix but missing from 'directions':"
                f"{missing}"
            )
        # Check direction values
        for dir in data["directions"].values():
            if not isinstance(dir, (str, int, float)):
                raise serializers.ValidationError(f"Wrong data in directions: {dir}")
            elif isinstance(dir, str) and dir not in ["min", "max"]:
                raise serializers.ValidationError(f"Expected 'min' or 'max', received: {dir}")
        # crit_weights, thresholds, veto_thresholds, crit_ranks: criteria must be known
        for field in ("crit_weights", "thresholds", "veto_thresholds", "crit_ranks"):
            if field in data:
                unknown = set(data[field].keys()) - direction_criteria
                if unknown:
                    raise ValidationError({field: f"Unknown criteria: {unknown}."})

        if data["groups"]:
            # Check that groups are defined consistently
            for field in ["group_weights", "local_weights", "group_ranks", "local_ranks"]:
                if dic := data.get(field):
                    missing = set(data["groups"].keys()) - set(dic.keys())
                    if missing:
                        raise serializers.ValidationError(
                            f"Unrecognized groups in '{field}': {missing}"
                        )
            # All criteria must belong to a group
            grouped_criteria = set()
            for group in data["groups"].values():
                grouped_criteria.update(group)
            missing = matrix_criteria - grouped_criteria
            if missing:
                raise serializers.ValidationError(
                    f"Criteria missing from groups: {missing}"
                )
        # Some weight_modes require group data
        if data["weight_mode"] == "group":
            if not data["groups"]:
                serializers.ValidationError("For grouped weighting, specify 'groups'")
        elif data["weight_mode"] == "hierarchical":
            if (not data["group_weights"]) or (data["groups"]):
                serializers.ValidationError("Hierarchical weighting requires both 'groups' and 'group_weights'")
        # Each group must have a weight; they must sum to 1
        if data["group_weights"]:
            missing = set(data["groups"].keys()) - set(data["group_weights"].keys())
            if missing:
                raise serializers.ValidationError(
                    f"Criteria missing from grouped_weights: {missing}"
                )
            total = sum(data["group_weights"].values())
            if abs(1 - total) > 1e-6:
                raise ValidationError(
                    f"Sum of group weights should be 1, it is {total}"
                )
        # Check that thresholds matches the method
        # promethee => tuples; promethee_like => float
        if data["method"] == self.METHOD_CHOICES[0] and data["thresholds"]:
            for th in data["thresholds"].values():
                if not isinstance(th, (tuple, list)) or len(th) != 2:
                    raise serializers.ValidationError(
                        f"Expected threshold as (q, p), received: {th}"
                    )
        elif data["method"] == self.METHOD_CHOICES[1] and data["thresholds"]:
            for th in data["thresholds"].values():
                if not isinstance(th, (float, int)):
                    raise serializers.ValidationError(
                        f"Expected threshold as number, received: {th}"
                    )
        # When veto is used, veto_thresholds must be specified
        if data["veto_type"] != "no" and not data["veto_thresholds"]:
            raise serializers.ValueError(
                "veto_thresholds must be provided when veto is used."
            )
        
        return data

# Serializers for output data

class GroupOrderSerializer(serializers.ModelSerializer):
    group1_name = serializers.CharField(source='group1.name')
    group2_name = serializers.CharField(source='group2.name')

    class Meta:
        model = GroupOrder
        fields = ['group1_name', 'group2_name', 'intensity']

    def to_representation(self, instance):
        return (instance.group1.name, instance.group2.name, instance.intensity)

class LocalOrderSerializer(serializers.ModelSerializer):
    criterion1_name = serializers.CharField(source='criterion1.name')
    criterion2_name = serializers.CharField(source='criterion2.name')

    class Meta:
        model = GroupOrder
        fields = ['criterion1_name', 'criterion2_name', 'intensity']

    def to_representation(self, instance):
        return (instance.criterion1.name, instance.criterion2.name, instance.intensity)

class IndicatorScoresSerializer(serializers.Serializer):
    indicator = serializers.CharField()
    score = serializers.FloatField()

class ExperimentRankingSerializer(serializers.Serializer):
    experiment_id = serializers.IntegerField()
    rank = serializers.IntegerField()
    score = serializers.IntegerField()
    indicators = IndicatorScoresSerializer

class McdaResultSerializer(serializers.Serializer):
    experiment_ranking = serializers.ListField(child=ExperimentRankingSerializer())
