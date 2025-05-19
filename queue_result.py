import os
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

CONFIGS = {
    "NON_PCN": ["NON_PCN_RUN_1", "NON_PCN_RUN_2"],
    "PCN": ["PCN_RUN_1", "PCN_RUN_2"],
    "PCN_MIN": ["PCN_RUN_1_MIN", "PCN_RUN_2_MIN"],
    "PCN_FIN_MIN": ["PCN_FIN_RUN_1_MIN", "PCN_FIN_RUN_2_MIN"],
    "PCN_HARMONIC": ["PCN_RUN_1_HARMONIC", "PCN_RUN_2_HARMONIC"],
    "PCN_FIN_HARMONIC": ["PCN_FIN_RUN_1_HARMONIC", "PCN_FIN_RUN_2_HARMONIC"]
}

def analyze_queue_vs_threshold(experiment_path, output_folder, tag):
    queue_path = os.path.join(experiment_path, "s2_queue_lengths.csv")
    threshold_path = os.path.join(experiment_path, "s2_threshold.csv")

    df_queue = pd.read_csv(queue_path)
    df_threshold = pd.read_csv(threshold_path)
    df_threshold.columns = df_threshold.columns.str.strip()
    df_threshold['Threshold'] = df_threshold['Threshold'].replace(0, 40)

    df_queue.columns = df_queue.columns.str.strip()
    df_threshold.columns = df_threshold.columns.str.strip()

    start_seconds = df_threshold['Time (s)'].iloc[0]

    df_queue['Time from start'] = df_queue['Time (s)'] - start_seconds
    df_threshold['Time from start'] = df_threshold['Time (s)'] - start_seconds

    queue_time = df_queue['Time from start']
    threshold_interp = np.interp(queue_time, df_threshold['Time from start'], df_threshold['Threshold'].replace(0, 40))
    df_queue['Threshold'] = threshold_interp

    os.makedirs(output_folder, exist_ok=True)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 6), sharex=True)
    ax1.plot(df_queue['Time from start'], df_queue['Queue Length'], label='Queue Length', color='blue')
    ax1.set_ylabel("Queue Length")
    ax1.set_title("Queue Length over Time")

    ax2.plot(df_threshold['Time from start'], df_threshold['Threshold'], label='Threshold', color='red')
    ax2.set_ylabel("Threshold")
    ax2.set_xlabel("Time (s)")
    ax2.set_title("Threshold over Time")

    plt.tight_layout()
    plt.savefig(os.path.join(output_folder, f"{tag}_queue_threshold_timeline.png"))
    plt.close()


def process_all_configs_queue(parent_folder):
    results_folder = os.path.join(parent_folder, "Results", "Queue_Analysis")
    os.makedirs(results_folder, exist_ok=True)
    for config_name, runs in CONFIGS.items():
        for i, run in enumerate(runs):
            run_path = os.path.join(parent_folder, run)
            run_tag = f"{config_name}_RUN_{i+1}"
            analyze_queue_vs_threshold(run_path, results_folder, run_tag)

if __name__ == "__main__":
    folders = [("/home/spurohi2/Desktop/Advaced_PCN/pcn_src/Results/10 MB", 10),
               ("/home/spurohi2/Desktop/Advaced_PCN/pcn_src/Results/20 MB", 20),
               ("/home/spurohi2/Desktop/Advaced_PCN/pcn_adv_src/Results/10 MB", 10),
               ("/home/spurohi2/Desktop/Advaced_PCN/pcn_adv_src/Results/20 MB", 20)]
               
    for folder, total_data_mb in folders:
        process_all_configs_queue(folder)
        print(f"Processed folder: {folder}")