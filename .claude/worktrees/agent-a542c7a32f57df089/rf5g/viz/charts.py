"""Matplotlib Charts — Link budget, SINR heatmap, service zones."""
from __future__ import annotations
import math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from ..models.output_schema import SizingOutput


def _style_axis(ax, title: str, xlabel: str, ylabel: str):
    """Apply consistent styling to axis."""
    ax.set_title(title, fontsize=14, fontweight="bold", pad=15)
    ax.set_xlabel(xlabel, fontsize=11)
    ax.set_ylabel(ylabel, fontsize=11)
    ax.grid(axis="y", alpha=0.3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def plot_link_budget(result: SizingOutput, output_path: str | None = None) -> str:
    """Generate link budget waterfall chart."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # DL
    dl = result.link_budget_dl
    dl_labels = ["EIRP", "MAPL"]
    dl_values = [dl.eirp_dbm, dl.mapl_db]
    colors_dl = ["#2196F3", "#4CAF50"]

    ax1.bar(range(len(dl_labels)), dl_values, color=colors_dl, edgecolor="white", linewidth=0.5)
    ax1.set_xticks(range(len(dl_labels)))
    ax1.set_xticklabels(dl_labels, fontsize=10)
    for i, v in enumerate(dl_values):
        ax1.text(i, v + 1, f"{v:.1f}", ha="center", fontsize=9, fontweight="bold")

    # Add margin bars
    margins = [
        ("Shadow Fading", -dl.shadow_fading_margin_db),
        ("Penetration", -dl.penetration_loss_db),
        ("Interference", -dl.interference_margin_db),
    ]
    margin_labels = [m[0] for m in margins]
    margin_values = [m[1] for m in margins]
    margin_colors = ["#FF9800"] * len(margins)

    all_labels = dl_labels + margin_labels + ["Rx Sens"]
    all_values = dl_values + margin_values + [dl.rx_sensitivity_dbm]
    all_colors = colors_dl + margin_colors + ["#9E9E9E"]

    ax1.clear()
    ax1.bar(range(len(all_labels)), all_values, color=all_colors, edgecolor="white", linewidth=0.5)
    ax1.set_xticks(range(len(all_labels)))
    ax1.set_xticklabels(all_labels, rotation=45, ha="right", fontsize=9)
    ax1.axhline(y=0, color="black", linewidth=0.5)
    _style_axis(ax1, "DL Link Budget", "Component", "dB / dBm")

    # UL
    ul = result.link_budget_ul
    ul_labels = ["EIRP", "MAPL"]
    ul_values = [ul.eirp_dbm, ul.mapl_db]
    colors_ul = ["#2196F3", "#4CAF50"]

    ul_margins = [
        ("Shadow Fading", -ul.shadow_fading_margin_db),
        ("Penetration", -ul.penetration_loss_db),
        ("Interference", -ul.interference_margin_db),
    ]

    all_ul_labels = ul_labels + [m[0] for m in ul_margins] + ["Rx Sens"]
    all_ul_values = ul_values + [m[1] for m in ul_margins] + [ul.rx_sensitivity_dbm]
    all_ul_colors = colors_ul + ["#FF9800"] * len(ul_margins) + ["#9E9E9E"]

    ax2.bar(range(len(all_ul_labels)), all_ul_values, color=all_ul_colors, edgecolor="white", linewidth=0.5)
    ax2.set_xticks(range(len(all_ul_labels)))
    ax2.set_xticklabels(all_ul_labels, rotation=45, ha="right", fontsize=9)
    ax2.axhline(y=0, color="black", linewidth=0.5)
    _style_axis(ax2, "UL Link Budget", "Component", "dB / dBm")

    limiting = result.site_estimate.limiting_link
    fig.suptitle(
        f"Link Budget -- {result.project_name} | Limiting: {limiting} | "
        f"Band: {result.band} {result.bandwidth_mhz:.0f}MHz",
        fontsize=13, fontweight="bold", y=1.02,
    )

    plt.tight_layout()

    if output_path is None:
        output_path = f"link_budget_{result.project_name.replace(' ', '_')}.png"
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return output_path


def plot_sinr_heatmap(result: SizingOutput, output_path: str | None = None) -> str:
    """Generate SINR vs distance heatmap."""
    from ..engine.propagation import path_loss, los_probability

    fig, ax = plt.subplots(figsize=(10, 6))

    # SINR vs distance for each scenario
    fc_ghz = 3.5 if "n78" in result.band or "n77" in result.band else 0.9
    if "n41" in result.band:
        fc_ghz = 2.5

    distances = np.linspace(10, result.propagation.cell_radius_m * 3, 200)
    mapl = min(result.link_budget_dl.mapl_db, result.link_budget_ul.mapl_db)
    interference = result.link_budget_dl.interference_margin_db if result.link_budget_dl.interference_margin_db else 3.0

    sinr_values = []
    for d in distances:
        pl = path_loss(result.environment, "NLOS", d, fc_ghz)
        sinr = mapl - pl - interference
        sinr_values.append(sinr)

    ax.plot(distances, sinr_values, linewidth=2, color="#2196F3", label="SINR (NLOS)")
    ax.axhline(y=0, color="green", linewidth=1, linestyle="--", alpha=0.7, label="SINR = 0 dB")
    ax.axhline(y=-3, color="orange", linewidth=1, linestyle="--", alpha=0.7, label="SINR = -3 dB (VoNR)")
    ax.axhline(y=-6, color="red", linewidth=1, linestyle="--", alpha=0.7, label="SINR = -6 dB (QPSK 1/2)")

    # Mark cell radius
    ax.axvline(x=result.propagation.cell_radius_m, color="purple", linewidth=2,
               linestyle=":", label=f"Cell edge ({result.propagation.cell_radius_m:.0f}m)")

    # Fill zones
    ax.fill_between(distances, sinr_values, 0, where=[s >= 0 for s in sinr_values],
                    alpha=0.15, color="green", label="_nolegend_")
    ax.fill_between(distances, sinr_values, 0, where=[s < 0 for s in sinr_values],
                    alpha=0.15, color="red", label="_nolegend_")

    ax.set_xlim(0, result.propagation.cell_radius_m * 3)
    ax.set_ylim(min(sinr_values) - 5, max(sinr_values) + 5)
    _style_axis(ax, f"SINR vs Distance — {result.project_name}", "Distance (m)", "SINR (dB)")
    ax.legend(loc="upper right", fontsize=9)

    if output_path is None:
        output_path = f"sinr_heatmap_{result.project_name.replace(' ', '_')}.png"
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return output_path


def plot_service_zones(result: SizingOutput, output_path: str | None = None) -> str:
    """Generate service zone pie chart."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # QoS pass/fail pie
    services = [(q.service, q.passed, q.area_percentage) for q in result.qos_verification]
    pass_count = sum(1 for _, p, _ in services if p)
    fail_count = len(services) - pass_count

    colors_qos = ["#4CAF50", "#F44336"]
    labels_qos = [f"Pass ({pass_count})", f"Fail ({fail_count})"]
    sizes_qos = [pass_count, fail_count]

    if fail_count == 0 and pass_count == 0:
        sizes_qos = [1]
        labels_qos = ["No data"]

    ax1.pie(sizes_qos, labels=labels_qos, colors=colors_qos[:len(sizes_qos)],
            autopct="%1.0f%%", startangle=90, textprops={"fontsize": 11})
    ax1.set_title("QoS Pass/Fail", fontsize=13, fontweight="bold")

    # Service area coverage bar chart
    service_names = [q.service for q in result.qos_verification]
    areas = [q.area_percentage for q in result.qos_verification]
    bar_colors = ["#4CAF50" if q.passed else "#F44336" for q in result.qos_verification]

    bars = ax2.barh(range(len(service_names)), areas, color=bar_colors, edgecolor="white")
    ax2.set_yticks(range(len(service_names)))
    ax2.set_yticklabels(service_names, fontsize=10)
    ax2.set_xlim(0, 105)

    for bar, area in zip(bars, areas):
        ax2.text(bar.get_width() + 1, bar.get_y() + bar.get_height() / 2,
                f"{area:.0f}%", va="center", fontsize=10)

    ax2.axvline(x=95, color="green", linewidth=1, linestyle="--", alpha=0.5)
    ax2.text(96, len(service_names) - 0.5, "95%", fontsize=8, color="green")
    _style_axis(ax2, "Coverage by Service", "Area Coverage (%)", "")

    fig.suptitle(
        f"Service Zones — {result.project_name} | {result.band} {result.bandwidth_mhz:.0f}MHz",
        fontsize=13, fontweight="bold", y=1.02,
    )
    plt.tight_layout()

    if output_path is None:
        output_path = f"service_zones_{result.project_name.replace(' ', '_')}.png"
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return output_path


def plot_capacity_comparison(result: SizingOutput, output_path: str | None = None) -> str:
    """Generate capacity vs demand bar chart."""
    if result.capacity is None:
        return ""

    fig, ax = plt.subplots(figsize=(8, 5))

    categories = ["DL Capacity", "DL Demand", "UL Capacity", "UL Demand"]
    values = [
        result.capacity.total_capacity_dl_gbps,
        result.capacity.total_demand_dl_gbps,
        result.capacity.cell_throughput_ul_mbps * result.site_estimate.coverage_sites / 1000,
        result.capacity.total_demand_dl_gbps * 0.2,  # UL demand ~20% of DL
    ]

    colors = ["#2196F3", "#FF9800", "#4CAF50", "#F44336"]
    bars = ax.bar(range(len(categories)), values, color=colors, edgecolor="white", linewidth=0.5)

    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                f"{val:.1f}", ha="center", fontsize=10, fontweight="bold")

    status = "SUFFICIENT" if result.capacity.capacity_sufficient else "INSUFFICIENT"
    status_color = "#4CAF50" if result.capacity.capacity_sufficient else "#F44336"
    ax.text(0.98, 0.95, f"Capacity: {status}",
            transform=ax.transAxes, fontsize=12, fontweight="bold",
            ha="right", va="top", color=status_color,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor=status_color))

    ax.set_xticks(range(len(categories)))
    ax.set_xticklabels(categories, fontsize=10)
    _style_axis(ax, f"Capacity vs Demand — {result.project_name}", "", "Gbps")

    plt.tight_layout()

    if output_path is None:
        output_path = f"capacity_{result.project_name.replace(' ', '_')}.png"
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return output_path