import argparse
import os
import sys
from time import sleep, time
from thrift.transport import TTransport, TSocket
from thrift.protocol import TBinaryProtocol
from thrift.protocol.TMultiplexedProtocol import TMultiplexedProtocol
from datetime import datetime

from bm_runtime.standard import Standard
from bm_runtime.standard.ttypes import *

s1_queue_file= 's1_queue_lengths.csv'
s2_queue_file= 's2_queue_lengths.csv'
start_time = 0

def readQueueLengths(switch, port, file):
    try:
        register_name = "queue_len"
        register_value = switch.bm_register_read(0, register_name, port)
        time_diff = time() - start_time
        time_str = datetime.now().strftime('%H:%M:%S')

        file.write(f'{time_str}, {time_diff}, {register_value}\n')
        print(f"Port {port} Queue Length: {register_value}, Time: {time_str}, Time Diff: {time_diff:.2f}s")
        file.flush()  # Ensure the data is written to the file immediately

    except Exception as e:
        print(f"Error reading queue length for port {port}: {e}")


def create_thrift_connection(host, port):
    """
    Create a Thrift connection to the switch.
    """
    transport = TSocket.TSocket(host, port)
    transport = TTransport.TBufferedTransport(transport)
    protocol = TBinaryProtocol.TBinaryProtocol(transport)

    mux_protocol =TMultiplexedProtocol(protocol, "standard")
    client = Standard.Client(mux_protocol)
    
    transport.open()
    return client, transport


def main(thrift_port_s1, thrift_port_s2):
    global start_time
    try:
    # Create Thrift connections to the switches
        s1, transport_s1 = create_thrift_connection('localhost', thrift_port_s1)
        s2, transport_s2 = create_thrift_connection('localhost', thrift_port_s2)

        s1_file = open(s1_queue_file, 'w')
        s2_file = open(s2_queue_file, 'w')

        # Write header to the files
        # Header will be the absolute time in HH:MM:SS format
        # and the current time after start_time and queue length
        s1_file.write('Time (in HH:MM:SS) ,Time (s), Queue Length\n')
        s2_file.write('Time (in HH:MM:SS) ,Time (s), Queue Length\n')

        # Open files for writing queue lengths
        start_time = time()
        while True:
            readQueueLengths(s1, 1, s1_file)  # Read queue length for port 1 on switch s1
            readQueueLengths(s2, 1, s2_file)  # Read queue length for port 2 on switch s2
            sleep(0.5)  # Sleep for a second before reading again

    except KeyboardInterrupt:
        print("Interrupted by user. Exiting...")
        transport_s1.close()
        transport_s2.close()
        s1_file.close()
        s2_file.close()

if __name__ == "__main__":
    main(thrift_port_s1=9090, thrift_port_s2=9091)
