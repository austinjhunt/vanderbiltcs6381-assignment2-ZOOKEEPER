import time
from mininet.net import Mininet
from mininet.topolib import TreeTopo
from mininet.node import Controller
from topologies.single_switch_topology import SingleSwitchTopo
import os
import logging
import sys
logging.basicConfig(
    stream=sys.stderr,
    level=logging.DEBUG,
    format='%(prefix)s - %(message)s')
__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))

class CentralizedDisseminationPubSubPerformanceTest:

    def __init__(self, num_events=50, event_interval=0.3, wait_factor=10):
        self.num_events = num_events
        self.event_interval = event_interval
        # Sleep self.wait_factor times longer than num events * event interval
        # to allow the network to initialize and all events to run.
        # Files not written by subscriber until it reaches num_events.
        self.wait_factor = wait_factor
        self.prefix = {'prefix': ''}

    def cleanup(self):
        os.system("mn -c")

    def debug(self, msg):
        logging.debug(msg, extra=self.prefix)

    def create_network(self, topo=None):
        """ Handle pre-cleanup if necessary """
        network = None
        if topo:
            try:
                network = Mininet(topo=topo)
            except Exception as e:
                os.system('mn -c')
                network = Mininet(topo=topo)
        return network


    def run_network(self, network=None, num_hosts=None, network_name=""):
        self.prefix['prefix'] = f'NET-{network_name}-TEST - '

        if network and num_hosts:
            # For subs, write data files into a folder within this folder
            # named after the network
            data_folder = os.path.join(__location__, f"data/centralized/{network_name}")
            log_folder = os.path.join(__location__, f"logs/centralized/{network_name}")
            # Make folders dynamically since the names are variable
            try:
                os.mkdir(data_folder)
            except FileExistsError:
                pass
            try:
                os.mkdir(log_folder)
            except FileExistsError:
                pass

            # Start the network
            network.start()
            # self.debug("Starting a pingAll test...")
            # network.pingAll()
            self.debug("Starting network...")
            num_subscribers = (num_hosts - 1) // 2
            num_publishers = num_hosts - 1 - num_subscribers

            self.debug(
                f'With {num_hosts} hosts, there will be 1 Broker, '
                f'{num_publishers} Publishers, and {num_subscribers} Subscribers...'
            )


            # Set up broker on first host (h1)
            broker_command = (
                f'python3 ../driver.py '
                '--broker 1 --verbose '
                f'--indefinite ' # max event count only matters for subscribers who write files at end.
                f'--centralized ' # CENTRALIZED TESTING
                f'&> {log_folder}/broker.log &'
            )
            broker_host = network.hosts[0]
            broker_host.cmd(broker_command)
            broker_ip = broker_host.IP()
            self.debug(f'Broker set up! (IP: {broker_ip})')

            subscribers = [
                network.hosts[i] for i in range(1, num_subscribers + 1)
            ]
            publishers = [
                network.hosts[i] for i in range(num_subscribers + 1, num_hosts)
            ]
            self.debug(f"Starting {num_subscribers} subscribers...")

            for index,host in enumerate(subscribers):
                host.cmd(
                    'python3 ../driver.py '
                    '--subscriber 1 '
                    '--topics A --topics B --topics C '
                    f'--max_event_count {self.num_events} '
                    f'--broker_address {broker_ip} '
                    f'--filename {data_folder}/subscriber-{index}.csv '
                    '--centralized ' # CENTRALIZED TESTING
                    f'--verbose &> {log_folder}/sub-{index}.log &'
                )
            self.debug("Subscribers created!")

            self.debug(f"Creating {num_publishers} publishers...")
            for index,host in enumerate(publishers):
                host.cmd(
                    f'python3 ../driver.py '
                    '--publisher 1 '
                    f'--sleep {self.event_interval} '
                    f'--indefinite ' # max event count only matters for subscribers who write files at end.
                    '--topics A --topics B --topics C '
                    f'--broker_address {broker_ip} '
                    '--centralized ' # CENTRALIZED TESTING
                    f'--verbose  &> {log_folder}/pub-{index}.log &'
                    )
            self.debug("Publishers created!")

            # Scale the wait time by a constant factor and with number of hosts
            # Decided to add 40% of num_hosts in seconds as additional constant time
            wait_time = self.wait_factor * (self.num_events * self.event_interval) + (num_hosts * .4)
            self.debug(f"Waiting for {wait_time} seconds for data to generate...")
            time.sleep(wait_time)
            self.debug(f"Finished waiting! Killing processes...")
            # Kill the processes
            for index,host in enumerate(subscribers):
                out = host.cmd(f'kill %1')

            for index,host in enumerate(publishers):
                out = host.cmd(f'kill %1')

            self.debug(f"Processes killed. Stopping network '{network_name}'...")
            # Stop the network
            network.stop()
            self.debug(f"Network '{network_name}' stopped!")

        else:
            logging.error("Need to pass network and num_hosts to initialize_network()")

    def test_tree_topology(self, depth=2, fanout=2):
        """ Create and test Pub/Sub on a Tree topology with fanout^depth hosts,
        with one broker and an equal number of subscribers and publishers """
        tree = TreeTopo(depth=depth, fanout=fanout)
        network = self.create_network(topo=tree)
        self.run_network(
            network=network,
            network_name=f"tree-d{depth}f{fanout}-{fanout**depth}hosts",
            num_hosts=fanout ** depth
        )
        self.cleanup()

    def test_single_switch_topology(self, num_hosts=3):
        """ Create and test Pub/Sub on a Single Switch Topology mininet network
        with a variable number of subscribers and publishers """
        if num_hosts < 3:
            # Raise exception. You need at least one broker, one subscriber and one publisher.
            raise Exception("Topology must include at least 3 hosts")
        topo = SingleSwitchTopo(n=num_hosts)
        network = self.create_network(topo=topo)
        self.run_network(
            network=network,
            num_hosts=num_hosts,
            network_name=f"singleswitch-{num_hosts}-hosts"
        )
        self.cleanup()


if __name__ == "__main__":

    centralized_perf_test = CentralizedDisseminationPubSubPerformanceTest(
        num_events=100,
        event_interval=0.1,
        wait_factor=5
    )

    # Min = 4 hosts, Max = 256 hosts
    for depth in range(2,5):
            for fanout in range(2,5):
                centralized_perf_test.test_tree_topology(depth=depth, fanout=fanout)