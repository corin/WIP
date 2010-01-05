#!/bin/sh
SERVICE='weather_processor'

if ps ax | grep -v grep | grep $SERVICE > /dev/null
then
    echo "$SERVICE is not running."
else
    python /var/weather/weather_processor.py
    echo "Ran $SERVICE."
fi
