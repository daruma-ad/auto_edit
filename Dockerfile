# Build stage for Node.js / Remotion
FROM node:20-slim AS node-build
WORKDIR /app/remotion-project
COPY remotion-project/package*.json ./
RUN npm install
COPY remotion-project/ ./

# Final stage
FROM python:3.11-slim
WORKDIR /app

# Install system dependencies (ffmpeg, nodejs for runtime)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    gnupg \
    build-essential \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Copy Node.js dependencies and code
COPY --from=node-build /app/remotion-project/node_modules /app/remotion-project/node_modules
COPY --from=node-build /app/remotion-project /app/remotion-project

# Expose ports (Streamlit: 8501, Remotion: 3001, Flask: 5001)
EXPOSE 8501 3001 5001

# Entrypoint script
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Cloud Run expects a single port (PORT env var). 
# We'll use 8501 as the main entry, but internal 3001 and 5001 need to be reachable.
CMD ["/app/entrypoint.sh"]
