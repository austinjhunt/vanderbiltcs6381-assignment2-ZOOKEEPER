
## Architecture

The following sections provide an overview of the basic architecture of this project, outlining the core entities that interact to form a fully-functional Publish-Subscribe distributed system with optional broker-based anonyomization between publishers and subscribers.


### The Subscriber [(src/lib/subscriber.py)](src/lib/subscriber.py)

#### Constructor
```
subscriber = Subscriber(
    filename=<file to write received messages>,
    broker_address=<IP address of broker (created before subscriber)>,
    topics=<list of topics of interest for subscriber>,
    indefinite=<whether to listen indefinitely, default false>,
    max_event_count=<max number of publish events to receive if not indefinite>,
    centralized=<whether publish subscribe system uses centralized broker dissemination>
)
```
#### Underlying methods
```
def configure(self):
    """ Method to perform initial configuration of Subscriber entity """

def register_sub(self):
    """ Register self with broker """

def parse_publish_event(self, topic=""):
    """ Method to parse a published event for a given topic
    Args: topic (string) - topic this publish event corresponds to
    """

def notify(self):
    """ Method to poll for published events (or notifications about new publishers from broker) either indefinitely (if indefinite=True in constructor) or until max_event_count (passed to constructor) is reached. """

def write_stored_messages(self):
    """ Method to write all stored messages to filename passed to constructor """

def get_host_address(self):
    """ Method to return IP address of current host.
    If using a mininet topology, use netifaces (socket.gethost... fails on mininet hosts)
    Otherwise, local testing without mininet, use localhost 127.0.0.1 """

def disconnect(self):
    """ Method to disconnect from the pub/sub network """

###################################################################################
#######################  CENTRALIZED DISSEMINATION METHODS  #######################
###################################################################################
def setup_broker_topic_port_connections(self, received_message):
    """ Method to set up one socket per topic to listen to the broker
    where each topic is published from a different port on the broker address
    Args: received_message (dict) - message received from broker containing mapping
    between topics published from the broker and ports on which they will be published
    """

###################################################################################
######################  DECENTRALIZED DISSEMINATION METHODS  ######################
###################################################################################
def setup_notification_polling(self):
    """ Method to set up a socket for polling for notifications about
    new publishers from the broker. The notify port is randomly allocated
    by the broker when the subscriber registers and is sent back to be passed
    to this method
    Args:
    - notify_port (int) """

def setup_publisher_direct_connections(self, notification=None):
    """ Method to set up direct connections with publishers
    provided by the broker based on the topic that a subscriber has
    just registered itself with
    Args:
    - notification (list of dicts) new publisher notification from broker in JSON form
    """

def parse_notification(self):
    """ Method to parse notification about new publishers from broker
    IF there are new publishers, setup direct connections. """

```
 The Subscriber class, representing a subscriber in a publish/subscribe distributed system, can be configured differently across multiple variables.
 #### How Long it Listens
 The subscriber can be configured to either listen **indefinitely** or listen until a **specified number of published events** have been received. If configured to listen indefinitely, the subscriber cannot be configured with a ```filename``` to write received message data out, as this write does not happen in real-time to avoid slowing the Subscriber down. It writes data If configured to listen with a ```max_event_count```, you have the option of passing ```filename``` to which the subscriber will write received messages (at the end of the notify() loop) in the following CSV format:
 ```
 <publisher IP Address>,<topic published>,<difference between publish time and receive time>
 ```
 This format, simple as it is, was chosen for the purpose of performance testing, where we are interested in latencies between specific Pub/Sub pairs across various virtualized network topologies, where these performance tests are run using [Mininet](http://mininet.org/walkthrough/), seen (for example) in [src/performance_tests/centralized.py](src/performance_tests/centralized.py).

#### The Broker Address
The subscriber **must** be provided the IP address of the broker, which also means that the **broker must be created before the subscriber**. This tells the subscriber either 1) where to listen for notifications about new publisher IP addresses (in the case of decentralized dissemination), or 2) where to listen for publish events (in the case of centralized broker dissemination)

#### The Topics
Of course, you can't have a real subscriber if they aren't subscribing to anything. The topics provided to the constructor tell the subscriber what to subscribe to, and this list of topics (which could just be one topic) are sent to the broker during registration (via ```register_pub```) so that the broker can either 1) tell the subscriber about the addresses of new publishers of that topic when they join (for *decentralized dissemination*) or 2) forward published events that match those topic subscriptions from publishers to the subscriber when they are published (for *centralized dissemination*)

#### Centralized or Not
This is perhaps the most important configuration parameter, as it governs the path of a lot of the internal logic of the subscriber. The same is true for the publisher and the broker, as well. In short, if centralized is set to True in the constructor, the subscriber listens only to the broker for published events; basically, in this case, the broker is the one publisher in the distributed system. With centralized dissemination, of course, there is the issue of the broker representing a bottleneck in the system, which means it is more likely that the latency between the original publisher and the subscriber will be greater, so you have the option of setting centralized to False. If you do this, the subscriber will 1) listen for notification events from the broker about IP addresses of newly joined publishers that are publishing a topic of interest, AND 2) listen directly to the publishers (about which the subscriber was notified) for publish events. This **decentralized dissemination method** lessens the load on the Broker and decreases latency between the original publisher(s) and the subscriber, since the connection is direct.

 where with many publishers and many subscribers, the broker has to receive and process all published events and forward them if necessary to subscribers whose subscriptions match those events. So,


### The Publisher [(src/lib/publisher.py)](src/lib/publisher.py)
Class representing a publisher. One or more publishers can be created at a time using the driver. If you create more than one publisher at a time (e.g. ./driver.py --publisher N>1 ), the first publisher will be bound to the bind port you specify (or 5556 if none specified), then the following publisher will be bound to the next port, etcetera. The publisher publishes information independently of the subscriber classes, so if it publishes an update for a topic no subscriber is subscribed to, the publish event just gets dropped. The publisher passes the time of publish as part of the published message, so if a subscriber receives that message, it is able to calculate the difference between publish time and receive time for performance testing with different network topologies. The publisher can publish updates indefinitely (with --indefinite argument to driver.py) or can publish only a specific number of events (with --max_event_count COUNT argument to driver.py). If you pass both --indefinite and --max_event_count COUNT to the driver, indefinite takes priority.

### The Broker [(src/lib/broker.py)](src/lib/broker.py)

## Setup
The setup directory contains bash scripts that provide an abstraction layer above the driver.py script for use with automation. If you want to spin up a set of publishers on a host, use ./setup_publishers.sh with arguments outlined in the script, and alternatively if you want to spin up a set of subscribers (or just one) on a host, use ./setup_subscribers.sh with arguments outlined in the script.

## Unit Testing

## Performance Testing