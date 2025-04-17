// Proactive Congestion Notification Implementation

#include <core.p4>
#include <v1model.p4>

/*************************************************************************
****************** D E F I N E   C O N S T A N T S ***********************
*************************************************************************/

// constants for headers
const bit<8> TCP_PROTOCOL = 0x06;
const bit<16> TYPE_IPV4 = 0x800;
const bit<8>  TYPE_TCP  = 6;
const bit<19> ECN_THRESHOLD = 40;
const bit<2> PCN_START = 0x01;
const bit<2> PCN_RESET = 0x03;

// constants for number of ports and number of flows
#define MAX_PORTS 8
#define NUM_FLOWS 16

#define MIN_THRESHOLD 1
#define HARMONIC_THRESHOLD 2

#define THRESHOLD_SCHEME 1

/*************************************************************************
*********************** H E A D E R S  ***********************************
*************************************************************************/

typedef bit<9> egreessSpec_t;
typedef bit<48> macAddr_t;
typedef bit<32> ip4Addr_t;

typedef bit<36> pcn_port_data_t;
typedef bit<20> flow_key_t;
typedef bit<19> queue_len_t;

header ethernet_t {
    macAddr_t dstAddr;
    macAddr_t srcAddr;
    bit<16> etherType;
}

/*
 * IPv4: TOS field is split to two fields 6 bit diffserve and 2 bit ecn
 * diffserve can then be used to represent 2 bit for pcn and 4 bit for threshold
 */
header ipv4_t {
    bit<4>    version;
    bit<4>    ihl;
    bit<6>    diffserve;
    bit<2>    ecn;
    bit<16>   totalLen;
    bit<16>   identification;
    bit<3>    flags;
    bit<13>   fragOffset;
    bit<8>    ttl;
    bit<8>    protocol;
    bit<16>   hdrChecksum;
    ip4Addr_t srcAddr;
    ip4Addr_t dstAddr;
}

header tcp_t{
    bit<16> srcPort;
    bit<16> dstPort;
    bit<32> seqNo;
    bit<32> ackNo;
    bit<4>  dataOffset;
    bit<4>  res;
    bit<1>  cwr;
    bit<1>  ece;
    bit<1>  urg;
    bit<1>  ack;
    bit<1>  psh;
    bit<1>  rst;
    bit<1>  syn;
    bit<1>  fin;
    bit<16> window;
    bit<16> checksum;
    bit<16> urgentPtr;
}

struct metadata {

}

struct headers {
    ethernet_t ethernet;
    ipv4_t ipv4;
    tcp_t tcp;
}

/*************************************************************************
********* C U S T O M   P E R - P O R T   S T R U C T U R E S ************
*************************************************************************/

/*

Since currently, register do not allow struct to be used, we have to convert
it to bit format. But the structure can be used as a reference for how the 
bit field can be broken to get differnt fields.

Define a single resister to store pcn_port_data_t
struct pcn_port_data_t {
    bit<1> pcn_enabled;
    bit<19> threshold;
    bit<16> number_of_flows;
}

so pcn_port_data register will be of size (1 + 19 + 16) = 36 
with structure as 
pcn_port_data[0] = pcn_enabled
pcn_port_data[1:19] = threshold
pcn_port_data[20:35] = number_of_flows

Define a single register to store flow details
struct flow_key_t {
    bit<1> flag;
    bit<19> threshold;
}

so flow_key register will be of size (1 + 19) = 20
with structure as 
flow_key[0] = flag
flow_key[1:19] = threshold

Define register to store ingress queue length for pakcets
struct queue_len_t{
    bit<19> queue_length;
}
so queue_len register will be of size 19 with all bits representing
queue_length

*/

register<pcn_port_data_t>(MAX_PORTS) pcn_port_data;
register<flow_key_t>(NUM_FLOWS) flow_key;
register<queue_len_t>(MAX_PORTS) queue_len;

/*************************************************************************
************************* P A R S E R  ***********************************
*************************************************************************/

parser MyParser(packet_in packet,
                  out headers hdr,
                  inout metadata meta,
                  inout standard_metadata_t standard_metadata) {

    state start {
        transition parse_ethernet;
    }

    state parse_ethernet {
        packet.extract(hdr.ethernet);
        transition select(hdr.ethernet.etherType) {
            TYPE_IPV4: parse_ipv4;
            default: accept;
        }
    }

    state parse_ipv4 {
        packet.extract(hdr.ipv4);
        transition select(hdr.ipv4.protocol){
            TYPE_TCP: parse_tcp;
            default: accept;
        }
    }

    state parse_tcp {
        packet.extract(hdr.tcp);
        transition accept;
    }
}


/*************************************************************************
************   C H E C K S U M    V E R I F I C A T I O N   **************
*************************************************************************/

control MyVerifyChecksum(inout headers hdr, inout metadata meta) {
    apply {  }
}


/************************************************************************
**************  I N G R E S S   P R O C E S S I N G   *******************
************************************************************************/

control MyIngress(inout headers hdr,
                  inout metadata meta,
                  inout standard_metadata_t standard_metadata){

    bit<32> reg_pos;
    bit<2> pcn;
    bit<19> threshold;

    action extract_pcn_threshold() {
        pcn = hdr.ipv4.diffserve[5:4];
        threshold = (bit<19>)hdr.ipv4.diffserve[3:0]*3;
    }

    action drop(){
        mark_to_drop(standard_metadata);
    }               

    action compute_hash(ip4Addr_t srcAddr, ip4Addr_t dstAddr, bit<16> srcPort, bit<16> dstPort) {
        // Get register position
        hash(reg_pos, HashAlgorithm.crc32, (bit<32>)0, {
            srcAddr, dstAddr, srcPort, dstPort
        }, (bit<32>)NUM_FLOWS);
    }

    action ipv4_forward(macAddr_t dstAddr, egreessSpec_t port) {
        standard_metadata.egress_spec = port;
        hdr.ethernet.srcAddr = hdr.ethernet.dstAddr;
        hdr.ethernet.dstAddr = dstAddr;
        hdr.ipv4.ttl = hdr.ipv4.ttl - 1;
    }

    table ipv4_exact {
        key = {
            hdr.ipv4.dstAddr: exact;
        }
        actions = {
            ipv4_forward;
            drop;
        }
        size = 1024;
        default_action = drop;
    }

    apply {
        if (hdr.ipv4.isValid() && hdr.tcp.isValid()) {
            extract_pcn_threshold();
            
            // Compute hash

            compute_hash(hdr.ipv4.srcAddr, hdr.ipv4.dstAddr, hdr.tcp.srcPort, hdr.tcp.dstPort);

            //pcn specific logic
            /* Since P4 does not allow read and write of registers from action which is 
                conditionally applied, all conditional logic of handling PCN_START and PCN_RESET
                will be written here only */

            if (pcn == PCN_START) {
                
                pcn_port_data_t current_data;
                pcn_port_data.read(current_data, (bit<32>)standard_metadata.ingress_port);

                // unmaksing the fields
                bit<1> pcn_enabled = (bit<1>)(current_data >> 35);
                bit<19> threshold_stored = (bit<19>)((current_data >> 16) & 0x7FFFF);
                bit<16> num_flows = (bit<16>)(current_data & 0xFFFF);

                num_flows = num_flows + 1;

                if (pcn_enabled == 0) {
                    pcn_enabled = 1;
                    threshold_stored = threshold;
                } else {
                    if (THRESHOLD_SCHEME == MIN_THRESHOLD) {
                        // use of minimum of current_data.threshold and threshold
                        if (threshold_stored > threshold) {
                            threshold_stored = threshold;
                        }
                    } else if (THRESHOLD_SCHEME == HARMONIC_THRESHOLD) {
                        // Approximate using interger math to avoid divide-by-zero
                        bit<32> inv_sum = (bit<32>)(1 << 16) / threshold + (bit<32>)(1 << 16) / threshold_stored;
                        threshold_stored = (bit<19>)((1 << 16) / inv_sum);
                    }
                }

                // Repack everything
                current_data = ((pcn_port_data_t)pcn_enabled << 35) |
                                ((pcn_port_data_t)threshold_stored << 16) |
                                (pcn_port_data_t)num_flows;

                pcn_port_data.write((bit<32>)standard_metadata.ingress_port, current_data);
                
                flow_key_t current_flow;

                // set fields
                bit<1> flag = 1;
                bit<19> threshold_flow = threshold;
                
                // pack
                current_flow = ((flow_key_t)flag << 19) | (flow_key_t)threshold_flow;

                flow_key.write(reg_pos, current_flow);

            }
            else if(pcn == PCN_RESET) {

                flow_key_t current_flow;
                flow_key.read(current_flow, reg_pos);

                // Unpack flow_key
                bit<1> flag = (bit<1>)(current_flow >> 19);
                bit<19> threshold_stored = (bit<19>)(current_flow & 0x7FFFF);

                threshold = threshold_stored;

                if (flag == 1) {
                    // Clear flow_key by writing all zeroes
                    flow_key.write(reg_pos, (flow_key_t)0);

                    // Update PCN port data
                    pcn_port_data_t current_data;
                    pcn_port_data.read(current_data, (bit<32>)standard_metadata.ingress_port);

                    // Unpack pcn_port_data
                    bit<1> pcn_enabled = (bit<1>)(current_data >> 35);
                    bit<19> current_threshold = (bit<19>)((current_data >> 16) & 0x7FFFF);
                    bit<16> num_flows = (bit<16>)(current_data & 0xFFFF);

                    // Decrement flow count
                    num_flows = num_flows - 1;
                    if (num_flows == 0) {
                        pcn_enabled = 0;
                        current_threshold = ECN_THRESHOLD;
                    } else {
                        if (THRESHOLD_SCHEME == HARMONIC_THRESHOLD) {
                            // Inverse subtraction
                            bit<32> inv_old = (1 << 16)/current_threshold;
                            bit<32> inv_removed = (1 << 16)/threshold_stored;
                            bit<32> inv_new = inv_old - inv_removed;

                            if (inv_new > 0) {
                                current_threshold = (bit<19>)((1 << 16)/inv_new);
                            } else {
                                current_threshold = ECN_THRESHOLD;
                            }
                        }
                    }

                    // Repack PCN port data
                    current_data = ((pcn_port_data_t)pcn_enabled << 35) |
                                    ((pcn_port_data_t)current_threshold << 16) |
                                    (pcn_port_data_t)num_flows;

                    pcn_port_data.write((bit<32>)standard_metadata.ingress_port, current_data);
                }                
            }

            ipv4_exact.apply();
        }
    }
}

/*************************************************************************
****************  E G R E S S   P R O C E S S I N G   ********************
*************************************************************************/

control MyEgress(inout headers hdr,
                 inout metadata meta,
                 inout standard_metadata_t standard_metadata) {

    action mark_ecn(){
        hdr.ipv4.ecn = 3;
    }

    apply {
        queue_len_t current_len;
        current_len = standard_metadata.enq_qdepth;
        queue_len.write((bit<32>)standard_metadata.ingress_port, current_len);

        // Compute (enq_qdepth / 6) and store lower 4 bits
        // bit<19> divided_qdepth = current_len / 6;
        // bit<4> temp_buff = (bit<4>)(divided_qdepth & 0xF);

        if (hdr.ipv4.diffserve[5:4]!=PCN_START) {
            pcn_port_data_t current_data;
            pcn_port_data.read(current_data, (bit<32>)standard_metadata.ingress_port);
            
            // Unpacke fields
            bit<1> pcn_enabled = (bit<1>)(current_data >> 35);
            bit<19> threshold = (bit<19>)((current_data >> 16) & 0x7FFFF);

            if (pcn_enabled == 1) {
                if (hdr.ipv4.diffserve[5:4]!=0 && standard_metadata.enq_qdepth >= ECN_THRESHOLD){
                    mark_ecn();
                } else if( hdr.ipv4.diffserve[5:4]==0 && standard_metadata.enq_qdepth >= threshold){
                    mark_ecn();
                }
            } else {
                if(hdr.ipv4.ecn == 1 || hdr.ipv4.ecn == 2){
                    if(standard_metadata.enq_qdepth >= ECN_THRESHOLD){
                        mark_ecn();
                    }
                }
            }

            // Encode buffer occupancy to diffserve
            // if (hdr.ipv4.diffserve[5:4]!=0) {
                
                // hdr.ipv4.diffserve[3:0] = temp_buff;
            // }
        }
    }
}

/*************************************************************************
*************   C H E C K S U M    C O M P U T A T I O N   ***************
*************************************************************************/

control MyComputeChecksum(inout headers hdr, inout metadata meta) {
     apply {
        update_checksum(
            hdr.ipv4.isValid(),
            { 
                hdr.ipv4.version,
                hdr.ipv4.ihl,
                hdr.ipv4.diffserve,
                hdr.ipv4.ecn,
                hdr.ipv4.totalLen,
                hdr.ipv4.identification,
                hdr.ipv4.flags,
                hdr.ipv4.fragOffset,
                hdr.ipv4.ttl,
                hdr.ipv4.protocol,
                hdr.ipv4.srcAddr,
                hdr.ipv4.dstAddr 
            },
            hdr.ipv4.hdrChecksum,
            HashAlgorithm.csum16
        );
    }
}

/*************************************************************************
************************  D E P A R S E R  *******************************
*************************************************************************/

control MyDeparser(packet_out packet, in headers hdr) {
    apply {
        packet.emit(hdr.ethernet);
        packet.emit(hdr.ipv4);
        packet.emit(hdr.tcp);
    }
}

/*************************************************************************
****************************  S W I T C H  *******************************
*************************************************************************/

V1Switch(
MyParser(),
MyVerifyChecksum(),
MyIngress(),
MyEgress(),
MyComputeChecksum(),
MyDeparser()
) main;