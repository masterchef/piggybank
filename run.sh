#!/bin/bash

# Activate virtual environment and run the application
source venv/bin/activate
export FLASK_APP=main.py
flask run --host=0.0.0.0
