#!/bin/bash
if [ -z "$1" ]; then
    echo "📋 Showing all logs..."
    docker-compose logs -f
else
    echo "📋 Showing logs for $1..."
    docker-compose logs -f $1
fi
