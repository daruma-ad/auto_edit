#!/bin/bash

# Start Flask API (Port 5001) in background
echo "Starting Flask API..."
python api_server.py &

# Start Remotion Studio (Port 3001) in background
echo "Starting Remotion Studio..."
cd remotion-project && npm run dev -- --port 3001 &

# Start Streamlit (Port 8501) in foreground
# Cloud Run normally uses the PORT environment variable, defaulting to 8080.
# Here we'll bind Streamlit to the provided PORT or 8501.
echo "Starting Streamlit Dashboard..."
cd /app
streamlit run app.py --server.port=${PORT:-8501} --server.address=0.0.0.0
