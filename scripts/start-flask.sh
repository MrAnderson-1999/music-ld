#!/bin/bash

# Activate the virtual environment
source /home/ubuntu/myenv/bin/activate

# Change to the app directory
cd /home/ubuntu/app

NUM_CORES=$(nproc --all)

# Start Gunicorn to serve the Flask app with optimal settings
gunicorn --workers $((2 * NUM_CORES + 1)) --timeout 120 --bind 0.0.0.0:5000 app:app

chmod +x start_flask.sh
