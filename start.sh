#!/bin/bash
echo "=== Starting web server ==="
exec gunicorn dashboard:app --bind 0.0.0.0:5000
