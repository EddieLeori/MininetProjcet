# from distutils import core
# import glob
import random
# from sqlite3.dbapi2 import _AggregateProtocol
if __name__ == '__main__':
    # mode: fattree mesh nsf
    mode = 'grid'
    option_edge = 7
    option_aggr = 2
    option_core = 1
    times = 10
    mesh_pair = 8
    nsf_pair = 10
    out = []
    if mode == 'fattree':
        core_host = {
            'h1':['h5','h6','h7','h8','h9','h10','h11','h12','h13','h14','h15','h16'],
            'h2':['h5','h6','h7','h8','h9','h10','h11','h12','h13','h14','h15','h16'],
            'h3':['h5','h6','h7','h8','h9','h10','h11','h12','h13','h14','h15','h16'],
            'h4':['h5','h6','h7','h8','h9','h10','h11','h12','h13','h14','h15','h16'],
            'h5':['h1','h2','h3','h4','h9','h10','h11','h12','h13','h14','h15','h16'],
            'h6':['h1','h2','h3','h4','h9','h10','h11','h12','h13','h14','h15','h16'],
            'h7':['h1','h2','h3','h4','h9','h10','h11','h12','h13','h14','h15','h16'],
            'h8':['h1','h2','h3','h4','h9','h10','h11','h12','h13','h14','h15','h16'],
            'h9':['h1','h2','h3','h4','h5','h6','h7','h8','h13','h14','h15','h16'],
            'h10':['h1','h2','h3','h4','h5','h6','h7','h8','h13','h14','h15','h16'],
            'h11':['h1','h2','h3','h4','h5','h6','h7','h8','h13','h14','h15','h16'],
            'h12':['h1','h2','h3','h4','h5','h6','h7','h8','h13','h14','h15','h16'],
            'h13':['h1','h2','h3','h4','h5','h6','h7','h8','h9','h10','h11','h12'],
            'h14':['h1','h2','h3','h4','h5','h6','h7','h8','h9','h10','h11','h12'],
            'h15':['h1','h2','h3','h4','h5','h6','h7','h8','h9','h10','h11','h12'],
            'h16':['h1','h2','h3','h4','h5','h6','h7','h8','h9','h10','h11','h12']
        }
        aggr_host = {
            'h1':['h3','h4'],
            'h2':['h3','h4'],
            'h3':['h1','h2'],
            'h4':['h1','h2'],
            'h5':['h7','h8'],
            'h6':['h7','h8'],
            'h7':['h5','h6'],
            'h8':['h5','h6'],
            'h9':['h11','h12'],
            'h10':['h11','h12'],
            'h11':['h9','h10'],
            'h12':['h9','h10'],
            'h13':['h15','h16'],
            'h14':['h15','h16'],
            'h15':['h13','h14'],
            'h16':['h13','h14']
        }
        edge_host = {
            'h1':['h2'],
            'h2':['h1'],
            'h3':['h4'],
            'h4':['h3'],
            'h5':['h6'],
            'h6':['h5'],
            'h7':['h8'],
            'h8':['h7'],
            'h9':['h10'],
            'h10':['h9'],
            'h11':['h12'],
            'h12':['h11'],
            'h13':['h14'],
            'h14':['h13'],
            'h15':['h16'],
            'h16':['h15']
        }
        for idx in range(times):
            for i in range(option_core):
                host1 = random.choice(list(core_host.keys()))
                host2 = random.choice(core_host[host1])
                out.append([host1, host2])
            for i in range(option_aggr):
                host1 = random.choice(list(aggr_host.keys()))
                host2 = random.choice(aggr_host[host1])
                out.append([host1, host2])
            for i in range(option_edge):
                host1 = random.choice(list(edge_host.keys()))
                host2 = random.choice(edge_host[host1])
                out.append([host1, host2])
    elif mode == 'mesh':
        for _ in range(times):
            host = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'h7', 'h8', 'h9', 'h10', 'h11', 'h12', 'h13', 'h14', 'h15', 'h16']
            host_tmp = host.copy()
            for idx in range(mesh_pair):
                host1 = random.choice(host_tmp)
                host_tmp.remove(host1)
                host2 = random.choice(host_tmp)
                host_tmp.remove(host2)
                out.append([host1, host2])
    elif mode == 'nsf':
        for _ in range(times):
            host = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'h7', 'h8', 'h9', 'h10', 'h11', 'h12', 'h13', 'h14']
            host_tmp = host.copy()
            for idx in range(nsf_pair):
                host1 = random.choice(host_tmp)
                host_tmp.remove(host1)
                host_tmp2 = host.copy()
                host_tmp2.remove(host1)
                host2 = random.choice(host_tmp2)
                out.append([host1, host2])
    elif mode == 'grid':
        host = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'h7', 'h8', 'h9', 'h10']
        host_tmp = host.copy()
        for _ in range(times):
            host1 = random.choice(host_tmp)
            host_tmp.remove(host1)
            tmp = host.copy()
            tmp.remove(host1)
            host2 = random.choice(tmp)
            out.append([host1, host2])
    else:
        print('no mode.')
    print('----------------------------------------------')
    print(out)
        