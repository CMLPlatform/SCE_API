import logging
import pandas as pd
from django.test import TestCase
from .mcda import McdaConfig, WeightConstraints, mcda

logger = logging.getLogger(__name__)
logger.setLevel('DEBUG')

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

        constraints = WeightConstraints(
            group_bounds, group_order_constraints,
            local_bounds, local_order_constraints,
        )

        # ============================================================
        # COMPOSING ALMOST ALL COMBINATIONS OF PARAMETERS
        # ============================================================

        # "scenario", "method", "weight", "veto", "sampling"
        test_cases = [
            ["deterministic", "promethee", "flat", "no", "random"],
            ["deterministic", "promethee", "flat", "soft", "random"],
            ["deterministic", "promethee", "flat", "hard", "random"],
            ["deterministic", "promethee", "group", "no", "random"],
            ["deterministic", "promethee", "hierarchical", "no", "random"],
            ["uncertain", "promethee", "flat", "no", "random"],
            ["uncertain", "promethee", "group", "no", "random"],
            ["uncertain", "promethee", "hierarchical", "no", "random"],
            ["uncertain", "promethee", "group", "no", "bounded"],
            ["uncertain", "promethee", "hierarchical", "no", "bounded"],
            ["uncertain", "promethee", "group", "no", "ordered"],
            ["uncertain", "promethee", "hierarchical", "no", "ordered"],
            ["deterministic", "promethee_like", "group", "no", "ordered"],
            ["deterministic", "promethee_like", "hierarchical", "no", "bounded_ordered"],
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
                sampling_mode=settings[4],
                n_samples=10,
                constraints=constraints,
            )
            result = mcda(config)
        return

class Explanations():
    # ============================================================
    # ANALYSIS SCENARIO SELECTION
    # ============================================================
    """
    The variable `scenario` controls whether the analysis uses:
        1) Fixed weights
        scenario = "deterministic"
        2) Uncertain weights sampled through SMAA
        scenario = "uncertain"

    The uncertainty on the performances is not selected manually.
    It is detected automatically by checking whether the decision
    matrix contains interval values, represented as tuples or lists:
        (lower_bound, upper_bound)

    Therefore, the final analysis type is determined by combining:
    - scenario
    - presence/absence of uncertain performances in df

    This generates four analysis_type cases:
    1. deterministic: Fixed weights + deterministic performance values
    2. performance_uncertainty: Fixed weights + uncertain performance values
    3. smaa_weights: Uncertain weights + deterministic performance values
    4. full_smaa: Uncertain weights + uncertain performance values
    """

    scenario = "uncertain"

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

        This mode is currently allowed only with:
            sampling_mode = "random"

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

    ------------------------------------------------------------
    The variable `sampling_mode` defines which constraints are
    activated during weight sampling:

    random:
        no bounds and no ordinal constraints are imposed.
    bounded:
        lower and upper bounds are imposed, but no ordinal
        constraints are imposed.
    ordered:
        ordinal constraints and preference intensities are imposed,
        but specific lower/upper bounds are not imposed.
    bounded_ordered:
        lower/upper bounds and ordinal/intensity constraints are
        imposed simultaneously.
    """

    weight_mode = "flat"
    sampling_mode = "random"
