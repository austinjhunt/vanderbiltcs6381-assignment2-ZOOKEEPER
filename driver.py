import argparse
import logging
from publisher import Publisher
from subscriber import Subscriber
from broker import Broker

def create_publishers(count=1):
    logging.info(f'Creating {count} publishers')
    pubs = {}
    for i in range(count):
        pubs[i] = Publisher()
    return pubs

def create_subscribers(count=1):
    logging.info(f'Creating {count} subscribers')
    subs = {}
    for i in range(count):
        subs[i] = Subscriber()
    return subs

def create_broker():
    broker = Broker()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Pass arguments to create publishers, subscribers, or an intermediate message broker')
    parser.add_argument('-v', '--verbose', help='increase output verbosity', action='store_true')
    # Choose type of entity
    parser.add_argument('-pub', '--publisher',  type=int,
        help='pass this followed by an integer N to create N publishers on this host')
    parser.add_argument('-sub', '--subscriber', type=int,
        help='pass this followed by an integer N to create N subscribers on this host')
    parser.add_argument('--broker', type=int,
        help='pass this followed by an integer N to create N publishers on this host')

    # Required with either --pub or --sub
    parser.add_argument('-t', '--topics', action='append',
        help=('if creating a pub or sub, provide list of topics to either publish or subscribe to.'
        ' required if using --sub or --pub '))
    parser.add_argument('-m', '--max_event_count', type=int, default=15,
        help=(
            'if used with --sub, max num of published events to receive. '
            'if used with --pub, max number of events to publish. default=15. '
            'this only matters if --indefinite is not used'))
    parser.add_argument('-i', '--indefinite', action='store_true',
        help=(
            'if used with --pub, publish events indefinitely from created publisher(s). '
            'if used with --sub, receive published events indefinitely with created subscriber(s)'
        ))

    # Required with --pub
    parser.add_argument('-b', '--bind_port', type=int,
        help='(for use with --pub) port on which to publish. If not provided with --pub, port 5556 used.')
    parser.add_argument('-s', '--sleep', type=float,
        help='Number of seconds to sleep between publish events. If not provided, 1 second used.')

    args = parser.parse_args()

    if args.broker and args.broker > 1:
        raise argparse.ArgumentTypeError('Maximum broker count is 1 (one)')

    # Default log level = warning
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
        logging.debug('Debug mode enabled')

    logging.debug(F'Creating {args.publisher if args.publisher else 0} publishers on this host')
    logging.debug(F'Creating {args.subscriber if args.subscriber else 0} subscribers on this host')
    logging.debug(F'Creating {args.broker if args.broker else 0} broker on this host')

    if (args.publisher and args.subscriber) or (args.publisher and args.broker) or \
        (args.broker and args.subscriber):
        raise argparse.ArgumentError(
            'Host should have 1) only publishers, 2) only subscribers, '
            'or 3) only a broker, not a . Cannot use mix of --publisher, '
            '--subscriber, --broker'
            )

    if args.publisher:
        if not args.topics:
            raise argparse.ArgumentError(
                'If creating a publisher with --publisher you must provide a set of topics to '
                'publish with -t <topic> [-t <topic> ...]'
                )
        create_publishers(count=args.publisher)
    if args.subscriber:
        if not args.topics:
            raise argparse.ArgumentError(
                'If creating a subscriber with --subscriber, you must provide a set of topics to '
                'subscribe to with -t <topic> [-t <topic> ...]'
                )
        create_subscribers(count=args.subscriber)
    if args.broker:
        create_broker()

