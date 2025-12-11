#!/bin/bash
BRANCH="main"
DELAY=60

cd /home/sywi/dagster-platform

echo "Watchdog started. Polling every ${DELAY}s for changes on ${BRANCH}..."

while true; do
    git fetch origin $BRANCH -q 2>/dev/null
    LOCAL=$(git rev-parse HEAD 2>/dev/null)
    REMOTE=$(git rev-parse origin/$BRANCH 2>/dev/null)

    if [ "$LOCAL" != "$REMOTE" ]; then
        echo "$(date): Changes detected. Deploying..."
        ./deploy.sh
    fi
    sleep $DELAY
done
