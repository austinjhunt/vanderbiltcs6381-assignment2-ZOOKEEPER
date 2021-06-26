"""
Message Broker to serve as anonymizing middleware between
publishers and subscribers
"""
import zmq
import json
import traceback
import random
import logging
import pickle
import netifaces
import sys
import uuid


#--------------------------------------------------------------------------
# Borrowed from Professor's sample code
#--------------------------------------------------------------------------
# Now import the kazoo package that supports Python binding
# to ZooKeeper
from kazoo.client import KazooClient   # client API
from kazoo.client import KazooState    # for the state machine
# to avoid any warning about no handlers for logging purposes, we
# do the following
import logging
logging.basicConfig ()
def listener4state (state):
    if state == KazooState.LOST:
        print ("Current state is now = LOST")
    elif state == KazooState.SUSPENDED:
        print ("Current state is now = SUSPENDED")
    elif state == KazooState.CONNECTED:
        print ("Current state is now = CONNECTED")
    else:
        print ("Current state now = UNKNOWN !! Cannot happen")


class Broker:
    #################################################################
    # constructor
    #################################################################
    def __init__(self, centralized=False, indefinite=False, max_event_count=15,
        pub_reg_port=5555, sub_reg_port=5556,
        zk_address="127.0.0.1", zk_port="2181"):
        self.centralized = centralized
        self.prefix = {'prefix': 'BROKER - '}
        if self.centralized:
            log_format = logging.Formatter('%(message)s')
            log_format._fmt = "CENTRAL PUBLISHING BROKER - " + log_format._fmt
            logging.debug("Initializing broker for centralized dissemination", extra=self.prefix)
        else:
            log_format = logging.Formatter('%(message)s')
            log_format._fmt = "DECENTRAL PUBLISHING BROKER - " + log_format._fmt
            logging.debug("Initializing broker for decentralized dissemination", extra=self.prefix)
        # Either poll for events indefinitely or for specified max_event_count
        self.indefinite = indefinite
        self.max_event_count = max_event_count
        self.subscribers = {}
        self.publishers = {}
        #  The zmq context
        self.context = None
        # we will use the poller to poll for incoming data
        self.poller = None
        # these are the sockets we open one for each registration
        self.pub_reg_socket = None
        self.sub_reg_socket = None

        # Socket to notify subscribers about publishers of topics
        # Used for decentralized dissemination
        # self.notify_sub_socket = None

        # To fix competitive poll()s among subscribers (one's subscriber's poll() steals another's)
        # use a separate socket per subscriber.
        self.notify_sub_sockets = {}

        # this is the centralized dissemination system
        # broker will have a list of sockets for receiving from publisher
        # broker will also have a list of sockets for sending to subscrbier
        self.receive_socket_dict = {}
        self.send_socket_dict = {}
        self.send_port_dict = {}
        self.used_ports = []

        # this is to connect with zookeeper Server
        self.zk_address = zk_address
        self.zk_port = zk_port
        self.zk_server = f"{zk_address}:{zk_port}"

        # this is an identifier for ZooKeeper
        self.instanceId = str(uuid.uuid4())
        print(f"My InstanceId is {self.instanceId}")

        # this is the zk node name
        self.zkName = '/broker'
        # this is for write into the znode about the broker information
        self.own_address = "127.0.0.1"
        self.pub_reg_port = pub_reg_port
        self.sub_reg_port = sub_reg_port
        self.znode_value = f"{self.own_address},{self.pub_reg_port},{self.sub_reg_port}"

    def connect_zk(self):
        try:
            print("Try to connect with ZooKeeper server: hosts = {}".format(self.zk_server))
            self.zk = KazooClient(self.zk_server)
            self.zk.add_listener (listener4state)
            print("ZooKeeper Current Status = {}".format (self.zk.state))
        except:
            print("Issues with ZooKeeper, cannot connect with Server")

    def start_session(self):
        """ Starting a Session """
        try:
            # now connect to the server
            self.zk.start()
        except:
            print("Exception thrown in start (): ", sys.exc_info()[0])

    def stop_session (self):
        """ Stopping a Session """
        try:
            # now disconnect from the server
            self.zk.stop ()
        except:
            print("Exception thrown in stop (): ", sys.exc_info()[0])
            return

    def close_connection(self):
        try:
            # now disconnect from the server
            self.zk.close()
        except:
            print("Exception thrown in close (): ", sys.exc_info()[0])
            return

    def create_znode (self):
        """ ******************* znode creation ************************ """
        try:

            print(f"Creating an ephemeral znode {self.zkName} with value {self.znode_value }")
            # self.zk.ensure_path(self.zkName)
            self.zk.create (self.zkName, value=self.znode_value .encode('utf-8'), ephemeral=True)

        except:
            print("Exception thrown in create (): ", sys.exc_info()[0])
            return

    def modify_znode_value (self, new_val):
        """ ******************* modify a znode value  ************************ """
        try:
            # Now let us change the data value on the znode and see if
            # our watch gets invoked
            print ("Setting a new value = {} on znode {}".format (new_val, self.zkName))
            # make sure that the znode exists before we actually try setting a new value
            if self.zk.exists (self.zkName):
                print ("{} znode still exists :-)".format(self.zkName))
                print ("Setting a new value on znode")
                self.zk.set (self.zkName, new_val)
                # Now see if the value was changed
                value,stat = self.zk.get (self.zkName)
                print(("New value at znode {}: value = {}, stat = {}".format (self.zkName, value, stat)))
            else:
                print ("{} znode does not exist, why?".format(self.zkName))
        except:
            print("Exception thrown checking for exists/set: ", sys.exc_info()[0])
            return

    def leader_function(self):
        print("I am the leader {}".format(str(self.instanceId)))
        print("Create a Znode with my information")
        if self.zk.exists(self.zkName):
            print("{} znode exists : only modify the value)".format(self.zkName))
            self.modify_znode_value(self.znode_value.encode('utf-8'))
        else:
            print("{} znode does not exists : create one)".format(self.zkName))
            self.create_znode()

        # the following does not necessarily change
        print("Configure Myself")
        self.configure()
        try:
            self.event_loop()
        except KeyboardInterrupt:
            # If you interrupt/cancel a broker, be sure to disconnect/clean all sockets
            self.disconnect()

    def zk_run_election(self):
        self.election = self.zk.Election("/electionpath", self.instanceId)
        print("contenders", self.election.contenders())
        self.election.run(self.leader_function)


    def configure(self):
        """ Method to perform initial configuration of Broker entity """
        print("Configure Start")
        #  The zmq context
        self.context = zmq.Context()
        # we will use the poller to poll for incoming data
        self.poller = zmq.Poller()
        # these are the sockets we open one for each registration
        logging.debug("Opening two REP sockets for publisher registration "
            "and subscriber registration", extra=self.prefix)
        self.pub_reg_socket = self.context.socket(zmq.REP)
        self.setup_pub_port_reg_binding()
        self.sub_reg_socket = self.context.socket(zmq.REP)
        self.setup_sub_port_reg_binding()
        self.used_ports.append(self.pub_reg_port)
        self.used_ports.append(self.sub_reg_port)
        logging.debug(f"Enabling publisher registration on port {self.pub_reg_port}", extra=self.prefix)
        logging.debug(f"Enabling subscriber registration on port {self.sub_reg_port}", extra=self.prefix)

        # register these sockets for incoming data
        logging.debug("Register sockets with a ZMQ poller", extra=self.prefix)
        self.poller.register(self.pub_reg_socket, zmq.POLLIN)
        self.poller.register(self.sub_reg_socket, zmq.POLLIN)
        print("Configure Stop")

    def setup_pub_port_reg_binding(self):
        """
        Method to bind socket to network address to begin publishing/accepting client connections
        using bind_port specified. If bind_port already in use, increment and keep trying until success.
        """
        success = False
        while not success:
            try:
                logging.info(f'Attempting bind to port {self.pub_reg_port}', extra=self.prefix)
                self.pub_reg_socket.bind(f'tcp://*:{self.pub_reg_port}')
                success = True
                logging.info(f'Successful bind to port {self.pub_reg_port}', extra=self.prefix)
            except:
                try:
                    logging.error(f'Port {self.pub_reg_port} already in use, attempting next port', extra=self.prefix)
                    success = False
                    self.pub_reg_port += 1
                except Exception as e:
                    print(e)
        logging.debug("Finished loop", extra=self.prefix)

    def setup_sub_port_reg_binding(self):
        """
        Method to bind socket to network address to begin publishing/accepting client connections
        using bind_port specified. If bind_port already in use, increment and keep trying until success.
        """
        success = False
        while not success:
            try:
                logging.info(f'Attempting bind to port {self.sub_reg_port}', extra=self.prefix)
                self.sub_reg_socket.bind(f'tcp://*:{self.sub_reg_port}')
                success = True
                logging.info(f'Successful bind to port {self.sub_reg_port}', extra=self.prefix)
            except:
                try:
                    logging.error(f'Port {self.sub_reg_port} already in use, attempting next port', extra=self.prefix)
                    success = False
                    self.sub_reg_port += 1
                except Exception as e:
                    print(e)
        logging.debug("Finished loop", extra=self.prefix)

    def parse_events(self, index):
        """ BOTH CENTRAL AND DECENTRALIZED DISSEMINATION
        Parse events returned by ZMQ poller and handle accordingly
        Args:
        - index (int) - event index, just used for logging current event loop index
         """
        # find which socket was enabled and accordingly make a callback
        # Note that we must check for all the sockets since multiple of them
        # could have been enabled.
        # The return value of poll() is a socket to event mask mapping
        # logging.debug("Polling for events...", extra=self.prefix)
        try:
            events = dict(self.poller.poll())
        except zmq.error.ZMQError as e:
            if 'Socket operation on non-socket' in str(e):
                logging.error(f'Exception with self.poller.poll(): {e}', extra=self.prefix)
                self.disconnect()
                sys.exit(1)

        if self.pub_reg_socket in events:
            self.register_pub()
            if self.centralized:
                # Open a SUB socket to receive from publisher
                self.update_receive_socket()
        elif self.sub_reg_socket in events:
            logging.debug(f"Event {index}: subscriber", extra=self.prefix)
            self.register_sub()
        # For centralized dissemination, also handle sending
        if self.centralized:
            for topic in self.receive_socket_dict.keys():
                if self.receive_socket_dict[topic] in events:
                    self.send(topic)

    #################################################################
    # Run the event loop
    #################################################################
    def event_loop(self):
        """ BOTH CENTRAL AND DECENTRALIZED DISSEMINATION
        Poll for events either indefinitely or until a specific
        event count (self.max_event_count, passed in constructor) is reached """
        print("Start Event Loop")
        if self.indefinite:
            logging.debug("Begin indefinite event poll loop", extra=self.prefix)
            i = 0 # index used just for logging event index
            while True:
                i += 1
                self.parse_events(i)
        else:
            logging.debug(f"Begin finite (max={self.max_event_count}) event poll loop", extra=self.prefix)
            event_count = 0
            while event_count < self.max_event_count:
                self.parse_events(event_count+1)
                event_count += 1

    # once a publisher register with broker, the broker will start to receive message from it
    # for a particular topic, the broker will open a SUB socket for a topic
    def update_receive_socket(self):
        """ CENTRALIZED DISSEMINATION
        Once publisher registers with broker, broker will begin receiving messages from it
        for a given topic; broker must open a SUB socket for the topic if not already opened"""
        logging.debug("Updating receive socket to 'subscribe' to publisher", extra=self.prefix)
        for topic in self.publishers.keys():
            if topic not in self.receive_socket_dict.keys():
                self.receive_socket_dict[topic] = self.context.socket(zmq.SUB)
                self.poller.register(self.receive_socket_dict[topic], zmq.POLLIN)
            for address in self.publishers[topic]:
                logging.debug(f"'Subscribing' to publisher {address}", extra=self.prefix)
                self.receive_socket_dict[topic].connect(f"tcp://{address}")
                self.receive_socket_dict[topic].setsockopt_string(zmq.SUBSCRIBE, topic)
        # logging.debug("Broker Receive Socket: {0:s}".format(str(list(self.receive_socket_dict.keys()))))

    def send(self, topic):
        """ CENTRALIZED DISSEMINATION
        Take a received message for a given topic and forward
        that message to the appropriate set of subscribers using
        send_socket_dict[topic] """
        if topic in self.send_socket_dict.keys():
            # received_message = self.receive_socket_dict[topic].recv_string()
            [topic,received_message] = self.receive_socket_dict[topic].recv_multipart()
            unpickled_message = pickle.loads(received_message)
            logging.debug(f"Forwarding Msg: <{unpickled_message}>", extra=self.prefix)
            # self.send_socket_dict[topic].send_string(received_message)
            self.send_socket_dict[topic.decode('utf8')].send_multipart([topic, received_message])

    def get_clear_port(self):
        """ Method to get a clear port that has not been allocated """
        while True:
            port = random.randint(10000, 20000)
            if port not in self.used_ports:
                break
        return port

    def disconnect_sub(self, msg):
        """ Method to remove data related to a disconnecting subscriber """
        logging.debug(f"Disconnecting subscriber...", extra=self.prefix)
        dc = msg['disconnect']
        topics = dc['topics']
        address = dc['address']
        sub_id = dc['id']
        if not self.centralized:
            notify_port = dc['notify_port']
            self.used_ports.remove(notify_port)
            # Close the notification socket for this subscriber with id as key
            self.notify_sub_sockets[sub_id].close()
        for t in topics:
            if t in self.subscribers:
                # if only subscriber to topic, remove topic altogether
                if len(self.subscribers[t]) == 1:
                    self.subscribers.pop(t)
                    if self.centralized:
                        # Close socket then remove. No other subscribers active for t.
                        self.send_socket_dict[t].close()
                        self.send_socket_dict.pop(t)
                else:
                    # Remove just this subscriber
                    self.subscribers[t].remove(address)
                    # No need to update self.send_socket_dict. No outward connections with connect()
                    # to disconnect() as with receive_socket_dict.

        response = {'disconnect': 'success'}
        return json.dumps(response)

    def register_sub(self):
        """ BOTH CENTRAL AND DECENTRALIZED DISSEMINATION
        Register a subscriber address as interested in a set of topics """
        try:
            # the format of the registration string is a json
            # '{ "address":"1234", "topics":['A', 'B']}'
            logging.debug("Subscriber Registration Started", extra=self.prefix)
            sub_reg_string = self.sub_reg_socket.recv_string()
            # Get topics and address of subscriber
            sub_reg_dict = json.loads(sub_reg_string)

            # Handle disconnect if requested
            if 'disconnect' in sub_reg_dict:
                response = self.disconnect_sub(msg=sub_reg_dict)
                # send response
                self.sub_reg_socket.send_string(response)
                return

            topics = sub_reg_dict['topics']
            sub_address = sub_reg_dict['address']
            sub_id = sub_reg_dict['id']
            for topic in topics:
                if topic not in self.subscribers.keys():
                    self.subscribers[topic] = [sub_address]
                else:
                    self.subscribers[topic].append(sub_address)

            if not self.centralized:
                # Allocate a random unique port to notify this subscriber about new hosts.
                # Port must be different for each subscriber since they are each polling
                # and subscribers steal poll pipeline events from each other.
                notify_port = self.get_clear_port()
                msg = {'register_sub': {'notify_port': notify_port}}
                ## Notify new subscriber about all publishers of topic
                ## so they can listen directly
                # Set up a new notify socket on a clear port for this subscriber
                logging.debug("Enabling subscriber notification (about publishers)",
                    extra=self.prefix)
                self.notify_sub_sockets[sub_id] = self.context.socket(zmq.REQ)
                self.used_ports.append(notify_port)
                self.notify_sub_sockets[sub_id].bind(f"tcp://*:{notify_port}")
                self.sub_reg_socket.send_string(json.dumps(msg))
                self.notify_subscribers(topics=topics, sub_id=sub_id)
            else:
                ## Make sure there is a socket for each new topic.
                self.update_send_socket()

                ## Publish topic messages to subscribers.
                reply_sub_dict = {}
                for topic in sub_reg_dict['topics']:
                    reply_sub_dict[topic] = self.send_port_dict[topic]
                logging.debug(f"Sending topic/ports: {reply_sub_dict}", extra=self.prefix)
                self.sub_reg_socket.send_string(json.dumps(reply_sub_dict, indent=4))

            logging.debug("Subscriber registered successfully", extra=self.prefix)
        except Exception as e:
            logging.error(e, extra=self.prefix)

    def notify_subscribers(self, topics, pub_address=None, sub_id=None):
        """ DECENTRALIZED DISSEMINATION
        Tell the subscribers of a given topic that a new publisher
        of this topic has been added; they should start listening to
        that/those publishers directly """
        logging.debug("Notifying subscribers", extra=self.prefix)
        message = []
        addresses = []
        if pub_address: # when registering single new publisher
            message = [
                {
                    'register_pub': {
                        'addresses': [pub_address],
                        'topic': topic
                    }
                } for topic in topics
            ]
            message = json.dumps(message)
            # Send to notify socket for each subscriber
            for sub_id, notify_socket in self.notify_sub_sockets.items():
                logging.debug(f"Sending notification to sub: {sub_id}", extra=self.prefix)
                notify_socket.send_string(message)
                logging.debug(f"Waiting for response...", extra=self.prefix)
                confirmation = notify_socket.recv_string()
                logging.debug(f"Subscriber notified successfully (confirmation: <{confirmation}>", extra=self.prefix)

        else: # when registering a new subscriber
            for t in topics:
                if t in self.publishers:
                    addresses = self.publishers[t]
                else:
                    addresses = []
                message.append(
                    {
                        'register_pub': {
                            'addresses': addresses,
                            'topic': t
                        }
                    }
                )
            message = json.dumps(message)
            # Send to notify socket for new subscriber address
            logging.debug(f"Sending message to subscriber: {message}", extra=self.prefix)
            self.notify_sub_sockets[sub_id].send_string(message)
            logging.debug(f"Waiting for response...", extra=self.prefix)
            confirmation = self.notify_sub_sockets[sub_id].recv_string()
            logging.debug(f"Subscriber notified successfully (confirmation: <{confirmation}>", extra=self.prefix)

    def disconnect_pub(self, msg):
        """ Method to remove data related to a disconnecting publisher """
        logging.debug(f"Disconnecting publisher...", extra=self.prefix)
        dc = msg['disconnect']
        topics = dc['topics']
        address = dc['address']
        for t in topics:
            # If this is the only publisher of a topic, remove the topic from
            # self.publishers and from self.receive_socket_dict
            if len(self.publishers[t]) == 1:
                self.publishers.pop(t,None)
                if self.centralized:
                    # Close socket then remove. No other publishers active for t.
                    self.receive_socket_dict[t].close()
                    self.receive_socket_dict.pop(t)
            else:
                # Only remove the single publisher connection from
                # publisher connections for this topic
                self.publishers[t].remove(address)
                if self.centralized:
                    self.receive_socket_dict[t].disconnect(address)
        response = {'disconnect': 'success'}
        return json.dumps(response)

    def register_pub(self):
        """ BOTH CENTRAL AND DECENTRALIZED DISSEMINATION
        Register (or disconnect) a publisher as a publisher of a given topic,
        e.g. 1.2.3.4 registering as publisher of topic "XYZ" """
        try:
            # the format of the registration string is a json
            # '{ "address":"1234", "topics":['A', 'B']}'
            pub_reg_string = self.pub_reg_socket.recv_string()
            logging.debug(f"Publisher Registration Started: {pub_reg_string}", extra=self.prefix)
            pub_reg_dict = json.loads(pub_reg_string)
            # Handle disconnect if requested
            if 'disconnect' in pub_reg_dict:
                response = self.disconnect_pub(msg=pub_reg_dict)
                # send response
                self.pub_reg_socket.send_string(response)
                return
            pub_address = pub_reg_dict['address']
            for topic in pub_reg_dict['topics']:
                if topic not in self.publishers.keys():
                    self.publishers[topic] = [pub_address]
                else:
                    self.publishers[topic].append(pub_address)

            if not self.centralized:
                # For de-centralized dissemination:
                # Subscribers interested in this topic need to know to listen
                # directly to this new publisher.
                # This starts a while loop on the subscriber.
                self.notify_subscribers(pub_reg_dict['topics'], pub_address=pub_address)
            response = {'success': 'registration success'}
        except Exception as e:
            response = {'error': f'registration failed due to exception: {e}'}
        logging.debug(f"Sending response: {response}", extra=self.prefix)
        self.pub_reg_socket.send_string(json.dumps(response))
        logging.debug("Publisher Registration Succeeded", extra=self.prefix)

    def get_host_address(self):
        """ Method to return IP address of current host.
        If using a mininet topology, use netifaces (socket.gethost... fails on mininet hosts)
        Otherwise, local testing without mininet, use localhost 127.0.0.1 """
        try:
            # Will succeed on mininet. Two interfaces, get second one.
            # Then get AF_INET address family with key = 2
            # Then get first element in that address family (0)
            # Then get addr property of that element.
            address = netifaces.ifaddresses(netifaces.interfaces()[-1])[2][0]['addr']
            address = f'{address}'
        except:
            address = f"127.0.0.1"
        return address

    def update_send_socket(self):
        """ CENTRALIZED DISSEMINATION
        Once a subscriber registers with the broker, the broker must
        create a socket to publish the topic; the broker will let the
        subscriber know the port """
        # Use PUB sockets (one per topic) for sending publish events
        for topic in self.subscribers.keys():
            if topic not in self.send_socket_dict.keys():
                self.send_socket_dict[topic] = self.context.socket(zmq.PUB)
                while True:
                    port = random.randint(10000, 20000)
                    if port not in self.send_port_dict.values():
                        break
                self.send_port_dict[topic] = port
                logging.debug(f"Topic {topic} is being sent at port {port}", extra=self.prefix)
                self.send_socket_dict[topic].bind(f"tcp://{self.get_host_address()}:{port}")

    def disconnect(self):
        """ Method to disconnect from the publish/subscribe system by destroying the ZMQ context """
        print("Disconnect")
        try:
            logging.info("Disconnecting. Destroying ZMQ context..", extra=self.prefix)
            self.context.destroy()
        except Exception as e:
            logging.error(f"Failed to destroy context: {e}", extra=self.prefix)