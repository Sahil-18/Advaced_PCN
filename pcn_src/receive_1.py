from scapy.all import *
from time import sleep, time
import random
from datetime import datetime

src_ip = '10.0.0.6'
dst_ip = '10.0.0.2'
src_port = 1234
iface = 'eth0'

class DCTCPReceiver:
    def __init__(self):
        self.file = open('buffer_position_1.csv', 'w')
        self.iteration = 0
        self.seq = 100

    def handle_pkt(self, pkt):
        if pkt[TCP].flags == 'S':
            print(f"Received SYN packet from {pkt[IP].src} to {pkt[IP].dst}")
            syn_ack = Ether()/IP(src=src_ip, dst=dst_ip)/TCP(sport=src_port, dport=pkt[TCP].sport, flags='SA', seq=self.seq, ack=pkt[TCP].seq + 1)
            send(syn_ack, iface=iface)
            self.seq += 1
            print(f"Sent SYN-ACK packet to {pkt[IP].src}")

        elif pkt[TCP].flags == 'A':
            print(f"Received ACK packet from {pkt[IP].src} to {pkt[IP].dst}")

        elif pkt[IP].tos >> 6 == 1:
            print(f"Received PCN Start packet from {pkt[IP].src} to {pkt[IP].dst}")
            self.iteration += 1
            # tos of IP header will be 10000001 = 0x81 = 129
            pcn_ack = Ether()/IP(src=src_ip, dst=dst_ip, tos=169)/TCP(sport=src_port, dport=pkt[TCP].sport, flags = 'PA', seq=self.seq, ack=pkt[TCP].seq+1)/'PCN_ACK'
            self.seq += 1
            send(pcn_ack, iface=iface)
            print(f"Sent PCN_ACK packet to {pkt[IP].src}")

        else:
            # Data Packet
            if pkt[IP].tos & 0b00000011 == 0b11:
                print(f"Received ECN marked data packet from {pkt[IP].src} to {pkt[IP].dst}")
                ack_pkt = Ether()/IP(src=src_ip, dst=dst_ip, tos=1)/TCP(sport=src_port, dport=pkt[TCP].sport, flags=0x10|0x40, seq=self.seq, ack=pkt[TCP].seq+1)
                send(ack_pkt, iface=iface)
                self.seq += 1
                print(f"Sent DCTCP ECN ACK packet to {pkt[IP].src}")
            else:
                print(f"Received data packet from {pkt[IP].src} to {pkt[IP].dst}")
                ack_pkt = Ether()/IP(src=src_ip, dst=dst_ip, tos=1)/TCP(sport=src_port, dport=pkt[TCP].sport, flags='PA', seq=self.seq, ack=pkt[TCP].seq+1)
                send(ack_pkt, iface=iface)
                self.seq += 1
                print(f"Sent ACK packet to {pkt[IP].src}")

    def receive_packets(self):
        while True:
            sniff(filter=f'tcp and src host {src_ip} and dst host {dst_ip} and dst port {src_port}', prn=self.handle_pkt)

if __name__ == '__main__':
    receiver = DCTCPReceiver()
    receiver.receive_packets()

# class DCTCPReceiver:
#     def __init__(self):
#         self.pcn_threshold = 10
#         self.file = open('buffer_position_1.csv', 'w')
#         self.iteration = 0
#         self.packets = 0

#     # When a packet is received, its pcn_threshold value will have its buffer position in the queue, multiply it with 3 and store it in a file.
#     def handle_pkt(self, pkt):
#         # Check if the packet is PCN start packet# in IP header, TOS bits are used for PCN and ECN
#         # First two bits are used for PCN, 01 for PCN Start
#         # Next 4 bits are used for sharing the pcn_threshold
#         # Last 2 bits are used for ECN
#         # so in this case the first two bits should be 01
#         time_str = datetime.now().strftime('%H:%M:%S')

#         if pkt[IP].tos >> 6 == 1:
#             self.pcn_threshold = pkt[IP].tos & 0b00111100
#             self.iteration += 1
#             self.packets = 0
#             self.file.write(f'{self.iteration},{time_str},PCN Start,{self.packets},0,N\n')
#             # send a PCN_ACK
#             # in IP header, TOS bits are used for PCN and ECN
#             # First two bits are used for PCN, 10 for PCN ACK
#             # Next 4 bits are used for sharing the pcn_threshold
#             # Last 2 bits are used for ECN
#             # so in this case TOS will be 10+ pcn_threshold in bits + 01
#             # 10101001 = 0xa9 = 169
#             pcn_ack_pkt = Ether(src=get_if_hwaddr(iface), dst='ff:ff:ff:ff:ff:ff') / IP(src=src_ip, dst=dst_ip, tos=169) / TCP(sport=src_port, dport=pkt[TCP].sport) / 'PCN_ACK'
#             sendp(pcn_ack_pkt, iface=iface)
#         else:
#             self.packets += 1
#             # TOS bits are split into 3 parts for PCN, ECN and pcn_threshold
#             # First two bits are used for PCN
#             # Next 4 bits are used for sharing the pcn_threshold
#             # Last 2 bits are used for ECN
#             # extract the pcn_threshold value from the packet
#             buffer_position = ((pkt[IP].tos & 0b00111100) >> 2)*6
#             # Data packet send TCP ACK 
#             # Also check whether the packet is ECN marked i.e. ECN bits are 11 if so, the TCP flag value will be 0x40 for DCTCP ECN
#             if pkt[IP].tos & 0b00000011 == 0b11:
#                 # if ecn bits are set, send a DCTCP ECN ACK
#                 # in TCP header, the ECN bits are set to 11
#                 # so the value will be 0x40
#                 ack_pkt = Ether(src=get_if_hwaddr(iface), dst='ff:ff:ff:ff:ff:ff') / IP(src=src_ip, dst=dst_ip, tos=193) / TCP(sport=src_port, dport=pkt[TCP].sport, flags=0x40)
#                 sendp(ack_pkt, iface=iface)
#                 self.file.write(f'{self.iteration},{time_str},DATA,{self.packets},{buffer_position}, Y\n')
#             else:
#                 ack_pkt = Ether(src=get_if_hwaddr(iface), dst='ff:ff:ff:ff:ff:ff') / IP(src=src_ip, dst=dst_ip, tos=193) / TCP(sport=src_port, dport=pkt[TCP].sport)
#                 sendp(ack_pkt, iface=iface)
#                 self.file.write(f'{self.iteration},{time_str},DATA,{self.packets},{buffer_position}, N\n')
    
#     def receive_packets(self):
#         # File will have following information in each line
#         # Iteration, Packet Number and Buffer Position
#         # Buffer position is calculated by multiplying pcn_threshold with 3
#         self.file.write('Iteration, Time (in HH:MM:SS), Packet Type, Packet Number, Buffer Position, Congestion\n')
#         try: 
#             while True:
#                 sniff(filter='tcp and port 1234', prn=self.handle_pkt)
#         # Close file when keyboard interrupt is received
#         except KeyboardInterrupt:
#             self.file.close()

# if __name__ == '__main__':
#     receiver = DCTCPReceiver()
#     receiver.receive_packets()