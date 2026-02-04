FROM public.ecr.aws/lambda/python:3.11

# Install Terraform CLI
RUN yum install -y yum-utils && \
    yum-config-manager --add-repo https://rpm.releases.hashicorp.com/AmazonLinux/hashicorp.repo && \
    yum install -y terraform && \
    yum clean all

# Copy requirements and install dependencies
COPY requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

# Copy MCP server code
COPY mcp_server.py ${LAMBDA_TASK_ROOT}/

# Set the handler
CMD ["mcp_server.handler"]
