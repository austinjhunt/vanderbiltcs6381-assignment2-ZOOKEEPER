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
    def __init__(self, own_address='127.0.0.1', centralized=False, indefinite=False, max_event_count=15):
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
        self.own_address = own_address
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
        self.notify_sub_socket = None

        # this is the centralized dissemination system
        # broker will have a list of sockets for receiving from publisher
        # broker will also have a list of sockets for sending to subscrbier
        self.receive_socket_dict = {}
        self.send_socket_dict = {}
        self.send_port_dict = {}

    def configure(self):
        """ Method to perform initial configuration of Broker entity """
        #  The zmq context
        self.context = zmq.Context()
        # we will use the poller to poll for incoming data
        self.poller = zmq.Poller()
        # these are the sockets we open one for each registration
        logging.debug("Opening two REP sockets for publisher registration "
            "and subscriber registration", extra=self.prefix)
        logging.debug("Enabling publisher registration on port 5555", extra=self.prefix)
        logging.debug("Enabling subscriber registration on port 5556", extra=self.prefix)
        self.pub_reg_socket = self.context.socket(zmq.REP)
        self.pub_reg_socket.bind("tcp://*:5555")
        self.sub_reg_socket = self.context.socket(zmq.REP)
        self.sub_reg_socket.bind("tcp://*:5556")

        if not self.centralized:
            logging.debug("Enabling subscriber notification (about publishers) on port 5557",
                extra=self.prefix)
            self.notify_sub_socket = self.context.socket(zmq.REQ)
            self.notify_sub_socket.bind("tcp://*:5557")

        # register these sockets for incoming data
        logging.debug("Register sockets with a ZMQ poller", extra=self.prefix)
        self.poller.register(self.pub_reg_socket, zmq.POLLIN)
        self.poller.register(self.sub_reg_socket, zmq.POLLIN)

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
        events = dict(self.poller.poll())
        if self.pub_reg_socket in events:
            logging.debug(f"Event {index}: publisher", extra=self.prefix)
            self.register_pub()
            if self.centralized:
                # Open a SUB socket to receive from publisher
                self.update_receive_socket()
        if self.sub_reg_socket in events:
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
        if self.indefinite:
            logging.debug("Begin indefinite event poll loop", extra=self.prefix)
            i = 0 # index used just for logging event index
            while True:
                i += 1
                self.parse_events(i)
        else:
            logging.debug(f"Begin finite (max={self.max_event_count}) event poll loop", extra=self.prefix)
            for i in range(self.max_event_count):
                self.parse_events(i+1)

    def notify_subscribers(self, topic, pub_address=None):
        """ DECENTRALIZED DISSEMINATION
        Tell the subscribers of a given topic that a new publisher
        of this topic has been added; they should start listening to
        that/those publishers directly """

        addresses = None
        if pub_address: # when registering single new publisher
            addresses = [pub_address]
        elif topic in self.publishers: # when registering a new subscriber
            addresses = self.publishers[topic]
        else: # when registering a new subscriber and no publishers of their topic
            addresses = []
        message = {
            'register_pub': {
                'addresses': addresses,
                'topic': topic
            }
        }
        message = json.dumps(message)
        if pub_address:
            # notify relevant subscribers about specific publisher for topic
            # (when registering pub)
            logging.debug(
                    f'Notifying relevant subscribers about newly registered publisher '
                    f'of topic <{topic}>', extra=self.prefix)
        else:
            # notify relevant subscribers about all publishers for topic
            # (when registering sub)
            logging.debug(f"Notifying newly registered subscriber about publishers of topic {topic}!",
                extra=self.prefix)

        # Send message to socket associated with this topic.
        # If topic not stored here, no one is subscribed to it. no need to send.
        self.notify_sub_socket.send_string(message)
        # Wait for a response
        logging.debug(f"Waiting for response...", extra=self.prefix)
        confirmation = self.notify_sub_socket.recv_string()
        logging.debug(f"Subscriber notified successfully (confirmation: <{confirmation}>", extra=self.prefix)

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
            received_message = self.receive_socket_dict[topic].recv_string()
            logging.debug(f"Forwarding Msg: <{received_message}>", extra=self.prefix)
            self.send_socket_dict[topic].send_string(received_message)

    def register_sub(self):
        """ BOTH CENTRAL AND DECENTRALIZED DISSEMINATION
        Register a subscriber address as interested in a set of topics """
        try:
            # the format of the registration string is a json
            # '{ "address":"1234", "topics":['A', 'B']}'
            logging.debug("Subscriber Registration Started", extra=self.prefix)
            sub_reg_string = self.sub_reg_socket.recv_string()
            sub_reg_dict = json.loads(sub_reg_string)
            topics = sub_reg_dict['topics']
            for topic in topics:
                if topic not in self.subscribers.keys():
                    self.subscribers[topic] = [sub_reg_dict['address']]
                else:
                    self.subscribers[topic].append(sub_reg_dict['address'])
                if not self.centralized:
                    ## Notify new subscriber about all publishers of topic
                    ## so they can listen directly
                    self.notify_subscribers(topic=topic)

            if self.centralized:
                ## Make sure there is a socket for each new topic.
                self.update_send_socket()
                ## Publish topic messages to subscribers.
                reply_sub_dict = {}
                for topic in sub_reg_dict['topics']:
                    reply_sub_dict[topic] = self.send_port_dict[topic]
                self.sub_reg_socket.send_string(json.dumps(reply_sub_dict, indent=4))
                confirmation = self.sub_reg_socket.recv_string()
                logging.debug(f"Subscriber acknowledged topic ports: {confirmation}", extra=self.prefix)
            response = {'success': 'registration complete'}
        except Exception as e:
            response = {'error': f'registration failed due to exception: {e}'}
        # Respond to registration request with either confirmation of failure message
        self.sub_reg_socket.send_string(json.dumps(response))

    def register_pub(self):
        """ BOTH CENTRAL AND DECENTRALIZED DISSEMINATION
        Register a publisher as a publisher of a given topic,
        e.g. 1.2.3.4 registering as publisher of topic "XYZ" """
        try:
            # the format of the registration string is a json
            # '{ "address":"1234", "topics":['A', 'B']}'
            logging.debug("Publisher Registration Started", extra=self.prefix)
            pub_reg_string = self.pub_reg_socket.recv_string()
            pub_reg_dict = json.loads(pub_reg_string)
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
                    self.notify_subscribers(topic=topic, pub_address=pub_address)
            response = {'success': 'registration success'}
        except Exception as e:
            response = {'error': f'registration failed due to exception: {e}'}
        self.pub_reg_socket.send_string(json.dumps(response))
        logging.debug("Publisher Registration Succeeded", extra=self.prefix)

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
                self.send_socket_dict[topic].bind(f"tcp://{self.own_address}:{port}")








