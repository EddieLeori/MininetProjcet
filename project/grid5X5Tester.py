from curses import start_color
from random import random
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import RemoteController
from mininet.link import TCLink
from mininet.util import dumpNodeConnections
import time
import random
# from subprocess import call

import threading
import sys
import os
import glob

cmd = 'sudo rm -r h*.log'
os.system(cmd)

unit = int(sys.argv[1])
unit_times = int(sys.argv[2])
print('unit=%s unit_times=%s' % (unit, unit_times))

bandwidth = 10 # MBytes/s

def getresult():
    path = './'
    files = glob.glob("h*.log")
    files.sort(key= lambda x: int(x.split('.')[0].split('-')[-2]))
    bws = []
    for file in files:
        host1=file.split('-')[0]
        host2=file.split('-')[1]
        # print(file)
        # print(host1)
        # print(host2)
        bw = None
        with open('./' + file, 'r') as f:
            lines = f.readlines()
            for line in lines:
                strings = line.split(' ')
                if 'sec' in strings and '0.0-60.0' in strings:
                    if 'Gbits/sec\n' in strings:
                        bw = strings[strings.index('Gbits/sec\n') - 1] * 1000
                    if 'Mbits/sec\n' in strings:
                        bw = strings[strings.index('Mbits/sec\n') - 1]
                    if 'Kbits/sec\n' in strings:
                        bw = float(strings[strings.index('Kbits/sec\n') - 1]) / 1000.0
                    # print(bw)
        # out = host1 + '\t' + host2 + '\t' + bw + '\n'
        # out = host1 + ' ' + host2 + ' ' + bw
        bws.append(bw)
        print('%3s %3s %s' % (host1, host2, bw))
        f.close()
    for b in bws:
        print(b)

class MyTopo(Topo):
 
    def __init__(self):
        super(MyTopo,self).__init__()
 
               #Marking the number of switch for per level
        '''
                        h1      h2      h3      h4      h5
                        |       |       |       |       |
                        16 ——   17  ——  18  ——  19  ——  20
                        |       |       |       |       |
                        6  ——   7   ——  8   ——  9   ——  10
                        |       |       |       |       |
                        1  ——   2   ——  3   ——  4   ——  5
                        |       |       |       |       |
                        11 ——   12  ——  13  ——  14  ——  15
                        |       |       |       |       |
                        21 ——   22  ——  23  ——  24  ——  25
                        |       |       |       |       |
                        h6      h7      h8      h9      h10

                        h1      h2      h3      h4      h5
                        |       |       |       |       |
                        15 ——   16  ——  17  ——  18  ——  19
                        |       |       |       |       |
                        5  ——   6   ——  7   ——  8   ——  9
                        |       |       |       |       |
                        0  ——   1   ——  2   ——  3   ——  4
                        |       |       |       |       |
                        10 ——   11  ——  12  ——  13  ——  14
                        |       |       |       |       |
                        20 ——   21  ——  22  ——  23  ——  24
                        |       |       |       |       |
                        h6      h7      h8      h9      h10
                
        '''
        def_core = [
            [1, 10],    # 0
            [2, 11],    # 1
            [3, 12],    # 2
            [4, 13],    # 3
            [14],       # 4
            [6, 0],     # 5
            [7, 1],     # 6
            [8, 2],     # 7
            [9, 3],     # 8
            [4],        # 9
            [11, 20],   # 10
            [12, 21],   # 11
            [13, 22],   # 12
            [14, 23],   # 13
            [24],       # 14
            [16, 5],    # 15
            [17, 6],    # 16
            [18, 7],    # 17
            [19, 8],    # 18
            [9],        # 19
            [21],       # 20
            [22],       # 21
            [23],       # 22
            [24],       # 23
            []          # 24
        ]
        c = []
        for idx in range(len(def_core)):
            sw = self.addSwitch('c{}'.format(idx+1), stp=True)
            c.append(sw)
        for idx in range(len(def_core)):
            for nodeidx in def_core[idx]:
                self.addLink(c[idx], c[nodeidx], bw=bandwidth * 8)

        def_host = [
            {'h': 'h1', 'mac':'02:60:2d:96:55:25', 'sw': 15}, 
            {'h': 'h2', 'mac':'06:1c:b5:d5:0e:fc', 'sw': 16},
            {'h': 'h3', 'mac':'82:56:5e:1b:56:d6', 'sw': 17}, 
            {'h': 'h4', 'mac':'fa:f8:9c:a1:91:08', 'sw': 18},
            {'h': 'h5', 'mac':'0e:40:34:83:48:2d', 'sw': 19},
            {'h': 'h6', 'mac':'8e:76:b9:2e:c0:dc', 'sw': 20},
            {'h': 'h7', 'mac':'aa:7c:df:92:79:b9', 'sw': 21},
            {'h': 'h8', 'mac':'72:72:4b:c4:95:68', 'sw': 22},
            {'h': 'h9', 'mac':'e6:6b:f7:a4:f4:ae', 'sw': 23},
            {'h': 'h10', 'mac':'0a:24:fd:c6:a2:00', 'sw': 24}
        ]
        for idx in range(len(def_host)):
            hs = self.addHost(def_host[idx]['h'], mac= def_host[idx]['mac'])
            self.addLink(c[def_host[idx]['sw']], hs, bw=bandwidth * 8)
 
topos = {"mytopo":(lambda:MyTopo())}


def job(obj, host1, host2, testtime):
    obj.iperf([host1, host2], seconds=testtime)

def testiperf(ipconfig, host, host1, start_idx, times, force1 = None, force2 = None):
    if force1 is not None:
        host2 = force1
    else:
        host2 = random.choice(host) # client
    if force2 is not None:
        host3 = force2
    else:
        host3 = random.choice(host1[host2]) # server
    # h5-h1-0-0 iperf -c 10.0.0.1 -t 60 -i 60 > h5-h1-0-0.log
    name = ipconfig[host2]['id']+'-'+ipconfig[host3]['id']+'-'+str(start_idx)+"-"+str(times)
    cmd = 'iperf -c %s -t 60 -i 60 > %s.log &' % (ipconfig[host3]['ip'], name)
    print('%s %s' % (name, cmd))
    host2.cmd(cmd)
    time.sleep(0.1)
    

def MyTest():
    topo = MyTopo()
    net = Mininet(topo=topo, link=TCLink,controller=None)
    net.addController('floodlight', controller=RemoteController, ip='127.0.0.1')
    net.start()
    print('Dumping host connections')
    # dumpNodeConnections(net.switches)
    dumpNodeConnections(net.hosts)
    time.sleep(20)
    # ---------------------------------------------------------------------
    print('Test network connectivity...')
    h1, h2, h3, h4, h5, h6, h7, h8, h9, h10 = net.get('h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'h7', 'h8', 'h9', 'h10')
    start_idx = 0
    host = [h1, h2, h3, h4, h5, h6, h7, h8, h9, h10]
    ipconfig = {
        h1: {'id':'h1', 'ip':'10.0.0.1'},
        h2: {'id':'h2', 'ip':'10.0.0.2'},
        h3: {'id':'h3', 'ip':'10.0.0.3'},
        h4: {'id':'h4', 'ip':'10.0.0.4'},
        h5: {'id':'h5', 'ip':'10.0.0.5'},
        h6: {'id':'h6', 'ip':'10.0.0.6'},
        h7: {'id':'h7', 'ip':'10.0.0.7'},
        h8: {'id':'h8', 'ip':'10.0.0.8'},
        h9: {'id':'h9', 'ip':'10.0.0.9'},
        h10: {'id':'h10', 'ip':'10.0.0.10'}
    }
    # start server
    for i in range(len(host)):
        # cmd = 'iperf -s -i 1 > server%s.log &' % (i+1)
        cmd = 'iperf -s -i 1 &'
        # print('h%s %s' % (i+1, cmd))
        host[i].cmd(cmd)

    select_debug = [
        [h7, h8], [h2, h1], [h9, h2], [h3, h9], [h5, h9], [h1, h6], [h10, h2], [h4, h5], [h6, h8], [h8, h5],
        [h8, h10], [h6, h10], [h4, h10], [h1, h5], [h5, h9], [h2, h9], [h7, h5], [h10, h1], [h3, h9], [h9, h7],
        [h9, h2], [h2, h8], [h1, h4], [h10, h9], [h7, h4], [h5, h9], [h6, h10], [h4, h9], [h3, h2], [h8, h6],
        [h2, h5], [h9, h7], [h4, h9], [h5, h1], [h7, h2], [h6, h9], [h1, h7], [h10, h3], [h3, h9], [h8, h6],
        [h1, h5], [h8, h5], [h9, h4], [h7, h8], [h2, h1], [h10, h2], [h3, h1], [h4, h2], [h5, h4], [h6, h9]
    ]

    for idx in range(unit_times):
        print('==========================================', idx)
        # print('------------------------------------------')
        net.pingAll()
        # start client
        for i in range(unit):
            _host1 = select_debug[idx * unit + i][0]
            _host2 = select_debug[idx * unit + i][1]
            testiperf(ipconfig, None, None, start_idx, idx, _host1, _host2)
            start_idx = start_idx + 1
        time.sleep(90)
   
    print('Done.')
    net.stop()
    cmd = 'sudo mn -c'
    os.system(cmd)
    getresult()

if __name__ == '__main__':
    MyTest()



