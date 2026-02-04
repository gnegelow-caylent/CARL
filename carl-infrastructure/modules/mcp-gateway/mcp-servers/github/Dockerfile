FROM public.ecr.aws/lambda/python:3.11

# Copy requirements and install dependencies
COPY requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

# Copy MCP server code
COPY mcp_server.py ${LAMBDA_TASK_ROOT}/

# Set the handler
CMD ["mcp_server.handler"]
