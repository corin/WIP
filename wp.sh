#!/bin/sh
SERVICE='weather_processor'

if ps ax | grep -v grep | grep $SERVICE > /dev/null
then
    echo "$SERVICE is already running."
else
    python /usr/local/lib/weather/weather_processor.py    
    echo "Ran $SERVICE."
fi
