#!/usr/bin/env python3
"""
plot_qdrant_results.py
----------------------
Visualises Qdrant benchmark output CSVs (latency, QPS, memory).

* Each CSV must have the format produced by run_benchmarks.sh:
    Vector Size,1M,5M,10M,25M,50M,100M
    384, ...
    768, ...
    ...

* Memory CSV values may include a 'GiB' suffix (stripped automatically).

Output:
    latency_plot.png
    qps_plot.png
    memory_plot.png
"""

import pathlib
import re
from typing import Tuple

import pandas as pd
import matplotlib.pyplot as plt
import argparse


# --------------------------------------------------------------------------- #
# Config – update paths here if your folder structure is different
# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# CLI argument parsing
# --------------------------------------------------------------------------- #
def parse_args():
    """Return argparse.Namespace with result and output directory paths."""
    parser = argparse.ArgumentParser(
        description="Visualise Qdrant benchmark CSV results."
    )
    parser.add_argument(
        "-r",
        "--result-dir",
        default="/tmp/qdrant_benchmark/results",
        help="Directory containing latency_results.csv, qps_results.csv, memory_results.csv",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default="qdrant_plots",
        help="Directory to write PNG plots",
    )
    return parser.parse_args()


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def load_csv(path: pathlib.Path, strip_gib: bool = False) -> pd.DataFrame:
    """
    Reads a CSV, converts numeric columns. Optionally strips 'GiB' suffix.
    Returns a tidy DataFrame with 'Vector Size' as index.
    """
    df = pd.read_csv(path)
    df = df.set_index("Vector Size")

    def _to_float(value: str) -> float:
        """
        Convert a cell to float.
        Accepts plain numbers, '<num>GiB', or '<num>MiB' (MiB is scaled /1024).
        """
        if pd.isna(value):
            return float("nan")

        text = str(value).strip()

        # Handle GiB / MiB suffixes
        if text.endswith("GiB"):
            return float(text.replace("GiB", "").strip())
        if text.endswith("MiB"):
            return float(text.replace("MiB", "").strip()) / 1024

        return float(text)

    # Convert every cell (except the index) to float
    df = df.applymap(_to_float)
    return df


def load_metric_pair(result_dir: pathlib.Path, metric: str, strip_gib: bool) -> dict:
    """
    Return {False: df, True: df_disk} where the key is the on‑disk flag.
    If the _disk file is missing, the dict will contain only {False: df}.
    """
    normal = load_csv(result_dir / f"{metric}_results.csv", strip_gib=strip_gib)
    pair = {False: normal}

    disk_path = result_dir / f"{metric}_results_disk.csv"
    if disk_path.exists():
        pair[True] = load_csv(disk_path, strip_gib=strip_gib)

    return pair


def tidy_for_plot(df: pd.DataFrame) -> Tuple[list, pd.DataFrame]:
    """
    Returns x-labels (dataset sizes) and a DataFrame ready for plotting.
    Drops any NaN-only columns (occurs if 25M/50M/100M not tested).
    """
    df = df.dropna(axis="columns", how="all")
    x_labels = df.columns.tolist()
    return x_labels, df


def plot_metric(
    df: pd.DataFrame, x_labels: list, title: str, ylabel: str, outfile: pathlib.Path
) -> None:
    """
    Plots one metric. Each vector size gets its own line/marker series.
    """
    plt.figure()  # separate figure per metric
    for vec_size, series in df.iterrows():
        plt.plot(x_labels, series.values, marker="o", label=f"Vector dim {vec_size}")

    plt.title(title)
    plt.xlabel("Corpus size (vectors)")
    plt.ylabel(ylabel)
    plt.legend()
    plt.grid(True, linestyle=":")
    plt.tight_layout()
    plt.savefig(outfile, dpi=300)
    plt.close()
    print(f"Wrote {outfile}")


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> None:
    args = parse_args()
    result_dir = pathlib.Path(args.result_dir)
    output_dir = pathlib.Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    metrics = {
        "latency": {"strip_gib": False},
        "qps": {"strip_gib": False},
        "memory": {"strip_gib": True},
    }

    pairs = {
        m: load_metric_pair(result_dir, m, info["strip_gib"])
        for m, info in metrics.items()
    }

    def plot_with_disk(metric_key, title, ylabel, outfile):
        pair = pairs[metric_key]
        plt.figure()
        markers = {384: "o", 768: "s", 1024: "^"}
        styles = {False: "-", True: "--"}

        # We assume all dfs share the same x-labels
        on_disk_false_df = pair[False]
        x_labels = on_disk_false_df.columns.tolist()

        for on_disk, df in pair.items():
            for vec_size, series in df.iterrows():
                plt.plot(
                    x_labels,
                    series.values,
                    marker=markers.get(vec_size, "o"),
                    linestyle=styles[on_disk],
                    label=f"Vector dim {vec_size} ({'disk' if on_disk else 'mem'})",
                )

        plt.title(title)
        plt.xlabel("Corpus size (vectors)")
        plt.ylabel(ylabel)
        plt.legend(fontsize="small", ncol=2)
        plt.grid(True, linestyle=":")
        plt.tight_layout()
        plt.savefig(outfile, dpi=300)
        plt.close()
        print(f"Wrote {outfile}")

    plot_with_disk(
        "latency",
        title="Average Query Latency vs. Dataset Size",
        ylabel="Latency (seconds)",
        outfile=output_dir / "latency_plot.png",
    )

    plot_with_disk(
        "qps",
        title="Query Throughput vs. Dataset Size",
        ylabel="Queries per second (QPS)",
        outfile=output_dir / "qps_plot.png",
    )

    plot_with_disk(
        "memory",
        title="Peak Docker-RSS vs. Dataset Size",
        ylabel="Memory (GiB)",
        outfile=output_dir / "memory_plot.png",
    )


if __name__ == "__main__":
    main()
