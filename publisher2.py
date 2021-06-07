import zmq
import json
import random
import time

class Publisher:
    #################################################################
    # constructor
    #################################################################
    def __init__(self, address, topics, broker_address):
        # when a publisher is initialized. it needs to provide its ip address and its topics
        self.address = address
        self.topics = topics
        self.broker_address = broker_address

        #  The zmq context
        self.context = None

        # we will use the poller to poll for incoming data
        self.poller = None

        # these are t sockets we open one for each subscription
        self.broker_reg_socket = None
        self.pub_socket = None
        self.pub_port = None

    def configure(self):
        # first get the context
        print ("Publisher::configure - set the context object")
        self.context = zmq.Context()

        # obtain the poller
        print ("Publisher::configure - set the poller object")
        self.poller = zmq.Poller()

        # now create socket to register with broker
        print("Publisher::configure - connect to register with broker")
        self.broker_reg_socket = self.context.socket(zmq.REQ)
        self.broker_reg_socket.connect("tcp://{0:s}:5555".format(self.broker_address))

        # now create socket to publish
        print("Publisher::configure - binding at {0:s} to publish".format(self.address))
        self.pub_socket = self.context.socket(zmq.PUB)
        self.pub_socket.bind("tcp://{0:s}".format(self.address))

    def register_pub(self):
        print("Publisher::event - registration started")
        message_dict = {'address': self.address, 'topics': self.topics}
        message = json.dumps(message_dict, indent=4)
        self.broker_reg_socket.send_string(message)
        # print("Publisher::event - receive message from broker - : {0:s}".format(self.broker_reg_socket.recv_string()))
        print("Publisher::event - registration completed")
        
    def publish(self):
        print("Publisher::event - start publishing")
        for i in range(100):
            topic = random.choice(self.topics)
            content = random.randint(0, 10000)
            self.pub_socket.send_string(f"{topic} {content}")
            print(f"Publishing: {topic} {content}")
            time.sleep(2)
            
try:
    test = Publisher('127.0.0.1:5559', ['B', 'C'], '127.0.0.1')
    test.configure()
    test.register_pub()
    test.publish()
except KeyboardInterrupt:
    print('> User forced exit!')    
except Exception as e:
    print("Oops!", e.__class__, "occurred.") 
#    traceback.print_exc()

