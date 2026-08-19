from io import BytesIO
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# Common figure settings
FIG_W = 12
FIG_H = 8
FONT = 20
CELL_FONT = 20

def fig_to_bytes(fig: plt.Figure) -> bytes:
    """Render a figure to raw SVG bytes and close it."""
    buf = BytesIO()
    fig.savefig(buf, format="svg", bbox_inches="tight", facecolor="#0f172a")
    buf.seek(0)
    data = buf.read()
    plt.close(fig)
    return data

# ============================================================
# FIGURES FOR SHOWING THE RESULTS
# ============================================================

def deterministic_promethee_figures(results: pd.DataFrame, S: pd.DataFrame):
    """Plot two figures for the deterministic PROMETHEE case
    """
    plt.rcParams.update({
        "font.size": FONT,
        "axes.titlesize": FONT,
        "axes.labelsize": FONT,
        "xtick.labelsize": FONT,
        "ytick.labelsize": FONT
    })

    # ============================================================
    # FIGURE 1: NET FLOW SCORE BAR PLOT
    # ============================================================

    # Sort NFS values according to the final PROMETHEE ranking
    sorted_nfs = results["NFS (phi)"].sort_values(ascending=False)
    alternatives = sorted_nfs.index
    nfs_values = sorted_nfs.values

    # Bar plot of the Net Flow Scores
    fig = plt.figure(figsize=(FIG_W, FIG_H))
    bars = plt.bar(alternatives, nfs_values)

    # Add a horizontal line at zero to distinguish positive and negative NFS
    plt.axhline(0, linewidth=1)

    # Place numerical labels just above the zero line
    offset = max(abs(nfs_values)) * 0.03

    for i, v in enumerate(nfs_values):
        plt.text(
            i,
            0 + offset,
            f"{v:.3f}",
            ha="center",
            va="bottom",
            fontsize=FONT
        )

    plt.ylabel("Net Flow Score")
    plt.xticks(rotation=45, ha="right")

    plt.tight_layout()
    plots = {"Net Flow Score": fig}

    # ============================================================
    # FIGURE 2: PAIRWISE PREFERENCE MATRIX WITH FLOWS
    # ============================================================
    """
    Create augmented matrix:
    - original pairwise preference matrix S(a,b)
    - FOR column, i.e. phi_plus
    - AGAINST row, i.e. phi_minus
    """
    S_aug = S.copy()
    S_aug["FOR"] = results["FOR (phi+)"]

    against_row = pd.DataFrame(
        [list(results["AGAINST (phi-)"]) + [np.nan]],
        columns=S_aug.columns,
        index=["AGAINST"]
    )
    S_aug = pd.concat([S_aug, against_row])

    # Convert to numerical array for plotting
    data = S_aug.values.astype(float)

    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))

    # Heatmap of pairwise preference scores and flows
    im = ax.imshow(
        data,
        aspect="auto",
        cmap="Oranges",
        vmin=0,
        vmax=np.nanmax(data)
    )

    # Axis labels
    ax.set_xticks(np.arange(len(S_aug.columns)))
    ax.set_yticks(np.arange(len(S_aug.index)))

    ax.set_xticklabels(S_aug.columns, rotation=45, ha="right")
    ax.set_yticklabels(S_aug.index)

    # Separation lines to visually separate:
    # - the FOR column from the pairwise preference matrix;
    # - the AGAINST row from the pairwise preference matrix.
    n_rows, n_cols = data.shape
    ax.axvline(x=n_cols - 1.5, color="black", linewidth=3)
    ax.axhline(y=n_rows - 1.5, color="black", linewidth=3)

    # ------------------------------------------------------------
    # Add numerical values inside each cell
    # ------------------------------------------------------------

    max_value = np.nanmax(data)

    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            if not np.isnan(data[i, j]):
                text_color = "white" if data[i, j] > max_value * 0.55 else "black"

                ax.text(
                    j,
                    i,
                    f"{data[i, j]:.3f}",
                    ha="center",
                    va="center",
                    fontsize=FONT,
                    color=text_color
                )

    plt.tight_layout()

    # Return two figures
    plots["Pairwise Preference Matrix"] = fig
    return plots

def performance_uncertainty_figures(perf_out: dict):
    """Create two figures for the performance uncertainty case
    """

    plt.rcParams.update({
        "font.size": FONT,
        "axes.titlesize": FONT,
        "axes.labelsize": FONT,
        "xtick.labelsize": FONT,
        "ytick.labelsize": FONT
    })

    # ============================================================
    # FIGURE 1: RANK ACCEPTABILITY HEATMAP
    # ============================================================

    rank_accept = perf_out["rank_acceptability"].copy()

    # Rename columns for clearer plotting
    rank_accept.columns = [
        f"Rank {i}"
        for i in range(1, len(rank_accept.columns) + 1)
    ]

    # Reorder alternatives according to expected rank
    rank_accept = rank_accept.loc[perf_out["expected_rank"].index]

    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))

    im = ax.imshow(
        rank_accept.values, cmap="Blues", vmin=0, vmax=1
    )

    ax.set_xticks(np.arange(rank_accept.shape[1]))
    ax.set_xticklabels(rank_accept.columns, fontsize=FONT)

    ax.set_yticks(np.arange(rank_accept.shape[0]))
    ax.set_yticklabels(rank_accept.index, fontsize=FONT)

    for i in range(rank_accept.shape[0]):
        for j in range(rank_accept.shape[1]):
            val = rank_accept.iloc[i, j]
            ax.text(
                j,
                i,
                f"{val:.2f}",
                ha="center",
                va="center",
                fontsize=CELL_FONT,
                color="white" if val > 0.4 else "black"
            )

    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Probability", fontsize=FONT)
    cbar.ax.tick_params(labelsize=FONT)

    for spine in ax.spines.values():
        spine.set_visible(False)

    plt.tight_layout()
    plots = {"Performance Uncertainty Rank Acceptability": fig}

    # ============================================================
    # FIGURE 2: PAIRWISE OUTRANKING PROBABILITIES
    #           WITH EXPECTED RANK
    # ============================================================

    outrank_prob = perf_out["outrank_probability"].copy()
    expected_rank = perf_out["expected_rank"].copy()

    # Reorder alternatives according to expected rank
    order = expected_rank.index
    outrank_prob = outrank_prob.loc[order, order]

    # Add expected rank as last column
    plot_df = outrank_prob.copy()
    plot_df["Expected rank"] = expected_rank.loc[order]

    # Replace diagonal values with NaN
    # because an alternative is not compared with itself
    for a in order:
        plot_df.loc[a, a] = np.nan

    data = plot_df.values.astype(float)

    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))

    im = ax.imshow(
        data,
        aspect="auto",
        cmap="Greens",
        vmin=0,
        vmax=np.nanmax(data)
    )

    ax.set_xticks(np.arange(len(plot_df.columns)))
    ax.set_yticks(np.arange(len(plot_df.index)))
    ax.set_xticklabels(plot_df.columns, rotation=45, ha="right")
    ax.set_yticklabels(plot_df.index)

    # Separation line before Expected rank column
    ax.axvline(
        x=len(plot_df.columns) - 1.5, color="black", linewidth=3
    )

    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            if not np.isnan(data[i, j]):
                text_color = (
                    "white"
                    if data[i, j] > np.nanmax(data) * 0.55
                    else "black"
                )
                ax.text(
                    j,
                    i,
                    f"{data[i, j]:.3f}",
                    ha="center",
                    va="center",
                    fontsize=CELL_FONT,
                    color=text_color
                )

            else:
                ax.text(
                    j, i, "--", ha="center", va="center", fontsize=16, color="black"
                )

    plt.tight_layout()
    plots["Performance Uncertainty - Pairwise Outranking Expected Rank"] = fig
    return plots

def smaa_figures(smaa_out: dict):
    """Create two figures for deterministic or uncertain SMAA results.
    """

    plt.rcParams.update({
        "font.size": FONT,
        "axes.titlesize": FONT,
        "axes.labelsize": FONT,
        "xtick.labelsize": FONT,
        "ytick.labelsize": FONT
    })

    # ============================================================
    # FIGURE 1: RANK ACCEPTABILITY HEATMAP
    # ============================================================

    rank_accept = smaa_out["rank_acceptability"].copy()

    # Rename columns for clearer plotting
    rank_accept.columns = [
        f"Rank {i}"
        for i in range(1, len(rank_accept.columns) + 1)
    ]

    # Reorder alternatives according to expected rank
    rank_accept = rank_accept.loc[smaa_out["expected_rank"].index]

    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))

    im = ax.imshow(
        rank_accept.values, cmap="Blues", vmin=0, vmax=1
    )

    # Axis ticks
    ax.set_xticks(np.arange(rank_accept.shape[1]))
    ax.set_yticks(np.arange(rank_accept.shape[0]))
    ax.set_xticklabels(
        rank_accept.columns,
        fontsize=FONT,
        rotation=25,
        ha="right"
    )
    ax.set_yticklabels(rank_accept.index, fontsize=FONT)

    # Add values inside cells
    for i in range(rank_accept.shape[0]):
        for j in range(rank_accept.shape[1]):
            val = rank_accept.iloc[i, j]
            ax.text(
                j,
                i,
                f"{val:.2f}",
                ha="center",
                va="center",
                fontsize=CELL_FONT,
                color="white" if val > 0.4 else "black"
            )

    # Colorbar
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Probability", fontsize=FONT)
    cbar.ax.tick_params(labelsize=FONT)

    # Remove spines for a cleaner look
    for spine in ax.spines.values():
        spine.set_visible(False)

    plt.tight_layout()
    plots = {"Rank Acceptability Heatmap": fig}

    # ============================================================
    # FIGURE 2: PAIRWISE OUTRANKING PROBABILITIES
    #           WITH EXPECTED RANK AND MEAN NET FLOW
    # ============================================================

    outrank_prob = smaa_out["outrank_probability"].copy()
    expected_rank = smaa_out["expected_rank"].copy()
    mean_net_flows = smaa_out["mean_net_flows"].copy()

    # Order alternatives according to expected rank
    order = expected_rank.index
    outrank_prob = outrank_prob.loc[order, order]

    # Add expected rank and mean NFS as summary columns
    plot_df = outrank_prob.copy()
    plot_df["Expected rank"] = expected_rank.loc[order]
    plot_df["Mean net flow"] = mean_net_flows.loc[order]

    # Replace diagonal values with NaN
    # because an alternative is not compared with itself
    for a in order:
        plot_df.loc[a, a] = np.nan

    data = plot_df.values.astype(float)
    n_alts = len(order)

    # ------------------------------------------------------------
    # COLOUR DATA
    # ------------------------------------------------------------
    #
    # Only pairwise outranking probabilities are represented
    # through the green colour scale.
    # Expected ranks and mean net flows use a neutral background
    # because they are measured on different scales.

    colour_data = np.full_like(data, np.nan, dtype=float)
    colour_data[:, :n_alts] = data[:, :n_alts]

    # Use a neutral colour for:
    # - diagonal cells;
    # - expected-rank column;
    # - mean-net-flow column.

    cmap = plt.get_cmap("Greens").copy()
    cmap.set_bad(color="#f2f2f2")

    fig, ax = plt.subplots(figsize=(FIG_W + 2, FIG_H))
    im = ax.imshow(
        colour_data, aspect="auto", cmap=cmap, vmin=0, vmax=1
    )

    # Axis ticks
    ax.set_xticks(np.arange(len(plot_df.columns)))
    ax.set_yticks(np.arange(len(plot_df.index)))

    ax.set_xticklabels(plot_df.columns, rotation=45, ha="right")
    ax.set_yticklabels(plot_df.index)

    # Separation line before Expected rank column
    ax.axvline(x=n_alts- 0.5, color="black", linewidth=3)
    # Separate expected rank from mean net flow.
    ax.axvline(x=n_alts + 0.5, color="black", linewidth=1)
    
    # ------------------------------------------------------------
    # NUMERICAL VALUES
    # ------------------------------------------------------------

    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            value = data[i, j]
            if np.isnan(value):
                ax.text(
                    j,
                    i,
                    "--",
                    ha="center",
                    va="center",
                    fontsize=16,
                    color="black"
                )

            else:
                # White text is used only for high probabilities.
                # Summary columns always use black text.
                if j < n_alts and value > 0.55:
                    text_color = "white"
                else:
                    text_color = "black"
                ax.text(
                    j,
                    i,
                    f"{value:.3f}",
                    ha="center",
                    va="center",
                    fontsize=CELL_FONT,
                    color=text_color
                )

    for spine in ax.spines.values():
        spine.set_visible(False)

    plt.tight_layout()
    plots["Pairwise Outranking - Expected Rank Mean Net Flow"] = fig
    return plots
