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

def parse_bitrate_to_mbps(bw_str):
    match = re.match(r"([\d\.]+)\s*([KMG])bits/sec", bw_str.strip())
    if not match:
        return 0.0
    val, unit = float(match.group(1)), match.group(2)
    if unit == 'K': return val / 1000
    elif unit == 'M': return val
    elif unit == 'G': return val * 1000
    return val

def analyze_all_configs_background_bandwidth(parent_folder):
    results_folder = os.path.join(parent_folder, "Results", "Background_Analysis")
    os.makedirs(results_folder, exist_ok=True)

    all_device_results = []
    per_device_time_series = defaultdict(list)

    for config_name, runs in CONFIGS.items():
        for run in runs:
            run_path = os.path.join(parent_folder, run)
            bg_path = os.path.join(run_path, "Background")
            bg_files = sorted(glob.glob(os.path.join(bg_path, "*.csv")))

            device_bw = defaultdict(list)
            for file in bg_files:
                df = pd.read_csv(file)
                df = df[:-8]
                filename = os.path.splitext(os.path.basename(file))[0]
                for _, row in df.iterrows():
                    bw = parse_bitrate_to_mbps(row['Bitrate'])
                    device_bw[filename].append(bw)

                    interval = row['Interval']
                    start_sec = int(float(interval.split('-')[0]))
                    per_device_time_series[(filename, run)].append((start_sec, bw))

            for dev, vals in device_bw.items():
                all_device_results.append({
                    'device': dev,
                    'config': config_name,
                    'avg_bw_mbps': np.mean(vals),
                    'std_bw_mbps': np.std(vals)
                })

    df_all = pd.DataFrame(all_device_results)
    df_all.to_csv(os.path.join(results_folder, "combined_device_bandwidth.csv"), index=False)

    devices = sorted(df_all['device'].unique())
    config_list = list(CONFIGS.keys())
    color_map = {cfg: clr for cfg, clr in zip(config_list, plt.cm.tab10.colors)}

    bar_width = 0.12
    x_positions = []
    colors = []
    heights = []
    errors = []
    xtick_pos = []
    xtick_labels = []
    base = 0

    for device in devices:
        subset = df_all[df_all['device'] == device]
        for i, cfg in enumerate(config_list):
            row = subset[subset['config'] == cfg]
            if not row.empty:
                x = base + i * bar_width
                x_positions.append(x)
                heights.append(row['avg_bw_mbps'].values[0])
                errors.append(row['std_bw_mbps'].values[0])
                colors.append(color_map[cfg])
        xtick_pos.append(base + (len(subset) - 1) * bar_width / 2)
        xtick_labels.append(device)
        base += (len(config_list) + 1) * bar_width * 1.5

    plt.figure(figsize=(14, 6))
    plt.bar(x_positions, heights, width=bar_width, color=colors, yerr=errors, capsize=5)
    plt.xticks(xtick_pos, xtick_labels)
    plt.ylabel("Avg Background Bandwidth (Mbps)")
    plt.title("Grouped Background Bandwidth by Device (Config Colored)")
    handles = [plt.Rectangle((0, 0), 1, 1, color=color_map[cfg]) for cfg in config_list]
    plt.legend(handles, config_list, title="Config")
    plt.tight_layout()
    plt.savefig(os.path.join(results_folder, "all_background_device_bandwidth_grouped.png"))
    plt.close()

    for run_tag in [r for run_list in CONFIGS.values() for r in run_list]:
        run_path = os.path.join(parent_folder, run_tag)
        threshold_path = os.path.join(run_path, "s2_threshold.csv")
        if not os.path.exists(threshold_path):
            continue

        df_thresh = pd.read_csv(threshold_path)
        df_thresh.columns = df_thresh.columns.str.strip()
        df_thresh['Threshold'] = df_thresh['Threshold'].replace(0, 40)
        df_thresh['Time from start'] = df_thresh['Time (s)'] - df_thresh['Time (s)'].iloc[0]

        df_thresh['Time (in HH:MM:SS)'] = pd.to_datetime(df_thresh['Time (in HH:MM:SS)'])
        experiment_start_time = df_thresh['Time (in HH:MM:SS)'].min()
        traffic_times = []
        for tf in sorted(os.listdir(run_path)):
            if tf.startswith("Traffic"):
                sfile = os.path.join(run_path, tf, "summary.csv")
                if os.path.exists(sfile):
                    df = pd.read_csv(sfile)
                    df['start'] = pd.to_datetime(df['start_time'])
                    df['end'] = pd.to_datetime(df['end_time'])
                    for _, row in df.iterrows():
                        start = pd.Timestamp.combine(experiment_start_time.date(), row['start'].time())
                        rel_start = max((start - experiment_start_time).total_seconds(), 0)
                        end = pd.Timestamp.combine(experiment_start_time.date(), row['end'].time())
                        rel_end = max((end - experiment_start_time).total_seconds(), 0)
                        traffic_times.append((rel_start, rel_end))

        start_line = min([x[0] for x in traffic_times]) if traffic_times else None
        end_line = max([x[1] for x in traffic_times]) if traffic_times else None

        plt.figure(figsize=(12, 6))
        ax1 = plt.subplot(2, 1, 1)
        for (device, cfg), series in per_device_time_series.items():
            if cfg == run_tag:
                times, values = zip(*sorted(series))
                ax1.plot(times, values, linewidth=0.6, label=device)
        if start_line is not None:
            ax1.axvline(x=start_line, color='black', linestyle='--', label='Traffic Start')
        if end_line is not None:
            ax1.axvline(x=end_line, color='black', linestyle='--', label='Traffic End')
        ax1.set_ylabel("Bandwidth (Mbps)")
        ax1.set_ylim(0, 15)
        ax1.set_yticks(np.arange(0, 16, 3))
        ax1.set_title(f"Background Bandwidth Timeline - {run_tag}")
        ax1.legend(loc='upper right', fontsize=6)

        ax2 = plt.subplot(2, 1, 2, sharex=ax1)
        ax2.plot(df_thresh['Time from start'], df_thresh['Threshold'], color='red', linewidth=0.8)
        ax2.set_ylabel("Threshold")
        ax2.set_xlabel("Time (s)")
        ax2.set_title("Threshold Timeline")

        plt.tight_layout()
        plt.savefig(os.path.join(results_folder, f"{run_tag}_bw_threshold_timeline.png"))
        plt.close()


if __name__ == "__main__":
    folders = [("/home/spurohi2/Desktop/Advaced_PCN/pcn_src/Results/10 MB", 10),
               ("/home/spurohi2/Desktop/Advaced_PCN/pcn_src/Results/20 MB", 20),
               ("/home/spurohi2/Desktop/Advaced_PCN/pcn_adv_src/Results/10 MB", 10),
               ("/home/spurohi2/Desktop/Advaced_PCN/pcn_adv_src/Results/20 MB", 20)]
               
    for folder, total_data_mb in folders:
        analyze_all_configs_background_bandwidth(folder)
        print(f"Processed folder: {folder}")