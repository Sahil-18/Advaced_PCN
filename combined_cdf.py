import os
import glob
import re
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

CONFIGS = {
    "NON_PCN": ["NON_PCN_RUN_1", "NON_PCN_RUN_2"],
    "PCN": ["PCN_RUN_1", "PCN_RUN_2"],
    "PCN_MIN": ["PCN_RUN_1_MIN", "PCN_RUN_2_MIN"],
    "PCN_FIN_MIN": ["PCN_FIN_RUN_1_MIN", "PCN_FIN_RUN_2_MIN"],
    "PCN_HARMONIC": ["PCN_RUN_1_HARMONIC", "PCN_RUN_2_HARMONIC"],
    "PCN_FIN_HARMONIC": ["PCN_FIN_RUN_1_HARMONIC", "PCN_FIN_RUN_2_HARMONIC"]
}

def convert_to_mb(value_str):
    match = re.match(r"([\d\.]+)\s*([KMG]?)Bytes", value_str.strip())
    if not match:
        return 0.0
    val, unit = float(match.group(1)), match.group(2)
    if unit == 'K': return val / 1024
    elif unit == 'M': return val
    elif unit == 'G': return val * 1024
    return val

def process_all_configs_combined(parent_folder, total_data_mb):
    all_config_cdfs = {}
    all_flow_durations = []

    results_folder = os.path.join(parent_folder, "Results", "Duration_Analysis")
    os.makedirs(results_folder, exist_ok=True)

    for config_name, runs in CONFIGS.items():
        all_cdfs = []
        all_durations = {}

        for run in runs:
            run_path = os.path.join(parent_folder, run)
            traffic_folders = sorted([f for f in os.listdir(run_path) if f.startswith("Traffic")])

            for traffic in traffic_folders:
                traffic_path = os.path.join(run_path, traffic)
                traffic_files = sorted(glob.glob(os.path.join(traffic_path, "traffic_*.csv")))

                for file in traffic_files:
                    df = pd.read_csv(file)
                    df = df[:-2]
                    df['start'] = df['start_time'].astype(int)
                    df['sent_MB'] = df['transfer'].apply(convert_to_mb)
                    per_sec = df.groupby('start')['sent_MB'].sum().sort_index()
                    cumulative = per_sec.cumsum()
                    filled = cumulative.reindex(range(cumulative.index.max() + 1), method='ffill').fillna(0)
                    filled.loc[0] = 0.0
                    filled = filled.sort_index()

                    all_cdfs.append(filled)
                    key = (traffic, config_name)
                    all_durations.setdefault(key, []).append(filled.index[-1])

        max_len = max(c.index.max() for c in all_cdfs)
        aligned = [c.reindex(range(max_len + 1), method='ffill').fillna(0) for c in all_cdfs]
        df_matrix = pd.DataFrame(aligned)
        mean_cdf = df_matrix.mean()
        percent_cdf = (mean_cdf / total_data_mb) * 100
        percent_cdf = percent_cdf.clip(upper=100)
        first_full_index = percent_cdf[percent_cdf >= 100].index.min()
        percent_cdf = percent_cdf.loc[:first_full_index]

        all_config_cdfs[config_name] = percent_cdf

        for (traffic, config), durations in all_durations.items():
            all_flow_durations.append({
                'traffic': traffic,
                'config': config,
                'avg_duration': np.mean(durations),
                'std_duration': np.std(durations)
            })

    # Combined CDF plot
    plt.figure(figsize=(10, 6))
    for config, cdf in all_config_cdfs.items():
        plt.plot(cdf.index, cdf.values, label=config)
    plt.xlabel("Time (s)")
    plt.ylabel("% Completion")
    plt.title("Combined Average CDF per Config")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(os.path.join(results_folder, "all_configs_combined_cdf.png"))
    plt.close()

    # Grouped bar plot
    df_dur = pd.DataFrame(all_flow_durations)
    traffic_labels = sorted(df_dur['traffic'].unique(), key=lambda x: int(x.replace('Traffic', '')))
    config_list = list(CONFIGS.keys())
    color_map = {cfg: clr for cfg, clr in zip(config_list, plt.cm.tab10.colors)}

    bar_width = 0.12
    x_positions = []
    labels = []
    colors = []
    heights = []
    errors = []
    xtick_pos = []
    xtick_labels = []
    base = 0

    for traffic in traffic_labels:
        subset = df_dur[df_dur['traffic'] == traffic]
        for i, cfg in enumerate(config_list):
            row = subset[subset['config'] == cfg]
            if not row.empty:
                x = base + i * bar_width
                x_positions.append(x)
                heights.append(row['avg_duration'].values[0])
                errors.append(row['std_duration'].values[0])
                colors.append(color_map[cfg])
        xtick_pos.append(base + (len(subset) - 1) * bar_width / 2)
        xtick_labels.append(traffic)
        base += (len(config_list) + 1) * bar_width * 1.5

    plt.figure(figsize=(14, 6))
    plt.bar(x_positions, heights, width=bar_width, color=colors, yerr=errors, capsize=5)
    plt.xticks(xtick_pos, xtick_labels)
    plt.ylabel("Avg Iteration Duration (s)")
    plt.title("Grouped Iteration Durations by Traffic (Config Colored)")
    handles = [plt.Rectangle((0, 0), 1, 1, color=color_map[cfg]) for cfg in config_list]
    plt.legend(handles, config_list, title="Config")
    plt.tight_layout()
    plt.savefig(os.path.join(results_folder, "all_flows_duration_grouped.png"))
    plt.close()

if __name__ == "__main__":
    folders = [("/home/spurohi2/Desktop/Advaced_PCN/pcn_src/Results/10 MB", 10),
               ("/home/spurohi2/Desktop/Advaced_PCN/pcn_src/Results/20 MB", 20),
               ("/home/spurohi2/Desktop/Advaced_PCN/pcn_adv_src/Results/10 MB", 10),
               ("/home/spurohi2/Desktop/Advaced_PCN/pcn_adv_src/Results/20 MB", 20)]
               
    for folder, total_data_mb in folders:
        process_all_configs_combined(folder, total_data_mb)
        print(f"Processed folder: {folder}")