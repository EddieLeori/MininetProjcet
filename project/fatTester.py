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

core_p = int(sys.argv[4])
aggreate_p = int(sys.argv[3])
edge_p = int(sys.argv[2])
unit = int(sys.argv[1])

print('unit=%s edge=%s aggreate=%s core=%s' % (unit, edge_p, aggreate_p, core_p))

# core_p = 7
# aggreate_p = 2
# edge_p = 1
# unit = 2
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
        k=4
        pod=k
        L1 = (pod//2)**2
        L2 = pod*pod//2
        L3 = L2
 
        #Starting create the switch
        c = []    #core switch
        a = []    #aggregate switch
        e = []    #edge switch
 
        #notice: switch label is a special data structure
        for i in range(L1):
            c_sw = self.addSwitch('c{}'.format(i+1))    #label from 1 to n,not start with 0
            c.append(c_sw)
 
        for i in range(L2):
            a_sw = self.addSwitch('a{}'.format(L1+i+1))
            a.append(a_sw)
 
        for i in range(L3):
            e_sw = self.addSwitch('e{}'.format(L1+L2+i+1))
            e.append(e_sw)
 
        #Starting create the link between switchs
        #first the first level and second level link
        for i in range(L1):     #i      0   1   2   3
            c_sw=c[i]           #c_sw   c1  c2  c3  c4
            # start=i%(pod//2)    #start  0   1   0   1
            start = i // (pod//2) #start    0   0   1   1
            for j in range(pod):
                self.addLink(c_sw,a[start+j*(pod//2)], bw=bandwidth * 8)
                                #      0   1   2   3
                                #c1j0 -> a[0 + 0 * 2] a[0] a5
                                #c1j1 -> a[0 + 1 * 2] a[2] a7
                                #c1j2 -> a[0 + 2 * 2] a[4] a9
                                #c1j3 -> a[0 + 3 * 2] a[6] a11
                                #c2j0 -> a[0 + 0 * 2] a[0] a5
                                #c2j1 -> a[0 + 1 * 2] a[2] a7
                                #c2j2 -> a[0 + 2 * 2] a[4] a9
                                #c2j3 -> a[0 + 3 * 2] a[6] a11
                                #c3j0 -> a[1 + 0 * 2] a[1] a6
                                #c3j1 -> a[1 + 1 * 2] a[3] a8
                                #c3j2 -> a[1 + 2 * 2] a[5] a10
                                #c3j3 -> a[1 + 3 * 2] a[7] a12
                                #c4j0 -> a[1 + 0 * 2] a[1] a6
                                #c4j1 -> a[1 + 1 * 2] a[3] a8
                                #c4j2 -> a[1 + 2 * 2] a[5] a10
                                #c4j3 -> a[1 + 3 * 2] a[7] a12
 
        #second the second level and third level link
        for i in range(L2):
            group=i//(pod//2)
            for j in range(pod//2):
                self.addLink(a[i],e[group*(pod//2)+j], bw=bandwidth * 8)
 
        #Starting create the host and create link between switchs and hosts
                macdef = [
             '02:60:2d:96:55:25',
             '06:1c:b5:d5:0e:fc',
             '82:56:5e:1b:56:d6',
             'fa:f8:9c:a1:91:08',
             '0e:40:34:83:48:2d',
             '8e:76:b9:2e:c0:dc',
             'aa:7c:df:92:79:b9',
             '72:72:4b:c4:95:68',
             'e6:6b:f7:a4:f4:ae',
             '0a:24:fd:c6:a2:00',
             '12:cd:f4:ea:7b:55',
             '32:e8:09:e0:e2:13',
             '8a:f0:fb:0f:8e:a6',
             '36:a2:ab:4f:62:9f',
             '3e:58:7c:5b:41:18',
             '3e:ca:d9:bd:64:7b'
        ]
        for i in range(L3):
            for j in range(2):
                hs = self.addHost('h{}'.format(i*2+j+1), mac=macdef[i*2 + j])
                self.addLink(e[i],hs, bw=bandwidth * 8)
        
        # # set bridge
        # for i in range(L1):
        #     s = 'brctl stp c' + str(i+1) + ' on'
        #     call(s)
        # for i in range(L2):
        #     s = 'brctl stp a' + str(L1+i+1) + ' on'
        #     call(s)
        # for i in range(L3):
        #     s = 'brctl stp e' + str(L1+L2+i+1) + ' on'
        #     call(s)
 
 
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
    # t = threading.Thread(target=job, args=(net, host2, host3, 60,))
    # thread.append(t)
    time.sleep(0.1)
    

def MyTest():
    topo = MyTopo()
    net = Mininet(topo=topo, link=TCLink,controller=None)
    net.addController('floodlight', controller=RemoteController, ip='127.0.0.1')
    net.start()
    print('Dumping host connections')
    dumpNodeConnections(net.hosts)
    time.sleep(20)
    # ---------------------------------------------------------------------
    print('Test network connectivity...')
    h1, h2, h3, h4, h5, h6, h7, h8, h9, h10, h11, h12, h13, h14, h15, h16 = net.get('h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'h7', 'h8', 'h9', 'h10', 'h11', 'h12', 'h13', 'h14', 'h15', 'h16')
    core_times = core_p
    aggreate_times = aggreate_p
    edge_times = edge_p
    thread = []
    start_idx = 0
    tmpServer = []
    host = [h1, h2, h3, h4, h5, h6, h7, h8, h9, h10, h11, h12, h13, h14, h15, h16]
    print('register core connection=', core_times)
    print('register aggreate connection=', aggreate_times)
    print('register edge connection=', edge_times)
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
        h10: {'id':'h10', 'ip':'10.0.0.10'},
        h11: {'id':'h11', 'ip':'10.0.0.11'},
        h12: {'id':'h12', 'ip':'10.0.0.12'},
        h13: {'id':'h13', 'ip':'10.0.0.13'},
        h14: {'id':'h14', 'ip':'10.0.0.14'},
        h15: {'id':'h15', 'ip':'10.0.0.15'},
        h16: {'id':'h16', 'ip':'10.0.0.16'}
    }
    # start server
    for i in range(len(host)):
        # cmd = 'iperf -s -i 1 > server%s.log &' % (i+1)
        cmd = 'iperf -s -i 1 &'
        # print('h%s %s' % (i+1, cmd))
        host[i].cmd(cmd)
    select_debug127 = None
    select_debug235 = None
    select_debug343 = None
    select_debug721 = None
    select_debug127 = [
        [h16, h12], [h13, h3], [h4, h16], [h14, h8], [h12, h16], [h4, h6], [h16, h12], [h2, h3], [h5, h7], [h13, h14], [h11, h13], [h1, h5], [h7, h10], [h16, h6], [h14, h3], [h5, h15], [h13, h2], [h2, h3], [h5, h8], [h2, h1], [h11, h4], [h13, h2], [h11, h1], [h8, h15], [h16, h10], [h4, h13], [h14, h7], [h14, h15], [h1, h4], [h3, h4], [h4, h14], [h13, h8], [h5, h12], [h6, h4], [h6, h11], [h15, h8], [h7, h13], [h15, h13], [h8, h6], [h3, h4], [h1, h12], [h1, h14], [h3, h11], [h14, h2], [h12, h3], [h6, h15], [h16, h11], [h6, h7], [h4, h2], [h15, h16]
    ]
    select_debug235 = [
        [h3, h7], [h14, h2], [h9, h4], [h2, h7], [h8, h10], [h11, h10], [h5, h8], [h14, h16], [h1, h2], [h1, h2], [h11, h4], [h4, h16], [h10, h3], [h7, h11], [h8, h2], [h14, h16], [h10, h12], [h1, h4], [h12, h11], [h2, h1], [h7, h10], [h5, h3], [h10, h3], [h12, h3], [h11, h8], [h5, h8], [h5, h7], [h12, h9], [h7, h8], [h11, h12], [h3, h7], [h7, h4], [h16, h6], [h3, h6], [h3, h8], [h11, h10], [h4, h1], [h15, h13], [h6, h5], [h15, h16], [h16, h11], [h1, h5], [h15, h12], [h5, h16], [h13, h10], [h14, h16], [h16, h13], [h7, h5], [h4, h3], [h7, h8]
    ]
    select_debug343 = [
        [h9, h4], [h12, h8], [h15, h8], [h14, h16], [h6, h7], [h5, h8], [h12, h9], [h1, h3], [h13, h14], [h11, h12], [h8, h7], [h3, h10], [h7, h4], [h4, h9], [h6, h7], [h10, h11], [h13, h16], [h2, h4], [h5, h7], [h10, h9], [h13, h14], [h5, h6], [h2, h15], [h14, h11], [h6, h10], [h7, h5], [h12, h10], [h7, h6], [h1, h3], [h6, h8], [h1, h2], [h11, h12], [h14, h13], [h9, h15], [h5, h4], [h7, h11], [h14, h16], [h1, h3], [h5, h8], [h8, h5], [h9, h12], [h16, h15], [h14, h13], [h13, h14], [h3, h11], [h11, h6], [h11, h2], [h8, h5], [h16, h13], [h14, h15]
    ]
    select_debug721 = [
        [h7, h11], [h10, h12], [h4, h2], [h14, h13], [h2, h1], [h3, h4], [h14, h13], [h12, h11], [h11, h12], [h1, h2], [h6, h12], [h13, h16], [h4, h1], [h11, h12], [h1, h2], [h2, h1], [h13, h14], [h7, h8], [h6, h5], [h4, h3], [h16, h10], [h5, h8], [h16, h14], [h2, h1], [h3, h4], [h7, h8], [h6, h5], [h2, h1], [h16, h15], [h14, h13], [h8, h9], [h13, h15], [h16, h14], [h15, h16], [h12, h11], [h5, h6], [h16, h15], [h1, h2], [h12, h11], [h5, h6], [h4, h16], [h11, h9], [h12, h10], [h8, h7], [h14, h13], [h16, h15], [h15, h16], [h9, h10], [h7, h8], [h6, h5]
    ]
    select_tmp = None
    if edge_times == 1 and aggreate_times == 2 and core_times == 7:
        select_tmp = select_debug127
    if edge_times == 2 and aggreate_times == 3 and core_times == 5:
        select_tmp = select_debug235
    if edge_times == 3 and aggreate_times == 4 and core_times == 3:
        select_tmp = select_debug343
    if edge_times == 7 and aggreate_times == 2 and core_times == 1:
        select_tmp = select_debug721
    if select_tmp is not None:
        for idx in range(unit):
            print('==========================================', idx)
            net.pingAll()
            cnt = edge_times + aggreate_times + core_times
            for i in range(cnt):
                _host1 = select_tmp[idx * cnt + i][0]
                _host2 = select_tmp[idx * cnt + i][1]
                testiperf(ipconfig, None, None, start_idx, idx, _host1, _host2)
                start_idx = start_idx + 1
            if idx == (unit-1):
                time.sleep(65)
            else:
                time.sleep(90)
    else:
        for idx in range(unit):
            print('==========================================', idx)
            # print('------------------------------------------')
            net.pingAll()
            # start client
            for i in range(core_times):
                host1= {
                    h1:[h5,h6,h7,h8,h9,h10,h11,h12,h13,h14,h15,h16],
                    h2:[h5,h6,h7,h8,h9,h10,h11,h12,h13,h14,h15,h16],
                    h3:[h5,h6,h7,h8,h9,h10,h11,h12,h13,h14,h15,h16],
                    h4:[h5,h6,h7,h8,h9,h10,h11,h12,h13,h14,h15,h16],
                    h5:[h1,h2,h3,h4,h9,h10,h11,h12,h13,h14,h15,h16],
                    h6:[h1,h2,h3,h4,h9,h10,h11,h12,h13,h14,h15,h16],
                    h7:[h1,h2,h3,h4,h9,h10,h11,h12,h13,h14,h15,h16],
                    h8:[h1,h2,h3,h4,h9,h10,h11,h12,h13,h14,h15,h16],
                    h9:[h1,h2,h3,h4,h5,h6,h7,h8,h13,h14,h15,h16],
                    h10:[h1,h2,h3,h4,h5,h6,h7,h8,h13,h14,h15,h16],
                    h11:[h1,h2,h3,h4,h5,h6,h7,h8,h13,h14,h15,h16],
                    h12:[h1,h2,h3,h4,h5,h6,h7,h8,h13,h14,h15,h16],
                    h13:[h1,h2,h3,h4,h5,h6,h7,h8,h9,h10,h11,h12],
                    h14:[h1,h2,h3,h4,h5,h6,h7,h8,h9,h10,h11,h12],
                    h15:[h1,h2,h3,h4,h5,h6,h7,h8,h9,h10,h11,h12],
                    h16:[h1,h2,h3,h4,h5,h6,h7,h8,h9,h10,h11,h12]
                }
                testiperf(ipconfig, host, host1, start_idx, idx)
                start_idx = start_idx + 1
                
            for i in range(aggreate_times):
                host = [h1, h2, h3, h4, h5, h6, h7, h8, h9, h10, h11, h12, h13, h14, h15, h16]
                host1= {
                    h1:[h3,h4],
                    h2:[h3,h4],
                    h3:[h1,h2],
                    h4:[h1,h2],
                    h5:[h7,h8],
                    h6:[h7,h8],
                    h7:[h5,h6],
                    h8:[h5,h6],
                    h9:[h11,h12],
                    h10:[h11,h12],
                    h11:[h9,h10],
                    h12:[h9,h10],
                    h13:[h15,h16],
                    h14:[h15,h16],
                    h15:[h13,h14],
                    h16:[h13,h14]
                }
                testiperf(ipconfig, host, host1, start_idx, idx)
                start_idx = start_idx + 1

            for i in range(edge_times):
                host = [h1, h2, h3, h4, h5, h6, h7, h8, h9, h10, h11, h12, h13, h14, h15, h16]
                host1= {
                    h1:[h2],
                    h2:[h1],
                    h3:[h4],
                    h4:[h3],
                    h5:[h6],
                    h6:[h5],
                    h7:[h8],
                    h8:[h7],
                    h9:[h10],
                    h10:[h9],
                    h11:[h12],
                    h12:[h11],
                    h13:[h14],
                    h14:[h13],
                    h15:[h16],
                    h16:[h15]
                }
                testiperf(ipconfig, host, host1, start_idx, idx)
                start_idx = start_idx + 1
            time.sleep(90)
    # # start
    # print('start thread...')
    # for i in range(len(thread)):
    #     thread[i].start()

    # # wait
    # for i in range(len(thread)):
    #     thread[i].join()


    
    

    # net.iperf((h5,h6), seconds=60)
    # time.sleep(20)
    # net.pingAll()
    # print('------------------------------------------')
    # net.iperf((h5,h8), seconds=60)
    # time.sleep(20)
    # net.pingAll()
    # print('------------------------------------------')
    # net.iperf((h5,h1), seconds=60)
    # time.sleep(20)
    # net.pingAll()
    # print('------------------------------------------')
    # net.iperf((h13,h14), seconds=60)
    # net.iperf((h13,h16), seconds=60)
    # net.iperf((h13,h3), seconds=60)
    # ---------------------------------------------------------------------
    # time.sleep(120)
    print('Done.')
    net.stop()
    cmd = 'sudo mn -c'
    os.system(cmd)
    getresult()

if __name__ == '__main__':
    MyTest()



