TOSHOW = False
FAT_TREE = 'FAT'
MESH_TREE = 'MESH'
GRID4X4_TREE = 'GRID4X4'
GRID5X5_TREE = 'GRID5X5'
NSF_TREE = 'NSF'
PATH_IFOSA = 'IFOSA'
PATH_SAPSM = 'SAPSM'
PATH_SAPSM_DELAY = 'SAPSM_DELAY'

#tree_mode = FAT_TREE
#tree_mode = MESH_TREE
#tree_mode = GRID4X4_TREE
tree_mode = GRID5X5_TREE
#tree_mode = NSF_TREE
method_mode = PATH_IFOSA
#method_mode = PATH_SAPSM
#method_mode = PATH_SAPSM_DELAY

ifosa_config = {
    'maxgen':5
}

sapsm_config = {
    'maxgen': 12,   # 迭代次數
    't_start': 100, # 初始溫度
    't_down' : 100, # 一次迭代退火多少
    'win_times': 3  # 連續幾次都選到就直接結束
}

tree_mac = {
    '02:60:2d:96:55:25': 13,
    '06:1c:b5:d5:0e:fc': 13,
    '82:56:5e:1b:56:d6': 14,
    'fa:f8:9c:a1:91:08': 14,
    '0e:40:34:83:48:2d': 15,
    '8e:76:b9:2e:c0:dc': 15,
    'aa:7c:df:92:79:b9': 16,
    '72:72:4b:c4:95:68': 16,
    'e6:6b:f7:a4:f4:ae': 17,
    '0a:24:fd:c6:a2:00': 17,
    '12:cd:f4:ea:7b:55': 18,
    '32:e8:09:e0:e2:13': 18,
    '8a:f0:fb:0f:8e:a6': 19,
    '36:a2:ab:4f:62:9f': 19,
    '3e:58:7c:5b:41:18': 20,
    '3e:ca:d9:bd:64:7b': 20
}

mesh_mac = {
    '02:60:2d:96:55:25': 13,
    '06:1c:b5:d5:0e:fc': 13,
    '82:56:5e:1b:56:d6': 14,
    'fa:f8:9c:a1:91:08': 14,
    '0e:40:34:83:48:2d': 15,
    '8e:76:b9:2e:c0:dc': 15,
    'aa:7c:df:92:79:b9': 16,
    '72:72:4b:c4:95:68': 16,
    'e6:6b:f7:a4:f4:ae': 17,
    '0a:24:fd:c6:a2:00': 17,
    '12:cd:f4:ea:7b:55': 18,
    '32:e8:09:e0:e2:13': 18,
    '8a:f0:fb:0f:8e:a6': 19,
    '36:a2:ab:4f:62:9f': 19,
    '3e:58:7c:5b:41:18': 20,
    '3e:ca:d9:bd:64:7b': 20
}

nsf_mac = {
    '02:60:2d:96:55:25': 1,
    '06:1c:b5:d5:0e:fc': 2,
    '82:56:5e:1b:56:d6': 3,
    'fa:f8:9c:a1:91:08': 4,
    '0e:40:34:83:48:2d': 5,
    '8e:76:b9:2e:c0:dc': 6,
    'aa:7c:df:92:79:b9': 7,
    '72:72:4b:c4:95:68': 8,
    'e6:6b:f7:a4:f4:ae': 9,
    '0a:24:fd:c6:a2:00': 10,
    '12:cd:f4:ea:7b:55': 11,
    '32:e8:09:e0:e2:13': 12,
    '8a:f0:fb:0f:8e:a6': 13,
    '36:a2:ab:4f:62:9f': 14
}

grid_mac = {
    '02:60:2d:96:55:25': 6,
    '06:1c:b5:d5:0e:fc': 7,
    '82:56:5e:1b:56:d6': 8,
    'fa:f8:9c:a1:91:08': 9,
    '0e:40:34:83:48:2d': 9,
    '8e:76:b9:2e:c0:dc': 10,
    'aa:7c:df:92:79:b9': 11,
    '72:72:4b:c4:95:68': 12,
    'e6:6b:f7:a4:f4:ae': 12,
    '0a:24:fd:c6:a2:00': 13,
    '12:cd:f4:ea:7b:55': 14,
    '32:e8:09:e0:e2:13': 15,
    '8a:f0:fb:0f:8e:a6': 15,
    '36:a2:ab:4f:62:9f': 4,
    '3e:58:7c:5b:41:18': 5,
    '3e:ca:d9:bd:64:7b': 6
}

grid_mac2 = {
    '02:60:2d:96:55:25': 20,
    '06:1c:b5:d5:0e:fc': 21,
    '82:56:5e:1b:56:d6': 22,
    'fa:f8:9c:a1:91:08': 23,
    '0e:40:34:83:48:2d': 24,
    '8e:76:b9:2e:c0:dc': 25,
    'aa:7c:df:92:79:b9': 26,
    '72:72:4b:c4:95:68': 27,
    'e6:6b:f7:a4:f4:ae': 28,
    '0a:24:fd:c6:a2:00': 29,
    '12:cd:f4:ea:7b:55': 30,
    '32:e8:09:e0:e2:13': 31,
    '8a:f0:fb:0f:8e:a6': 16,
    '36:a2:ab:4f:62:9f': 17,
    '3e:58:7c:5b:41:18': 18,
    '3e:ca:d9:bd:64:7b': 19
}

grid4X4_mac3 = {
    '02:60:2d:96:55:25': 9,
    '06:1c:b5:d5:0e:fc': 9,
    '82:56:5e:1b:56:d6': 10,
    'fa:f8:9c:a1:91:08': 10,
    '0e:40:34:83:48:2d': 11,
    '8e:76:b9:2e:c0:dc': 11,
    'aa:7c:df:92:79:b9': 12,
    '72:72:4b:c4:95:68': 12,
    'e6:6b:f7:a4:f4:ae': 13,
    '0a:24:fd:c6:a2:00': 13,
    '12:cd:f4:ea:7b:55': 14,
    '32:e8:09:e0:e2:13': 14,
    '8a:f0:fb:0f:8e:a6': 15,
    '36:a2:ab:4f:62:9f': 15,
    '3e:58:7c:5b:41:18': 16,
    '3e:ca:d9:bd:64:7b': 16
}

grid5X5_mac3 = {
    '02:60:2d:96:55:25': 16,
    '06:1c:b5:d5:0e:fc': 17,
    '82:56:5e:1b:56:d6': 18,
    'fa:f8:9c:a1:91:08': 19,
    '0e:40:34:83:48:2d': 20,
    '8e:76:b9:2e:c0:dc': 21,
    'aa:7c:df:92:79:b9': 22,
    '72:72:4b:c4:95:68': 23,
    'e6:6b:f7:a4:f4:ae': 24,
    '0a:24:fd:c6:a2:00': 25
}

def TreeMode():
    return tree_mode

def MethodMode():
    return method_mode

IFOSA_CFG = ifosa_config # ifosa_mesh_config if tree_mode == MESH_TREE else ifosa_config
SAPSM_CFG = sapsm_config # sapsm_mesh_config if tree_mode == MESH_TREE else sapsm_config

def MacCFG():
    if tree_mode == FAT_TREE:
        return tree_mac
    elif tree_mode == MESH_TREE:
        return mesh_mac
    elif tree_mode == NSF_TREE:
        return nsf_mac
    elif tree_mode == GRID4X4_TREE:
        return grid4X4_mac3
    elif tree_mode == GRID5X5_TREE:
        return grid5X5_mac3

def LogConfigInfo():
    print('*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*')
    print('TREE_MODE=%s' % (tree_mode))
    print('TRAFFIC_PATH_TYPE=%s' % (method_mode))
    if method_mode != PATH_IFOSA:
        name = 'SAPSM' if method_mode == PATH_SAPSM else 'SAPSM_DELAY'
        print('%s_MAXGEN=%s' % (name, SAPSM_CFG['maxgen']))
        print('%s_T_START=%s' % (name, SAPSM_CFG['t_start']))
        print('%s_T_DOWN_C=%s' % (name, SAPSM_CFG['t_down']))
        print('%s_WIN_TIMES=%s' % (name, SAPSM_CFG['win_times']))
    print('*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*-*')
