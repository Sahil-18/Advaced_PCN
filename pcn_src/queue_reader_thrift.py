import argparse
import os
import sys
from time import sleep, time
from thrift.transport import TTransport, TSocket
from thrift.protocol import TBinaryProtocol

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gen-py'))
from bm_runtime import Standard
from bm_runtime.ttypes import *

s1_queue_file= 's1_queue_lengths.csv'
s2_queue_file= 's2_queue_lengths.csv'
start_time = 0

def readQueueLengths(switch, port, file):
    try:
        register_name = "queue_length"
        register_value = switch.bm_read_register(0, register_name, port)
        time_diff = time() - start_time

        file.write(f'{time_diff}, {register_value}\n')
        print(f'Port {port} queue length: {register_value}')

    except Exception as e:
        print(f"Error reading queue length for port {port}: {e}")


def create_thrift_connection(host, port):
    """
    Create a Thrift connection to the switch.
    """
    transport = TSocket.TSocket(host, port)
    transport = TTransport.TBufferedTransport(transport)
    protocol = TBinaryProtocol.TBinaryProtocol(transport)
    client = Standard.Client(protocol)
    
    transport.open()
    return client, transport


def main(thrift_port_s1, thrift_port_s2):
    global start_time
    try:
    # Create Thrift connections to the switches
        s1, transport_s1 = create_thrift_connection('localhost', thrift_port_s1)
        s2, transport_s2 = create_thrift_connection('localhost', thrift_port_s2)

        # Open files for writing queue lengths
        with open(s1_queue_file, 'w') as s1_file, open(s2_queue_file, 'w') as s2_file:
            start_time = time()
            while True:
                readQueueLengths(s1, 1, s1_file)  # Read queue length for port 1 on switch s1
                readQueueLengths(s2, 2, s2_file)  # Read queue length for port 2 on switch s2
                sleep(0.5)  # Sleep for a second before reading again

        # Close the Thrift connections
        transport_s1.close()
        transport_s2.close()
    except KeyboardInterrupt:
        print("Interrupted by user. Exiting...")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main(thrift_port_s1=9090, thrift_port_s2=9091)
