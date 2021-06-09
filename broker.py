"""
Message Broker to serve as anonymizing middleware between
publishers and subscribers
"""
import zmq
import json
import traceback
import random
import logging
class Broker:
    #################################################################
    # constructor
    #################################################################
    def __init__(self, address='127.0.0.1', centralized=False, indefinite=False, max_event_count=15):
        logging.debug("Initializing")
        self.centralized = centralized
        # Either poll for events indefinitely or for specified max_event_count
        self.indefinite = indefinite
        self.max_event_count = max_event_count
        self.address = address
        self.subscribers = {}
        self.publishers = {}
        #  The zmq context
        self.context = zmq.Context()
        # we will use the poller to poll for incoming data
        self.poller = zmq.Poller()
        # these are the sockets we open one for each registration
        logging.debug("Opening two REP sockets for publisher registration "
            "and subscriber registration")
        logging.debug("Enabling publisher registration on port 5555")
        logging.debug("Enabling subscriber registration on port 5556")
        self.pub_reg_socket = self.context.socket(zmq.REP)
        self.pub_reg_socket.bind("tcp://*:5555")
        self.sub_reg_socket = self.context.socket(zmq.REP)
        self.sub_reg_socket.bind("tcp://*:5556")
        # register these sockets for incoming data
        logging.debug("Register sockets with a ZMQ poller")
        self.poller.register(self.pub_reg_socket, zmq.POLLIN)
        self.poller.register(self.sub_reg_socket, zmq.POLLIN)

        # this is the centralized dissemination system
        # broker will have a list of sockets for receiving from publisher
        # broker will also have a list of sockets for sending to subscrbier
        self.receive_socket_dict = {}
        self.send_socket_dict = {}
        self.send_port_dict = {}

    def parse_events(self, index):
        """ Parse events returned by ZMQ poller and handle accordingly
        Args:
        - index (int) - event index, just used for logging current event loop index
         """
        # find which socket was enabled and accordingly make a callback
        # Note that we must check for all the sockets since multiple of them
        # could have been enabled.
        # The return value of poll() is a socket to event mask mapping
        events = dict(self.poller.poll())
        if self.pub_reg_socket in events:
            logging.debug(f"Event {index}: publisher")
            self.register_pub()
            self.update_receive_socket()
        if self.sub_reg_socket in events:
            logging.debug(f"Event {index}: subscriber")
            self.register_sub()
        # For each stored topic, if it's part of the event, send to subscribers
        for topic in self.receive_socket_dict.keys():
            if self.receive_socket_dict[topic] in events:
                self.send(topic)

    #################################################################
    # Run the event loop
    #################################################################
    def event_loop(self):
        """ Poll for events either indefinitely or until a specific
        event count (self.max_event_count, passed in constructor) is reached """
        if self.indefinite:
            logging.debug("Begin indefinite event poll loop")
            i = 0 # index used just for logging event index
            while True:
                i += 1
                self.parse_events(i)
        else:
            logging.debug(f"Begin finite (max={self.max_event_count}) event poll loop")
            for i in range(self.max_event_count):
                self.parse_events(i+1)

    def register_pub(self):
        """ Register a publisher as a publisher of a given topic,
        e.g. 1.2.3.4 registering as publisher of topic "XYZ" """
        # the format of the registration string is a json
        # '{ "address":"1234", "topics":['A', 'B']}'
        logging.debug("Publisher Registration Started")
        pub_reg_string = self.pub_reg_socket.recv_string()
        pub_reg_dict = json.loads(pub_reg_string)
        for topic in pub_reg_dict['topics']:
            if topic not in self.publishers.keys():
                self.publishers[topic] = [pub_reg_dict['address']]
            else:
                self.publishers[topic].append(pub_reg_dict['address'])
        self.pub_reg_socket.send_string("Publisher Registration Succeed")
        logging.debug("Publisher Registration Succeeded")

    # once a publisher register with broker, the broker will start to receive message from it
    # for a particular topic, the broker will open a SUB socket for a topic
    def update_receive_socket(self):
        """ Once publisher registers with broker, broker will begin receiving messages from it
        for a given topic; broker must open a SUB socket for the topic if not already opened"""
        for topic in self.publishers.keys():
            if topic not in self.receive_socket_dict.keys():
                self.receive_socket_dict[topic] = self.context.socket(zmq.SUB)
                self.poller.register(self.receive_socket_dict[topic], zmq.POLLIN)
            for address in self.publishers[topic]:
                self.receive_socket_dict[topic].connect(f"tcp://{address}")
                self.receive_socket_dict[topic].setsockopt_string(zmq.SUBSCRIBE, topic)
        # logging.debug("Broker Receive Socket: {0:s}".format(str(list(self.receive_socket_dict.keys()))))

    def send(self, topic):
        """ Take a received message for a given topic and forward
        that message to the appropriate set of subscribers using send_socket_dict[topic] """
        if topic in self.send_socket_dict.keys():
            received_message = self.receive_socket_dict[topic].recv_string()
            logging.debug(f"Broker Sending {received_message}")
            self.send_socket_dict[topic].send_string(received_message)

    def register_sub(self):
        """ Register a subscriber address as interested in a set of topics """
        # the format of the registration string is a json
        # '{ "address":"1234", "topics":['A', 'B']}'
        logging.debug("Subscriber Registration Started")
        sub_reg_string = self.sub_reg_socket.recv_string()
        sub_reg_dict = json.loads(sub_reg_string)
        for topic in sub_reg_dict['topics']:
            if topic not in self.subscribers.keys():
                self.subscribers[topic] = [sub_reg_dict['address']]
            else:
                self.subscribers[topic].append(sub_reg_dict['address'])
        # Create socket to publish the topic if not already created
        # Each topic sent from a different port on broker
        self.update_send_socket()
        reply_sub_dict = {}
        for topic in sub_reg_dict['topics']:
            reply_sub_dict[topic] = self.send_port_dict[topic]
        self.sub_reg_socket.send_string(json.dumps(reply_sub_dict, indent=4))
        logging.debug("Subscriber Registration Succeed")

    def update_send_socket(self):
        """ Once a subscriber registers with the broker, the broker must
        create a socket to publish the topic; the broker will let the
        subscriber know the port """
        for topic in self.subscribers.keys():
            if topic not in self.send_socket_dict.keys():
                self.send_socket_dict[topic] = self.context.socket(zmq.PUB)
                while True:
                    port = random.randint(10000, 20000)
                    if port not in self.send_port_dict.values():
                        break
                self.send_port_dict[topic] = port
                logging.debug(f"Topic {topic} is being sent at port {port}")
                self.send_socket_dict[topic].bind(f"tcp://{self.address}:{port}")

class CentralizedDisseminationBroker(Broker):
    def __init__(self, address='127.0.0.1', indefinite=False, max_event_count=15):
        super().__init__(address=address, centralized=True, indefinite=indefinite,
            max_event_count=max_event_count )
        log_format = logging.Formatter('%(message)s')
        log_format._fmt = "CENTRAL BROKER - " + log_format._fmt

class DecentralizedDisseminationBroker(Broker):
    def __init__(self, address='127.0.0.1', indefinite=False, max_event_count=15):
        super().__init__(address=address, centralized=False, indefinite=indefinite,
            max_event_count=max_event_count )
        log_format = logging.Formatter('%(message)s')
        log_format._fmt = "DECENTRAL BROKER - " + log_format._fmt

    # Override subscriber registration
    def register_sub(self):
        """ Register a subscriber address as interested in a set of topics """
        # the format of the registration string is a json
        # '{ "address":"1234", "topics":['A', 'B']}'
        logging.debug("Subscriber Registration Started")
        sub_reg_string = self.sub_reg_socket.recv_string()
        sub_reg_dict = json.loads(sub_reg_string)
        for topic in sub_reg_dict['topics']:
            if topic not in self.subscribers.keys():
                self.subscribers[topic] = [sub_reg_dict['address']]
            else:
                self.subscribers[topic].append(sub_reg_dict['address'])

    def register_pub(self):
        """ Register a publisher as a publisher of a given topic,
        e.g. 1.2.3.4 registering as publisher of topic "XYZ" """
        # the format of the registration string is a json
        # '{ "address":"1234", "topics":['A', 'B']}'
        logging.debug("Publisher Registration Started")
        pub_reg_string = self.pub_reg_socket.recv_string()
        pub_reg_dict = json.loads(pub_reg_string)
        pub_address = pub_reg_dict['address']
        for topic in pub_reg_dict['topics']:
            if topic not in self.publishers.keys():
                self.publishers[topic] = [pub_address]
            else:
                self.publishers[topic].append(pub_address)
            # Subscribers interested in this topic need to know to listen
            # directly to this new publisher.
            self.notify_subscribers_new_publisher(topic, pub_address)
        self.pub_reg_socket.send_string("Publisher Registration Succeed")
        logging.debug("Publisher Registration Succeeded")

    def notify_subscribers(self, topic, pub_address):
        """ Tell the subscribers of a given topic that a new publisher
        of this topic has been added; they should start listening to it directly """
        message = {'register_pub': {'address': pub_address}}
        message = json.dumps(message)
        self.send_socket_dict[topic].send_string(message)

    # Override parse events. No centralized sending of published events.
    def parse_events(self, index):
        """ Parse events returned by ZMQ poller and handle accordingly
        Args:
        - index (int) - event index, just used for logging current event loop index
         """
        # find which socket was enabled and accordingly make a callback
        # Note that we must check for all the sockets since multiple of them
        # could have been enabled.
        # The return value of poll() is a socket to event mask mapping
        events = dict(self.poller.poll())
        if self.pub_reg_socket in events:
            logging.debug(f"Event {index}: publisher")
            self.register_pub()
        if self.sub_reg_socket in events:
            logging.debug(f"Event {index}: subscriber")
            self.register_sub()



