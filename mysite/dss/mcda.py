# Generated from: Promethee_Smaa.ipynb
# Converted at: 2026-06-30

import pandas as pd
import numpy as np


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
    if direction == "max":
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


def disadvantage_difference(x_a: float, x_b: float, direction: str) -> float:
    """
    Returns a positive value when a is worse than b.
    """
    if direction == "max":
        return x_b - x_a
    elif direction == "min":
        return x_a - x_b
    else:
        raise ValueError(f"Unknown direction: {direction}")


def veto_is_triggered(
    a, b, df_current, directions_dict, veto_thresholds_dict
):
    """
    Check whether alternative a is much worse than alternative b
    on at least one criterion with a veto threshold.
    """
    for c, v in veto_thresholds_dict.items():
        disadvantage = disadvantage_difference(
            df_current.loc[a, c],
            df_current.loc[b, c],
            directions_dict[c]
        )
        if disadvantage > v:
            return True
    return False


def run_performance_uncertainty(
    df,
    criteria_list,
    directions_dict,
    weights_dict,
    n_samples=10000,
    rng=None,
    method="promethee_like",
    thresholds_dict=None,
    use_veto=False,
    veto_thresholds_dict=None,
    veto_type="hard",
    penalty_factor=0.5
):
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

    alts = df.index.tolist()
    n_alts = len(alts)

    rank_counts = pd.DataFrame(
        0,
        index=alts,
        columns=[f"rank_{r}" for r in range(1, n_alts + 1)],
        dtype=int
    )

    win_counts = pd.Series(0, index=alts, dtype=int)

    nfs_samples = {a: [] for a in alts}
    rank_samples = {a: [] for a in alts}

    for s in range(n_samples):
        current_df = sample_performance_matrix(df, rng)
        nfs = promethee_nfs(
            df=current_df,
            criteria_list=criteria_list,
            directions_dict=directions_dict,
            weights_dict=weights_dict,
            method=method,
            thresholds_dict=thresholds_dict,
            use_veto=use_veto,
            veto_thresholds_dict=veto_thresholds_dict,
            veto_type=veto_type,
            penalty_factor=penalty_factor
        )

        order = nfs.sort_values(ascending=False).index.tolist()
        rank_map = {a: r for r, a in enumerate(order, start=1)}

        for a in alts:
            nfs_samples[a].append(float(nfs[a]))
            rank_samples[a].append(rank_map[a])

        for r, a in enumerate(order, start=1):
            rank_counts.loc[a, f"rank_{r}"] += 1

        win_counts[order[0]] += 1

    rank_accept = rank_counts / n_samples
    win_prob = win_counts / n_samples

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
        "mean_nfs": mean_nfs,
        "n_samples": n_samples,
        "simulations": sim_df
    }


# ============================================================
# ACTIVATE CONSTRAINTS ACCORDING TO SAMPLING MODE
# ============================================================
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

if sampling_mode == "random":
    active_group_lb = {g: 0.0 for g in groups}
    active_group_ub = {g: 1.0 for g in groups}
    active_group_order = []

    active_local_lb = {
        g: {c: 0.0 for c in crits}
        for g, crits in groups.items()
    }
    active_local_ub = {
        g: {c: 1.0 for c in crits}
        for g, crits in groups.items()
    }
    active_local_order = {g: [] for g in groups}

elif sampling_mode == "bounded":
    active_group_lb = group_lb
    active_group_ub = group_ub
    active_group_order = []

    active_local_lb = local_lb
    active_local_ub = local_ub
    active_local_order = {g: [] for g in groups}

elif sampling_mode == "ordered":
    active_group_lb = {g: 0.0 for g in groups}
    active_group_ub = {g: 1.0 for g in groups}
    active_group_order = group_order_constraints

    active_local_lb = {
        g: {c: 0.0 for c in crits}
        for g, crits in groups.items()
    }
    active_local_ub = {
        g: {c: 1.0 for c in crits}
        for g, crits in groups.items()
    }
    active_local_order = local_order_constraints

else:
    raise ValueError(
        "sampling_mode must be either "
        "'random', 'bounded', or 'ordered'"
    )


def sample_weights_dirichlet_constrained(
    items,
    lb_dict,
    ub_dict,
    order_cons=None,
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

    lb_vec = np.array([lb_dict[x] for x in items], dtype=float)
    ub_vec = np.array([ub_dict[x] for x in items], dtype=float)

    idx = {x: i for i, x in enumerate(items)}
    order_cons = order_cons or []

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

        return {x: float(w[idx[x]]) for x in items}

    raise RuntimeError(
        "Could not sample a feasible weight vector. "
        "Relax bounds/constraints or increase max_tries."
    )


def sample_hierarchical_weights(
    groups,
    group_names,

    active_group_lb,
    active_group_ub,
    active_group_order,

    active_local_lb,
    active_local_ub,
    active_local_order,

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
        items=group_names,
        lb_dict=active_group_lb,
        ub_dict=active_group_ub,
        order_cons=active_group_order,
        alpha=alpha_group,
        rng=rng,
        stats=sampler_stats,
        stats_key="group_weights"
    )

    final_weights = {}

    for g, crits in groups.items():

        local_weights_sampled = sample_weights_dirichlet_constrained(
            items=crits,
            lb_dict=active_local_lb[g],
            ub_dict=active_local_ub[g],
            order_cons=active_local_order[g],
            alpha=alpha_local,
            rng=rng,
            stats=sampler_stats,
            stats_key=f"local_weights_{g}"
        )

        for c in crits:
            final_weights[c] = group_weights_sampled[g] * local_weights_sampled[c]

    return final_weights


def sample_smaa_weights(
    criteria_list,

    groups,
    group_names,

    weight_mode,

    active_group_lb,
    active_group_ub,
    active_group_order,

    active_local_lb,
    active_local_ub,
    active_local_order,

    lb_dict,
    ub_dict,
    order_cons,

    alpha=1.0,
    alpha_group=1.0,
    alpha_local=1.0,

    rng=None,
    sampler_stats=None
):
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

    if weight_mode == "flat":
        criterion_lb = {c: 0.0 for c in criteria_list}
        criterion_ub = {c: 1.0 for c in criteria_list}
        final_weights = sample_weights_dirichlet_constrained(
            items=criteria_list,
            lb_dict=criterion_lb,
            ub_dict=criterion_ub,
            order_cons=[],
            alpha=alpha,
            rng=rng,
            stats=sampler_stats,
            stats_key="flat_weights"
        )
        return final_weights

    elif weight_mode == "group":
        group_weights_sampled = sample_weights_dirichlet_constrained(
            items=group_names,
            lb_dict=active_group_lb,
            ub_dict=active_group_ub,
            order_cons=active_group_order,
            alpha=alpha_group,
            rng=rng,
            stats=sampler_stats,
            stats_key="group_weights"
        )

        final_weights = {}
        for g, crits in groups.items():
            for c in crits:
                final_weights[c] = group_weights_sampled[g] / len(crits)
        return final_weights

    elif weight_mode == "hierarchical":
        return sample_hierarchical_weights(
            groups=groups,
            group_names=group_names,

            active_group_lb=active_group_lb,
            active_group_ub=active_group_ub,
            active_group_order=active_group_order,

            active_local_lb=active_local_lb,
            active_local_ub=active_local_ub,
            active_local_order=active_local_order,

            alpha_group=alpha_group,
            alpha_local=alpha_local,

            sampler_stats=sampler_stats,
            rng=rng
        )

    else:
        raise ValueError(
            "weight_mode must be either "
            "'flat', 'group', or 'hierarchical'"
        )

# ============================================================
# PROMETHEE EVALUATION ENGINE
# ============================================================

def promethee_nfs(
    df,
    criteria_list,
    directions_dict,
    weights_dict,
    method="promethee_like",
    thresholds_dict=None,
    use_veto=False,
    veto_thresholds_dict=None,
    veto_type="hard",
    penalty_factor=0.5
):
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
    alts = df.index.tolist()
    S = pd.DataFrame(0.0, index=alts, columns=alts)

    if use_veto and veto_thresholds_dict is None:
        raise ValueError("veto_thresholds_dict must be provided when use_veto=True.")

    for a in alts:
        for b in alts:
            if a == b:
                continue

            score = 0.0

            for c in criteria_list:
                d = preference_difference(
                    df.loc[a, c],
                    df.loc[b, c],
                    directions_dict[c]
                )

                if method == "promethee_like":
                    q = thresholds_dict[c]["q"]
                    pref = promethee_like_preference(d, q)

                elif method == "promethee":
                    q = thresholds_dict[c]["q"]
                    p = thresholds_dict[c]["p"]
                    pref = promethee_linear_preference(d, q, p)

                else:
                    raise ValueError("method must be either 'promethee_like' or 'promethee'.")

                score += weights_dict[c] * pref

            # Apply optional veto / penalty after aggregation
            if use_veto and veto_is_triggered(
                a=a,
                b=b,
                df=df,
                directions_dict=directions_dict,
                veto_thresholds_dict=veto_thresholds_dict
            ):
                if veto_type == "hard":
                    score = 0.0

                elif veto_type == "soft":
                    score *= penalty_factor

                else:
                    raise ValueError("veto_type must be either 'hard' or 'soft'.")

            S.loc[a, b] = score

    phi_plus = S.sum(axis=1)
    phi_minus = S.sum(axis=0)
    nfs = phi_plus - phi_minus

    return nfs

# ============================================================
# SMAA MONTE CARLO SIMULATION
# ============================================================

def run_smaa(
    df,
    criteria_list,
    directions_dict,
    analysis_type="full_smaa",
    n_samples=100000,
    lb_dict=None,
    ub_dict=None,
    order_cons=None,
    alpha=1.0,
    rng=None,
    method="promethee_like",
    thresholds_dict=None,
    use_veto=False,
    veto_thresholds_dict=None,
    veto_type="hard",
    penalty_factor=0.5,
    weight_mode="flat",
    sampling_mode="random",
    groups=None,
    group_lb=None,
    group_ub=None,
    group_order_constraints=None,
    local_lb=None,
    local_ub=None,
    local_order_constraints=None,
    alpha_group=1.0,
    alpha_local=1.0
):
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

    if weight_mode == "flat" and sampling_mode != "random":
        raise ValueError(
            "With weight_mode='flat', only sampling_mode='random' is supported. "
            "Use weight_mode='group' or weight_mode='hierarchical' for bounded or ordered sampling."
        )

    alts = df.index.tolist()
    n_alts = len(alts)

    rank_counts = pd.DataFrame(
        0,
        index=alts,
        columns=[f"rank_{r}" for r in range(1, n_alts + 1)],
        dtype=int
    )

    win_counts = pd.Series(0, index=alts, dtype=int)
    outrank_counts = pd.DataFrame(0, index=alts, columns=alts, dtype=int)
    weight_samples = {c: [] for c in criteria_list}

    nfs_samples = {a: [] for a in alts}
    rank_samples = {a: [] for a in alts}

    accepted = 0

    sampler_stats = {}

    for _ in range(n_samples):
        # Generate one realization of uncertainty
        if analysis_type == "smaa_weights":
            current_df = df
        elif analysis_type == "full_smaa":
            current_df = sample_performance_matrix(df, rng)
        else:
            raise ValueError(
                "analysis_type must be either "
                "'smaa_weights' or 'full_smaa'"
            )

        # Sample one feasible weight vector
        w = sample_smaa_weights(
            criteria_list=criteria_list,

            groups=groups,
            group_names=group_names,

            weight_mode=weight_mode,

            active_group_lb=active_group_lb,
            active_group_ub=active_group_ub,
            active_group_order=active_group_order,

            active_local_lb=active_local_lb,
            active_local_ub=active_local_ub,
            active_local_order=active_local_order,

            lb_dict=lb_dict,
            ub_dict=ub_dict,
            order_cons=order_cons,

            alpha=alpha,
            alpha_group=alpha_group,
            alpha_local=alpha_local,

            rng=rng,
            sampler_stats=sampler_stats
        )

        for c in criteria_list:
            weight_samples[c].append(w[c])

        # Evaluate alternatives using PROMETHEE
        nfs = promethee_nfs(
            df=current_df,
            criteria_list=criteria_list,
            directions_dict=directions_dict,
            weights_dict=w,
            method=method,
            thresholds_dict=thresholds_dict,
            use_veto=use_veto,
            veto_thresholds_dict=veto_thresholds_dict,
            veto_type=veto_type,
            penalty_factor=penalty_factor
        )
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
        {c: float(np.mean(weight_samples[c])) for c in criteria_list}
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



def mcda(df, directions, scenario, method, weight_mode="equal"):
    # ============================================================
    # UNCERTAINTY SETTINGS
    # ============================================================
    
    # Detect whether the decision matrix contains interval-valued performances.
    # If at least one cell is a tuple/list, performance uncertainty is activated.
    performance_uncertainty = has_uncertain_performances(df)

    # Select the actual analysis type.
    if scenario == "deterministic":
        if performance_uncertainty:
            analysis_type = "performance_uncertainty"
        else:
            analysis_type = "deterministic"

    elif scenario == "uncertain":
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
    """
    This block is executed when:
        scenario = "deterministic"
    and the decision matrix does not contain interval-valued performances.

    In this case:
    - the decision matrix is fixed;
    - the weights are fixed;
    - one PROMETHEE evaluation is performed;
    - the final output is a deterministic ranking.
    """

    if analysis_type == "deterministic":

        criteria = df.columns.tolist()
        alts = df.index.tolist()
        S = pd.DataFrame(0.0, index=alts, columns=alts)

        for a in alts:
            for b in alts:
                if a == b:
                    continue

                score = 0.0

                for c in criteria:
                    d = preference_difference(
                        df.loc[a, c], df.loc[b, c], directions[c]
                    )

                    if method == "promethee_like":
                        q = thresholds[c]["q"]
                        pref = promethee_like_preference(d, q)
                    elif method == "promethee":
                        q = thresholds[c]["q"]
                        p = thresholds[c]["p"]
                        pref = promethee_linear_preference(d, q, p)
                    else:
                        raise ValueError(
                            "method must be either 'promethee_like' or 'promethee'"
                        )
                    score += weights[c] * pref

                if use_veto and veto_is_triggered(a, b):
                    if veto_type == "hard":
                        score = 0.0
                    elif veto_type == "soft":
                        score *= penalty_factor
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

        pd.set_option("display.precision", 6)

        print("\n--- DETERMINISTIC SCENARIO ---")
        print("\nDecision matrix (numeric):")
        print(df)
        print("\nPairwise preference matrix S(a,b):")
        print(S)
        print("\nPROMETHEE flows and NFS:")
        print(results)
        print("\nRanking (best to worst):")
        print(list(results.index))

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

        perf_out = run_performance_uncertainty(
            df=df,
            criteria_list=criteria,
            directions_dict=directions,
            weights_dict=weights,
            n_samples=10000,
            rng=rng,
            method=method,
            thresholds_dict=thresholds,
            use_veto=use_veto,
            veto_thresholds_dict=veto_thresholds,
            veto_type=veto_type,
            penalty_factor=penalty_factor
        )

        print("\n--- PERFORMANCE UNCERTAINTY SCENARIO ---")
        print(f"Samples used: {perf_out['n_samples']}")

        print("\nWinning probabilities (P[rank=1]):")
        print(perf_out["win_probability"])

        print("\nExpected rank (lower is better):")
        print(perf_out["expected_rank"])

        print("\nRank acceptability indices b_{i,r}:")
        print(perf_out["rank_acceptability"])

        print("\nMean NFS:")
        print(perf_out["mean_nfs"])
    

    # ============================================================
    # FIXED CRITERION WEIGHTS
    # ============================================================
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

    if weight_mode == "equal":
        weights = {c: 1 / len(criteria) for c in criteria}

    elif weight_mode == "group":
        weights = {}
        for g, crits in groups.items():
            wg = group_weights[g]
            for c in crits:
                weights[c] = wg / len(crits)

    elif weight_mode == "hierarchical":
        weights = {}
        for g, crits in groups.items():
            Wg = group_weights[g]
            total_local = sum(local_weights[g].values())
            for c in crits:
                w_local = local_weights[g][c] / total_local
                weights[c] = Wg * w_local

    else:
        raise ValueError(
            "weight_mode must be either 'equal', 'group', or 'hierarchical'"
        )
    
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

    if scenario == "uncertain":
        smaa_out = run_smaa(
            df=df,
            criteria_list=criteria,
            directions_dict=directions,
            analysis_type=analysis_type,
            n_samples=10000,

            # General SMAA settings
            alpha=1.0,
            rng=rng,

            # PROMETHEE settings
            method=method,
            thresholds_dict=thresholds,

            # Veto settings
            use_veto=use_veto,
            veto_thresholds_dict=veto_thresholds,
            veto_type=veto_type,
            penalty_factor=penalty_factor,

            # Weight structure settings
            weight_mode=weight_mode,
            sampling_mode=sampling_mode,

            # Group-level settings
            groups=groups,
            group_lb=group_lb,
            group_ub=group_ub,
            group_order_constraints=group_order_constraints,

            # Local criterion-level settings
            local_lb=local_lb,
            local_ub=local_ub,
            local_order_constraints=local_order_constraints,

            # Hierarchical sampling parameters
            alpha_group=1.0,
            alpha_local=1.0
        )

        print("\n--- SMAA RESULTS (Scenario 2) ---")
        print(f"Samples used: {smaa_out['n_samples']}")

        print("\nWinning probabilities (P[rank=1]):")
        print(smaa_out["win_probability"])

        print("\nExpected rank (lower is better):")
        print(smaa_out["expected_rank"])

        print("\nRank acceptability indices b_{i,r}:")
        print(smaa_out["rank_acceptability"])

        print("\nMean sampled weights (barycenter):")
        print(smaa_out["mean_weights"])

        print("\nRejection sampling diagnostics:")
        print(smaa_out["sampler_stats"])

        print("\nPairwise outranking probabilities P(i outranks j) based on NFS:")
        print(smaa_out["outrank_probability"])
