import subprocess
import csv
from pathlib import Path
import time
from datetime import datetime

# configuration
SERVER_IP = "10.0.0.9"
ITERATION = 5
SLEEP_DURATION = 5
DATA_SEND = "10M"
OUTPUT_DIR = Path("./Results/Traffic3")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
SUMMARY_FILE = OUTPUT_DIR / "summary.csv"

summary_data = [("iteration", "start_time", "end_time", "duration")]

for i in range(1, ITERATION + 1):
    log_file = OUTPUT_DIR / f"traffic_{i}.txt"
    start_time = datetime.now()
    print(f"Starting iteration {i} at {start_time}")

    try:
        result = subprocess.run(
            ["iperf3", "-c", SERVER_IP, "-n", DATA_SEND, "-i", "1"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        # save the output to a file
        with log_file.open("w") as f:
            f.write(result.stdout)

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        summary_data.append((
            i,
            start_time.isoformat(),
            end_time.isoformat(),
            round(duration, 2),
        ))

    except Exception as e:
        summary_data.append((
            i,
            start_time.isoformat(),
            None,
            None,
        ))
        print(f"Error during iteration {i}: {e}")

    print(f"Iteration {i} completed. Sleeping for {SLEEP_DURATION} seconds.")
    time.sleep(SLEEP_DURATION)

# Write summary data to CSV
with SUMMARY_FILE.open("w", newline="") as csvfile:
    writer = csv.writer(csvfile)
    writer.writerows(summary_data)

print("\n All iterations completed. Summary saved to summary.csv.")