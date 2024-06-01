#!/bin/bash

# Stop the Gunicorn process
pkill -f 'gunicorn --bind 0.0.0.0:5000'

# Stop the Celery worker process
pkill -f 'celery -A celery_worker.celery worker'

chmod +x stop_services.sh


