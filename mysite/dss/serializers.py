from rest_framework import serializers

class McdaRequestSerializer(serializers.Serializer):
    SCENARIO_CHOICES = ["uncertain", "deterministic"]
    METHOD_CHOICES = ["promethee", "promethee_like"]
    WEIGHT_CHOICES = ["flat", "group", "hierarchical"]
    VETO_CHOICES = ["no", "soft", "hard"]
    SAMPLING_CHOICES = ["random", "bounded", "ordered", "bounded_ordered"]

    decision_matrix = serializers.DictField()  # {"alternative": {"criterion": value},}
    directions = serializers.DictField()  # {"criterion": "min"|"max"|value}

    scenario = serializers.ChoiceField(choices=SCENARIO_CHOICES)
    method = serializers.ChoiceField(choices=METHOD_CHOICES, default=METHOD_CHOICES[1])
    weight_mode = serializers.ChoiceField(choices=WEIGHT_CHOICES, default=WEIGHT_CHOICES[0])

    groups = serializers.DictField(required=False)  # {"group": [criteria]}
    group_weights = serializers.DictField(required=False)  # {"group": weight}
    local_weights = serializers.DictField(required=False)  # {"group": {"criterion": weight}}

    thresholds = serializers.DictField(required=False)  # Promethee parameters: {"criterion": (q, p)} or {"criterion": q}, where q=indifference, p=preference
    veto_type = serializers.ChoiceField(choices=VETO_CHOICES, default="no")
    veto_thresholds = serializers.DictField(required=False)  # {"criterion": value}
    penalty_factor = serializers.FloatField(default=0.5)  # used if veto_type=="soft"

    sampling_mode = serializers.ChoiceField(SAMPLING_CHOICES, required=False)  # If weight_mode=="flat", this must be "random"
    n_samples = serializers.IntegerField(required=False)
    alpha = serializers.FloatField(required=False)
    alpha_group = serializers.FloatField(required=False)
    alpha_local = serializers.FloatField(required=False)
    group_lb = serializers.DictField(required=False)  # {"group": lower_bound}
    group_ub = serializers.DictField(required=False)  # {"group": upper_bound}
    group_order_constraints = serializers.ListField(required=False)  # [("group1", "group2", intensity)]
    local_lb = serializers.DictField(required=False)  # {"group": {"criterion": lower_bound}}
    local_ub = serializers.DictField(required=False)  # {"group": {"criterion": lower_bound}}
    local_order_constraints = serializers.DictField(required=False)  # {"group: [("criterion1", "criterion2", intensity)]}

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
                "Criteria found in matrix but missing from directions:"
                f"{missing}"
            )
        # All criteria must belong to a group
        if data["groups"]:
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
            sum = sum(data["group_weights"].values())
            if abs(1 - sum) > 1e-6:
                raise serializers.ValidationError(
                    f"Sum of group weights should be 1, it is {sum}"
                )
        # Check that thresholds matches the method
        # promethee => tuples; promethee_like => float
        if data["method"] == self.METHOD_CHOICES[0] and data["thresholds"]:
            for th in data["thresholds"]:
                if not isinstance(th, (tuple, list)) or len(th) != 2:
                    raise serializers.ValidationError(
                        f"Expected threshold as (q, p), received: {th}"
                    )
        elif data["method"] == self.METHOD_CHOICES[1] and data["thresholds"]:
            for th in data["thresholds"]:
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

class IndicatorScoresSerializer(serializers.Serializer):
    indicator = serializers.CharField()
    score = serializers.FloatField()

class ExperimentRankingSerializer(serializers.Serializer):
    experiment_id = serializers.IntegerField()
    rank = serializers.IntegerField()
    score = serializers.IntegerField()
    indicators = IndicatorScoresSerializer

class McdaResponseSerializer(serializers.Serializer):
    experiment_ranking = serializers.ListField(child=ExperimentRankingSerializer())
