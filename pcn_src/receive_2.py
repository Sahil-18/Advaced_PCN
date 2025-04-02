from scapy.all import *
from time import sleep, time
import random

src_ip = '10.0.0.7'
dst_ip = '10.0.0.3'
src_port = 1234
iface = 'eth0'

class DCTCPReceiver:
    def __init__(self):
        self.pcn_threshold = 10
        self.file = open('buffer_position_2.csv', 'w')
        self.iteration = 0
        self.packets = 0

    # When a packet is received, its pcn_threshold value will have its buffer position in the queue, multiply it with 3 and store it in a file.
    def handle_pkt(self, pkt):
        # Check if the packet is PCN start packet# in IP header, TOS bits are used for PCN and ECN
        # First two bits are used for PCN, 01 for PCN Start
        # Next 4 bits are used for sharing the pcn_threshold
        # Last 2 bits are used for ECN
        # so in this case the first two bits should be 01
        if pkt[IP].tos >> 6 == 1:
            self.pcn_threshold = pkt[IP].tos & 0b00111100
            self.iteration += 1
            self.packets = 0
            # send a PCN_ACK
            # in IP header, TOS bits are used for PCN and ECN
            # First two bits are used for PCN, 10 for PCN ACK
            # Next 4 bits are used for sharing the pcn_threshold
            # Last 2 bits are used for ECN
            # so in this case TOS will be 10+ pcn_threshold in bits + 01
            # 10101001 = 0xa9 = 169
            pcn_ack_pkt = Ether(src=get_if_hwaddr(iface), dst='ff:ff:ff:ff:ff:ff') / IP(src=src_ip, dst=dst_ip, tos=169) / TCP(sport=src_port, dport=pkt[TCP].sport) / 'PCN_ACK'
            sendp(pcn_ack_pkt, iface=iface)
        else:
            self.packets += 1
            # TOS bits are split into 3 parts for PCN, ECN and pcn_threshold
            # First two bits are used for PCN
            # Next 4 bits are used for sharing the pcn_threshold
            # Last 2 bits are used for ECN
            # extract the pcn_threshold value from the packet
            buffer_position = ((pkt[IP].tos & 0b00111100) >> 2)*3
            self.file.write(f'{self.iteration},{self.packets},{buffer_position}\n')
            # Data packet send TCP ACK 
            # Also check whether the packet is ECN marked i.e. ECN bits are 11 if so, the TCP flag value will be 0x40 for DCTCP ECN
            if pkt[IP].tos & 0b00000011 == 0b11:
                # if ecn bits are set, send a DCTCP ECN ACK
                # in TCP header, the ECN bits are set to 11
                # so the value will be 0x40
                ack_pkt = Ether(src=get_if_hwaddr(iface), dst='ff:ff:ff:ff:ff:ff') / IP(src=src_ip, dst=dst_ip, tos=193) / TCP(sport=src_port, dport=pkt[TCP].sport, flags=0x40)
                sendp(ack_pkt, iface=iface)
            else:
                ack_pkt = Ether(src=get_if_hwaddr(iface), dst='ff:ff:ff:ff:ff:ff') / IP(src=src_ip, dst=dst_ip, tos=193) / TCP(sport=src_port, dport=pkt[TCP].sport)
                sendp(ack_pkt, iface=iface)
    
    def receive_packets(self):
        # File will have following information in each line
        # Iteration, Packet Number and Buffer Position
        # Buffer position is calculated by multiplying pcn_threshold with 3
        self.file.write('Iteration,Packet Number,Buffer Position\n')
        try: 
            while True:
                sniff(filter='tcp and port 1234', prn=self.handle_pkt)
        # Close file when keyboard interrupt is received
        except KeyboardInterrupt:
            self.file.close()

if __name__ == '__main__':
    receiver = DCTCPReceiver()
    receiver.receive_packets()