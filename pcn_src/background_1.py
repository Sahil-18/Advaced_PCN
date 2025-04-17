import subprocess
from pathlib import Path


# Configuration
SERVER_IP = "10.0.0.5"
FLOW_COUNT = 4
DURATION = 100
INTERVAL = 0.5
OUTPUT_DIR = Path("./Results/Background")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


for i in range(1, FLOW_COUNT + 1):
    log_file = OUTPUT_DIR / f"flow1_{i}.txt"
    start_delay = (i - 1) * INTERVAL
    cmd = [
        "iperf3", 
        "-c", SERVER_IP,
        "-t", str(DURATION),
        "-i", "1",
        "--logfile", str(log_file),
    ]

    # Start the iperf3 server with a delay
    subprocess.Popen(["bash", "-c", f"sleep {start_delay} && {' '.join(cmd)}"])
