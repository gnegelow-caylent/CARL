# CARL Architect Agent - AgentCore Runtime Container
FROM public.ecr.aws/docker/library/python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY carl-infrastructure/agentcore-code/architect-agent/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY carl-infrastructure/agentcore-code/architect-agent/carl_architect_agent.py .

# Copy knowledge base for dynamic pattern loading (ALL 37 pattern files)
COPY carl-app/src/knowledge/ ./knowledge/

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV AWS_REGION=us-east-1

# Expose port for AgentCore Runtime
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run the agent
CMD ["python", "carl_architect_agent.py"]
