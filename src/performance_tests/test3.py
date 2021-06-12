from mininet.net import Mininet
from mininet.topolib import TreeTopo
import time
tree4 = TreeTopo(depth=3,fanout=3)
net = Mininet(topo=tree4)
net.start()
h1, h2, h3, h4, h5  = net.hosts[0], net.hosts[1], net.hosts[2], net.hosts[3], net.hosts[4]
h1.cmd(f"python3 ../driver.py --broker 1 -v --max_event_count 15 &> broker.txt &")
pid = int(h1.cmd('echo $!'))
h2.cmd(f'python3 ../driver.py --publisher 1 --sleep 0.3 --max_event_count 40 --topics A --topics B --topics C '
            f'--broker_address {h1.IP()} --verbose  &> 1_1.txt &')
h3.cmd(f'python3 ../driver.py --subscriber 1 --topics A --topics B --topics C '
            f'--max_event_count 10  --broker_address {h1.IP()} --verbose '
            f'--filename sub_direct.txt &> 2_2.txt &')
# h4.cmd(f"python3 subscriber.py -a {h4.IP()} -b {h1.IP()} -t C -t B &> subscriber_{h4.IP().replace('.','')}.txt &")
# h5.cmd(f"python3 publisher.py -a {h5.IP()} -b {h1.IP()} -t A -t B &> publisher_{h5.IP().replace('.','')}.txt &")
time.sleep(30)
h1.cmd('kill pid')
net.stop()