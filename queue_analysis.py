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

def evaluate_queue_behavior(parent_folder):
    results_folder = os.path.join(parent_folder, "Results", "Queue_Analysis")
    os.makedirs(results_folder, exist_ok=True)
    summary_rows = []

    for config_name, runs in CONFIGS.items():
        combined_queues = []
        for run in runs:
            run_path = os.path.join(parent_folder, run)
            queue_path = os.path.join(run_path, "s2_queue_lengths.csv")
            if not os.path.exists(queue_path):
                continue

            df_queue = pd.read_csv(queue_path)
            df_queue.columns = df_queue.columns.str.strip()
            df_queue['Time (s)'] = pd.to_numeric(df_queue['Time (s)'], errors='coerce')
            df_queue['Queue Length'] = pd.to_numeric(df_queue['Queue Length'], errors='coerce')

            # Get reference experiment start time from threshold
            thresh_path = os.path.join(run_path, "s2_threshold.csv")
            df_thresh = pd.read_csv(thresh_path)
            df_thresh.columns = df_thresh.columns.str.strip()
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

            if not traffic_times:
                continue

            pcn_start_time = min(start for start, _ in traffic_times)
            pcn_end_time = max(end for _, end in traffic_times)

            df_active = df_queue[(df_queue['Time (s)'] >= pcn_start_time) & (df_queue['Time (s)'] <= pcn_end_time)]
            df_active_nonzero = df_active[df_active['Queue Length'] > 0]
            if not df_active.empty:
                start_queue = df_active_nonzero.iloc[0]['Queue Length'] if not df_active_nonzero.empty else np.nan
                max_queue = np.percentile(df_active_nonzero['Queue Length'], 99) if not df_active_nonzero.empty else np.nan
                avg_queue = df_active_nonzero['Queue Length'].mean() if not df_active_nonzero.empty else np.nan
                combined_queues.append((start_queue, max_queue, avg_queue))

        if combined_queues:
            start_queues, max_queues, avg_queues = zip(*combined_queues)
            summary_rows.append({
                'config': config_name,
                'start_queue_length': np.nanmean(start_queues),
                'max_queue_length': np.nanmean(max_queues),
                'avg_queue_length': np.nanmean(avg_queues)
            })

    df_summary = pd.DataFrame(summary_rows)
    df_summary.to_csv(os.path.join(results_folder, "queue_evaluation_summary.csv"), index=False)


if __name__ == "__main__":
    folders = [("/home/spurohi2/Desktop/Advaced_PCN/pcn_src/Results/10 MB", 10),
               ("/home/spurohi2/Desktop/Advaced_PCN/pcn_src/Results/20 MB", 20),
               ("/home/spurohi2/Desktop/Advaced_PCN/pcn_adv_src/Results/10 MB", 10),
               ("/home/spurohi2/Desktop/Advaced_PCN/pcn_adv_src/Results/20 MB", 20)]
               
    for folder, total_data_mb in folders:
        evaluate_queue_behavior(folder)
        print(f"Processed folder: {folder}")