#!/bin/sh
SERVICE='python'

if ps ax | grep -v grep | grep $SERVICE > /dev/null
then
    echo "$SERVICE is not running."
else
    python /var/weather/weather_processor_v1.1.py
    echo "Ran $SERVICE."
fi
