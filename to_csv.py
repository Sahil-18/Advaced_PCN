import os
import re
import pandas as pd

# ---- Parsing functions ---- #

def parse_parallel_iperf(file_path):
    results = []
    with open(file_path, 'r') as f:
        lines = f.readlines()

    pattern = re.compile(
        r"\[\s*(\d+)\]\s+(\d+\.\d+)-(\d+\.\d+)\s+sec\s+([\d\.]+\s+\w+Bytes)\s+([\d\.]+\s+Mbits/sec)(?:\s+(\d+))?(?:\s+([\d\.]+\s+\w+Bytes))?"
    )

    for line in lines:
        match = pattern.search(line)
        if match:
            conn_id = int(match.group(1))
            interval = f"{match.group(2)}-{match.group(3)}"
            results.append({
                'ID': conn_id,
                'Interval': interval,
                'Transfer': match.group(4),
                'Bitrate': match.group(5),
                'Retr': match.group(6) if match.group(6) else "",
                'Cwnd': match.group(7) if match.group(7) else ""
            })

    return pd.DataFrame(results)

def parse_single_iperf(file_path):
    results = []
    pattern = re.compile(
        r'\[\s*\d+\]\s+(\d+\.\d+)-(\d+\.\d+)\s+sec\s+([\d\.]+\s+\w+Bytes)\s+([\d\.]+\s+\w+/sec)'
    )

    with open(file_path, 'r') as f:
        for line in f:
            match = pattern.search(line)
            if match:
                results.append({
                    "start_time": float(match.group(1)),
                    "end_time": float(match.group(2)),
                    "transfer": match.group(3),
                    "bandwidth": match.group(4)
                })

    return pd.DataFrame(results)

# ---- Folder walker ---- #

def convert_all_iperf_in_folder(root_folder):
    for exp_folder in os.listdir(root_folder):
        exp_path = os.path.join(root_folder, exp_folder)
        print(f"\nProcessing folder: {exp_path}\n")
        if not os.path.isdir(exp_path):
            continue

        # Background folder
        bg_path = os.path.join(exp_path, "Background")
        if os.path.isdir(bg_path):
            for file in os.listdir(bg_path):
                if file.endswith(".txt"):
                    txt_path = os.path.join(bg_path, file)
                    csv_path = txt_path.replace(".txt", ".csv")
                    df = parse_parallel_iperf(txt_path)
                    df.to_csv(csv_path, index=False)
                    print(f"Parsed (parallel): {csv_path}")

        # Traffic folders
        for item in os.listdir(exp_path):
            traffic_path = os.path.join(exp_path, item)
            if os.path.isdir(traffic_path) and item.startswith("Traffic"):
                for file in os.listdir(traffic_path):
                    if file.endswith(".txt") and file.startswith("traffic_"):
                        txt_path = os.path.join(traffic_path, file)
                        csv_path = txt_path.replace(".txt", ".csv")
                        df = parse_single_iperf(txt_path)
                        df.to_csv(csv_path, index=False)
                        print(f"Parsed (single): {csv_path}")

if __name__ == "__main__":
    folders = ["/home/spurohi2/Desktop/Advaced_PCN/pcn_src/Results/10 MB",
               "/home/spurohi2/Desktop/Advaced_PCN/pcn_src/Results/20 MB",
               "/home/spurohi2/Desktop/Advaced_PCN/pcn_adv_src/Results/10 MB",
               "/home/spurohi2/Desktop/Advaced_PCN/pcn_adv_src/Results/20 MB"]
    for folder in folders:
        print(f"Converting files in folder: {folder}")
        convert_all_iperf_in_folder(folder)
        print(f"Finished converting files in folder: {folder}")
    print("All files converted successfully.")