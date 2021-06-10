import sys
import argparse   # argument parser
import zmq
from publisher import Publisher
from subscriber import Subscriber
from broker import Broker

##################################
# Command line parsing
##################################
def parseCmdLineArgs ():
    # parse the command line
    parser = argparse.ArgumentParser ()

    # add optional arguments
    parser.add_argument ("-b", "--broker",  action="store_true", help="indicate if it is a broker")
    parser.add_argument ("-p", "--publisher",  action="store_true", help="indicate if it is a publisher")
    parser.add_argument ("-s", "--subscriber",  action="store_true", help="indicate if it is a publisher")
    parser.add_argument ("-t", "--topics", action='append')
    parser.add_argument ("-o", "--own", default="127.0.0.1", help="own address")
    parser.add_argument ("-a", "--address", default="127.0.0.1", help="broker_address")
    parser.add_argument ('-m', '--max_event_count', default=15, type=int)
    parser.add_argument ('-i', '--indefinite', action="store_true")
   # parse the args
    args = parser.parse_args ()
    return args

def main():
    try:
        args = parseCmdLineArgs()
        if args.broker:
            a_broker = Broker(args.own)
            a_broker.configure()
            a_broker.event_loop()
        elif args.publisher:
            a_publisher = Publisher(broker_address=args.address,
                                    own_address=args.own,
                                    topics=args.topics,
                                    max_event_count=args.max_event_count,
                                    indefinite=args.indefinite)
            a_publisher.configure()
            a_publisher.register_pub()
            a_publisher.publish()
        elif args.subscriber:
            a_subscriber = Subscriber(broker_address=args.address,
                                    own_address=args.own,
                                    topics=args.topics,
                                    max_event_count=args.max_event_count,
                                    indefinite=args.indefinite)
            a_subscriber.configure()
            a_subscriber.register_sub()
            a_subscriber.notify()
    except KeyboardInterrupt:
        print('> User forced exit!')
    except Exception as e:
        print("Oops!", e.__class__, "occurred.")


if __name__ == "__main__":
    main()
