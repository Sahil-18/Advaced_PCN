import os
import glob
import re
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Convert transfer strings like '489 KBytes' to MB
def convert_to_mb(value_str):
    match = re.match(r"([\d\.]+)\s*([KMG]?)Bytes", value_str.strip())
    if not match:
        return 0.0
    val, unit = float(match.group(1)), match.group(2)
    if unit == 'K':
        return val / 1024
    elif unit == 'M':
        return val
    elif unit == 'G':
        return val * 1024
    return val

# Mapping of configuration names to their folder pairs
CONFIGS = {
    "NON_PCN": ["NON_PCN_RUN_1", "NON_PCN_RUN_2"],
    "PCN_MIN": ["PCN_RUN_1_MIN", "PCN_RUN_2_MIN"],
    "PCN_FIN_MIN": ["PCN_FIN_RUN_1_MIN", "PCN_FIN_RUN_2_MIN"],
    "PCN_HARMONIC": ["PCN_RUN_1_HARMONIC", "PCN_RUN_2_HARMONIC"],
    "PCN_FIN_HARMONIC": ["PCN_FIN_RUN_1_HARMONIC", "PCN_FIN_RUN_2_HARMONIC"]
}

def process_combined_experiment(config_name, folders, parent_folder, output_folder, total_data_mb):
    all_traffic_data = {}
    all_durations = {}

    for folder in folders:
        full_path = os.path.join(parent_folder, folder)
        traffic_folders = sorted([f for f in os.listdir(full_path) if f.startswith("Traffic")])

        for traffic in traffic_folders:
            traffic_path = os.path.join(full_path, traffic)
            traffic_files = sorted(glob.glob(os.path.join(traffic_path, "traffic_*.csv")))

            for file in traffic_files:
                df = pd.read_csv(file)
                df = df[:-2]  # remove last 2 lines (summary)
                df['start'] = df['start_time'].astype(int)
                df['sent_MB'] = df['transfer'].apply(convert_to_mb)
                per_sec = df.groupby('start')['sent_MB'].sum().sort_index()
                cumulative = per_sec.cumsum()
                filled = cumulative.reindex(range(cumulative.index.max() + 1), method='ffill').fillna(0)
                filled.loc[0] = 0.0  # force (0, 0.0) explicitly
                filled = filled.sort_index()

                if traffic not in all_traffic_data:
                    all_traffic_data[traffic] = []
                    all_durations[traffic] = []

                all_traffic_data[traffic].append(filled)
                all_durations[traffic].append(filled.index[-1])

    os.makedirs(output_folder, exist_ok=True)

    # Generate normalized CDF plot
    fig_cdf, ax_cdf = plt.subplots(figsize=(10, 6))
    colors = plt.cm.get_cmap("tab10")
    duration_stats = {}

    for idx, traffic in enumerate(sorted(all_traffic_data.keys())):
        cdfs = all_traffic_data[traffic]
        durations = all_durations[traffic]
        max_time = max(cdf.index.max() for cdf in cdfs)
        time_index = range(max_time + 1)
        aligned = [cdf.reindex(time_index, method='ffill').fillna(0) for cdf in cdfs]
        matrix = pd.DataFrame(aligned)
        mean_cdf = matrix.mean()
        mean_cdf.loc[0] = 0.0  # ensure mean also starts from 0

        percent_cdf = (mean_cdf / total_data_mb) * 100
        percent_cdf = percent_cdf.clip(upper=100)

        # Trim after first 100% point
        first_full_index = percent_cdf[percent_cdf >= 100].index.min()
        percent_cdf = percent_cdf.loc[:first_full_index]

        ax_cdf.plot(percent_cdf.index, percent_cdf.values, label=traffic, color=colors(idx % 10))
        duration_stats[traffic] = (np.mean(durations), np.std(durations))

    ax_cdf.set_xlabel("Time (s)")
    ax_cdf.set_ylabel("Cumulative Completion (%)")
    ax_cdf.set_title(f"Average CDF (% Completion) - {config_name}")
    ax_cdf.set_ylim(0, 105)
    ax_cdf.set_xlim(left=0)
    ax_cdf.legend()
    ax_cdf.grid(False)
    ax_cdf.spines['left'].set_position('zero')
    ax_cdf.spines['bottom'].set_position('zero')
    plt.tight_layout()
    fig_cdf.savefig(os.path.join(output_folder, f"{config_name}_cdf_data_sent.png"))
    plt.close(fig_cdf)

    # Bar chart for duration statistics
    traffic_names = sorted(duration_stats.keys())
    mean_durations = [duration_stats[t][0] for t in traffic_names]
    std_durations = [duration_stats[t][1] for t in traffic_names]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(traffic_names, mean_durations, yerr=std_durations, capsize=5, color='skyblue', width=0.5)
    ax.set_ylabel("Average Iteration Completion Time (s)")
    ax.set_title(f"Avg & Std Dev of Iteration Duration - {config_name}")
    ax.grid(False)
    plt.tight_layout()
    fig.savefig(os.path.join(output_folder, f"{config_name}_avg_duration_variance.png"))
    plt.close(fig)

    # Save to CSV
    df_stats = pd.DataFrame({
        'traffic': traffic_names,
        'avg_duration': mean_durations,
        'std_dev': std_durations
    })
    df_stats.to_csv(os.path.join(output_folder, f"{config_name}_iteration_duration_stats.csv"), index=False)

def process_all_configs(parent_folder, total_data_mb):
    results_folder = os.path.join(parent_folder, "Results")
    os.makedirs(results_folder, exist_ok=True)
    for config_name, runs in CONFIGS.items():
        process_combined_experiment(config_name, runs, parent_folder, results_folder, total_data_mb)

if __name__ == "__main__":
    folders = [("/home/spurohi2/Desktop/Advaced_PCN/pcn_src/Results/10 MB/Big Exp", 10),
               ("/home/spurohi2/Desktop/Advaced_PCN/pcn_src/Results/20 MB/Big Exp", 20),
               ("/home/spurohi2/Desktop/Advaced_PCN/pcn_adv_src/Results/10 MB", 10),
               ("/home/spurohi2/Desktop/Advaced_PCN/pcn_adv_src/Results/20 MB", 20)]
               
    for folder, total_data_mb in folders:
        process_all_configs(folder, total_data_mb)
        print(f"Processed folder: {folder}")