from django.db import models
from .mcda import McdaConfig, WeightConstraints
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
import pandas as pd


def validate_direction(value):
    try:
        float(value)
    except ValueError:
        if value not in ["min", "max"]:
            raise ValidationError("Must be either 'min', 'max' or target value.")

def validate_number_or_range(value):
    """
    Validates that the value is either a single number or a range (min-max).
    Raises ValidationError if the format is invalid.
    """
    if not isinstance(value, str):
        raise ValidationError("Must be a string in the format 'number' or 'min,max'.")
    elif value == "":
        return

    try:  # Check for single number
        float(value)
    except ValueError:
        try:  # Check for range
            min_val, max_val = map(float, value.split(','))
            if min_val > max_val:
                raise ValidationError("'min' cannot be greater than 'max'.")
            return {'min': min_val, 'max': max_val}
        except ValueError:
            raise ValidationError("Invalid value, use 'min,max' or a number.")

class McdaSession(models.Model):
    """Ties the whole flow together. Tracks where the user is in the decision tree."""
    class Status(models.TextChoices):
        PENDING     = "pending"      # request received, forms not started
        IN_PROGRESS = "in_progress"  # user is in the form wizard
        COMPLETE    = "complete"     # mcda() has run

    class Scenario(models.TextChoices):
        DETERMINISTIC   = "deterministic"
        RANDOM          = "random"
        BOUNDED         = "bounded"
        ORDERED         = "ordered"
        BOUNDED_ORDERED = "bounded_ordered"

    class Method(models.TextChoices):
        PROMETHEE_LIKE = "promethee_like"
        PROMETHEE      = "promethee"

    class WeightMode(models.TextChoices):
        FLAT         = "flat"
        GROUP        = "group"
        HIERARCHICAL = "hierarchical"

    class VetoType(models.TextChoices):
        NO   = "no"
        HARD = "hard"
        SOFT = "soft"

    status      = models.CharField(max_length=11, choices=Status, default=Status.PENDING)
    created_at  = models.DateTimeField(auto_now_add=True)
    user_type   = models.CharField(max_length=3, choices={"pd": "Process developer", "kam": "Key account manager"}, null=True)

    # Form 1 - always present
    scenario    = models.CharField(max_length=15, choices=Scenario, null=True)
    method      = models.CharField(max_length=15, choices=Method, null=True)
    weight_mode = models.CharField(max_length=12, choices=WeightMode, null=True)
    veto_type   = models.CharField(max_length=4, choices=VetoType, null=True)

    # Form 2 - conditional; stored as JSON to handle float|tuple values
    group_weights    = models.JSONField(null=True)  # {"group_name": float | [lo, hi]}
    local_weights    = models.JSONField(null=True)  # {"criterion": {"group": float | [lo, hi]}}
    criterion_weights= models.JSONField(null=True)  # {"criterion": float | [lo, hi]}
    thresholds       = models.JSONField(null=True)  # {"criterion": float | [lo, hi]}
    veto_thresholds  = models.JSONField(null=True)  # {"criterion": float}
    penalty_factor   = models.FloatField(default=0.5)

    # Form 3 - conditional
    n_samples   = models.IntegerField(null=True)
    group_ranks = models.JSONField(default=dict)  # {"group_name": int}
    local_ranks = models.JSONField(default=dict)  # {"group_name": {"criterion": int}}
    crit_ranks  = models.JSONField(default=dict)  # {"criterion": int}

    @property
    def criteria(self):
        return self.all_criteria.filter(used=True)

    def init_criteria_n_groups(self):
        """Create all criteria and groups needed for the MCDA.
        Some criteria and all groups are pre-defined.
        """
        cost = CritGroup(session=self, name="Costs")
        sust = CritGroup(session=self, name="Sustainability")
        circ = CritGroup(session=self, name="Circularity", weight=0)
        qual = CritGroup(session=self, name="Technical quality")
        cost.save()
        sust.save()
        circ.save()
        qual.save()
        Criterion(session=self, name="Operating costs", group=cost, direction="min").save()
        Criterion(session=self, name="Process energy use", group=sust, direction="min").save()
        Criterion(session=self, name="Process carbon footprint", group=sust, direction="min").save()
        #TODO: if self.user_type == self.UserType.KAM:
        # Add more groups and criteria
    
    def ranking_to_pairwise(self, ranking) -> list[tuple]:
        sorted_items = sorted(ranking.items(), key=lambda x: x[1])
        pairwise_list = []
        n = len(sorted_items)
        for i in range(n):
            for j in range(i + 1, n):
                if sorted_items[i][1] < sorted_items[j][1]:
                    pairwise_list.append(
                        (sorted_items[i][0], sorted_items[j][0], 1.0)
                    )
        return pairwise_list
    
    def build_config(self) -> McdaConfig:
        criteria = list(self.criteria)
        criterion_names = [c.name for c in criteria]
        criterion_names.sort()

        matrix = {
            alt.name: [alt.values[c] for c in criterion_names]
            for alt in self.alternatives.all()
        }
        groups = {
            group.name: [c.name for c in group.criteria.all()]
            for group in self.groups.all()
        }

        constraints = WeightConstraints(
            group       = self.group_weights,
            local       = self.local_weights,
            criterion   = self.criterion_weights,
            group_order = self.ranking_to_pairwise(self.group_ranks),
            criterion_order  = self.ranking_to_pairwise(self.crit_ranks)
        )
        if self.local_ranks:
            constraints.local_order = {
                g: self.ranking_to_pairwise(self.local_ranks[g])
                if g in self.local_ranks else None
                for g in groups
            },

        return McdaConfig(
            df              = pd.DataFrame.from_dict(matrix, orient='index', columns=criterion_names),
            directions      = {c.name: c.direction for c in criteria},
            scenario        = self.scenario,
            method          = self.method,
            criteria        = criterion_names,
            weight_mode     = self.weight_mode,
            groups          = groups,
            thresholds      = self.thresholds,
            veto_type       = self.veto_type,
            veto_thresholds = self.veto_thresholds,
            penalty_factor  = self.penalty_factor,
            n_samples       = self.n_samples,
            constraints     = constraints
        )

class DecisionMatrix(models.Model):
    """One row with performance values per alternative."""
    session = models.ForeignKey(McdaSession, on_delete=models.CASCADE,
                                related_name="alternatives")
    name = models.CharField(max_length=40)
    values = models.JSONField()  # {"price": 100, "quality": 0.8}

    class Meta:
        unique_together = ['session', 'name']

class CritGroup(models.Model):
    session   = models.ForeignKey(McdaSession, on_delete=models.CASCADE,
                                  related_name="groups")
    name      = models.CharField(max_length=40)
    weight    = models.CharField(max_length=10, null=True, validators=[validate_number_or_range])  # filled in during form wizard

    def __str__(self):
        return self.name

class Criterion(models.Model):
    """One row per criterion. Partially populated from the request,
    completed during the form wizard.
    """
    session  = models.ForeignKey(McdaSession, on_delete=models.CASCADE,
                                 related_name="all_criteria")
    used = models.BooleanField(default=True)
    name      = models.CharField(max_length=40) # e.g. "price"
    group     = models.ForeignKey(CritGroup, on_delete=models.SET_NULL, blank=True, null=True, related_name="criteria")
    direction = models.CharField(max_length=10, blank=True, validators=[validate_direction], help_text="Enter 'min', 'max' or a target value")
    weight    = models.CharField(max_length=10, blank=True, validators=[validate_number_or_range]) # filled in during form wizard

    def __str__(self):
        return f"{self.name} ({self.group})"

    class Meta:
        # To have distinct criteria in the decision matrix, they need to be unique in a session
        verbose_name_plural = "Criteria"
        unique_together = ['name', 'session']
    
    def clean(self):
        if self.direction not in ["min", "max"]:
            try:
                float(self.direction)
            except ValueError:
                raise ValidationError("The direction must be either 'min', 'max', or a numeric target value.")
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

class GroupOrder(models.Model):
    """Defines the importance order of groups"""
    session = models.ForeignKey(McdaSession, on_delete=models.CASCADE, related_name="group_orders")
    group1 = models.ForeignKey(CritGroup, on_delete=models.CASCADE, related_name="ordered_higher")
    group2 = models.ForeignKey(CritGroup, on_delete=models.CASCADE, related_name="ordered_lower")
    intensity = models.FloatField(validators=[MinValueValidator(0)], default=1)

    class Meta:
        unique_together = ['session', 'group1', 'group2']

class LocalOrder(models.Model):
    """Defines the importance order of criteria in a group"""
    session = models.ForeignKey(McdaSession, on_delete=models.CASCADE, related_name="local_orders")
    criterion1 = models.ForeignKey(Criterion, on_delete=models.CASCADE, related_name="ordered_higher")
    criterion2 = models.ForeignKey(Criterion, on_delete=models.CASCADE, related_name="ordered_lower")
    intensity = models.FloatField(validators=[MinValueValidator(0)], default=1)

    class Meta:
        unique_together = ['session', 'criterion1', 'criterion2']
    
    def clean(self):
        if self.criterion1.group != self.criterion2.group:
            raise ValidationError("Criteria must belong to the same group.")
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

class Results(models.Model):
    session = models.OneToOneField(
        McdaSession, on_delete=models.CASCADE, primary_key=True, related_name='results'
    )
    title = models.CharField(max_length=255)
    plots = models.JSONField(default=dict)
    sections = models.JSONField(default=list)

    def __str__(self):
        return f"Results for {self.title}"