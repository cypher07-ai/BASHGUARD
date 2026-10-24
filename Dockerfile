FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all source files
COPY simulator.py executor.py sandbox.py rollback.py agent.py server.py ./
COPY bashguard_hook.sh bashguard_hook.ps1 ./
COPY README.md ./

# Create .env placeholder (user must provide API key)
RUN echo "# Set your Gemini API key" > .env.example && \
    echo "GEMINI_API_KEY=your_key_here" >> .env.example

# Expose the API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/')" || exit 1

# Default: start the API server
CMD ["python", "server.py"]
