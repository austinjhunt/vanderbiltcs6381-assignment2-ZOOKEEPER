import zmq
import json
import random
import time

class Subscriber:
    #################################################################
    # constructor
    #################################################################
    def __init__(self, address, topics, broker_address):
        # when a subscriber is initialized. it needs to specify its topics
        self.address = address
        self.topics = topics
        self.broker_address = broker_address

        #  The zmq context
        self.context = None

        # we will use the poller to poll for incoming data
        self.poller = None

        # these are the sockets we open one for each subscription
        self.broker_reg_socket = None
        self.sub_socket_dict = {}

    def configure(self):
        # first get the context
        print ("Subscriber::configure - set the context object")
        self.context = zmq.Context()

        # obtain the poller
        print ("Subscriber::configure - set the poller object")
        self.poller = zmq.Poller()

        # now create socket to register with broker
        print("Subscriber::configure - connect to register with broker")
        self.broker_reg_socket = self.context.socket(zmq.REQ)
        self.broker_reg_socket.connect("tcp://{0:s}:5556".format(self.broker_address))
        

    def register_sub(self):
        print("Subscriber::event - registration started")
        message_dict = {'address': self.address, 'topics': self.topics}
        message = json.dumps(message_dict, indent=4)
        self.broker_reg_socket.send_string(message)
        
        received_message = self.broker_reg_socket.recv_string()
        broker_port_dict = json.loads(received_message)
        
        # now create socket to receive message from broker
        for topic in self.topics:
            broker_port = broker_port_dict[topic]
            self.sub_socket_dict[topic] = self.context.socket(zmq.SUB)
            self.poller.register(self.sub_socket_dict[topic], zmq.POLLIN)
            self.sub_socket_dict[topic].connect("tcp://{0:s}:{1:d}".format(self.broker_address, broker_port))
            self.sub_socket_dict[topic].setsockopt_string(zmq.SUBSCRIBE, '')
            print("Subscriber:: Getting Topic {0:s} from Broker at {1:s}:{2:d}".format(topic, self.broker_address, broker_port))
        print("Subscriber::event - registration completed")    
        

    def notify(self):
        print ("Subscriber:event_loop - start to receive message")
        while True:
            events = dict(self.poller.poll())           
            for topic in self.sub_socket_dict.keys():
                if self.sub_socket_dict[topic] in events:
                    print(self.sub_socket_dict[topic].recv_string())
                

try:
    test = Subscriber('60000', ['B'], '127.0.0.1')
    test.configure()
    test.register_sub()
    test.notify()
except KeyboardInterrupt:
    print('> User forced exit!')    
except Exception as e:
    print("Oops!", e.__class__, "occurred.") 