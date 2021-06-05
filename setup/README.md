## Setup
This folder contains a set of bash scripts that can be used to automate the setup of new MiniNet hosts
without dealing directly with the driver.py script.

* **setup_subscribers.sh** [-c COUNT (how many subscribers on this host? can be 1 or more)] [-t TOPIC [-t TOPIC ..] (topics to subscribe to)] [-m COUNT or -i (if -i (indefinite), receive published events indefinitely, otherwise receive only COUNT events then stop)]
* **setup_publishers.sh** [-c COUNT (how many publishers on this host? can be 1 or more)] [-t TOPIC [-t TOPIC ...] (topics to publish)] [-m COUNT or --i (if -i (indefinite), publish events indefinitely, otherwise publish only COUNT events then stop)] [-b PORT (port on which to publish] [-s SECONDS (number of seconds to sleep between each publish event)]