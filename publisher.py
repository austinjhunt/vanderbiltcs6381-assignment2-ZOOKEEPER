import socket as sock
import zmq
import logging
import time
class Publisher:
    """ Class to represent a single publisher in a Publish/Subscribe distributed
    system. Publisher does not need to know who is consuming the information, it
    simply publishes information independently of the consumer. If publisher has
    no connected subscribers, it will drop all messsages it produces. """

    def __init__(self, topics=[], sleep_period=1, bind_port=5556,
        indefinite=False, max_event_count=15):
        """ Constructor
        args:
        - topics (list) - list of topics to publish
        - sleep_period (int) - number of seconds to sleep between each publish event
        - bind_port - port on which to publish information
        - indefinite (boolean) - whether to publish events/updates indefinitely
        - max_event_count (int) - if not (indefinite), max number of events/updates to publish
        """
        self.topics = topics
        self.sleep_period = sleep_period
        self.bind_port = bind_port
        self.indefinite = indefinite
        self.max_event_count = max_event_count

        # Create ZMQ context
        self.zmq_context = zmq.Context()
        # Create and store single zmq publisher socket type
        self.socket = self.zmq_context.socket(zmq.PUB)
        # Bind socket to network address to begin accepting client connections
        # using port specified
        self.socket.bind(f'tcp://*:{self.bind_port}')


    # Maybe define a maximum number of topics per publisher
    max_num_topics = 0

    # Assumption:
    # Publisher is only going to publish a limited number of topics.
    import random
    def publish(self):
        if self.indefinite:
            while True:
                event = {
                    'testing': 'okay'
                }
                self.socket.send_json(event)
                time.sleep(self.sleep_period)