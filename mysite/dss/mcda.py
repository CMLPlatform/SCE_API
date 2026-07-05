# Generated from: Promethee_Smaa.ipynb
# Converted at: 2026-06-30

from dataclasses import dataclass
import numpy as np
import pandas as pd
from typing import Literal, Optional

from . import plot
from .serializers import McdaRequestSerializer

# Aliases for reused data structures
Criteria = dict[str, float | tuple[float, float]]
Bounds = dict[str, float]
OrderConstraint = list[tuple[str, str, float]]

@dataclass(slots=True)
class WeightConstraints:
    """
    Class for storing weight costraints in terms of
    upper and lower bounds for (groups of) criteria.
    """
    group_lb: Optional[Bounds] = None
    group_ub: Optional[Bounds] = None
    group_order: Optional[OrderConstraint] = None
    local_lb: Optional[dict[str, Bounds]] = None
    local_ub: Optional[dict[str, Bounds]] = None
    local_order: Optional[dict[str, OrderConstraint]] = None

@dataclass(slots=True)
class McdaConfig:
    # General
    df: pd.DataFrame
    # decision_matrix: dict[str, Criteria]
    directions: dict[str, Literal["min", "max"] | float]
    scenario: str
    method: str
    criteria: Optional[list[str]] = None  # automatically created

    # Weighing and grouping
    weight_mode: str = McdaRequestSerializer.WEIGHT_CHOICES[0]
    groups: Optional[dict[str, list[str]]] = None
    group_weights: Optional[dict[str, float]] = None
    local_weights: Optional[dict[str, float]] = None
    _weights: Optional[dict[str, float]] = None

    # PROMETHEE parameters
    thresholds: Optional[Criteria] = None
    veto_type: str = "no"
    _use_veto: bool = False
    veto_thresholds: Optional[Bounds] = None
    penalty_factor: float = 0.5

    # Sampling
    sampling_mode: Optional[str] = None
    n_samples: int = 10000
    alpha: float = 1.0
    alpha_group: float = 1.0
    alpha_local: float = 1.0

    # Weight constraints
    constraints: Optional[WeightConstraints] = None


# ============================================================
# PERFORMANCE UNCERTAINTY SAMPLING
# ============================================================

def has_uncertain_performances(df):
    """
    Returns True if at least one cell contains
    an interval instead of a deterministic value.
    """
    for col in df.columns:
        for value in df[col]:
            if isinstance(value, (tuple, list)):
                return True
    return False

def sample_performance_matrix(df, rng):
    """
    This function generates one sampled decision matrix.
    If a performance value is deterministic, it is left unchanged.
    If a performance value is an interval (lower, upper)
    then one value is sampled uniformly inside that interval:
        x ~ Uniform(lower, upper)
    """
    sampled_df = df.copy()
    for col in sampled_df.columns:
        for alt in sampled_df.index:
            value = sampled_df.loc[alt, col]
            if isinstance(value, (tuple, list)):
                lower, upper = value
                sampled_df.loc[alt, col] = rng.uniform(lower, upper)
    return sampled_df

# ============================================================
# PROMETHEE HELPER FUNCTIONS
# ============================================================

def preference_difference(x_a: float, x_b: float, direction: str) -> float:
    """
    Compute the performance difference between alternatives a and b.
    The returned value is positive when alternative a is preferred to
    alternative b on the considered criterion.

    For benefit criteria:
        higher values are better, so difference = x_a - x_b

    For cost criteria:
        lower values are better, so difference = x_b - x_a
    """
    if isinstance(direction, (int, float)):
        return abs(x_b - direction) - abs(x_a - direction)
    elif direction == "max":
        return x_a - x_b
    elif direction == "min":
        return x_b - x_a
    else:
        raise ValueError(f"Unknown direction: {direction}")


def promethee_like_preference(d: float, q: float = 0.0) -> float:
    """
    PROMETHEE-like binary preference function.

    If the advantage of a over b is greater than the indifference
    threshold q, then preference is complete:
        P(a,b) = 1
    Otherwise:
        P(a,b) = 0

    With q = 0, this corresponds to a usual criterion (type 1).
    With q > 0, this introduces an indifference threshold (type 2).
    """
    return 1.0 if d > q else 0.0


def promethee_linear_preference(d: float, q: float, p: float) -> float:
    """
    PROMETHEE linear preference function.

    Parameters:
        q : indifference threshold
        p : preference threshold

    Preference is computed as follows:

        if d <= q:
            P(a,b) = 0

        if q < d < p:
            P(a,b) increases linearly from 0 to 1

        if d >= p:
            P(a,b) = 1

    If q = 0, this corresponds to a V-shape preference function (type 3).
    If q > 0, this corresponds to a linear preference function with
    indifference area (type 5).
    """
    if d <= q:
        return 0.0
    if d >= p:
        return 1.0
    return (d - q) / (p - q)


def veto_is_triggered(
    a, b, df_current, directions_dict, veto_thresholds_dict
):
    """
    Check whether alternative a is much worse than alternative b
    on at least one criterion with a veto threshold.
    """
    for c, v in veto_thresholds_dict.items():
        # disadvantage is the inverse of preference
        disadvantage = -preference_difference(
            df_current.loc[a, c],
            df_current.loc[b, c],
            directions_dict[c]
        )
        if disadvantage > v:
            return True
    return False


def set_fixed_weights(config: McdaConfig):
    """
    The dictionary `weights` contains the final weight assigned to
    each criterion.
    Equal weighting:
        each final criterion receives weight 1 / number_of_criteria.
    Group-based weighting:
        each group has a fixed weight W_g.
        The weight of the group is distributed uniformly among
        the criteria belonging to that group.
        For criterion c belonging to group g:
            w_c = W_g / |G_g|
    Hierarchical weighting:
        each final criterion weight is obtained by multiplying:
            group-level weight × normalized local weight
        For criterion c belonging to group g:
            w_c = W_g × w_{c|g}
        where local weights are normalized within each group.
    """

    if config.weight_mode == "flat":
        weights = {c: 1 / len(config.criteria) for c in config.criteria}

    elif config.weight_mode == "group":
        weights = {}
        for g, crits in config.groups.items():
            wg = config.group_weights[g]
            for c in crits:
                weights[c] = wg / len(crits)

    elif config.weight_mode == "hierarchical":
        weights = {}
        for g, crits in config.groups.items():
            Wg = config.group_weights[g]
            total_local = sum(config.local_weights[g].values())
            for c in crits:
                w_local = config.local_weights[g][c] / total_local
                weights[c] = Wg * w_local

    config._weights = weights


# ============================================================
# ACTIVATE CONSTRAINTS ACCORDING TO SAMPLING MODE
# ============================================================
def get_active_constraints(config: McdaConfig) -> WeightConstraints:
    """
    This block translates the selected sampling_mode into the
    actual constraints used by the rejection sampler.

    The active constraints depend on sampling_mode:

    ------------------------------------------------------------
    sampling_mode = "random"
    - group weights are only constrained by the simplex:
            W_g >= 0, sum_g W_g = 1
    - local weights are only constrained by the simplex:
            w_{j|g} >= 0, sum_j w_{j|g} = 1
    - no specific lower/upper bounds are used;
    - no ordinal constraints are used.

    ------------------------------------------------------------
    sampling_mode = "bounded"
    - group lower/upper bounds are activated;
    - local lower/upper bounds are activated;
    - ordinal constraints are not activated.

    ------------------------------------------------------------
    sampling_mode = "ordered"
    - ordinal constraints and preference intensities are activated;
    - specific lower/upper bounds are not activated;
    - only natural simplex bounds 0 <= w <= 1 are used.
    """
    groups = config.groups
    active = WeightConstraints()

    if config.sampling_mode == "random":
        active.group_lb = {g: 0.0 for g in groups}
        active.group_ub = {g: 1.0 for g in groups}
        active.group_order = []

        active.local_lb = {
            g: {c: 0.0 for c in crits}
            for g, crits in groups.items()
        }
        active.local_ub = {
            g: {c: 1.0 for c in crits}
            for g, crits in groups.items()
        }
        active.local_order = {g: [] for g in groups}

    elif config.sampling_mode == "bounded":
        active = config.constraints
        active.group_order = []
        active.local_order = {g: [] for g in groups}

    elif config.sampling_mode == "ordered":
        active.group_lb = {g: 0.0 for g in groups}
        active.group_ub = {g: 1.0 for g in groups}
        active.group_order = config.constraints.group_order

        active.local_lb = {
            g: {c: 0.0 for c in crits}
            for g, crits in groups.items()
        }
        active.local_ub = {
            g: {c: 1.0 for c in crits}
            for g, crits in groups.items()
        }
        active.local_order = config.constraints.local_order

    elif config.sampling_mode == "bounded_ordered":
        active = config.constraints

    else:
        raise ValueError(
            "sampling_mode must be either "
            "'random', 'bounded', 'ordered', or 'bounded_ordered'"
        )

    return active


def sample_weights_dirichlet_constrained(
    lb_dict,
    ub_dict,
    order_cons=[],
    max_tries=100000,
    alpha=1.0,
    rng=None,
    stats=None,
    stats_key="weights"
):
    """
    Sample one feasible weight vector from a constrained Dirichlet
    distribution using rejection sampling.

    The function first draws a candidate vector:
        w ~ Dirichlet(alpha, ..., alpha)

    and then accepts it only if all active constraints are satisfied.

    The constraints are:
    1) Lower and upper bounds:
        lb_i <= w_i <= ub_i

    2) Optional ordinal constraints:
        w_more >= w_less

    3) Optional preference intensity constraints:
        w_more >= intensity * w_less

    Notes
    -----
    With alpha = 1, the Dirichlet distribution is uniform on the
    simplex. Therefore, rejection sampling produces samples uniformly
    distributed over the feasible region defined by the active
    constraints.

    The optional `stats` dictionary records how many candidate
    vectors are generated, accepted and rejected. This is useful to
    evaluate the efficiency of rejection sampling.
    """

    if rng is None:
        rng = np.random.default_rng()

    if stats is not None and stats_key not in stats:
        stats[stats_key] = {
            "draws": 0, "accepted": 0, "rejected": 0
        }

    items = list(lb_dict.keys())
    lb_vec = np.array([lb_dict[x] for x in items], dtype=float)
    ub_vec = np.array([ub_dict[x] for x in items], dtype=float)

    idx = {x: i for i, x in enumerate(items)}

    k = len(items)
    alpha_vec = np.full(k, alpha, dtype=float)

    for _ in range(max_tries):
        w = rng.dirichlet(alpha_vec)

        if stats is not None:
            stats[stats_key]["draws"] += 1

        # Check lower and upper bounds
        rejected = False
        if np.any(w < lb_vec - 1e-12) or np.any(w > ub_vec + 1e-12):
            rejected = True

        # Check ordinal and intensity constraints
        if not rejected:
            for cons in order_cons:

                if len(cons) == 2:
                    hi, lo = cons
                    intensity = 1.0

                elif len(cons) == 3:
                    hi, lo, intensity = cons

                else:
                    raise ValueError(
                        "Each ordinal constraint must be either "
                        "(more_important, less_important) or "
                        "(more_important, less_important, intensity)."
                    )

                if w[idx[hi]] + 1e-12 < intensity * w[idx[lo]]:
                    rejected = True
                    break

        if rejected:
            if stats is not None:
                stats[stats_key]["rejected"] += 1
            continue

        if stats is not None:
            stats[stats_key]["accepted"] += 1

        return {x: float(w[idx[x]]) for x in idx}

    raise RuntimeError(
        "Could not sample a feasible weight vector. "
        "Relax bounds/constraints or increase max_tries."
    )


def sample_hierarchical_weights(
    groups,
    constraints,

    alpha_group=1.0,
    alpha_local=1.0,
    rng=None,
    sampler_stats=None
):
    """
    Sample hierarchical criterion weights.

    The hierarchical model is based on two sampling levels.

    Level 1: group weights
    ----------------------
    A vector of group weights is sampled:
        W = (W_CRM, W_Circularity, W_Environmental, W_Manufacturer)
    with:
        sum_g W_g = 1
    and with the active group-level constraints.

    Level 2: local criterion weights
    ---------------------------------
    For each group g, a local weight vector is sampled:
        w_{j|g}
    with:
        sum_{j in G_g} w_{j|g} = 1
    and with the active local constraints for that group.

    Final global weights
    --------------------
    The final criterion weight is obtained as:
        w_j = W_g * w_{j|g}
    where criterion j belongs to group g.

    The optional sampler_stats object stores rejection sampling
    diagnostics separately for:
        - group weights;
        - local weights of each group.
    """

    if rng is None:
        rng = np.random.default_rng()

    group_weights_sampled = sample_weights_dirichlet_constrained(
        lb_dict=constraints.group_lb,
        ub_dict=constraints.group_ub,
        order_cons=constraints.group_order,
        alpha=alpha_group,
        rng=rng,
        stats=sampler_stats,
        stats_key="group_weights"
    )

    final_weights = {}

    for g, crits in groups.items():

        local_weights_sampled = sample_weights_dirichlet_constrained(
            lb_dict=constraints.local_lb[g],
            ub_dict=constraints.local_ub[g],
            order_cons=constraints.local_order[g],
            alpha=alpha_local,
            rng=rng,
            stats=sampler_stats,
            stats_key=f"local_weights_{g}"
        )

        for c in crits:
            final_weights[c] = group_weights_sampled[g] * local_weights_sampled[c]

    return final_weights


def sample_smaa_weights(config: McdaConfig, sampler_stats={}, rng=None):
    """
    Sample one criterion-weight vector according to the selected
    SMAA weight structure.

    Available weight structures
    ---------------------------

    1) flat
        Final criterion weights are sampled directly:
            w ~ Dirichlet(alpha, ..., alpha)

        No group structure is used.

    2) group
       Only group weights are sampled:
           W_g

       Then each group weight is uniformly distributed among the
       criteria in that group:
           w_j = W_g / |G_g|

       This mode is useful when the decision maker can express
       uncertainty at the group level, but not within groups.

    3) hierarchical
       Group weights and local within-group weights are both sampled:
           w_j = W_g * w_{j|g}

       This is the most flexible structured model, because it allows
       both group-level and criterion-level uncertainty.

    Returns
    -------
    final_weights : dict
        Dictionary mapping each final criterion to its sampled weight.
    """
    if rng is None:
        rng = np.random.default_rng()

    active_constr = get_active_constraints(config)

    if config.weight_mode == "flat":
        criterion_lb = {c: 0.0 for c in config.criteria}
        criterion_ub = {c: 1.0 for c in config.criteria}
        final_weights = sample_weights_dirichlet_constrained(
            lb_dict=criterion_lb,
            ub_dict=criterion_ub,
            order_cons=[],
            alpha=config.alpha,
            rng=rng,
            stats=sampler_stats,
            stats_key="flat_weights"
        )
        return final_weights

    elif config.weight_mode == "group":
        group_weights_sampled = sample_weights_dirichlet_constrained(
            lb_dict=active_constr.group_lb,
            ub_dict=active_constr.group_ub,
            order_cons=active_constr.group_order,
            alpha=config.alpha_group,
            rng=rng,
            stats=sampler_stats,
            stats_key="group_weights"
        )

        final_weights = {}
        for g, crits in config.groups.items():
            for c in crits:
                final_weights[c] = group_weights_sampled[g] / len(crits)
        return final_weights

    elif config.weight_mode == "hierarchical":
        return sample_hierarchical_weights(
            groups=config.groups,
            constraints=config.constraints,
            alpha_group=config.alpha_group,
            alpha_local=config.alpha_local,
            rng=rng,
            sampler_stats=sampler_stats,
        )

    else:
        raise ValueError(
            "weight_mode must be either "
            "'flat', 'group', or 'hierarchical'"
        )

# ============================================================
# PROMETHEE EVALUATION ENGINE
# ============================================================

def promethee_nfs(config: McdaConfig, decision_matrix: pd.DataFrame=None):
    """
    Compute PROMETHEE net flow scores for a given decision matrix
    and a given criterion-weight vector.

    For each ordered pair of alternatives (a,b), the function computes
    an aggregated preference score:
        S(a,b) = sum_j w_j * P_j(a,b)

    where:
        w_j       = criterion weight
        P_j(a,b)  = unicriterion preference of a over b

    Two preference models are supported:

    1) promethee_like
        Binary preference function:
            P_j(a,b) = 1 if d_j(a,b) > q_j
                     = 0 otherwise

    2) promethee
        Linear PROMETHEE preference function with indifference and
        preference thresholds:
            P_j(a,b) = 0                          if d <= q
                     = (d - q) / (p - q)          if q < d < p
                     = 1                          if d >= p

    After computing S(a,b), an optional veto or penalty can be applied.

    The final PROMETHEE flows are:

        phi_plus(a)  = sum_b S(a,b)
        phi_minus(a) = sum_b S(b,a)
        phi(a)       = phi_plus(a) - phi_minus(a)

    Returns
    -------
    nfs : pandas.Series
        Net flow score for each alternative.
    """
    # Fall-back to defaults for unspecified parameters
    df = decision_matrix if decision_matrix is not None else config.df
    method = config.method or "promethee_like"
    config._use_veto = (config.veto_type != "no")
    alts = config.df.index.tolist()

    S = pd.DataFrame(0.0, index=alts, columns=alts)

    if config._use_veto and config.veto_thresholds is None:
        raise ValueError("veto_thresholds must be provided when use_veto=True.")

    for a in alts:
        for b in alts:
            if a == b:
                continue

            score = 0.0

            for c in df.columns:
                d = preference_difference(
                    df.loc[a, c],
                    df.loc[b, c],
                    config.directions[c]
                )

                if method == "promethee_like":
                    q = config.thresholds[c]
                    pref = promethee_like_preference(d, q)
                elif method == "promethee":
                    q, p = config.thresholds[c]
                    pref = promethee_linear_preference(d, q, p)
                else:
                    raise ValueError("method must be either 'promethee_like' or 'promethee'.")

                score += config._weights[c] * pref

            # Apply optional veto / penalty after aggregation
            if config._use_veto and veto_is_triggered(
                a=a,
                b=b,
                df=df,
                directions_dict=config.directions,
                veto_thresholds_dict=config.veto_thresholds,
            ):
                if config.veto_type == "hard":
                    score = 0.0
                elif config.veto_type == "soft":
                    score *= config.penalty_factor
                else:
                    raise ValueError("veto_type must be either 'hard' or 'soft'.")

            S.loc[a, b] = score

    phi_plus = S.sum(axis=1)
    phi_minus = S.sum(axis=0)
    nfs = phi_plus - phi_minus

    return nfs

def deterministic_promethee(config: McdaConfig):
    """
    This function is applicable when:
        scenario = "deterministic"
    and the decision matrix does not contain interval-valued performances.

    In this case:
    - the decision matrix is fixed;
    - the weights are fixed;
    - one PROMETHEE evaluation is performed;
    - the final output is a deterministic ranking.
    """
    alts = config.df.index.tolist()
    S = pd.DataFrame(0.0, index=alts, columns=alts)

    for a in alts:
        for b in alts:
            if a == b:
                continue

            score = 0.0

            for c in config.criteria:
                d = preference_difference(
                    config.df.loc[a, c], config.df.loc[b, c], config.directions[c]
                )

                if config.method == "promethee_like":
                    q = config.thresholds[c]
                    pref = promethee_like_preference(d, q)
                elif config.method == "promethee":
                    if isinstance(config.thresholds[c], (float, int)):
                        print(config.method, c, config.thresholds[c])
                    q, p = config.thresholds[c]
                    pref = promethee_linear_preference(d, q, p)
                else:
                    raise ValueError(
                        "method must be either 'promethee_like' or 'promethee'"
                    )
                score += config._weights[c] * pref

            if config._use_veto and veto_is_triggered(
                a, b, config.df, config.directions, config.veto_thresholds
            ):
                if config.veto_type == "hard":
                    score = 0.0
                elif config.veto_type == "soft":
                    score *= config.penalty_factor
                else:
                    raise ValueError(
                        "veto_type must be either 'hard' or 'soft'"
                    )

            S.loc[a, b] = score

    # ============================================================
    # OUTRANKING FLOWS
    # ============================================================

    phi_plus = S.sum(axis=1)
    phi_minus = S.sum(axis=0)
    nfs = phi_plus - phi_minus

    results = pd.DataFrame({
        "FOR (phi+)": phi_plus,
        "AGAINST (phi-)": phi_minus,
        "NFS (phi)": nfs
    }).sort_values("NFS (phi)", ascending=False)
    return results, S

def run_performance_uncertainty(config: McdaConfig, rng=None):
    """
    Run a Monte Carlo analysis with uncertainty only on alternative
    performances.

    In this analysis:
        - criterion weights are fixed;
        - performance values may be uncertain;
        - uncertain performances are sampled from their intervals;
        - PROMETHEE is applied to each sampled decision matrix;
        - rank acceptability indices are computed from the simulated rankings.
    """

    if rng is None:
        rng = np.random.default_rng()

    n_samples = config.n_samples
    alts = config.df.index.tolist()
    n_alts = len(alts)

    rank_counts = pd.DataFrame(
        0,
        index=alts,
        columns=[f"rank_{r}" for r in range(1, n_alts + 1)],
        dtype=int
    )
    outrank_counts = pd.DataFrame(
        0, index=alts, columns=alts, dtype=int
    )

    win_counts = pd.Series(0, index=alts, dtype=int)

    nfs_samples = {a: [] for a in alts}
    rank_samples = {a: [] for a in alts}

    for s in range(n_samples):
        current_df = sample_performance_matrix(config.df, rng)
        nfs = promethee_nfs(config, decision_matrix=current_df)

        order = nfs.sort_values(ascending=False).index.tolist()
        rank_map = {a: r for r, a in enumerate(order, start=1)}

        for a in alts:
            nfs_samples[a].append(float(nfs[a]))
            rank_samples[a].append(rank_map[a])

        for r, a in enumerate(order, start=1):
            rank_counts.loc[a, f"rank_{r}"] += 1

        win_counts[order[0]] += 1

        for a in alts:
            for b in alts:
                if a != b and nfs[a] > nfs[b]:
                    outrank_counts.loc[a, b] += 1

    rank_accept = rank_counts / n_samples
    win_prob = win_counts / n_samples
    outrank_prob = outrank_counts / n_samples

    ranks = np.arange(1, n_alts + 1, dtype=float)

    exp_rank = (rank_accept.values * ranks).sum(axis=1)
    exp_rank = pd.Series(exp_rank, index=alts).sort_values()

    mean_nfs = pd.Series(
        {a: float(np.mean(nfs_samples[a])) for a in alts}
    ).sort_values(ascending=False)

    sim_rows = []

    for a in alts:
        for i in range(n_samples):
            sim_rows.append({
                "Alternative": a,
                "Simulation": i + 1,
                "NFS": nfs_samples[a][i],
                "Rank": rank_samples[a][i]
            })

    sim_df = pd.DataFrame(sim_rows)

    return {
        "rank_acceptability": rank_accept,
        "expected_rank": exp_rank,
        "win_probability": win_prob.sort_values(ascending=False),
        "outrank_probability": outrank_prob,
        "mean_nfs": mean_nfs,
        "simulations": sim_df
    }


# ============================================================
# SMAA MONTE CARLO SIMULATION
# ============================================================

def run_smaa(config: McdaConfig, analysis_type="full_smaa", rng=None):
    """
    Run the SMAA Monte Carlo simulation.

    At each simulation, the procedure performs three steps:

    1) Generate one realization of the decision problem
       ------------------------------------------------
        If analysis_type = "smaa_weights":
            the decision matrix is fixed.

        If analysis_type = "full_smaa":
            uncertain performance values are sampled from their
            intervals, generating a new decision matrix.

    2) Sample one feasible criterion-weight vector
       -------------------------------------------
        The sampled weights depend on weight_mode:
            flat         -> sample final criterion weights directly
            group        -> sample group weights only
            hierarchical -> sample group and local weights

       Active constraints depend on sampling_mode:
           random  -> no specific constraints
           bounded -> lower/upper bounds
           ordered -> ordinal and intensity constraints

    3) Evaluate alternatives using PROMETHEE
       -------------------------------------
       PROMETHEE net flow scores are computed and converted into
       rankings.

    The function then aggregates all simulations to compute:
        - rank acceptability indices;
        - winning probabilities;
        - pairwise outranking probabilities;
        - expected ranks;
        - mean sampled weights;
        - rejection sampling diagnostics.

    Returns
    -------
    dict
        Dictionary containing SMAA outputs and diagnostic information.
    """

    if rng is None:
        rng = np.random.default_rng()

    # The flat model samples final criterion weights directly.
    # Since no group or local structure is used, this implementation
    # allows flat sampling only in the unconstrained random case.

    if config.weight_mode == "flat" and config.sampling_mode != "random":
        raise ValueError(
            "With weight_mode='flat', only sampling_mode='random' is supported. "
            "Use weight_mode='group' or weight_mode='hierarchical' for bounded or ordered sampling."
        )

    alts = config.df.index.tolist()
    n_alts = len(alts)

    rank_counts = pd.DataFrame(
        0,
        index=alts,
        columns=[f"rank_{r}" for r in range(1, n_alts + 1)],
        dtype=int
    )

    win_counts = pd.Series(0, index=alts, dtype=int)
    outrank_counts = pd.DataFrame(0, index=alts, columns=alts, dtype=int)
    weight_samples = {c: [] for c in config.criteria}

    nfs_samples = {a: [] for a in alts}
    rank_samples = {a: [] for a in alts}
    accepted = 0
    sampler_stats = {}

    for _ in range(config.n_samples):
        # Generate one realization of uncertainty
        if analysis_type == "smaa_weights":
            current_df = config.df
        elif analysis_type == "full_smaa":
            current_df = sample_performance_matrix(config.df, rng)
        else:
            raise ValueError(
                "analysis_type must be either "
                "'smaa_weights' or 'full_smaa'"
            )

        # Sample one feasible weight vector
        w = sample_smaa_weights(config, sampler_stats, rng)

        for c in config.criteria:
            weight_samples[c].append(w[c])

        # Evaluate alternatives using PROMETHEE
        nfs = promethee_nfs(config, decision_matrix=current_df)
        # Convert NFS values into a ranking
        order = nfs.sort_values(ascending=False).index.tolist()
        rank_map = {a: r for r, a in enumerate(order, start=1)}

        # Update SMAA statistics
        for a in alts:
            nfs_samples[a].append(float(nfs[a]))
            rank_samples[a].append(rank_map[a])

        for r, a in enumerate(order, start=1):
            rank_counts.loc[a, f"rank_{r}"] += 1

        win_counts[order[0]] += 1

        for a in alts:
            for b in alts:
                if a == b:
                    continue
                if nfs[a] > nfs[b]:
                    outrank_counts.loc[a, b] += 1

        accepted += 1

    rank_accept = rank_counts / accepted
    win_prob = win_counts / accepted
    outrank_prob = outrank_counts / accepted

    ranks = np.arange(1, n_alts + 1, dtype=float)
    exp_rank = (rank_accept.values * ranks).sum(axis=1)
    exp_rank = pd.Series(exp_rank, index=alts).sort_values()

    w_mean = pd.Series(
        {c: float(np.mean(weight_samples[c])) for c in config.criteria}
    ).sort_values(ascending=False)

    sim_rows = []

    for a in alts:
        for i in range(accepted):
            sim_rows.append({
                "Alternative": a,
                "Simulation": i + 1,
                "NFS": nfs_samples[a][i],
                "Rank": rank_samples[a][i]
            })

    sim_df = pd.DataFrame(sim_rows)

    sampler_stats_df = pd.DataFrame.from_dict(
        sampler_stats, orient="index"
    )

    if not sampler_stats_df.empty:
        sampler_stats_df["acceptance_rate"] = (
            sampler_stats_df["accepted"] / sampler_stats_df["draws"]
        )

        sampler_stats_df["rejection_rate"] = (
            sampler_stats_df["rejected"] / sampler_stats_df["draws"]
        )

    return {
        "rank_acceptability": rank_accept,
        "expected_rank": exp_rank,
        "win_probability": win_prob.sort_values(ascending=False),
        "outrank_probability": outrank_prob,
        "mean_weights": w_mean,
        "n_samples": accepted,
        "simulations": sim_df,
        "sampler_stats": sampler_stats_df
    }


def mcda(config: McdaConfig):
    # ============================================================
    # UNCERTAINTY SETTINGS
    # ============================================================
    
    # Detect whether the decision matrix contains interval-valued performances.
    # If at least one cell is a tuple/list, performance uncertainty is activated.
    performance_uncertainty = has_uncertain_performances(config.df)
    config._use_veto = (config.veto_type!="no")
    config.criteria = list(config.directions.keys())
    set_fixed_weights(config)

    if config.method == "promethee_like":  # Try to fix if thresholds has tuples
        for c, val in config.thresholds.items():
            if not isinstance(val, float):
                config.thresholds[c] = sum(val)/len(val)

    # Select the actual analysis type.
    if config.scenario == "deterministic":
        if performance_uncertainty:
            analysis_type = "performance_uncertainty"
        else:
            analysis_type = "deterministic"

    elif config.scenario == "uncertain":
        if performance_uncertainty:
            analysis_type = "full_smaa"
        else:
            analysis_type = "smaa_weights"

    else:
        raise ValueError(
            "scenario must be either 'deterministic' or 'uncertain'"
        )

    # ============================================================
    # CASE 1: DETERMINISTIC PROMETHEE ANALYSIS
    # ============================================================

    if analysis_type == "deterministic":
        results, pairwise = deterministic_promethee(config)

        pd.set_option("display.precision", 6)
        print("\n--- DETERMINISTIC SCENARIO ---")
        print("\nDecision matrix (numeric):")
        print(config.df)
        print("\nPairwise preference matrix S(a,b):")
        print(pairwise)
        print("\nPROMETHEE flows and NFS:")
        print(results)
        print("\nRanking (best to worst):")
        print(list(results.index))

        plot.deterministic_promethee_figures(results, pairwise)

    # ============================================================
    # CASE 2: PERFORMANCE UNCERTAINTY ANALYSIS
    # ============================================================
        """
        This block is executed when:
            scenario = "deterministic"
        but the decision matrix contains interval-valued performances.

        In this case:
        - criterion weights are fixed;
        - performance values are sampled through Monte Carlo;
        - PROMETHEE is applied to each sampled matrix;
        - rank acceptability indices and winning probabilities are
            computed from the resulting rankings.
        """

    elif analysis_type == "performance_uncertainty":
        rng = np.random.default_rng(42)
        results = run_performance_uncertainty(config, rng)

        print("\n--- PERFORMANCE UNCERTAINTY SCENARIO ---")
        print(f"Samples used: {config.n_samples}")

        print("\nWinning probabilities (P[rank=1]):")
        print(results["win_probability"])

        print("\nExpected rank (lower is better):")
        print(results["expected_rank"])

        print("\nRank acceptability indices b_{i,r}:")
        print(results["rank_acceptability"])

        print("\nMean NFS:")
        print(results["mean_nfs"])

        plot.performance_uncertainty_figures(results)
    
    # ============================================================
    # UNCERTAIN SCENARIO EXECUTION
    # ============================================================
    """
    This block is executed when:
        scenario = "uncertain"

    Depending on the automatically selected analysis_type, the function
    run_smaa performs either:
        smaa_weights
            uncertainty only on weights;

        full_smaa
            uncertainty on both weights and performance values.

    The outputs include:
    - winning probabilities;
    - expected ranks;
    - rank acceptability indices;
    - mean sampled weights;
    - rejection sampling diagnostics;
    - pairwise outranking probabilities.
    """

    if config.scenario == "uncertain":
        rng = np.random.default_rng(42)
        results = run_smaa(config, analysis_type=analysis_type, rng=rng)

        print("\n--- SMAA SCENARIO ---")
        print(f"Samples used: {results['n_samples']}")

        print("\nWinning probabilities (P[rank=1]):")
        print(results["win_probability"])

        print("\nExpected rank (lower is better):")
        print(results["expected_rank"])

        print("\nRank acceptability indices b_{i,r}:")
        print(results["rank_acceptability"])

        print("\nMean sampled weights (barycenter):")
        print(results["mean_weights"])

        print("\nRejection sampling diagnostics:")
        print(results["sampler_stats"])

        print("\nPairwise outranking probabilities P(i outranks j) based on NFS:")
        print(results["outrank_probability"])

        plot.smaa_figures(results)
