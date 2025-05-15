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

def save_and_plot_graphs(df_per_flow, df_device, folder, tag):
    df_per_flow.to_csv(os.path.join(folder, f"{tag}_per_flow_bandwidth.csv"), index=False)
    df_device.to_csv(os.path.join(folder, f"{tag}_per_device_bandwidth.csv"), index=False)

    plt.figure(figsize=(12, 4))
    bars = plt.bar(df_per_flow['flow'], df_per_flow['avg_bw_during'], color='skyblue', width=0.5)
    if len(df_per_flow) > 40:
        plt.xticks([])
    else:
        plt.xticks(rotation=45)
    plt.ylabel("Avg Bandwidth During PCN (Mbps)")
    plt.title(f"Per-Flow Background Bandwidth - {tag}")
    plt.tight_layout()
    plt.savefig(os.path.join(folder, f"{tag}_per_flow_bandwidth.png"))
    plt.close()

    plt.figure(figsize=(8, 4))
    plt.bar(df_device['device'], df_device['avg_bw_during'], color='orange', width=0.4)
    plt.xticks(rotation=45)
    plt.ylabel("Avg Bandwidth During PCN (Mbps)")
    plt.title(f"Per-Device Background Bandwidth - {tag}")
    plt.tight_layout()
    plt.savefig(os.path.join(folder, f"{tag}_per_device_bandwidth.png"))
    plt.close()

def generate_bandwidth_data_from_experiment(folder_path, config_name):
    flat_windows = []
    all_flows = []
    experiment_start_time = None

    main_folder = folder_path
    bg_folder = os.path.join(main_folder, "Background")
    threshold_path = os.path.join(main_folder, "s2_threshold.csv")

    df_thresh = pd.read_csv(threshold_path)
    df_thresh.columns = df_thresh.columns.str.strip()
    df_thresh['Time (in HH:MM:SS)'] = pd.to_datetime(df_thresh['Time (in HH:MM:SS)'])
    experiment_start_time = df_thresh['Time (in HH:MM:SS)'].min()

    traffic_folders = sorted([f for f in os.listdir(main_folder) if f.startswith("Traffic")])
    for traffic in traffic_folders:
        summary_path = os.path.join(main_folder, traffic, "summary.csv")
        if not os.path.exists(summary_path):
            continue
        df_summary = pd.read_csv(summary_path)
        df_summary['start_time'] = pd.to_datetime(df_summary['start_time']).dt.time
        df_summary['end_time'] = pd.to_datetime(df_summary['end_time']).dt.time
        for _, row in df_summary.iterrows():
            start = pd.Timestamp.combine(experiment_start_time.date(), row['start_time'])
            end = pd.Timestamp.combine(experiment_start_time.date(), row['end_time'])
            rel_start = max((start - experiment_start_time).total_seconds(), 0)
            rel_end = max((end - experiment_start_time).total_seconds(), 0)
            flat_windows.append((rel_start, rel_end))

    bg_files = sorted(glob.glob(os.path.join(bg_folder, "*.csv")))
    for file in bg_files:
        df = pd.read_csv(file)
        df = df[:-8]
        for _, row in df.iterrows():
            flow_data = {
                'Interval': row['Interval'],
                'Bitrate': row['Bitrate'],
                'ID': row['ID'],
                'device': os.path.splitext(os.path.basename(file))[0]
            }
            all_flows.append(flow_data)

    return flat_windows, all_flows


def analyze_individual_and_combined(config_name, folders, parent_folder, output_folder):
    all_flat_windows = []
    all_flows = []
    run_results = []

    bg_result_folder = os.path.join(output_folder, "Background_Analysis")
    os.makedirs(bg_result_folder, exist_ok=True)

    for i, folder_name in enumerate(folders):
        run_tag = f"{config_name}_RUN_{i+1}"
        folder_path = os.path.join(parent_folder, folder_name)
        flat_windows, flows = generate_bandwidth_data_from_experiment(folder_path, config_name)
        all_flat_windows.extend(flat_windows)
        all_flows.extend(flows)
        run_results.append((flat_windows, flows))

        global_start = min(start for start, _ in flat_windows)
        global_end = max(end for _, end in flat_windows)

        df_per_flow, df_device = compute_bandwidth_statistics(flows, global_start, global_end)
        save_and_plot_graphs(df_per_flow, df_device, bg_result_folder, run_tag)

    # Combined analysis
    global_start = min(start for start, _ in all_flat_windows)
    global_end = max(end for _, end in all_flat_windows)

    df_per_flow, df_device = compute_bandwidth_statistics(all_flows, global_start, global_end)
    save_and_plot_graphs(df_per_flow, df_device, bg_result_folder, config_name)

def compute_bandwidth_statistics(all_flows, global_start, global_end):
    flow_stats = defaultdict(list)
    device_stats = defaultdict(list)
    flow_id_map = {}
    flow_counter = 1

    for row in all_flows:
        interval = row['Interval']
        id_ = int(row['ID'])
        device = row['device']
        bw = parse_bitrate_to_mbps(row['Bitrate'])
        start_sec = int(float(interval.split('-')[0]))
        flow_key = f"{device}_id{id_}"
        label = flow_id_map.setdefault(flow_key, f"flow{flow_counter}")
        if label == f"flow{flow_counter}":
            flow_counter += 1

        timing = 'before' if start_sec < global_start else 'during' if start_sec < global_end else 'after'
        flow_stats[label].append((timing, bw))
        device_stats[device].append((timing, bw))

    df_per_flow = pd.DataFrame([
        {
            'flow': label,
            'avg_bw_before': np.mean([bw for t, bw in entries if t == 'before']) if entries else 0,
            'avg_bw_during': np.mean([bw for t, bw in entries if t == 'during']) if entries else 0,
            'avg_bw_after': np.mean([bw for t, bw in entries if t == 'after']) if entries else 0
        }
        for label, entries in flow_stats.items()
    ])

    df_device = pd.DataFrame([
        {
            'device': dev,
            'avg_bw_before': np.mean([bw for t, bw in entries if t == 'before']) if entries else 0,
            'avg_bw_during': np.mean([bw for t, bw in entries if t == 'during']) if entries else 0,
            'avg_bw_after': np.mean([bw for t, bw in entries if t == 'after']) if entries else 0
        }
        for dev, entries in device_stats.items()
    ])

    df_device.loc[len(df_device.index)] = {
        'device': 'ALL_DEVICES',
        'avg_bw_before': df_device['avg_bw_before'].mean(),
        'avg_bw_during': df_device['avg_bw_during'].mean(),
        'avg_bw_after': df_device['avg_bw_after'].mean()
    }

    return df_per_flow, df_device

def process_all_configs_background(parent_folder):
    results_folder = os.path.join(parent_folder, "Results")
    os.makedirs(results_folder, exist_ok=True)
    for config_name, runs in CONFIGS.items():
        analyze_individual_and_combined(config_name, runs, parent_folder, results_folder)

if __name__ == "__main__":
    folders = [("/home/spurohi2/Desktop/Advaced_PCN/pcn_src/Results/10 MB/Big Exp", 10),
               ("/home/spurohi2/Desktop/Advaced_PCN/pcn_src/Results/20 MB/Big Exp", 20),
               ("/home/spurohi2/Desktop/Advaced_PCN/pcn_adv_src/Results/10 MB", 10),
               ("/home/spurohi2/Desktop/Advaced_PCN/pcn_adv_src/Results/20 MB", 20)]
               
    for folder, total_data_mb in folders:
        process_all_configs_background(folder)
        print(f"Processed folder: {folder}")