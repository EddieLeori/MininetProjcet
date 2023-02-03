# Copyright (C) 2016 Nippon Telegraph and Telephone Corporation.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, DEAD_DISPATCHER, HANDSHAKE_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib import dpid as dpid_lib
from ryu.lib import stplib, hub
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.app import simple_switch_13

from ryu.controller import ofp_event
from ryu.lib.packet import ether_types
from ryu.topology.api import get_switch, get_link, get_host
from ryu.topology import event

from operator import attrgetter

import networkx as nx
import random

from ryu.lib.packet import arp
from ryu.lib.packet import ipv4
from ryu.lib.packet import icmp
import datetime
import time
import setting

ARP = arp.arp.__name__
ETHERNET = ethernet.ethernet.__name__
ETHERNET_MULTICAST = "ff:ff:ff:ff:ff:ff"
TREE_MODE = setting.TreeMode() # 哪種topo
TRAFFIC_PATH_TYPE = setting.MethodMode() # 塞車時使用的方法
MONITOR_PERIOD = 2
TOSHOW = setting.TOSHOW
LINK_BANDWIDTH_KBS = 10000 # 10000KBytes = 10MBytes
LINK_TRAFFIC_THRESHOLD_PERCENT = 0.1 # 10% LINK_BANDWIDTH_KBS
LINK_BACKGROUND_PENALTY_EDGE_PERCENT = 0
LINK_BACKGROUND_PENALTY_AGGREAGTION_PERCENT = 0
LINK_BACKGROUND_PENALTY_CORE_PERCENT = 0

class SimpleSwitch13(simple_switch_13.SimpleSwitch13):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    # _CONTEXTS = {'stplib': stplib.Stp}

    def __init__(self, *args, **kwargs):
        super(SimpleSwitch13, self).__init__(*args, **kwargs)
        # self.stp = kwargs['stplib']

        # init
        self.G = nx.DiGraph()
        self.dynamicG = None
        self.topology_api_app = self
        self.real_all_paths = {}# 舊路線(包含 src, dst)
        self.all_paths = {}     # 舊路線(不含 src, dst)
        self.datapaths = {} # switch datapath        
        self.mac = setting.MacCFG()
        self.last_add_flow = {} # 紀錄最後一次 add flow 的時間
        self.error_times = 0
        # arp
        self.arp_table = {}
        self.sw = {}
        
        # 監控
        self.port_features = {} # port 的設定狀態(不會變動) {dpid:{port:(config, state, curr_speed),},}
        self.stats = {} # 詢問 switch 回來的 reply 暫存
        self.flow_stats = {} # switch 的狀態 {dpid:{(1, src, dst):[(packet_count,byte_count,duration_sec,duration_nsec),,,,]},},}
        self.flow_speed = {} # switch 的速度 Bytes/s {dpid:{(1, src, dst):[speed,,,,],},}
        self.port_stats = {} # swtich port_stats: {(dpid, port):[(tx_bytes,rx_bytes,rx_errors,duration_sec,duration_nsec),,,,],}
        self.port_speed = {} # swtich port 的速度 Bytes/s {(dpid, port):[speed,,,,],}
        self.free_bandwidth = {} # 剩餘可用頻寬(不包含背景流量) KBytes/s {dpid:{port_no:free_bw,},}
        self.traffic = {} # 大象流
        self.traffic_enable = False
        self.problem_data = {}
        self.echoDelay = {} # controller <-> swtich 的 delay
        self.monitor_thread = hub.spawn(self._monitor)
        self.monitor_thread3 = hub.spawn(self.detector)

        # SAPSM
        self.choice_times = {} # 選此條路徑幾次的次數記錄 {'12-13-14':1,,}
        self.used_times = {} # 路徑的使用度紀錄 {'12-13':1,}

        # log compare
        self.node_cnt = 0 # 經過節點數的總和
        self.acc_time = 0.0 # 累積的搜尋時間
        self.acc_times = 0 # 累積的搜尋次數
        self.acc_cv = 0 # 累積 cv 值 link標準差/link平均值
        self.acc_cv_times = 0 # 累積 cv 次數
        self.max_path_cnt = 0
        setting.LogConfigInfo()

        # option
        self.down = False

    def delete_flow(self, datapath, dst=None):
        '''
            刪除 flow entry，若 port is None 刪除此節點全部 flow entry。
        '''
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        if dst is not None:
            # 刪除 flow
            match = parser.OFPMatch(eth_dst=dst)
            mod = parser.OFPFlowMod(
                datapath, command=ofproto.OFPFC_DELETE,
                idle_timeout=1500, hard_timeout=6000,
                out_port=ofproto.OFPG_ANY, out_group=ofproto.OFPG_ANY,
                priority=1, match=match)
            datapath.send_msg(mod)
            print('delete  flow:%2d %s' % (datapath.id, dst))
            # print('delete mac  :%2d %s %2s' % (dpid, dst, port))
        else:
            for dst in self.G[datapath.id].keys():
                match = parser.OFPMatch(eth_dst=dst)
                mod = parser.OFPFlowMod(
                    datapath, command=ofproto.OFPFC_DELETE,
                    out_port=ofproto.OFPP_ANY, out_group=ofproto.OFPG_ANY,
                    priority=1, match=match)
                datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        '''
            沒有規則的封包會傳送於此，進行記憶以及轉送。

                (dp)
                node
                /  \
               h1  h2
             (src)(dst)
        '''
        msg = ev.msg
        pkt = packet.Packet(msg.data)
        if len(pkt.get_protocols(ethernet.ethernet)) == 0:
            return
        eth = pkt.get_protocols(ethernet.ethernet)[0]
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return
        arp_pkt = pkt.get_protocol(arp.arp)
        ip_pkt = pkt.get_protocol(ipv4.ipv4)

        datapath = msg.datapath
        dpid = datapath.id
        dst = eth.dst
        src = eth.src
        in_port = msg.match['in_port']

        # update networkx gragh
        self.update_topo(dpid, src, in_port)

        if isinstance(arp_pkt, arp.arp):
            self.arp_work(pkt, dpid, arp_pkt.src_mac, arp_pkt.dst_mac, in_port, msg.buffer_id , msg.data)
            return 

        if isinstance(ip_pkt, ipv4.ipv4):
            # 同樣路徑 add flow 間隔1s以上
            # if self.is_allow_add(src, dst, dpid) is False:
            #     return
            self.logger.info("---------------------------------------------------------------------%s" % (str(self.error_times)))
            self.logger.info("packet in %2s %s %s %s" % (dpid, src, dst, in_port))
            self.ip_work(ip_pkt, dpid, src, dst, in_port, eth.ethertype, msg.buffer_id, msg.data)
            return
                
    def update_topo(self, dpid, src, inport):
        '''
            更新 host，topo 一開始 host 資料不完整
        '''
        if src not in self.G and \
            self.ishost(src):
            if self.get_sw(src) == dpid:
                print("add node= %s <-> %s" % (str(src), str(dpid)))
                self.G.add_node(src)
                self.G.add_edge(dpid, src, attr_dict={'port':inport})
                self.G.add_edge(src, dpid)
                print(self.G)
                '''for node in self.G.nodes:
                    print('node=%s %s' % (node, self.G[node]))
                    '''

    def get_port(self, topo, src, dst):
        '''
            取得此來源到目的的port (src 出去到 sdt 的 port)
        '''
        return topo[src][dst]['attr_dict']['port']

    def arp_work(self, pkt, dpid, src, dst, in_port, buffer_id, data):
        '''
            如果目標已經知道就直接轉發，否則 OFPP_FLOOD(群發)
        '''
        # showlog = False

        header_list = dict(
            (p.protocol_name, p)for p in pkt.protocols if type(p) != str)
        if ARP in header_list:
            self.arp_table[header_list[ARP].src_ip] = src  # ARP learning
        
        pkt = pkt.get_protocol(arp.arp)

        # if showlog is True:
        #     self.logger.info("---------------------------------------------------------------------")
        #     self.logger.info("packet in %2s %s %s %s", dpid, src, dst, in_port)
        #     if pkt.opcode == arp.ARP_REQUEST:
        #         print("ARP")
        #     elif pkt.opcode == arp.ARP_REPLY:
        #         print("ARP_REPLY")
        #     else:
        #         print("ARP processing = ", pkt.opcode)
                
        datapath = self.datapaths[dpid]
        out_port = datapath.ofproto.OFPP_FLOOD
        if dst in self.G:
            todpid = self.get_sw(dst)
            out_port = self.get_port(self.G, todpid, dst)
            datapath = self.datapaths[todpid]
            in_port = datapath.ofproto.OFPP_CONTROLLER
            # if showlog is True:
            #     print('arp sended ok %s -> %s' %(dpid, todpid))
        elif self.arp_handler(header_list, datapath, in_port, buffer_id):
            return None
        self.send_msg(datapath, in_port, out_port, buffer_id, data)

    def arp_handler(self, header_list, datapath, in_port, msg_buffer_id):
        header_list = header_list
        datapath = datapath
        in_port = in_port
 
        if ETHERNET in header_list:
            eth_dst = header_list[ETHERNET].dst
            eth_src = header_list[ETHERNET].src
 
        if eth_dst == ETHERNET_MULTICAST and ARP in header_list:
            arp_dst_ip = header_list[ARP].dst_ip
            if (datapath.id, eth_src, arp_dst_ip) in self.sw:  # Break the loop
                if self.sw[(datapath.id, eth_src, arp_dst_ip)] != in_port:
                    out = datapath.ofproto_parser.OFPPacketOut(
                        datapath=datapath,
                        buffer_id=datapath.ofproto.OFP_NO_BUFFER,
                        in_port=in_port,
                        actions=[], data=None)
                    datapath.send_msg(out)
                    return True
            else:
                self.sw[(datapath.id, eth_src, arp_dst_ip)] = in_port
 
        if ARP in header_list:
            hwtype = header_list[ARP].hwtype
            proto = header_list[ARP].proto
            hlen = header_list[ARP].hlen
            plen = header_list[ARP].plen
            opcode = header_list[ARP].opcode
 
            arp_src_ip = header_list[ARP].src_ip
            arp_dst_ip = header_list[ARP].dst_ip
 
            actions = []
 
            if opcode == arp.ARP_REQUEST:
                if arp_dst_ip in self.arp_table:  # arp reply
                    actions.append(datapath.ofproto_parser.OFPActionOutput(
                        in_port)
                    )
 
                    ARP_Reply = packet.Packet()
                    ARP_Reply.add_protocol(ethernet.ethernet(
                        ethertype=header_list[ETHERNET].ethertype,
                        dst=eth_src,
                        src=self.arp_table[arp_dst_ip]))
                    ARP_Reply.add_protocol(arp.arp(
                        opcode=arp.ARP_REPLY,
                        src_mac=self.arp_table[arp_dst_ip],
                        src_ip=arp_dst_ip,
                        dst_mac=eth_src,
                        dst_ip=arp_src_ip))
 
                    ARP_Reply.serialize()
 
                    out = datapath.ofproto_parser.OFPPacketOut(
                        datapath=datapath,
                        buffer_id=datapath.ofproto.OFP_NO_BUFFER,
                        in_port=datapath.ofproto.OFPP_CONTROLLER,
                        actions=actions, data=ARP_Reply.data)
                    datapath.send_msg(out)
                    return True
        return False

    def ip_work(self, pkt, dpid, src, dst, in_port, ethertype, buffer_id, data):
        '''
            處理 ipv4 flow entry 規則設定與轉送封包
            if topo complete:
                if traffic
                    path function
                else
                    path default
            else
                OFPP_FLOOD
        '''
        # showlog = False
        # if showlog is True:
        #     pkt_icmp = pkt.get_protocol(icmp.icmp)
        #     if pkt_icmp.type == icmp.ICMP_ECHO_REQUEST:
        #         print("ipv4 ICMP_ECHO_REQUEST = ", pkt_icmp.type)
        #     elif pkt_icmp.type == icmp.ICMP_ECHO_REPLY:
        #         print("ipv4 ICMP_ECHO_REPLY   = ", pkt_icmp.type)
        #     else:
        #         print("ipv4 processing = ", pkt_icmp.type)
        
        try:
            datapath = self.datapaths[dpid]
            out_port = datapath.ofproto.OFPP_FLOOD
            if dst in self.G and src in self.G:
                # # 同樣路徑 add flow 間隔1s以上
                # if self.is_allow_add(src, dst, dpid) is False:
                #     return
                path = None
                dtime = None
                if self.traffic_enable is True and \
                    self.mac[src] != self.mac[dst]:
                    path, dtime = self.get_traffic_path(src, dst)
                else:
                    path, dtime = self.get_init_path(src, dst)
                # print('path=%s time=%s' % (path, dtime/1000000)) # microsecond -> second
                print('path=%s time=%s' % (path, dtime))
                
                # 如果現在在路徑上就轉發下個dp，若否則轉發路徑第一個dp
                dpid_next = None
                if dpid in path:
                    dpid_next = path[path.index(dpid)+1]
                    out_port = self.get_port(self.G, dpid, dpid_next)
                else:
                    first_dpid = self.get_sw(path[0])
                    datapath = self.datapaths[first_dpid]
                    dpid_next = path[path.index(first_dpid)+1]
                    in_port = datapath.ofproto.OFPP_CONTROLLER
                    out_port = self.get_port(self.G, first_dpid, dpid_next)
                
                # add flow entry (just once)
                if (src,dst,dpid) not in self.real_all_paths.keys():
                    self.real_all_paths.setdefault((src,dst,dpid), [])
                    self.real_all_paths[(src,dst,dpid)] = path
                    self.install_flow_by_path(path, ethertype)
                    # self.install_flow(dpid, src, dst, in_port, out_port, ethertype)

                # print('send_msg %2s -> %2s in=%2s out=%2s' % (datapath.id, dpid_next, in_port, out_port))
            self.send_msg(datapath, in_port, out_port, buffer_id, data)
        except Exception as e:
            print("*************************************************************************")
            print("*************************************************************************Exception!:%s" % (e))
            for node in self.G.nodes:
                print('= ', node)
                print(self.G[node])
            self.error_times += 1
            time.sleep(60)
        
    def add_flow2(self, datapath, priority, match, actions, buffer_id=None):
        '''
            新增 flow entry
        '''
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]
        if buffer_id:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,
                                    idle_timeout=1500, hard_timeout=6000, command=ofproto.OFPFC_ADD,
                                    priority=priority, match=match,
                                    instructions=inst)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    idle_timeout=1500, hard_timeout=6000, command=ofproto.OFPFC_ADD,
                                    match=match, instructions=inst)
        datapath.send_msg(mod)

    def install_flow(self, dpid, src, dst, in_port, out_port, ethertype):
        '''
            新增 flow entry
        '''
        dp = self.datapaths[dpid]
        parser = dp.ofproto_parser
        actions = [parser.OFPActionOutput(out_port)]
        match = parser.OFPMatch(\
            in_port=in_port, eth_src=src, eth_dst=dst, eth_type=ethertype)
        # match = parser.OFPMatch(eth_dst=dst, eth_src=src, eth_type=ethertype)
        # match = parser.OFPMatch(in_port=in_port, eth_dst=dst)
        self.add_flow2(dp, 1, match, actions)
        print('add flow  %2s %s %s inport:%2s outport:%2s ethertype=%s' % (dpid, src, dst, in_port, out_port, ethertype))

    def install_flow_by_path(self, path, ethertype):
        '''
            依照路徑個別新增 flow entry
            host to host
        '''
        if path is None or len(path) < 3:
            print('install_flow_by_path error:path!')
            return
        # print('path    =%s' % (path))
        for idx in range(1, len(path)-1):
            dpid_pre, dpid_now, dpid_next = path[idx-1], path[idx], path[idx+1] 
            inport = self.get_port(self.G, dpid_now, dpid_pre)
            outport = self.get_port(self.G, dpid_now, dpid_next)
            self.install_flow(dpid_now, path[0], path[-1], inport, outport, ethertype)

    def send_msg(self, datapath, in_port, out_port, buffer_id, msg_data):
        '''
            轉發封包
        '''
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        actions = [parser.OFPActionOutput(out_port)]

        data = None
        if buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg_data

        out = parser.OFPPacketOut(datapath=datapath, buffer_id=buffer_id,
                                    in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out) 

    def get_sw(self, src):
        '''
            取得 host 連接的 dp
        '''
        if src in self.mac:
            return self.mac[src]
        return src
    
    def get_dynamic_G(self):
        '''
            取得排除非正常FORWARD狀態的可用 topo
        '''
        if self.dynamicG is not None:
            return self.dynamicG

        dynamic_g = nx.DiGraph()
        nodes = [node for node in self.G.nodes]
        dynamic_g.add_nodes_from(nodes)
        
        link_list = get_link(self.topology_api_app, None)
        links = []
        for link in link_list:
            l1src, l1dst, l1port = link.src.dpid, link.dst.dpid, link.src.port_no
            l2src, l2dst, l2port = link.dst.dpid, link.src.dpid, link.dst.port_no
            if self.ishost(l1src) is False and self.ishost(l1dst) is False:
                if self.port_speed[(l1src, l1port)][-1] < (LINK_BANDWIDTH_KBS * 0.5 * 1000):
                    links.append((l1src, l1dst, {'attr_dict': {'port': l1port}}))
                if self.port_speed[(l2src, l2port)][-1] < (LINK_BANDWIDTH_KBS * 0.5 * 1000):   
                    links.append((l2src, l2dst, {'attr_dict': {'port': l2port}}))
        dynamic_g.add_edges_from(links)
        # for host in self.mac.keys():
        #     node = self.mac[host]
        #     port = self.get_port(self.G, node, host)
        #     dynamic_g.add_edge(node, host, attr_dict={'port':port})
        #     dynamic_g.add_edge(host, node)
        
        # print('self.G=')
        # for node in self.G.nodes:
        #     print('= ', node)
        #     print(self.G[node])
        # print('dynamicG=')
        # for node in dynamic_g.nodes:
        #     print('= ', node)
        #     print(dynamic_g[node])
        self.dynamicG = dynamic_g
        return self.dynamicG
        
    def get_link_background_penalty(self, dp1, dp2):
        percent = 1
        core_dps = [1, 2, 3, 4]
        aggregatoin_dps = [5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]
        edge_dps = self.mac.keys()
        if dp1 in core_dps or dp2 in core_dps:
            percent = LINK_BACKGROUND_PENALTY_CORE_PERCENT
        elif dp1 in aggregatoin_dps or dp2 in aggregatoin_dps:
            percent = LINK_BACKGROUND_PENALTY_AGGREAGTION_PERCENT
        elif dp1 in edge_dps or dp2 in edge_dps:
            percent = LINK_BACKGROUND_PENALTY_EDGE_PERCENT
        else:
            print('<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< get_link_background_penalty error')
            return None
        return LINK_BANDWIDTH_KBS * percent

    def get_free_bandwidth(self, dp1, dp2):
        # penalty = self.get_penalty(dp1, dp2) # Bytes/s
        # free = LINK_BANDWIDTH_KBS # KBytes
        # return max((free * 1000 - penalty), 0) # Bytes
        if self.ishost(dp1) is True:
            # return 0
            port = self.get_port(self.G, dp2, dp1)
            return self.free_bandwidth[dp2][port] # Bytes/s
        port = self.get_port(self.G, dp1, dp2)
        return self.free_bandwidth[dp1][port] # Bytes/s

    def get_free_bandwidth_by_path(self, path):
        free = 0
        for idx in range(1, len(path)):
            free += self.get_free_bandwidth(path[idx-1], path[idx])
        return free # Bytes/s

    def update_free_bandwidth(self, src, dst, path):
        if (src,dst) in self.problem_data.keys() and len(path) > 1:
            link_load_flow = self.problem_data[(src,dst)] / (len(path) - 1)
            for idx in range(1, len(path)):
                dp1, dp2 = path[idx-1], path[idx]
                port = self.get_port(self.G, dp1, dp2)
                free = max(self.get_free_bandwidth(dp1, dp2)-link_load_flow ,0)
                self.free_bandwidth[dp1][port] = free

    def get_init_path(self, src, dst):
        '''
            預設路徑方法
        '''
        # log
        if self.traffic_enable is False:
            testps = len(list(nx.all_simple_paths(self.G, source=self.get_sw(src), target=self.get_sw(dst))))
            self.max_path_cnt += testps

        # call init path method
        s_time = datetime.datetime.now()
        result = self.get_path(src, dst)
        e_time = datetime.datetime.now()
        return result, (e_time - s_time).microseconds
        
    def get_traffic_path(self, src, dst):
        '''
            當塞車條件達成時選用的路徑方法
        '''
        s_time = datetime.datetime.now()
        result = None
        if TRAFFIC_PATH_TYPE == setting.PATH_IFOSA:
            result = self.get_path1(src, dst)
        elif TRAFFIC_PATH_TYPE == setting.PATH_SAPSM:
            result = self.get_path2(src, dst)
        elif TRAFFIC_PATH_TYPE == setting.PATH_SAPSM_DELAY:
            result = self.get_path2(src, dst)
        else:
            print('<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<get_traffic_path error')
            return None, 0
        e_time = datetime.datetime.now()
        return result, (e_time - s_time).microseconds

    def get_path(self, src, dst):
        '''
            取得最短跳數路徑，多條時隨機選擇。
        '''
        # 1. 判斷是否計算過
        key = '%s-%s' % (self.get_sw(src), self.get_sw(dst))
        if key in self.all_paths:
            path = self.all_paths[key].copy()
            path.insert(0, src)
            path.append(dst)
            return path

        s_time = datetime.datetime.now()

        # 2. 算出到達目標最短路徑
        paths = [path for path in nx.all_shortest_paths(\
            self.G, source=src, target=dst)]
        # print('paths   =%s' % (paths))

        # 3. 隨機選擇1條
        path = random.choice(paths)
        _path = path.copy()
        _path.pop(0)
        _path.pop(len(_path) - 1)
        self.all_paths[key] = _path

        if self.traffic_enable is True:
            self.updateLogInfo(s_time, _path)

        return path

    def get_path1(self, src, dst):
        '''
            迭代取得最短跳數路徑 (IFOSA)，多條時隨機選擇。
        '''
        s_time = datetime.datetime.now()

        # 1. 判斷是否計算過
        key = '%s-%s' % (self.get_sw(src), self.get_sw(dst))
        if key in self.all_paths:
            path = self.all_paths[key].copy()
            path.insert(0, src)
            path.append(dst)
            return path
        
        tmp_path = None
        for _ in range(setting.IFOSA_CFG['maxgen']):
            # 2. 計算最少跳數路徑
            # paths = [path for path in nx.all_shortest_paths(\
            #     self.G, source=self.get_sw(src), target=self.get_sw(dst))]
            paths = list(nx.all_simple_paths(self.G, source=self.get_sw(src), target=self.get_sw(dst)))
            paths = sorted(paths, key=len)
            paths = [path for path in paths if len(path) == len(paths[0])]
            # print('paths   =%s' % (paths))

            # 3. 隨機產生新解
            # _path = random.choice(paths).copy()
            _path = paths[0].copy()
            # _path.pop(0)
            # _path.pop(len(_path) - 1)

            # 4. FitnessFun
            if tmp_path is not None:
                old_f = self.FitnessFun(tmp_path, src, dst)
                new_f = self.FitnessFun(_path, src, dst)
                if new_f < old_f:
                    tmp_path = _path
            else:
                tmp_path = _path
        
        self.all_paths[key] = tmp_path
        out_path = tmp_path.copy()

        # log compare
        self.updateLogInfo(s_time, out_path)

        # 把 host 端加回來
        out_path.insert(0, src)
        out_path.append(dst)

        return out_path
    
    def get_path2(self, src, dst):
        '''
            迭代取得模擬退火路徑選擇方法 (SAPSM)
        '''
        s_time = datetime.datetime.now()
        if src not in self.G or dst not in self.G:
            print("get_path2 error!")
            return

        # 1. 判斷是否計算過
        # host 端不納入選擇計算中，因 host端link無法選擇，故從 edge 層開始計算
        src_sw, dst_sw = self.get_sw(src), self.get_sw(dst) # src, dst => src_sw, dst_sw
        key = '%s-%s' % (src_sw, dst_sw)
        # print('sw_src, sw_dst = %s %s' % (src_sw, dst_sw))
        if key in self.all_paths:
            out_path = self.all_paths[key].copy()
            out_path.insert(0, src)
            out_path.append(dst)
            return out_path
        
        # 2. get new path (networkx get all path for src_sw -> dst_sw)
        # 全部會經過的路徑
        # def_all_paths = []
        # if TREE_MODE == setting.FAT_TREE or TREE_MODE == setting.MESH_TREE:
        #     dynamic_topo = self.get_dynamic_G()
        #     def_all_paths = list(nx.all_simple_paths(dynamic_topo, source=src_sw, target=dst_sw))
        #     if len(def_all_paths) == 0:
        #         print('def_all_paths size=', str(len(def_all_paths)))
        #         def_all_paths = list(nx.all_simple_paths(self.G, source=src_sw, target=dst_sw))
        # else:
        #     def_all_paths = list(nx.all_simple_paths(self.G, source=src_sw, target=dst_sw))
        # dynamic_topo = self.get_dynamic_G()
        # def_all_paths = list(nx.all_simple_paths(dynamic_topo, source=src_sw, target=dst_sw))
        # if len(def_all_paths) == 0:
        #     print('def_all_paths size=', str(len(def_all_paths)))
        #     def_all_paths = list(nx.all_simple_paths(self.G, source=src_sw, target=dst_sw))
        def_all_paths = list(nx.all_simple_paths(self.G, source=src_sw, target=dst_sw))
        _setting = setting.SAPSM_CFG
        t_now = _setting['t_start'] # 目前迭代中退火的溫度
        self.choice_times = {} # 暫存迭代次數中路徑被選到的次數
        self.used_times = {}
        init_path = None
        tmp_path = None
        for idx in range(_setting['maxgen']):
            # 3. get F(S) by old path
            old_path = None
            if tmp_path is None: # 第一次進來隨機選一條路徑當起始路徑
                # old_path = random.choice(def_all_paths)
                # old_idx = def_all_paths.index(old_path)
                old_idx = 0
                old_path = def_all_paths[old_idx]
                tmp_path = old_path
                self.update_used_times(old_path)
                ckey = '-'.join(str(x) for x in old_path)
                self.choice_times.setdefault(ckey, 1)
                # print('first=%s c=%s f=%s load=%s'% 
                #     (old_path, self.get_cost(old_path, self.used_times[old_idx]), \
                #     self.get_free_bandwidth_by_path(old_path), \
                #     self.problem_data[(src, dst)]
                #     ))
            else:
                old_path = tmp_path
            old_f = self.FitnessFun(old_path, src, dst)

            # 4. get F(S') by new path
            new_path = self.get_low_cost_path(def_all_paths) # get cost path
            if init_path is None:
                init_path = new_path.copy()
            self.update_used_times(new_path)
            new_f = self.FitnessFun(new_path, src, dst)

            # 5. F(S') - F(S)
            # accept = 'X'
            if new_f <= old_f or (\
                (self.random_accept(old_f, new_f, _setting['t_start'], t_now) is True) and \
                (self.is_traffic_down(src, dst, new_path) is False)): # 選用新解
                tmp_path = new_path
                ckey = '-'.join(str(x) for x in new_path)
                self.choice_times.setdefault(ckey, 0)
                self.choice_times[ckey] = self.choice_times[ckey] + 1
                # accept = 'O'
            
            # print('(%s)[%2s]new=%s u=%s c=%s f=%s F=%s F\'=%s' % 
            #     (accept, idx, new_path, self.used_times[new_idx], \
            #     self.get_cost(new_path, self.used_times[new_idx]), \
            #     self.get_free_bandwidth_by_path(new_path), \
            #     old_f, new_f
            #     ))

            # 6. check end 檢查是否達到退出條件
            if max(self.choice_times.values()) >= _setting['win_times']:
                print('find the best path!')
                break
            elif idx == (_setting['maxgen']-1):
                print('maxgen stop!')
                tmp_path = init_path

            # 7. update: 退火
            t_now = max((t_now - _setting['t_down']), 0)

        self.all_paths[key] = tmp_path

        out_path = self.all_paths[key].copy()

        # update free bandwidth
        self.update_free_bandwidth(src, dst, out_path)

        # log compare
        self.updateLogInfo(s_time, out_path)

        # 把 host 端加回來
        out_path.insert(0, src)
        out_path.append(dst)

        return out_path

    def get_cv_by_path(self, path):
        '''
            取得 coefficient of variation (cv)值 變異係數
            cv = link 標準差 / link 平均值
        '''
        if path is None or len(path) < 1:
            print('get_cv_by_path path error!')
            return None
        total_link_free = self.get_free_bandwidth_by_path(path) # Bytes/s
        result = 0
        link_cnt = len(path) - 1
        av_link = total_link_free/link_cnt
        if av_link == 0:
            print('get_cv_by_path av_link 0')
            return 1
        for idx in range(1, len(path)):
            link_free = self.get_free_bandwidth(path[idx-1], path[idx]) # Bytes/s
            result += (link_free - av_link) ** 2                
        result = (result/link_cnt)**0.5 / av_link
        return result

    def get_cv_by_all_link(self):
        '''
            取得全部Link coefficient of variation (cv)值 變異係數
            cv = link 標準差 / link 平均值
        '''
        linkcnt = 0
        all_free_link = 0
        for node1 in self.G.nodes.keys():
            for node2 in self.G[node1].keys():
                linkcnt += 1
                all_free_link += self.get_free_bandwidth(node1, node2)
        if linkcnt == 0:
            print('get_cv_by_all_link error!')
            return None
        av_link = all_free_link / linkcnt
        cv = 0
        for node1 in self.G.nodes.keys():
            for node2 in self.G[node1].keys():
                cv += (self.get_free_bandwidth(node1, node2) - av_link) ** 2
        cv = ((cv / linkcnt) ** 0.5) / av_link
        print('linkcnt=%s' % (linkcnt))
        print('all_free_link=%s' % (all_free_link))
        print('av_link=%s' % (av_link))
        print('cv=%s' % (cv))
        return cv
    
    def get_fm_by_all_link(self):
        '''
            取得全部Link Fairness measure值
            FM = SUM(penalty)^2/(n*SUM(penalty^2))
            範圍 1/n ~ 1 (越接近1越好)
        '''
        linkcnt = 0
        all_penaltys = 0
        tmp_penaltys = 0
        for node1 in self.G.nodes.keys():
            for node2 in self.G[node1].keys():
                # if self.ishost(node1) == True or self.ishost(node2) == True:
                #     continue
                linkcnt += 1
                penalty = self.get_penalty(node1, node2)
                all_penaltys += penalty
                tmp_penaltys += penalty ** 2
        if linkcnt == 0 or all_penaltys == 0:
            print('get_fm_by_all_link error! linkcnt=%s all_penaltys=%s' % (linkcnt, all_penaltys))
            return None
        fm = (all_penaltys ** 2) / (linkcnt * tmp_penaltys)
        # print('linkcnt=%s' % (linkcnt))
        # print('all_penaltys=%s' % (all_penaltys))
        # print('tmp_penaltys=%s' % (tmp_penaltys))
        # print('fm=%s' % (fm))
        return fm

    def update_used_times(self, path):
        for idx in range(1, len(path)):
            key = "%s-%s" % (path[idx-1], path[idx])
            self.used_times.setdefault(key, 1)
            self.used_times[key] = self.used_times[key] * 2
        
    # def get_used_times(self, path):
    #     if path is None or len(path) < 1:
    #         print('get_used_times error!')
    #         return None
    #     times = 0
    #     for idx in range(1, len(path)):
    #         key = "%s-%s" % (path[idx-1], path[idx])
    #         if key not in self.used_times.keys():
    #             times += 1
    #         else:
    #             times += self.used_times[key]
    #     times = times / (len(path)-1)
    #     return times

    def random_accept(self, old_f, new_f, t_start, t_now):
        if old_f == new_f:
            return True
        if t_now == 0:
            return False
        r = random.random() # 0 ~ 1
        p = (1/(new_f-old_f))*(t_now/t_start)
        if p >= r:
            print('random accept')
        return p >= r

    def is_traffic_down(self, src, dst, new_path):
        '''
            判斷此新路徑是否會對舊路徑無法負荷
            return new_path_free - load_flow < 0
            True: 擁塞
        '''
        if new_path is None:
            print('is_traffic_down path error!')
            return None
        new_free = self.get_free_bandwidth_by_path(new_path)
        load_flow = self.problem_data[(src, dst)] if (src, dst) in self.problem_data.keys() else 0
        return (new_free - load_flow) < 0

    # def get_cost(self, path, times = 1):
    #     if path is None or len(path) == 0:
    #         print('get_cost error')
    #         return None
    #     penaltys = self.get_penaltys_by_path(path) # 各link使用流量
    #     linkcnt = len(penaltys)
    #     totall_penalty = sum(penaltys) # 此路總使用頻寬
    #     # load_penalty = 1
    #     load_penalty = len(path) - 1
    #     used = times # 使用率
    #     cost = 0
    #     if linkcnt == 0:
    #         print('get_cost error:totall_penalty=%s, linkcnt=%s' % (totall_penalty, linkcnt))
    #         return None
    #     if totall_penalty > 0:    
    #         # cost = 負載懲罰 * (路徑負載 + 路長*平均選用度 + 平均負載/路徑負載)
    #         cost = load_penalty * (totall_penalty + linkcnt * used + \
    #               (totall_penalty / linkcnt) / totall_penalty)
    #     return cost

    def get_low_cost_path(self, all_paths):
        '''
            取得最低的 cost 路徑
        '''
        if all_paths is None:
            print('get_low_cost_path error')
            return None
        min_idx, min_cost= 0, -1
        for idx in range(len(all_paths)):
            # cost = self.get_cost(all_paths[idx], self.get_used_times(all_paths[idx]))
            path = all_paths[idx]
            penaltys = [] # node 對應的使用頻寬
            for i in range(1, len(path)):
                penaltys.append(self.get_penalty(path[i-1], path[i])) # Bytes/s
            # penaltys = self.get_penaltys_by_path(path) # 各link使用流量
            linkcnt = len(penaltys)
            totall_penalty = sum(penaltys) # 此路總使用頻寬
            if linkcnt == 0:
                print('get_cost error:totall_penalty=%s, linkcnt=%s' % (totall_penalty, linkcnt))
                return None

            # load_penalty = 1
            load_penalty = linkcnt

            # used = self.get_used_times(path) # 使用率
            used = 0
            for i in range(1, len(path)):
                key = "%s-%s" % (path[i-1], path[i])
                if key not in self.used_times.keys():
                    used += 1
                else:
                    used += self.used_times[key]
            used = used / linkcnt

            cost = 0
            if totall_penalty > 0:    
                # cost = 負載懲罰 * (路徑負載 + 路長*平均選用度 + 平均負載/路徑負載)
                cost = load_penalty * (totall_penalty + linkcnt * used + \
                    (totall_penalty / linkcnt) / totall_penalty)
            if min_cost is -1 or min_cost > cost:
                min_cost = cost
                min_idx = idx
        return all_paths[min_idx] # , min_idx

    def get_penalty(self, dp1, dp2):
        if self.ishost(dp1):
            dp1, dp2 = dp2, dp1
        port = self.get_port(self.G, dp1, dp2)
        penalty = self.port_speed[(dp1, port)][-1]
        # background = self.get_link_background_penalty(dp1, dp2) * 1000 # KBytes -> Bytes
        # return penalty + background # Bytes/s
        return penalty # Bytes/s

    # def get_penaltys_by_path(self, path):
    #     '''
    #         取得路徑間 link 使用的流量
    #         ex:
    #         path = [1, 2, 3, 4, 5]
    #         return [2, 3, 4, 5]
    #     '''
    #     if path is None:
    #         print('get_penaltys_by_path error!')
    #         return None
    #     penaltys = [] # node 對應的使用頻寬
    #     for idx in range(1, len(path)):
    #         penaltys.append(self.get_penalty(path[idx-1], path[idx]))
    #     return penaltys  # Bytes/s
    
    def FitnessFun(self, path, src, dst):
        '''
            SAPSM 適應函數 越小越好
            sum((free - frees/cnt - speed)^2)/cnt
        '''
        if path is None or len(path) == 0:
            print('FitnessFun path error!')
            return None
        total_link_free = self.get_free_bandwidth_by_path(path) # Bytes/s
        result = 0
        link_cnt = len(path) - 1
        problem_penalty = 0 # Bytes/s
        if (src, dst) in self.problem_data.keys():
            problem_penalty = self.problem_data[(src, dst)]
        else:
            print('FitnessFun: problem_data is none=%s %s' % (src, dst))
        for idx in range(1, len(path)):
            link_free = self.get_free_bandwidth(path[idx-1], path[idx]) # Bytes/s
            result += (link_free - total_link_free/link_cnt - problem_penalty) ** 2                
        # print('total_link_free=', total_link_free)
        # print('linkcnt=', link_cnt)
        result = (result/link_cnt)
        if TRAFFIC_PATH_TYPE == setting.PATH_SAPSM_DELAY:
            # delay_time = self.get_echo_delay_by_path(path)
            # result = result * delay_time
            result = result * len(path)
        return result

    # EventOFPStatureChange的信息類用來監測交換器的連線中斷，會被觸發在#Dathpath狀態改變時
    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def _state_change_handler(self, ev):   
        '''
            switch(dp) 狀態改變時觸發
        '''
        datapath = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            if datapath.id not in self.datapaths:
                self.logger.info('register datapath: %016x', datapath.id)
                self.datapaths[datapath.id] = datapath
        elif ev.state == DEAD_DISPATCHER:
            if datapath.id in self.datapaths:
                self.logger.info('unregister datapath: %016x', datapath.id)
                del self.datapaths[datapath.id]
        else:
            pass

    @set_ev_cls(event.EventLinkAdd, [CONFIG_DISPATCHER, MAIN_DISPATCHER])
    def get_topo(self, ev):
        '''
            EventLinkAdd: 當 link 加入時觸發
            更新 self.G topo，但 host 資訊並不完整
        '''
        switch_list = get_switch(self.topology_api_app, None)
        switches = [switch.dp.id for switch in switch_list] 
        self.G.add_nodes_from(switches)

        link_list = get_link(self.topology_api_app, None)
        links = [(link.src.dpid, link.dst.dpid, {
                'attr_dict': {'port': link.src.port_no}}) for link in link_list]
        self.G.add_edges_from(links)
        links = [(link.dst.dpid, link.src.dpid, {
                'attr_dict': {'port': link.dst.port_no}}) for link in link_list]
        self.G.add_edges_from(links)
	
    @set_ev_cls(ofp_event.EventOFPErrorMsg, MAIN_DISPATCHER) # pylint: disable=no-member
    def _error_handler(self, ryu_event):
        """Handle an OFPError from a datapath.

        Args:
            ryu_event (ryu.controller.ofp_event.EventOFPErrorMsg): trigger
        """
        msg = ryu_event.msg
        ryu_dp = msg.datapath
        dp_id = ryu_dp.id
        print('*************************************************************************ofp_event.EventOFPErrorMsg')
        print('dpid=%s msg=%s' % (dp_id, msg))

    @set_ev_cls(ofp_event.EventOFPPortDescStatsReply, MAIN_DISPATCHER)
    def port_desc_stats_reply_handler(self, ev):
        # print('EventOFPPortDescStatsReply')
        """
			Save port description info.
            port 的描述、狀態、速度
		"""
        msg = ev.msg
        dpid = msg.datapath.id
        ofproto = msg.datapath.ofproto

        config_dict = {ofproto.OFPPC_PORT_DOWN: "Down",
					   ofproto.OFPPC_NO_RECV: "No Recv",
					   ofproto.OFPPC_NO_FWD: "No Farward",
					   ofproto.OFPPC_NO_PACKET_IN: "No Packet-in"}

        state_dict = {ofproto.OFPPS_LINK_DOWN: "Down",
					  ofproto.OFPPS_BLOCKED: "Blocked",
					  ofproto.OFPPS_LIVE: "Live"}

        # ports = []
        for p in ev.msg.body:
            # ports.append('port_no=%d hw_addr=%s name=%s config=0x%08x '
			# 			 'state=0x%08x curr=0x%08x advertised=0x%08x '
			# 			 'supported=0x%08x peer=0x%08x curr_speed=%d '
			# 			 'max_speed=%d' %
			# 			 (p.port_no, p.hw_addr,
			# 			  p.name, p.config,
			# 			  p.state, p.curr, p.advertised,
			# 			  p.supported, p.peer, p.curr_speed,
			# 			  p.max_speed))

            if p.config in config_dict:
                config = config_dict[p.config]
            else:
                config = "up"

            if p.state in state_dict:
                state = state_dict[p.state]
            else:
                state = "up"

			# Recording data.
            port_feature = (config, state, p.curr_speed)
            self.port_features.setdefault(dpid, {})
            self.port_features[dpid][p.port_no] = port_feature

	# 對FlowStatsReply消息的回覆進行事件處理
    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def _flow_stats_reply_handler(self, ev):
        print('EventOFPFlowStatsReply')
        '''
            switch(dp) 狀態資訊
            flow_stats: packet_count、byte_count、duration_sec、duration_nsec
            flow_speed: 速度差
        '''
        # body中存放了OFPFlowStats的列表，存儲了每一個Flow Entry的統計資料，並作爲OFPFlowStatsRequest的迴應
        body = ev.msg.body  

        # showlog = False
        # if showlog is True:
        #     Showd = False
        #     # 對各個優先級非0的流表項按接收端口和目的MAC地址進行排序後遍歷
        #     for stat in sorted([flow for flow in body if flow.priority == 1],
        #                     key=lambda flow: (flow.match.get('eth_src'),
        #                                         flow.match.get('eth_dst'))):
        #         if Showd is False:
        #             self.logger.info('datapath         ''eth_src            eth-dst          ''in-port  out-port')
        #             self.logger.info('---------------- ''----------------- ----------------- ''-------- --------')
        #             Showd = True
        #         # 對交換機的datapath.id，目的MAC地址，輸出端口和包以及字節流量進行打印
        #         self.logger.info('%016x %17s %17s %2s         %2s',
        #                          ev.msg.datapath.id,
        #                          stat.match.get('eth_src'), stat.match.get('eth_dst'),
        #                          stat.match.get('in_port'), stat.instructions[0].actions[0].port)
        dpid = ev.msg.datapath.id
        self.stats['flow'][dpid] = body
        self.flow_stats.setdefault(dpid, {})
        self.flow_speed = {}
        self.flow_speed.setdefault(dpid, {})
        for stat in sorted([flow for flow in body if ((flow.priority not in [0, 65535]) and (flow.match.get('eth_src')) and (flow.match.get('eth_dst')))], 
                            key=lambda flow: (flow.priority, flow.match.get('eth_src'), flow.match.get('eth_dst'))):
            key = (stat.priority, stat.match.get('eth_src'), stat.match.get('eth_dst'))
            value = (stat.packet_count, stat.byte_count, stat.duration_sec, stat.duration_nsec)
            self._save_stats(self.flow_stats[dpid], key, value, 5) # 只存最新 5 筆

			# Get flow's speed and Save it.
            pre = 0
            period = MONITOR_PERIOD
            tmp = self.flow_stats[dpid][key]
            if len(tmp) > 1: # 1 筆以上
                pre = tmp[-2][1] # 前1筆的byte_count
                period = self._get_period(tmp[-1][2], tmp[-1][3], # 最新1筆duration_sec, duration_nsec
										  tmp[-2][2], tmp[-2][3]) #   前1筆duration_sec, duration_nsec
            speed = self._get_speed(self.flow_stats[dpid][key][-1][1], pre, period)
            self._save_stats(self.flow_speed[dpid], key, speed, 5)

	# 對PortStatsReply消息的回覆事件進行處理    
    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def _port_stats_reply_handler(self, ev):
        # print('EventOFPPortStatsReply')
        '''
            switch(dp) port 狀態資訊
            port_stats: tx_bytes、rx_bytes、rx_errors、duration_sec、duration_nsec
            port_speed: 速度
        '''
        '''
        body = ev.msg.body

        self.logger.info('datapath         port     '
                         'rx-pkts  rx-bytes rx-error '
                         'tx-pkts  tx-bytes tx-error')
        self.logger.info('---------------- -------- '
                         '-------- -------- -------- '
                         '-------- -------- --------')
        # 根據端口號進行排序並遍歷
        for stat in sorted(body, key=attrgetter('port_no')):
        	# 打印交換機id，端口號和接收及發送的包的數量字節數和錯誤數
            self.logger.info('%016x %8x %8d %8d %8d %8d %8d %8d',
                             ev.msg.datapath.id, stat.port_no,
                             stat.rx_packets, stat.rx_bytes, stat.rx_errors,
                             stat.tx_packets, stat.tx_bytes, stat.tx_errors)
        '''
        body = ev.msg.body
        dpid = ev.msg.datapath.id
        self.stats['port'][dpid] = body
        for stat in sorted(body, key=attrgetter('port_no')):
            port_no = stat.port_no
            if port_no != ofproto_v1_3.OFPP_LOCAL:
                key = (dpid, port_no)
                value = (stat.tx_bytes, stat.rx_bytes, stat.rx_errors,
						 stat.duration_sec, stat.duration_nsec)
                self._save_stats(self.port_stats, key, value, 5)

				# Get port speed and Save it.
                pre = 0
                period = MONITOR_PERIOD
                tmp = self.port_stats[key]
                if len(tmp) > 1:
					# Calculate only the tx_bytes, not the rx_bytes. (hmc)
                    pre = tmp[-2][0]
                    period = self._get_period(tmp[-1][3], tmp[-1][4], tmp[-2][3], tmp[-2][4])
                speed = self._get_speed(self.port_stats[key][-1][0], pre, period)
                self._save_stats(self.port_speed, key, speed, 5)
                self._save_freebandwidth(dpid, port_no, speed)
    
    def ishost(self, src):
        '''
            是否是 host 主機
        '''
        return src in self.mac.keys()
    
    def _monitor(self):
        '''
            緒 定期發送要求、更新目前狀態、監聽流量是否達塞車條件
            OFPPortDescStatsRequest -> EventOFPPortDescStatsReply
            OFPFlowStatsRequest -> EventOFPFlowStatsReply
            OFPPortStatsRequest -> EventOFPPortStatsReply
        '''
        while True:
            # print('OFPPortDescStatsRequest')
            self.stats['flow'] = {}
            self.stats['port'] = {}
            for datapath in self.datapaths.values():               
                # self.logger.debug('send stats request: %016x', datapath.id)
                ofproto = datapath.ofproto
                parser = datapath.ofproto_parser
                req = parser.OFPPortDescStatsRequest(datapath, 0)
                datapath.send_msg(req)
                req = parser.OFPFlowStatsRequest(datapath)
                datapath.send_msg(req)
                req = parser.OFPPortStatsRequest(datapath, 0, ofproto.OFPP_ANY)
                datapath.send_msg(req)
            hub.sleep(MONITOR_PERIOD)
            # if self.stats['flow'] or self.stats['port']:
            #     # self.show_stat('flow')
            #     # self.show_stat('port')
            self.check_traffic()
            hub.sleep(1)

            # log compare
            self.logInfo()
    
    def detector(self):
        while True:
            self.send_echo_request()
            hub.sleep(2)
    
    def logInfo(self):
        # log compare
        if self.acc_times != 0:
            setting.LogConfigInfo()
            print('node cnt= %s' % (self.node_cnt))
            print('av node cnt= %s' % (self.node_cnt / self.acc_times))
            print('algo= %s' % ((self.acc_time / self.acc_times) / 1000)) # microsecond -> msecond
            print('fm= %s' % (self.acc_cv / self.acc_cv_times))
            print('acc_times= %s' % (self.acc_times))
            print('all_paths_cont= %s' % (self.max_path_cnt))

    def updateLogInfo(self, stime, path):
        self.node_cnt += len(path)
        e_time = datetime.datetime.now()
        self.acc_time += (e_time - stime).microseconds
        self.acc_times += 1
        self.acc_cv += self.get_fm_by_all_link()
        self.acc_cv_times += 1

    # 由控制器向交换机发送echo报文，同时记录此时时间
    def send_echo_request(self):
        # 循环遍历交换机，逐一向存在的交换机发送echo探测报文
        for datapath in self.datapaths.values():
            echo_req = datapath.ofproto_parser.OFPEchoRequest(\
                datapath, data=bytes("%.12f" % time.time(), encoding="utf8"))  # 获取当前时间
            datapath.send_msg(echo_req)
            # 每隔0.5秒向下一个交换机发送echo报文，防止回送报文同时到达控制器
            hub.sleep(0.5)

    # 交换机向控制器的echo请求回应报文，收到此报文时，控制器通过当前时间-时间戳，计算出往返时延
    @set_ev_cls(ofp_event.EventOFPEchoReply, [MAIN_DISPATCHER, CONFIG_DISPATCHER, HANDSHAKE_DISPATCHER])
    def echo_reply_handler(self, ev):
        now_timestamp = time.time()
        try:
            echo_delay = now_timestamp - eval(ev.msg.data)
            # 将交换机对应的echo时延写入字典保存起来
            self.echoDelay[ev.msg.datapath.id] = echo_delay
        except Exception as error:
            print("echo error:", error)
            return

    def get_echo_delay_by_path(self, path):
        if path is None:
            print('get_delay_penalty_by_path error')
            return None
        delay_time = 0
        for idx in range(1, len(path)):
            delay_time += self.echoDelay[path[idx-1]] + self.echoDelay[path[idx]]
        return delay_time

    def get_add_delay_penalty(self, dp1, dp2):
        return (self.echoDelay[dp1] + self.echoDelay[dp2]) * LINK_BANDWIDTH_KBS * 1000 # Bytes/s

    def get_add_delay_penalty_by_path(self, path):
        delay_penalty = 0
        for idx in range(1, len(path)):
            delay_penalty += self.get_add_delay_penalty(path[idx-1],path[idx])
        return delay_penalty

    def _save_stats(self, _dict, key, value, length=5):
        if key not in _dict:
            _dict[key] = []
        _dict[key].append(value)
        if len(_dict[key]) > length:
            _dict[key].pop(0)
    
    def _get_period(self, n_sec, n_nsec, p_sec, p_nsec):
        return (n_sec + n_nsec / 1000000000.0) - (p_sec + p_nsec / 1000000000.0)

    def _get_speed(self, now, pre, period):
        if period:
            if (now - pre) / (period) > 0:
                return (now - pre) / (period)
            else:
                return 0
            # return (now - pre) / (period)
        else:
            return 0
        
    def _save_freebandwidth(self, dpid, port_no, speed):
        """
			Calculate free bandwidth of port and Save it.
            free = linkbandwitch - speed
		"""
        port_state = self.port_features.get(dpid).get(port_no)
        if port_state:
            capacity = LINK_BANDWIDTH_KBS   # The true bandwidth of link, instead of 'curr_speed'.
            free_bw = max(capacity - speed, 0) # Bytes/s
            self.free_bandwidth.setdefault(dpid, {})
            self.free_bandwidth[dpid].setdefault(port_no, None)
            self.free_bandwidth[dpid][port_no] = free_bw
        else:
            self.logger.info("Port is Down")

    def check_traffic(self):
        '''
            檢查是否達到塞車條件，若達到則刪除 flow entry
        '''
        # print('check_traffic problem_data = {}')
        # self.problem_data = {}
        problem_data = {}
        for dpid in self.flow_speed.keys():
            for key in self.flow_speed[dpid].keys():
                src, dst = key[1], key[2]
                speed = self.flow_speed[dpid][key][-1]
                # print('flow_speed dpid=%2s %s %s speed=%s' % (dpid, src, dst, speed))
                # self.problem_data.setdefault((src, dst), 0)
                # self.problem_data[(src, dst)] = self.problem_data[(src, dst)] + speed
                problem_data.setdefault((src, dst), 0)
                problem_data[(src, dst)] = problem_data[(src, dst)] + speed
                _key = '%s-%s' % (self.get_sw(src), self.get_sw(dst))
                if _key in self.all_paths and dpid not in self.all_paths[_key]:
                    continue
                if self.is_traffic(speed):
                    # if _key in self.all_paths:
                        self.traffic.setdefault(self.get_sw(src), [])
                        if dst not in self.traffic[self.get_sw(src)]:
                            self.traffic[self.get_sw(src)].append(dst)
                    # else:
                    #     print('*****************retraficc------------------------')
                # print('problem_data=',self.problem_data)
        for item in problem_data.keys():
            self.problem_data.setdefault((item[0], item[1]),0)
            self.problem_data[(item[0], item[1])] = problem_data[item]

        # for key in self.port_speed.keys():
        #     dpid = key[0]
        #     port = key[1]
        #     speed = self.port_speed[key][-1]
        #     print('port_speed dpid=%2s port=%2s speed=%s' % (dpid, port, speed))
                
        if len(self.traffic) > 0:
            print('========================================================================================traffic')
            self.all_paths = {}
            self.real_all_paths = {}
            self.traffic_enable = True
            self.dynamicG = None
            for dpid in self.traffic.keys():
                for dst in self.traffic[dpid]:
                    self.delete_flow(self.datapaths[dpid], dst)
            self.traffic = {}
            
        '''elif self.traffic_enable is True:
            self.traffic_enable = False
            print('========================================================================================traffic stop')
            '''

    def is_traffic(self, speed):
        '''
            是否達到塞車條件
        '''
        return speed > (LINK_BANDWIDTH_KBS * LINK_TRAFFIC_THRESHOLD_PERCENT * 1000) # Bytes/s

    def is_allow_add(self, src, dst, dpid):
        '''
            避免同時間同樣動作執行多次的1秒鎖
        '''
        cur = datetime.datetime.now()
        key = (src, dst, dpid)
        if key in self.last_add_flow:
            # print("cur=", cur)
            # print("las=", self.last_add_flow[key])
            if (cur - self.last_add_flow[key]).seconds > 1:
                self.last_add_flow[key] = cur
                return True
            return False
        self.last_add_flow.setdefault(key, cur)
        return True


    '''
    # @set_ev_cls(ofp_event.EventOFPPortStatus, MAIN_DISPATCHER)
    # def _port_status_handler(self, ev):
    #     """
	# 		Handle the port status changed event.
	# 	"""
    #     msg = ev.msg
    #     ofproto = msg.datapath.ofproto
    #     reason = msg.reason
    #     dpid = msg.datapath.id
    #     port_no = msg.desc.port_no

    #     reason_dict = {ofproto.OFPPR_ADD: "added",
	# 				   ofproto.OFPPR_DELETE: "deleted",
	# 				   ofproto.OFPPR_MODIFY: "modified", }

    #     if reason in reason_dict:
    #         print("switch%d: port %s %s" % (dpid, reason_dict[reason], port_no))
    #     else:
    #         print("switch%d: Illeagal port state %s %s" % (dpid, port_no, reason))
    

    # def show_stat(self, _type):
    #     """
    #         Show statistics information according to data type.
    #         _type: 'port' / 'flow'
    #     """
    #     if TOSHOW is False:
    #         return
    #     # print(self.stats[_type])
    #     bodys = self.stats[_type]
    #     if _type == 'flow':
    #         print('\ndatapath  '
    #             'priority        ip_src        ip_dst  '
    #             '  packets        bytes  flow-speed(KB/s)')
    #         print('--------  '
    #             '--------  ------------  ------------  '
    #             '---------  -----------  ----------------')
    #         for dpid in sorted(bodys.keys()):
    #             for stat in sorted(
    #                 [flow for flow in bodys[dpid] if (
    #                     (flow.priority not in [0, 65535]) and 
    #                     (flow.match.get('eth_src')) and 
    #                     (flow.match.get('eth_dst')))],
    #                 key=lambda flow: (flow.priority, flow.match.get('eth_src'), flow.match.get('eth_dst'))):
    #                 print('%8d  %8s  %12s  %12s  %9d  %11d  %16.1f' % (
    #                     dpid,
    #                     stat.priority, stat.match.get('eth_src'), stat.match.get('eth_dst'),
    #                     stat.packet_count, stat.byte_count,
    #                     abs(self.flow_speed[dpid][(stat.priority, stat.match.get('eth_src'), stat.match.get('eth_dst'))][-1])/1000.0))
    #         print

    #     if _type == 'port':
    #         print('\ndatapath  port '
    #             '   rx-pkts     rx-bytes ''   tx-pkts     tx-bytes '
    #             ' port-bw(KB/s)  port-speed(KB/s)  port-freebw(KB/s) '
    #             ' port-state  link-state')
    #         print('--------  ----  '
    #             '---------  -----------  ''---------  -----------  '
    #             '-------------  ---------------  -----------------  '
    #             '----------  ----------')
    #         _format = '%8d  %4x  %9d  %11d  %9d  %11d  %13d  %15.1f  %17.1f  %10s  %10s'
    #         # print(bodys.keys())
    #         link_free_bandwidth = self.free_bandwidth[dpid][stat.port_no]
    #         for dpid in sorted(bodys.keys()):
    #             for stat in sorted(bodys[dpid], key=attrgetter('port_no')):
    #                 if stat.port_no != ofproto_v1_3.OFPP_LOCAL:
    #                     print(_format % (
    #                         dpid, stat.port_no,
    #                         stat.rx_packets, stat.rx_bytes,
    #                         stat.tx_packets, stat.tx_bytes,
    #                         link_free_bandwidth,
    #                         abs(self.port_speed[(dpid, stat.port_no)][-1] / 1000.0),
    #                         self.free_bandwidth[dpid][stat.port_no],
    #                         self.port_features[dpid][stat.port_no][0],
    #                         self.port_features[dpid][stat.port_no][1]))
    #         print

    # @set_ev_cls(ofp_event.EventOFPPortStateChange, MAIN_DISPATCHER)
    # def _port_state_change_handler(self, ev):
    #     """
    #         switch(dp) prot 狀態改變時觸發
    #     """
    #     dpid_str = dpid_lib.dpid_to_str(ev.dp.id)
    #     of_state = {stplib.PORT_STATE_DISABLE: 'DISABLE',
    #                 stplib.PORT_STATE_BLOCK: 'BLOCK',
    #                 stplib.PORT_STATE_LISTEN: 'LISTEN',
    #                 stplib.PORT_STATE_LEARN: 'LEARN',
    #                 stplib.PORT_STATE_FORWARD: 'FORWARD'}
    #     self.logger.debug("[dpid=%s][port=%d] state=%s",
    #                       dpid_str, ev.port_no, of_state[ev.port_state])
    #     self.port_stp_state.setdefault(ev.dp.id, {})
    #     self.port_stp_state[ev.dp.id][ev.port_no] = of_state[ev.port_state]
    '''
    