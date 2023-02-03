# MininetProjcet

Mininet test for IFOSA, SAPSM and HVFR of path selection algorithm in SDN controller.

Run k=4 Fat-Tree topo networks
setting modify:
	tree_mode = FAT_TREE
	method_mode = PATH_IFOSA or PATH_SAPSM or PATH_SAPSM_DELAY
sudo python3 fatTester.py 5 1 2 7
sudo python3 fatTester.py 5 2 3 5
sudo python3 fatTester.py 5 3 4 3
sudo python3 fatTester.py 5 7 2 1

Run Grid 4x4 topo networks
setting modify:
tree_mode = GRID4X4_TREE
method_mode = PATH_IFOSA or PATH_SAPSM or PATH_SAPSM_DELAY
sudo python3 grid4X4Tester.py 10 5

Run Grid 5x5 topo networks
setting modify:
tree_mode = GRID5X5_TREE
method_mode = PATH_IFOSA or PATH_SAPSM or PATH_SAPSM_DELAY
sudo python3 grid5X5Tester.py 5 4

Run NSF topo networks
setting modify:
tree_mode = NSF_TREE
method_mode = PATH_IFOSA or PATH_SAPSM or PATH_SAPSM_DELAY
sudo python3 nsfTester.py 10 5

Then will create out for the *.log files.
Run iperf_parser2 can out clean data from *.log files.
sudo python3 iperf_parser2.py

random_pair.py is a random create host tool.
