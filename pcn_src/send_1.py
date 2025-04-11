from scapy.all import IP, TCP, Ether, sendp, get_if_hwaddr, sniff
from time import sleep, time
import random
import threading
from datetime import datetime

src_ip = '10.0.0.2'
dst_ip = '10.0.0.6'
src_port = random.randint(49152, 65535)
dst_port = 1234
iface = 'eth0'

cwnd_lock = threading.Lock()

class DCTCPControllerWithPCN:
    def __init__(self, file, iteration):
        self.alpha = 1.0
        self.cwnd = 10
        self.max_cwnd = 100
        self.min_cwnd = 2
        self.pcn_threshold = 10
        self.sent_packets = 0
        self.acked_packets = 0
        self.total = 250 * 1024
        self.wait = 0
        self.file = file
        self.iter = 0
        self.end_ack_thread = False

    def handle_ack_pkt(self, pkt):
        if pkt[IP].src == dst_ip and pkt[IP].dst == src_ip and pkt[TCP].dport == src_port and pkt[TCP].sport == dst_port:
            # Check if the packet has DCTCP ecn bits set for congestion notification
            # usually 
            if pkt[TCP].flags & 0x40:
                # if ecn bits are set, then reduce the cwnd
                cwnd_lock.acquire()
                self.cwnd = max(self.min_cwnd, self.cwnd * self.alpha/2)
                cwnd_lock.release()
            else:
                # if ecn bits are not set, then increase the cwnd
                cwnd_lock.acquire()
                self.cwnd = min(self.max_cwnd, self.cwnd + 1)
                cwnd_lock.release()
            self.acked_packets += 1
            print(f'ACK received for packet {self.acked_packets}, cwnd: {self.cwnd}, total: {self.total}')

    def handle_ack(self):
        while self.end_ack_thread == False:
            sniff(filter=f'tcp and port {src_port}', prn=self.handle_ack_pkt, timeout=2)

    def send_data_packets(self):
        # send packets with total data of 250 MB
        # Make use of TCP MTU of 1460 bytes
        # Also, the IP TOS field will be PCN with 11 in the first two bits and ecn with 01 in the last two bits
        # So, the TOS field will be 11000001 = 0xC1 = 193
        while self.total > 0:
            # check if cwnd is greater than zero
            cwnd_lock.acquire()
            if self.cwnd <= 0:
                cwnd_lock.release()
                continue
            cwnd_lock.release()
            # send a packet
            data_len = min(1460, self.total)
            self.total -= data_len
            pkt = Ether(src=get_if_hwaddr(iface), dst='ff:ff:ff:ff:ff:ff') / IP(src=src_ip, dst=dst_ip, tos=193) / TCP(sport=src_port, dport=dst_port) / ('A' * data_len)
            sendp(pkt, iface=iface)
            print(f'Sent packet with TOS: {pkt[IP].tos}, Data Length: {data_len}, Total: {self.total}')
            cwnd_lock.acquire()
            self.cwnd -= 1
            self.sent_packets += 1
            cwnd_lock.release()
            time_str = datetime.now().strftime('%H:%M:%S')
            self.file.write(f'{self.iter},{time_str},{self.sent_packets},PCN Start,{self.cwnd},{self.total},,,\n')
                
    
    def handle_pcn_ack(self, pkt):
        # check if the IP tos bit has 10 in the first two bits
        # if it does, then it is a PCN_ACK
        # also check if the tcp port as same as the one we sent the packet to
        return pkt[IP].tos >> 6 == 2 and pkt[IP].src == dst_ip and pkt[IP].dst == src_ip and pkt[TCP].dport == src_port and pkt[TCP].sport == dst_port
    
    def wait_for_pcn_ack(self):
        while True:
            print('Waiting for PCN_ACK...')
            pkt = sniff(filter=f'tcp and port {src_port}', count=1, timeout=2)
            if pkt and self.handle_pcn_ack(pkt[0]):
                print('Received PCN_ACK')
                break


    def send_pcn_start(self):
        # in IP header, TOS bits are used for PCN and ECN
        # First two bits are used for PCN, 01 for PCN Start
        # Next 4 bits are used for sharing the pcn_threshold value, it codes actual value/3 in bits i.e. if actual threshold is 21 then pcn_threshold will be 7
        # Last 2 bits are used for ECN
        # so in this case TOS will be 01+ pcn_threshold in bits + 01
        # 01011101 = 0x5D = 93
        pcn_start_pkt = Ether(src=get_if_hwaddr(iface), dst='ff:ff:ff:ff:ff:ff') / IP(src=src_ip, dst=dst_ip, tos=93) / TCP(sport=src_port, dport=dst_port) / 'PCN_START'
        sendp(pcn_start_pkt, iface=iface)
        print(f'Sent PCN_START packet with TOS: {pcn_start_pkt[IP].tos}')
        time_str = datetime.now().strftime('%H:%M:%S')
        self.file.write(f'{self.iter},{time_str},{self.sent_packets},PCN Start,{self.cwnd},{self.total},,,\n')
        # sniff the network for PCN_ACK
        self.wait_for_pcn_ack()

    def send_data(self):
        self.iter += 1
        self.wait = 0
        self.acked_packets = 0
        self.sent_packets = 0
        self.cwnd = 10
        self.total = 250 * 1024
        self.send_pcn_start()
        self.end_ack_thread = False
        ack_thread = threading.Thread(target=self.handle_ack)
        ack_thread.start()
        self.send_data_packets()
        while self.sent_packets != self.acked_packets and self.total == 0:
            if(self.wait == 10 and self.total == 0):
                break
            self.wait += 1
            sleep(0.1)
        self.end_ack_thread = True
        ack_thread.join()


def worker_node_loop():
    # Create a csv file to store start time, end time and total time for each iteration 
    # Open a file in write mode
    file = open('worker_node_2.csv', 'w')
    file.write('Iteration, Time (HH:MM:SS), Packet Number, Packet Type, Congestion Window, Total Bytes Sent, Total Time (Sec), Start Time, End Time\n')
    controller = DCTCPControllerWithPCN(file, 0)
    for i in range(1):
        # Save start time and end time in the csv file using hh:mm:ss format
        # but save the total time in seconds
        start_time = time()
        start_time_str = datetime.now().strftime('%H:%M:%S')
        controller.send_data()
        end_time = time()
        end_time_str = datetime.now().strftime('%H:%M:%S')
        total_time = end_time - start_time
        file.write(f'{i+1}, {total_time:.2f}, {start_time_str}, {end_time_str}\n')
        sleep(6)
    # close the file
    file.close()

if __name__ == '__main__':
    worker_node_loop()