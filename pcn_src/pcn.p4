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

// Define a single resister to store pcn_port_data_t
struct pcn_port_data_t {
    bit<1> pcn_enabled;
    bit<19> threshold;
    bit<16> number_of_flows;
}

// Define a single register to store flow details
struct flow_key_t {
    bit<1> flag;
    ip4Addr_t srcAddr;
    ip4Addr_t dstAddr;
    bit<16> srcPort;
    bit<16> dstPort;
    bit<19> threshold;
}

// Define register to store ingress queue length for pakcets
struct queue_len_t{
    bit<16> queue_length;
}

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

    action handle_pcn_start (egreessSpec_t port){
        pcn_port_data_t current_data;
        pcn_port_data.read(current_data, (bit<32>)port);

        current_data.number_of_flows = current_data.number_of_flows + 1;
        if(current_data.pcn_enabled == 0){
            current_data.pcn_enabled = 1;
            current_data.threshold = threshold;
        }else{
            if(THRESHOLD_SCHEME == MIN_THRESHOLD){
                // use minimum of current_data.threshold and threshold
                if(current_data.threshold > threshold){
                    current_data.threshold = threshold;
                }
            }else if (THRESHOLD_SCHEME == HARMONIC_THRESHOLD){
                current_data.threshold = 1/(1/current_data.threshold + 1/threshold);
            }
        }
        
        pcn_port_data.write((bit<32>)port, current_data);

        flow_key_t current_flow;
        current_flow.flag = 1;
        current_flow.srcAddr = hdr.ipv4.srcAddr;
        current_flow.dstAddr = hdr.ipv4.dstAddr;
        current_flow.srcPort = hdr.tcp.srcPort;
        current_flow.dstPort = hdr.tcp.dstPort;
        current_flow.threshold = threshold;

        flow_key.write(reg_pos, current_flow);
    }

    action handle_pcn_reset (egreessSpec_t port) {
        flow_key_t current_flow;
        flow_key.read(current_flow, reg_pos);
        threshold = current_flow.threshold;

        if(current_flow.flag == 1){
            current_flow.flag = 0;
            current_flow.srcAddr = 0;
            current_flow.dstAddr = 0;
            current_flow.srcPort = 0;
            current_flow.dstAddr = 0;
            current_flow.threshold = 0;

            flow_key.write(reg_pos, current_flow);

            pcn_port_data_t current_data;
            pcn_port_data.read(current_data, (bit<32>)port);

            current_data.number_of_flows = current_data.number_of_flows - 1;
            if(current_data.number_of_flows == 0){
                current_data.pcn_enabled = 0;
                current_data.threshold = ECN_THRESHOLD;
            }else{
                if(THRESHOLD_SCHEME == HARMONIC_THRESHOLD){
                    current_data.threshold = 1/(1/current_data.threshold - 1/threshold);
                }
            }

            pcn_port_data.write((bit<32>)port, current_data);
        }
    }

    action drop(){
        mark_to_drop(standard_metadata);
    }               

    action compute_hash(ip4Addr_t srcAddr, ip4Addr_t dstAddr, bit<16> srcPort, bit<16> dstPort){
        // Get register position
        hash(reg_pos, HashAlgorithm.crc32, (bit<32>)0, {
            srcAddr, dstAddr, srcPort, dstPort
        }, (bit<32>)1024);

        reg_pos = reg_pos % NUM_FLOWS;
    }

    action ipv4_forward(macAddr_t dstAddr, egreessSpec_t port){
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
        if(hdr.ipv4.isValid() && hdr.tcp.isValid()){
            extract_pcn_threshold();
            
            // Compute hash
            compute_hash(hdr.ipv4.srcAddr, hdr.ipv4.dstAddr, hdr.tcp.srcPort, hdr.tcp.dstPort);

            //pcn specific logic
            if(pcn == PCN_START){
                handle_pcn_start(standard_metadata.ingress_port);
            }else if(pcn == PCN_RESET){
                handle_pcn_reset(standard_metadata.ingress_port);
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
        current_len.queue_length = (bit<16>)standard_metadata.enq_qdepth;

        queue_len.write((bit<32>)standard_metadata.ingress_port, current_len);
        if (hdr.ipv4.diffserve[5:4]!=PCN_START){
            pcn_port_data_t current_data;
            pcn_port_data.read(current_data, (bit<32>)standard_metadata.ingress_port);
            bit<4> buffer_pos = (bit<4>)(standard_metadata.enq_qdepth/3);
            if(current_data.pcn_enabled==1){
                if(hdr.ipv4.diffserve[5:4]!=0 && standard_metadata.enq_qdepth >= ECN_THRESHOLD){
                    mark_ecn();
                }else if(hdr.ipv4.diffserve[5:4]==0 && standard_metadata.enq_qdepth >= current_data.threshold){
                    mark_ecn();
                }
            }else{
                if(hdr.ipv4.ecn == 1 || hdr.ipv4.ecn == 2){
                    if(standard_metadata.enq_qdepth >= ECN_THRESHOLD){
                        mark_ecn();
                    }
                }
            }
            if(hdr.ipv4.diffserve[5:4]!=0){
                hdr.ipv4.diffserve[3:0] = buffer_pos;
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