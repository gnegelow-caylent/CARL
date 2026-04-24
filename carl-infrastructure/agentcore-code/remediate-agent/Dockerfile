# CARL Remediation Agent Dockerfile
# Built for ARM64 architecture (required by AgentCore Runtime)

FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install dependencies first (for caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy agent code
COPY carl_remediate_agent.py .

# Expose port 8080 (required by AgentCore Runtime)
EXPOSE 8080

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the agent
CMD ["python", "carl_remediate_agent.py"]
