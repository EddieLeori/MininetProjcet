import glob

if __name__ == '__main__':
    path = './'
    files = glob.glob("h*.log")
    files.sort(key= lambda x: int(x.split('.')[0].split('-')[-2]))
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
        print('%3s %3s %s' % (host1, host2, bw))
        f.close()
        