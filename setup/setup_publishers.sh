#!/bin/bash
# Automate creation of publisher(s) on current host
while getopts c:t:m:i:b:s: flag
do
    case "${flag}" in
        c) count=${OPTARG};;
        t) topics+=(${OPTARG});;
        m) max_event_count=${OPTARG};;
        i) indefinite=${OPTARG};;
        b) bind_port=${OPTARG};;
        s) sleep_seconds=${OPTARG};;
    esac
done
topic_arguments=""
for topic in "${topics[@]}"; do
  topic_arguments+="-t \"${topic}\" "
done

# Defaults
if [ -z "$bind_port" ] ; then
    bind_port=5556
fi
if [ -z "$sleep_seconds" ] ; then
    sleep_seconds=1
fi
if [ -z "$count" ] ; then
    count=1
fi


echo "Creating publishers..."
sleep 1

if [ -z "$max_event_count" ] ; then
    # Use indefinite publishing if -i is provided or if neither -i nor -m COUNT provided
    # Use max event count
    echo "python ../driver.py --publisher $count $topic_arguments --indefinite --bind_port $bind_port --sleep $sleep_seconds"
    python ../driver.py --publisher $count $topic_arguments --indefinite --bind_port $bind_port --sleep $sleep_seconds
else
    # Use max event count
    echo "python ../driver.py --publisher $count $topic_arguments --max_event_count $max_event_count --bind_port $bind_port --sleep $sleep_seconds"
    python ../driver.py --publisher $count $topic_arguments --max_event_count $max_event_count --bind_port $bind_port --sleep $sleep_seconds
fi

echo "$count publishers created on this host"
exit 0