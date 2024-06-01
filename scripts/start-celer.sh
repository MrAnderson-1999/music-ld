#!/bin/bash

# Activate the virtual environment
source /home/ubuntu/myenv/bin/activate

# Change to the app directory
cd /home/ubuntu/app

# Start the Celery worker
celery -A celery_worker.celery worker --loglevel=info

chmod +x start_celery.sh