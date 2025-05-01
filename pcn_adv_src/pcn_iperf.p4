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
const bit<32> FLOW1 = 0x0a000001;
const bit<32> FLOW2 = 0x0a000002;
const bit<32> FLOW3 = 0x0a000003;
const bit<32> FLOW4 = 0x0a000004;
const bit<32> FLOW5 = 0x0a000005;
const bit<32> FLOW6 = 0x0a000006;
const bit<19> K = 2;

const bit<32> FLOW1_IDX = 0;
const bit<32> FLOW2_IDX = 1;
const bit<32> FLOW3_IDX = 2;
const bit<32> FLOW4_IDX = 3;
const bit<32> FLOW5_IDX = 4;
const bit<32> FLOW6_IDX = 5;

// constants for number of ports and number of flows
#define MAX_PORTS 8
#define NUM_FLOWS 16

#define MIN_THRESHOLD 1
#define HARMONIC_THRESHOLD 2

#define THRESHOLD_SCHEME 2

/*************************************************************************
*********************** H E A D E R S  ***********************************
*************************************************************************/

typedef bit<9> egreessSpec_t;
typedef bit<48> macAddr_t;
typedef bit<32> ip4Addr_t;

typedef bit<16> pcn_port_data_t;
typedef bit<19> pcn_port_thresh_t;
typedef bit<1> flow_key_t;
typedef bit<19> queue_len_t;
typedef bit<19> flow_thresh_t;

header ethernet_t {
    macAddr_t dstAddr;
    macAddr_t srcAddr;
    bit<16> etherType;
}

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

header tcp_t {
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
    bit<16> number_of_flows;
}

so pcn_port_data register will be of size 16

Define a single resister to store pcn_port_thresh_t
struct pcn_port_thresh_t {
    bit<19> threshold;
}

so pcn_port_data register will be of size 16



Define a single register to store flow details
struct flow_key_t {
    bit<1> flag;
}

so flow_key register will be of size 1

struct flow_thresh_t {
    bit<19> threshold;
}

so flow_thresh register will be of size 19

Define register to store ingress queue length for pakcets
struct queue_len_t{
    bit<19> queue_length;
}
so queue_len register will be of size 19 with all bits representing
queue_length

*/

register<pcn_port_data_t>(MAX_PORTS) pcn_port_data;
register<pcn_port_thresh_t>(MAX_PORTS) pcn_port_thresh;
register<flow_key_t>(NUM_FLOWS) flow_key;
register<flow_thresh_t>(NUM_FLOWS) flow_thresh;
register<queue_len_t>(MAX_PORTS) queue_len;
register<flow_thresh_t>(100) inverse_thresh;

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
        transition select(hdr.ipv4.protocol) {
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
                  inout standard_metadata_t standard_metadata) {

    action drop(){
        mark_to_drop(standard_metadata);
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
    
    apply{
        if (hdr.ipv4.isValid() && hdr.tcp.isValid()){

            // check for PCN flows
            if (hdr.ipv4.srcAddr == FLOW1 || hdr.ipv4.srcAddr == FLOW2 || 
                hdr.ipv4.srcAddr == FLOW3 || hdr.ipv4.srcAddr == FLOW4 ||
                hdr.ipv4.srcAddr == FLOW5 || hdr.ipv4.srcAddr == FLOW6) {
                bit<32> pos;
                if (hdr.ipv4.srcAddr == FLOW1) {
                    pos = FLOW1_IDX;
                } else if (hdr.ipv4.srcAddr == FLOW1) {
                    pos = FLOW1_IDX;
                } else if (hdr.ipv4.srcAddr == FLOW2) {
                    pos = FLOW2_IDX;
                } else if (hdr.ipv4.srcAddr == FLOW3) {
                    pos = FLOW3_IDX;
                } else if (hdr.ipv4.srcAddr == FLOW4) {
                    pos = FLOW4_IDX;
                } else if (hdr.ipv4.srcAddr == FLOW5) {
                    pos = FLOW5_IDX;
                } else {
                    pos = FLOW6_IDX;
                }

                // PCN START if TCP SYN is true
                if(hdr.tcp.syn == 1){
                    flow_thresh_t threshold;
                    flow_thresh.read(threshold, pos);

                    pcn_port_data_t current_data;
                    pcn_port_data.read(current_data, (bit<32>)standard_metadata.ingress_port);

                    flow_key_t current_flow;
                    flow_key.read(current_flow, pos);

                    pcn_port_thresh_t current_thresh;
                    pcn_port_thresh.read(current_thresh, (bit<32>)standard_metadata.ingress_port);

                    if (current_flow == 0){
                        
                        if (current_data == 0) {
                            current_thresh = threshold;
                        } else {
                            if (THRESHOLD_SCHEME == MIN_THRESHOLD) {
                                // use of minimum of current_data.threshold and threshold
                                if (current_thresh > threshold) {
                                    current_thresh = threshold;
                                }
                            } else if (THRESHOLD_SCHEME == HARMONIC_THRESHOLD) {
                                if (current_thresh > 10 && current_thresh < 15) {
                                    current_thresh = 10;
                                } else if (current_thresh > 15 && current_thresh < 20) {
                                    current_thresh = 15;
                                } else if (current_thresh > 20 && current_thresh < 25) {
                                    current_thresh = 20;
                                } else if (current_thresh > 25 && current_thresh < 30) {
                                    current_thresh = 25;
                                } else if (current_thresh > 30 && current_thresh < 35) {
                                    current_thresh = 30;
                                } else if (current_thresh > 35 && current_thresh < 40) {
                                    current_thresh = 35;
                                } else if (current_thresh > 40 && current_thresh < 45) {
                                    current_thresh = 40;
                                } else if (current_thresh > 45 && current_thresh < 50) {
                                    current_thresh = 45;
                                } else {
                                    current_thresh = 50;
                                }

                                bit<19> inv_curr_thresh;
                                inverse_thresh.read(inv_curr_thresh, (bit<32>)current_thresh);
                                bit<19> threshold_k = K * threshold;
                                bit<19> inv_thresh;
                                inverse_thresh.read(inv_thresh, (bit<32>)threshold_k);
                                inv_curr_thresh = inv_curr_thresh + inv_thresh;

                                if (inv_curr_thresh > 10 && inv_curr_thresh < 15) {
                                    inv_curr_thresh = 10;
                                } else if (inv_curr_thresh > 15 && inv_curr_thresh < 20) {
                                    inv_curr_thresh = 15;
                                } else if (inv_curr_thresh > 20 && inv_curr_thresh < 25) {
                                    inv_curr_thresh = 20;
                                } else if (inv_curr_thresh > 25 && inv_curr_thresh < 30) {
                                    inv_curr_thresh = 25;
                                } else if (inv_curr_thresh > 30 && inv_curr_thresh < 35) {
                                    inv_curr_thresh = 30;
                                } else if (inv_curr_thresh > 35 && inv_curr_thresh < 40) {
                                    inv_curr_thresh = 35;
                                } else if (inv_curr_thresh > 40 && inv_curr_thresh < 45) {
                                    inv_curr_thresh = 40;
                                } else if (inv_curr_thresh > 45 && inv_curr_thresh < 50) {
                                    inv_curr_thresh = 45;
                                } else {
                                    inv_curr_thresh = 50;
                                }

                                inverse_thresh.read(current_thresh, (bit<32>)inv_curr_thresh);
                            }
                        }

                        current_data = current_data + 1;

                        pcn_port_data.write((bit<32>)standard_metadata.ingress_port, current_data);
                        pcn_port_thresh.write((bit<32>)standard_metadata.ingress_port, current_thresh);

                        // set fields
                        current_flow = 1;
                        flow_key.write(pos, current_flow);
                    }

                } else if (hdr.tcp.fin == 1) {

                    flow_key_t current_flow;
                    flow_key.read(current_flow, pos);

                    if (current_flow == 1) {
                        flow_thresh_t threshold;
                        flow_thresh.read(threshold, pos);

                        current_flow = 0;

                        // Write flow info
                        flow_key.write(pos, current_flow);

                        // Update PCN port data
                        pcn_port_data_t current_data;
                        pcn_port_data.read(current_data, (bit<32>)standard_metadata.ingress_port);

                        pcn_port_thresh_t current_thresh;
                        pcn_port_thresh.read(current_thresh, (bit<32>)standard_metadata.ingress_port);

                        // Decrement flow count
                        current_data = current_data - 1;
                        
                        if (current_data == 0) {
                            current_thresh = ECN_THRESHOLD;
                        } else {
                            if (THRESHOLD_SCHEME == HARMONIC_THRESHOLD) {
                                if (current_thresh > 10 && current_thresh < 15) {
                                    current_thresh = 10;
                                } else if (current_thresh > 15 && current_thresh < 20) {
                                    current_thresh = 15;
                                } else if (current_thresh > 20 && current_thresh < 25) {
                                    current_thresh = 20;
                                } else if (current_thresh > 25 && current_thresh < 30) {
                                    current_thresh = 25;
                                } else if (current_thresh > 30 && current_thresh < 35) {
                                    current_thresh = 30;
                                } else if (current_thresh > 35 && current_thresh < 40) {
                                    current_thresh = 35;
                                } else if (current_thresh > 40 && current_thresh < 45) {
                                    current_thresh = 40;
                                } else if (current_thresh > 45 && current_thresh < 50) {
                                    current_thresh = 45;
                                } else {
                                    current_thresh = 50;
                                }

                                bit<19> inv_curr_thresh;
                                inverse_thresh.read(inv_curr_thresh, (bit<32>)current_thresh);
                                bit<19> threshold_k = K * threshold;
                                bit<19> inv_thresh;
                                inverse_thresh.read(inv_thresh, (bit<32>)threshold_k);
                                inv_curr_thresh = inv_curr_thresh - inv_thresh;
                                if (inv_curr_thresh > 10 && inv_curr_thresh < 15) {
                                    inv_curr_thresh = 10;
                                } else if (inv_curr_thresh > 15 && inv_curr_thresh < 20) {
                                    inv_curr_thresh = 15;
                                } else if (inv_curr_thresh > 20 && inv_curr_thresh < 25) {
                                    inv_curr_thresh = 20;
                                } else if (inv_curr_thresh > 25 && inv_curr_thresh < 30) {
                                    inv_curr_thresh = 25;
                                } else if (inv_curr_thresh > 30 && inv_curr_thresh < 35) {
                                    inv_curr_thresh = 30;
                                } else if (inv_curr_thresh > 35 && inv_curr_thresh < 40) {
                                    inv_curr_thresh = 35;
                                } else if (inv_curr_thresh > 40 && inv_curr_thresh < 45) {
                                    inv_curr_thresh = 40;
                                } else if (inv_curr_thresh > 45 && inv_curr_thresh < 50) {
                                    inv_curr_thresh = 45;
                                } else {
                                    inv_curr_thresh = 50;
                                }
                                
                                inverse_thresh.read(current_thresh, (bit<32>)inv_curr_thresh);
                            }
                        }

                        pcn_port_data.write((bit<32>)standard_metadata.ingress_port, current_data);
                        pcn_port_thresh.write((bit<32>)standard_metadata.ingress_port, current_thresh);

                    }
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

        pcn_port_data_t current_data;
        pcn_port_data.read(current_data, (bit<32>)standard_metadata.ingress_port);

        pcn_port_thresh_t current_thresh;
        pcn_port_thresh.read(current_thresh, (bit<32>)standard_metadata.ingress_port);

        if (current_data > 0) {
            if (hdr.ipv4.srcAddr == FLOW1 || hdr.ipv4.srcAddr == FLOW2 ||
                hdr.ipv4.srcAddr == FLOW3 || hdr.ipv4.srcAddr == FLOW4 ||
                hdr.ipv4.srcAddr == FLOW5 || hdr.ipv4.srcAddr == FLOW6 ) {
                if(hdr.tcp.syn == 0 && current_len >= ECN_THRESHOLD) {
                    mark_ecn();
                }
            } else {
                if (current_len >= current_thresh) {
                    mark_ecn();
                }
            }

        } else {
            if (hdr.ipv4.ecn == 1 || hdr.ipv4.ecn ==2) {
                if (current_len > ECN_THRESHOLD) {
                    mark_ecn();
                }
            }
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