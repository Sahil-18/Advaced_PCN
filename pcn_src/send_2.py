from scapy.all import IP, UDP, Ether, sendp, sniff
from time import sleep, time
import threading
from datetime import datetime

src_ip = '10.0.0.2'
dst_ip = '10.0.0.6'
src_mac = '08:00:00:00:00:02'
dst_mac = '08:00:00:00:00:06'
src_port = 4321
dst_port = 1234
iface = 'eth0'
cwnd_lock = threading.Lock()

class DCTCPControllerWithPCN:
    def __init__(self, file, iteration):
        self.alpha = 1.0
        self.cwnd = 10
        self.max_cwnd = 100
        self.min_cwnd = 2
        self.pcn_threshold = 7
        self.sent_packets = 0
        self.acked_packets = 0
        self.total = 250 * 1024 * 1024
        self.wait = 0
        self.file = file
        self.iter = iteration
        self.end_ack_thread = False

    def send_pcn_start(self):
        # tos = 01 (PCN_START) + pcn_threshold (4 bits) + 01 (ECN)
        tos = 0b00000001 | (self.pcn_threshold << 2) | 0b00000001
        pcn_pkt = Ether(src=src_mac, dst=dst_mac) / IP(src=src_ip, dst=dst_ip, tos=tos) / UDP(sport=src_port, dport=dst_port) / 'PCN_START'
        sendp(pcn_pkt, iface=iface)
        print(f"Sent PCN_START packet to {dst_ip}")
    
    def wait_for_pcn_ack(self):
        def check(pkt):
            return pkt[IP].tos >> 6 == 2 and pkt[IP].src == dst_ip and pkt[IP].dst == src_ip and pkt[UDP].dport == src_port
        
        while True:
            print("Waiting for PCN_ACK...")
            pkt = sniff(filter='udp and dst port 4321', count=1, timeout=1)
            if pkt and check(pkt[0]):
                print(f"Received PCN_ACK packet from {pkt[IP].src} to {pkt[IP].dst}")
                break

    def send_data_packets(self):
        while self.total > 0:
            with cwnd_lock:
                if self.cwnd <= 0:
                    continue
                data_len = min(1460, self.total)
                self.total -= data_len
                tos = 0b11000001
                data_pkt = Ether(src=src_mac, dst=dst_mac) / IP(src=src_ip, dst=dst_ip, tos=tos) / UDP(sport=src_port, dport=dst_port) / ('A' * data_len)
                sendp(data_pkt, iface=iface)
                print(f"Sent data packet to {dst_ip} with length {data_len}")
                self.sent_packets += 1
                self.cwnd -= 1

    def handle_ack_pkt(self, pkt):
        if pkt[IP].src == dst_ip and pkt[UDP].sport == dst_port and pkt[UDP].dport == src_port:
            if pkt[IP].tos & 0b11 == 0b11:
                print(f"Received ECN marked ACK packet from {pkt[IP].src} to {pkt[IP].dst}")
                with cwnd_lock:
                    self.cwnd = max(self.min_cwnd, self.cwnd*self.alpha/2)
                    self.acked_packets += 1
            else:
                print(f"Received ACK packet from {pkt[IP].src} to {pkt[IP].dst}")
                with cwnd_lock:
                    self.cwnd = min(self.max_cwnd, self.cwnd + 1)
                    self.acked_packets += 1

    def handle_ack(self):
        while not self.end_ack_thread:
            sniff(filter='udp and dst port 4321', prn=self.handle_ack_pkt, count=1, timeout=1)


    def send_data(self):
        self.send_pcn_start()
        self.wait_for_pcn_ack()
        self.end_ack_thread = False
        ack_thread = threading.Thread(target=self.handle_ack)
        ack_thread.start()
        self.send_data_packets()
        self.end_ack_thread = True
        ack_thread.join()
        self.file.close()


if __name__ == '__main__':
    controller = DCTCPControllerWithPCN(open('buffer_position_1.csv', 'w'), 1)
    controller.send_data()