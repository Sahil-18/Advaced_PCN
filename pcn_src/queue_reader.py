import argparse
import os
import sys
from time import sleep, time

import grpc

sys.path.append(
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 '../../utils/'))
import p4runtime_lib.bmv2
import p4runtime_lib.helper
from p4runtime_lib.error_utils import printGrpcError
from p4runtime_lib.switch import ShutdownAllSwitchConnections

# Global file for saving the queue lengths differnt for each switch
s1_queue_file= 's1_queue_lengths.csv'
s2_queue_file= 's2_queue_lengths.csv'
start_time = 0

def readQueueLengths(helper, switch, port, file):
    """
    Read the queue length from switch register and save it to a file, read only one port
    read new time and calculate the time difference to save it in the file

    Output file format is: time, queue_length
    """
    queue_length = switch.ReadRegister(helper.get_register_id('queue_lengths'), index=port)
    queue_length = queue_length.register_entry[0].data
    queue_length = int.from_bytes(queue_length, byteorder='big')
    time_diff = time() - start_time
    file.write(f'{time_diff}, {queue_length}\n')
    print(f'Port {port} queue length: {queue_length}')



def main(p4info_file_path, bmv2_file_path):
    # Instantiate a P4Runtime helper from the p4info file
    helper = p4runtime_lib.helper.P4InfoHelper(p4info_file_path)
    
    try:
        # Create a switch connection object
        s1 = p4runtime_lib.bmv2.Bmv2SwitchConnection(
            name='s1',
            address='',
            device_id=0,
            proto_dump_file='logs/s1-p4runtime-requests.txt')
        
        s2 = p4runtime_lib.bmv2.Bmv2SwitchConnection(
            name='s2',
            address='',
            device_id=1,
            proto_dump_file='logs/s2-p4runtime-requests.txt')
        
        s1.MasterArbitrationUpdate()
        s2.MasterArbitrationUpdate()

        # Install P4 program on the switches
        s1.SetForwardingPipelineConfig(p4info=p4info_file_path, bmv2_json_file_path=bmv2_file_path)
        s2.SetForwardingPipelineConfig(p4info=p4info_file_path, bmv2_json_file_path=bmv2_file_path)

        # Open both file for writing
        s1_queue_file = open(s1_queue_file, 'w')
        s2_queue_file = open(s2_queue_file, 'w')

        start_time = time.time()

        # Read the queue length from the switches every 0.5 seconds
        while True:
            sleep(0.5)
            print('\n---Reading queue lengths---')
            readQueueLengths(helper, s1, port=1, file=s1_queue_file)
            readQueueLengths(helper, s2, port=1, file=s2_queue_file)

    except KeyboardInterrupt:
        print(" Shutting down.")
    except grpc.RpcError as e:
        printGrpcError(e)

    ShutdownAllSwitchConnections()



if __name__== '__main__':
    parser = argparse.ArgumentParser(description='P4Runtime Queue Reader')
    parser.add_argument('--grpc-addr', help='P4Runtime gRPC server address',
                        type=str, action="store", required=True)
    parser.add_argument('--bmv2-json', help='BMv2 JSON file',
                        type=str, action="store", required=True)
    args = parser.parse_args()

    if not os.path.exists(args.p4info):
        parser.print_help()
        print("\np4info file not found: %s\nHave you run 'make'?" % args.p4info)
        parser.exit(1)
    if not os.path.exists(args.bmv2_json):
        parser.print_help()
        print("\nBMv2 JSON file not found: %s\nHave you run 'make'?" % args.bmv2_json)
        parser.exit(1)
    main(args.p4info, args.bmv2_json)