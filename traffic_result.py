import os
import re
import glob
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from collections import defaultdict

# Convert bitrate strings to Mbps
def parse_bitrate_to_mbps(bw_str):
    match = re.match(r"([\d\.]+)\s*([KMG])bits/sec", bw_str.strip())
    if not match:
        return 0.0
    val, unit = float(match.group(1)), match.group(2)
    if unit == 'K':
        return val / 1000
    elif unit == 'M':
        return val
    elif unit == 'G':
        return val * 1000
    return val

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

CONFIGS = {
    "NON_PCN": ["NON_PCN_RUN_1", "NON_PCN_RUN_2"],
    "PCN": ["PCN_RUN_1", "PCN_RUN_2"],
    "PCN_MIN": ["PCN_RUN_1_MIN", "PCN_RUN_2_MIN"],
    "PCN_FIN_MIN": ["PCN_FIN_RUN_1_MIN", "PCN_FIN_RUN_2_MIN"],
    "PCN_HARMONIC": ["PCN_RUN_1_HARMONIC", "PCN_RUN_2_HARMONIC"],
    "PCN_FIN_HARMONIC": ["PCN_FIN_RUN_1_HARMONIC", "PCN_FIN_RUN_2_HARMONIC"]
}

def analyze_traffic_bandwidth(config_name, folders, parent_folder, output_folder):
    traffic_result_folder = os.path.join(output_folder, "Traffic_Analysis")
    os.makedirs(traffic_result_folder, exist_ok=True)

    traffic_device_data = defaultdict(list)

    for folder_name in folders:
        folder_path = os.path.join(parent_folder, folder_name)
        traffic_folders = sorted([f for f in os.listdir(folder_path) if f.startswith("Traffic")])

        for traffic in traffic_folders:
            traffic_path = os.path.join(folder_path, traffic)
            traffic_files = sorted(glob.glob(os.path.join(traffic_path, "traffic_*.csv")))
            all_bw = []
            for file in traffic_files:
                df = pd.read_csv(file)
                df = df[:-2]  # remove summary lines
                df['sent_MB'] = df['transfer'].apply(convert_to_mb)
                bw_vals = df['sent_MB'].values * 8  # MBps to Mbps
                all_bw.extend(bw_vals)
            if all_bw:
                traffic_device_data[traffic].append(all_bw)

    # Flatten and calculate mean/var
    results = []
    for device, bw_lists in traffic_device_data.items():
        all_values = [v for sublist in bw_lists for v in sublist]
        results.append({
            'traffic_device': device,
            'avg_bandwidth_Mbps': np.mean(all_values),
            'var_bandwidth_Mbps': np.var(all_values)
        })

    df_traffic = pd.DataFrame(results)
    df_traffic.to_csv(os.path.join(traffic_result_folder, f"{config_name}_traffic_bandwidth.csv"), index=False)

    # Bar plot
    plt.figure(figsize=(8, 4))
    plt.bar(df_traffic['traffic_device'], df_traffic['avg_bandwidth_Mbps'],
            yerr=np.sqrt(df_traffic['var_bandwidth_Mbps']), capsize=5, color='purple', width=0.5)
    plt.xticks(rotation=45)
    plt.ylabel("Avg Bandwidth (Mbps)")
    plt.title(f"PCN Traffic Bandwidth per Device - {config_name}")
    plt.tight_layout()
    plt.savefig(os.path.join(traffic_result_folder, f"{config_name}_traffic_bandwidth.png"))
    plt.close()

def process_all_configs_traffic(parent_folder):
    results_folder = os.path.join(parent_folder, "Results")
    os.makedirs(results_folder, exist_ok=True)
    for config_name, runs in CONFIGS.items():
        analyze_traffic_bandwidth(config_name, runs, parent_folder, results_folder)

if __name__ == "__main__":
    folders = [("/home/spurohi2/Desktop/Advaced_PCN/pcn_src/Results/10 MB/Big Exp", 10),
               ("/home/spurohi2/Desktop/Advaced_PCN/pcn_src/Results/20 MB/Big Exp", 20),
               ("/home/spurohi2/Desktop/Advaced_PCN/pcn_adv_src/Results/10 MB", 10),
               ("/home/spurohi2/Desktop/Advaced_PCN/pcn_adv_src/Results/20 MB", 20)]
               
    for folder, total_data_mb in folders:
        process_all_configs_traffic(folder)
        print(f"Processed folder: {folder}")