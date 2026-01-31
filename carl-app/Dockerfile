# Lambda container image for CARL with PDF generation support
# Base image: AWS Lambda Python 3.12 (Amazon Linux 2023)
FROM public.ecr.aws/lambda/python:3.12

# Install system dependencies for WeasyPrint and Matplotlib
# Amazon Linux 2023 uses dnf instead of yum
RUN dnf install -y \
    cairo \
    cairo-devel \
    pango \
    pango-devel \
    gdk-pixbuf2 \
    gdk-pixbuf2-devel \
    libffi \
    libffi-devel \
    libjpeg-turbo \
    libjpeg-turbo-devel \
    zlib \
    zlib-devel \
    && dnf clean all \
    && rm -rf /var/cache/dnf

# Copy requirements file
COPY requirements.txt ${LAMBDA_TASK_ROOT}/

# Install Python dependencies
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

# Copy application code
COPY src/ ${LAMBDA_TASK_ROOT}/

# Copy compliance frameworks (YAML definitions)
COPY compliance-frameworks/ ${LAMBDA_TASK_ROOT}/compliance-frameworks/

# Set the Lambda handler
CMD ["handlers.slack_router.lambda_handler"]
