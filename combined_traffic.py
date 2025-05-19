import os
import re
import glob
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from collections import defaultdict

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

def analyze_all_configs_traffic_bandwidth(parent_folder):
    results_folder = os.path.join(parent_folder, "Results", "Traffic_Analysis")
    os.makedirs(results_folder, exist_ok=True)

    all_results = []

    for config_name, runs in CONFIGS.items():
        traffic_device_data = defaultdict(list)

        for folder_name in runs:
            folder_path = os.path.join(parent_folder, folder_name)
            traffic_folders = sorted([f for f in os.listdir(folder_path) if f.startswith("Traffic")])

            for traffic in traffic_folders:
                traffic_path = os.path.join(folder_path, traffic)
                traffic_files = sorted(glob.glob(os.path.join(traffic_path, "traffic_*.csv")))
                all_bw = []
                for file in traffic_files:
                    df = pd.read_csv(file)
                    df = df[:-2]
                    df['sent_MB'] = df['transfer'].apply(convert_to_mb)
                    bw_vals = df['sent_MB'].values * 8  # MBps to Mbps
                    all_bw.extend(bw_vals)
                if all_bw:
                    traffic_device_data[traffic].append(all_bw)

        for device, bw_lists in traffic_device_data.items():
            all_values = [v for sublist in bw_lists for v in sublist]
            avg_bw = np.mean(all_values)
            var_bw = np.var(all_values)
            all_results.append({
                'traffic_device': device,
                'config': config_name,
                'avg_bandwidth_Mbps': avg_bw,
                'std_bandwidth_Mbps': np.sqrt(var_bw)
            })

    df_all = pd.DataFrame(all_results)
    df_all.to_csv(os.path.join(results_folder, "combined_traffic_bandwidth.csv"), index=False)

    # Plot grouped bar chart
    traffic_labels = sorted(df_all['traffic_device'].unique(), key=lambda x: int(x.replace('Traffic', '')))
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
        subset = df_all[df_all['traffic_device'] == traffic]
        for i, cfg in enumerate(config_list):
            row = subset[subset['config'] == cfg]
            if not row.empty:
                x = base + i * bar_width
                x_positions.append(x)
                heights.append(row['avg_bandwidth_Mbps'].values[0])
                errors.append(row['std_bandwidth_Mbps'].values[0])
                colors.append(color_map[cfg])
        xtick_pos.append(base + (len(subset) - 1) * bar_width / 2)
        xtick_labels.append(traffic)
        base += (len(config_list) + 1) * bar_width * 1.5

    plt.figure(figsize=(14, 6))
    plt.bar(x_positions, heights, width=bar_width, color=colors, yerr=errors, capsize=5)
    plt.xticks(xtick_pos, xtick_labels)
    plt.ylabel("Avg Bandwidth (Mbps)")
    plt.title("Grouped Bandwidth Usage by Traffic Device (Config Colored)")
    handles = [plt.Rectangle((0, 0), 1, 1, color=color_map[cfg]) for cfg in config_list]
    plt.legend(handles, config_list, title="Config")
    plt.tight_layout()
    plt.savefig(os.path.join(results_folder, "all_traffic_bandwidth_grouped.png"))
    plt.close()

if __name__ == "__main__":
    folders = [("/home/spurohi2/Desktop/Advaced_PCN/pcn_src/Results/10 MB", 10),
               ("/home/spurohi2/Desktop/Advaced_PCN/pcn_src/Results/20 MB", 20),
               ("/home/spurohi2/Desktop/Advaced_PCN/pcn_adv_src/Results/10 MB", 10),
               ("/home/spurohi2/Desktop/Advaced_PCN/pcn_adv_src/Results/20 MB", 20)]
               
    for folder, total_data_mb in folders:
        analyze_all_configs_traffic_bandwidth(folder)
        print(f"Processed folder: {folder}")