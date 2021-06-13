from mininet.net import Mininet
from mininet.topolib import TreeTopo
import time
import argparse
import string
import random

parser = argparse.ArgumentParser()
parser.add_argument ("-c", "--centralized",  action="store_true", help="indicate if it is for centralized dissemination")
args = parser.parse_args()

tree27= TreeTopo(depth=3,fanout=3)
net = Mininet(topo=tree27)
net.start()

broker = net.hosts[13]
# publisher = [0, 2, 5, 7, 8, 10, 12, 15, 17, 20, 21, 24, 26]
# subscriber = [1, 3, 4, 6, 9, 11, 14, 16, 18, 19, 22, 23, 25]

# publisher = [0, 10, 15, 20]
# subscriber = [1, 3, 16, 18]

publisher = [0, 7, 10, 15, 20, 25]
subscriber = [1, 3, 9, 16, 18, 26]

publisher_max = 200
subscriber_max = 50
# running with centralized dissemination
if args.centralized:
    # start broker and running in the background
    broker.cmd(f"python3 driver.py --broker 1 -v --indefinite --centralized &")
    pid = int(broker.cmd('echo $!'))

    # start each publisher
    for idx in publisher:
        publisher_host = net.hosts[idx]
        publisher_host.cmd(f'python3 driver.py --publisher 1 --centralized '
                        f'--sleep 0.1 --max_event_count {publisher_max} '
                        f'--topics A --topics B --topics C '
                        f'--broker_address {broker.IP()} --verbose &')

    for idx in subscriber:
        subscriber_host = net.hosts[idx]
        subscriber_host.cmd(f'python3 driver.py --subscriber 1 --centralized '
                    f'--topics D --topics B --topics C '
                    f'--max_event_count {subscriber_max}  --broker_address {broker.IP()} --verbose '
                    f'--filename result/central/sub_{subscriber_host.IP().replace(".", "")}.txt &')
    time.sleep(300)
    broker.cmd('kill pid')
else:
    # start broker and running in the background
    broker.cmd(f"python3 driver.py --broker 1 -v --indefinite &")
    pid = int(broker.cmd('echo $!'))

    # start each publisher
    for idx in publisher:
        publisher_host = net.hosts[idx]
        publisher_host.cmd(f'python3 driver.py --publisher 1 '
                        f'--sleep 0.1 --max_event_count {publisher_max} '
                        f'--topics A --topics B --topics C '
                        f'--broker_address {broker.IP()} --verbose &')

    for idx in subscriber:
        subscriber_host = net.hosts[idx]
        subscriber_host.cmd(f'python3 driver.py --subscriber 1 '
                    f'--topics D --topics B --topics C '
                    f'--max_event_count {subscriber_max} --broker_address {broker.IP()} --verbose '
                    f'--filename result/direct/sub_{subscriber_host.IP().replace(".", "")}.txt &')
    time.sleep(300)
    broker.cmd('kill pid')
# h1, h2, h3, h4, h5  = net.hosts[0], net.hosts[1], net.hosts[2], net.hosts[3], net.hosts[4]
# h1.cmd(f"python3 driver.py --broker 1 -v --indefinite &")
# pid = int(h1.cmd('echo $!'))
# h2.cmd(f'python3 driver.py --publisher 1 --sleep 0.3 --max_event_count 40 --topics A --topics B --topics C '
#             f'--broker_address {h1.IP()} --verbose &')
# h3.cmd(f'python3 driver.py --subscriber 1 --topics A --topics B --topics C '
#             f'--max_event_count 10  --broker_address {h1.IP()} --verbose '
#             f'--filename result/sub_{h3.IP().replace(".", "")}.txt &')
#
# h4.cmd(f'python3 driver.py --publisher 1 --sleep 0.3 --max_event_count 40 --topics D --topics B --topics C '
#             f'--broker_address {h1.IP()} --verbose &')
# h5.cmd(f'python3 driver.py --subscriber 1 --topics D --topics B --topics C '
#             f'--max_event_count 10  --broker_address {h1.IP()} --verbose '
#             f'--filename result/sub_{h5.IP().replace(".", "")}.txt &')
# h4.cmd(f"python3 subscriber.py -a {h4.IP()} -b {h1.IP()} -t C -t B &> subscriber_{h4.IP().replace('.','')}.txt &")
# h5.cmd(f"python3 publisher.py -a {h5.IP()} -b {h1.IP()} -t A -t B &> publisher_{h5.IP().replace('.','')}.txt &")
net.stop()
