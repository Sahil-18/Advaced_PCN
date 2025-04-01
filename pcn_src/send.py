from scapy.all import *
from time import sleep, time
import random
import threading

src_ip = '10.0.0.2'
dst_ip = '10.0.0.1'
rc_port = random.randint(49152, 65535)
dst_port = 1234
iface = 'eth0'

cwnd_lock = threading.Lock()

class DCTCPControllerWithPCN:
    def __init__(self):
        self.alpha = 1.0
        self.cwnd = 20
        self.max_cwnd = 100
        self.min_cwnd = 2
        self.pcn_threshold = 10
        self.sent_packets = 0
        self.acked_packets = 0
        self.total = 250 * 1024 * 1024

    def handle_ack_pkt(self, pkt):
        if pkt[TCP].dport == rc_port and pkt[TCP].sport == dst_port:
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

    def handle_ack(self):
        while True:
            sniff(filter='tcp and port 1234', prn=self.handle_ack_pkt)

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
            pkt = Ether(src=get_if_hwaddr(iface), dst='ff:ff:ff:ff:ff:ff') / IP(src=src_ip, dst=dst_ip, tos=193) / TCP(sport=rc_port, dport=dst_port) / ('A' * data_len)
            sendp(pkt, iface=iface)
            cwnd_lock.acquire()
            self.cwnd -= 1
            self.sent_packets += 1
            cwnd_lock.release()
                
    
    def handle_pcn_ack(self, pkt):
        # check if the IP tos bit has 10 in the first two bits
        # if it does, then it is a PCN_ACK
        # also check if the tcp port as same as the one we sent the packet to
        if pkt[IP].tos >> 6 == 2 and pkt[TCP].dport == rc_port and pkt[TCP].sport == dst_port:
            return
        else :
            sniff(filter='tcp and port 1234', prn=self.handle_pcn_ack, timeout=2)

    def send_pcn_start(self):
        # in IP header, TOS bits are used for PCN and ECN
        # First two bits are used for PCN, 01 for PCN Start
        # Next 4 bits are used for sharing the pcn_threshold
        # Last 2 bits are used for ECN
        # so in this case TOS will be 01+ pcn_threshold in bits + 01
        # 01101001 = 0x69 = 105
        pcn_start_pkt = Ether(src=get_if_hwaddr(iface), dst='ff:ff:ff:ff:ff:ff') / IP(src=src_ip, dst=dst_ip, tos=105) / TCP(sport=rc_port, dport=dst_port) / 'PCN_START'
        sendp(pcn_start_pkt, iface=iface)
        # sniff the network for PCN_ACK
        sniff(filter='tcp and port 1234', prn=self.handle_pcn_ack, timeout=2)

    def send_data(self):
        self.acked_packets = 0
        self.sent_packets = 0
        self.cwnd = 20
        self.total = 250 * 1024 * 1024
        self.send_pcn_start()
        ack_thread = threading.Thread(target=self.handle_ack)
        ack_thread.start()
        self.send_data_packets()
        while self.sent_packets != self.acked_packets and self.total == 0:
            sleep(1)


def worker_node_loop():
    controller = DCTCPControllerWithPCN()

    for _ in range(10):
        controller.send_data()
        sleep(2)

if __name__ == '__main__':
    worker_node_loop()