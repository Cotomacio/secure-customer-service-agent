# Streamlit chat UI for Ada. Designed for Cloud Run.
FROM python:3.12-slim

WORKDIR /app

# System deps required by some transitive packages
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

# Cloud Run sets $PORT to whatever it routes to (default 8080).
ENV PORT=8080
EXPOSE 8080

# Streamlit options tuned for Cloud Run:
#   --server.headless=true  : don't try to open a browser
#   --server.port=$PORT     : bind to Cloud Run's injected port
#   --server.address=0.0.0.0: listen on all interfaces (Cloud Run requires)
#   --browser.gatherUsageStats=false : skip telemetry
CMD streamlit run app.py \
    --server.headless=true \
    --server.port=$PORT \
    --server.address=0.0.0.0 \
    --browser.gatherUsageStats=false
