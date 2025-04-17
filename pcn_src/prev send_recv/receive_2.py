from scapy.all import IP, UDP, Ether, sendp, sniff
from time import sleep, time
import threading
from datetime import datetime

src_ip = '10.0.0.6'
dst_ip = '10.0.0.2'
src_mac = '08:00:00:00:00:06'
dst_mac = '08:00:00:00:00:02'
src_port = 1234
dst_port = 4321
iface = 'eth0'
cwnd_lock = threading.Lock()

class DCTCPReceiver:
    def __init__(self):
        self.packet_count = 0

    def handle_pkt(self, pkt):
        if pkt[IP].tos >> 6 == 1 and pkt[IP].src == dst_ip and pkt[IP].dst == src_ip and pkt[UDP].dport == src_port:
            print(f"Received PCN_START packet from {pkt[IP].src} to {pkt[IP].dst}")
            tos = 0b10000001
            pcn_ack = Ether(src=src_mac, dst=dst_mac) / IP(src=src_ip, dst=dst_ip, tos=tos) / UDP(sport=src_port, dport=dst_port) / 'PCN_ACK'
            sendp(pcn_ack, iface=iface)
            print(f"Sent PCN_ACK packet to {dst_ip}")
        elif pkt[IP].tos & 0b11 == 0b11 and pkt[IP].src == dst_ip and pkt[IP].dst == src_ip and pkt[UDP].dport == src_port:
            print(f"Received data packet from {pkt[IP].src} to {pkt[IP].dst}")
            self.packet_count += 1
            print(f"Packet count: {self.packet_count}")
            tos = 0b00000011
            ack_pkt = Ether(src=src_mac, dst=dst_mac) / IP(src=src_ip, dst=dst_ip, tos=tos) / UDP(sport=src_port, dport=dst_port) / 'ACK'
            sendp(ack_pkt, iface=iface)
            print(f"Sent ACK packet to {dst_ip}")
        else:
            print(f"Received unknown packet from {pkt[IP].src} to {pkt[IP].dst}")
            ack_pkt = Ether(src=src_mac, dst=dst_mac) / IP(src=src_ip, dst=dst_ip) / UDP(sport=src_port, dport=dst_port) / 'ACK'
            sendp(ack_pkt, iface=iface)
            print(f"Sent ACK packet to {dst_ip}")
            self.packet_count += 1

    def receive_packets(self):
        while True:
            sniff(filter='udp and dst port 4321', prn=self.handle_pkt, count=1)

if __name__ == '__main__':
    receiver = DCTCPReceiver()
    receiver.receive_packets()