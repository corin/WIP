#!/bin/sh

if python isRunning.py | grep hung > /dev/null
then    
    pkill python
else
    echo "Weather_processor is not hung."
fi