import zmq
import json
import random
import time
import datetime

class Publisher:
    """
    Class to represent a single publisher in a Publish/Subscribe distributed
    system. Publisher does not need to know who is consuming the information, it
    simply publishes information independently of the consumer. If publisher has
    no connected subscribers, it will drop all messsages it produces.
    """
    def __init__(self, broker_address, own_address,
                 topics=[], sleep_period=1, bind_port=10000, 
                 indefinite=False, max_event_count=15):
        """ Constructor
        args:
        - topics (list) - list of topics to publish
        - sleep_period (int) - number of seconds to sleep between each publish event
        - bind_port - port on which to publish information
        - indefinite (boolean) - whether to publish events/updates indefinitely
        - max_event_count (int) - if not (indefinite), max number of events/updates to publish
        """        
        # when a publisher is initialized. it needs to provide its ip address and its topics
        self.broker_address = broker_address 
        self.own_address = own_address
        self.topics = topics
        self.bind_port = bind_port
        self.indefinite = indefinite
        self.max_event_count = max_event_count 
        self.sleep_period = sleep_period

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
        self.pub_socket = self.context.socket(zmq.PUB)
        success = False
        while not success: 
            try: 
                self.pub_socket.bind(f'tcp://{self.own_address}:{self.bind_port}')
                success = True
            except:
                success = False
                self.bind_port += 1
        print(f"Publisher::configure - binding at {self.own_address}:{self.bind_port} to publish")
        
        

    def register_pub(self):
        print("Publisher::event - registration started")
        message_dict = {'address': f'{self.own_address}:{self.bind_port}', 'topics': self.topics}
        message = json.dumps(message_dict, indent=4)
        self.broker_reg_socket.send_string(message)
        # print("Publisher::event - receive message from broker - : {0:s}".format(self.broker_reg_socket.recv_string()))
        print("Publisher::event - registration completed")
        
    def publish(self):
        print("Publisher::event - start publishing")
        if self.indefinite:
            topic = random.choice(self.topics)
            content = time.time()
            self.pub_socket.send_string(f"{topic} - {content} - {self.own_address}")
            print(f"Publishing: {topic} - {content} - {self.own_address}")
            time.sleep(self.sleep_period)        
        else:
            for i in range(self.max_event_count):
                topic = random.choice(self.topics)
                content = time.time()
                self.pub_socket.send_string(f"{topic} - {content} - {self.own_address}")
                print(f"Publishing: {topic} - {content} - {self.own_address}")
                time.sleep(self.sleep_period)
            
try:
    test = Publisher(broker_address='127.0.0.1', own_address='127.0.0.1', 
                     topics=['A', 'C'], )
    test.configure()
    test.register_pub()
    test.publish()
except KeyboardInterrupt:
    print('> User forced exit!')    
except Exception as e:
    print("Oops!", e.__class__, "occurred.") 
#    traceback.print_exc()

