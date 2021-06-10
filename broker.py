"""
Message Broker to serve as anonymizing middleware between
publishers and subscribers
"""
import zmq
import json
import traceback
import random
class Broker:
    #################################################################
    # constructor
    #################################################################
    def __init__(self, address='127.0.0.1'):
        self.address = address

        self.subscribers = {}
        self.publishers = {}


        #  The zmq context
        self.context = None

        # we will use the poller to poll for incoming data
        self.poller = None

        # these are the sockets we open one for each registration
        self.pub_reg_socket = None
        self.sub_reg_socket = None

        # this is the centralized disimention system
        # broker will have a list of sockets for receiving from publisher
        # broker will also have a list of sockets for sending to subscrbier
        self.receive_socket_dict = {}
        self.send_socket_dict = {}
        self.send_port_dict = {}

    #################################################################
    # configure the broker
    #################################################################
    def configure(self):
        # first get the context
        print ("Broker::configure - set the context object")
        self.context = zmq.Context()

        # obtain the poller
        print ("Broker::configure - set the poller object")
        self.poller = zmq.Poller()

        # now create sockets for publisher and subscriber registration
        print("Broker::configure - open two REP sockets for publisher registration and subscriber registration")
        print("Broker::configure - Publisher registration on port 5555")
        print("Broker::configure - Subscriber registration on port 5556")
        self.pub_reg_socket = self.context.socket(zmq.REP)
        self.pub_reg_socket.bind("tcp://*:5555")
        self.sub_reg_socket = self.context.socket(zmq.REP)
        self.sub_reg_socket.bind("tcp://*:5556")

        # register these sockets for incoming data
        print("Broker::configure - register our sockets with a poller")
        self.poller.register(self.pub_reg_socket, zmq.POLLIN)
        self.poller.register(self.sub_reg_socket, zmq.POLLIN)

    #################################################################
    # run the event loop
    #################################################################
    def event_loop(self):
        print ("Broker:event_loop - run the event loop")
        while True:
            # poll for events. We give it an infinite timeout.
            # The return value is a socket to event mask mapping
            events = dict(self.poller.poll())

            # find which socket was enabled and accordingly make a callback
            # Note that we must check for all the sockets since multiple of them
            # could have been enabled.
            if self.pub_reg_socket in events:
                print("Broker:event_loop - publisher ")
                self.register_pub()
                self.update_receive_socket()

            if self.sub_reg_socket in events:
                self.register_sub()

            for topic in self.receive_socket_dict.keys():
                if self.receive_socket_dict[topic] in events:
                    self.send(topic)

    # when someone register to publich a topic "XYZ",
    def register_pub(self):
        # the format of the registration string is a json
        # '{ "address":"1234", "topics":['A', 'B']}'
        print("Broker:event_loop - Publisher Registration Started")
        pub_reg_string = self.pub_reg_socket.recv_string()
        pub_reg_dict = json.loads(pub_reg_string)

        for topic in pub_reg_dict['topics']:
            if topic not in self.publishers.keys():
                self.publishers[topic] = [pub_reg_dict['address']]
            else:
                self.publishers[topic].append(pub_reg_dict['address'])
        self.pub_reg_socket.send_string("Publisher Registration Succeed")
        print("Broker:event_loop - Publisher Registration Succeed")
        # print("Current Pulisher Info:")
        # print(json.dumps(self.publishers, indent=4))

    # once a publisher register with broker, the broker will start to receive message from it
    # for a particular topic, the broker will open a SUB socket for a topic
    def update_receive_socket(self):
        for topic in self.publishers.keys():
            if topic not in self.receive_socket_dict.keys():
                self.receive_socket_dict[topic] = self.context.socket(zmq.SUB)
                self.poller.register(self.receive_socket_dict[topic], zmq.POLLIN)
            for address in self.publishers[topic]:
                self.receive_socket_dict[topic].connect("tcp://{0:s}".format(address))
                self.receive_socket_dict[topic].setsockopt_string(zmq.SUBSCRIBE, topic)
        # print("Broker Receive Socket: {0:s}".format(str(list(self.receive_socket_dict.keys()))))



    def send(self, topic):
        if topic in self.send_socket_dict.keys():
            received_message = self.receive_socket_dict[topic].recv_string()
            print(f"Broker Sending {received_message}")
            self.send_socket_dict[topic].send_string(received_message)


    def register_sub(self):
        # the format of the registration string is a json
        # '{ "address":"1234", "topics":['A', 'B']}'
        print("Broker:event_loop - Subscriber Registration Started")
        sub_reg_string = self.sub_reg_socket.recv_string()
        sub_reg_dict = json.loads(sub_reg_string)

        for topic in sub_reg_dict['topics']:
            if topic not in self.subscribers.keys():
                self.subscribers[topic] = [sub_reg_dict['address']]
            else:
                self.subscribers[topic].append(sub_reg_dict['address'])

        # once a subscriber register with the broker,
        # the broker will create socket to publish the topic
        # the broker will let the subscriper know the port
        self.update_send_socket()
        reply_sub_dict = {}
        for topic in sub_reg_dict['topics']:
            reply_sub_dict[topic] = self.send_port_dict[topic]
        self.sub_reg_socket.send_string(json.dumps(reply_sub_dict, indent=4))
        print("Broker:event_loop - Subscriber Registration Succeed")
        # print("Current Subscriber Info:")
        # print(json.dumps(self.subscribers, indent=4))


    def update_send_socket(self):
        for topic in self.subscribers.keys():
            if topic not in self.send_socket_dict.keys():
                self.send_socket_dict[topic] = self.context.socket(zmq.PUB)
#                self.poller.register(self.send_socket_dict[topic], zmq.POLLOUT)
                while True:
                    port = random.randint(10000, 20000)
                    if port not in self.send_port_dict.values():
                        break
                self.send_port_dict[topic] = port
                print("Broker:event_loop - Topic {0:s} is being sent at port {1:d}".format(topic, port))
                self.send_socket_dict[topic].bind("tcp://{0:s}:{1:d}".format(self.address, port))
        # print("Broker Send Socket: {0:s}".format(str(list(self.send_socket_dict.keys()))))
