#!/bin/bash

echo "Updating project..."
git pull origin main

echo "Installing dependencies..."
pip3 install -U -r requirements.txt

echo "Starting bot..."
exec python3 main.py
