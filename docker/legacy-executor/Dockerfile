# Dockerfile for Legacy Binary Execution
# Supports COBOL, FORTRAN, and mainframe binaries with side effect capture

FROM ubuntu:22.04

# Install legacy runtime dependencies
RUN apt-get update && apt-get install -y \
    # COBOL compiler and runtime
    gnucobol \
    libcob4 \
    # FORTRAN compiler and runtime
    gfortran \
    libgfortran5 \
    # Build tools
    build-essential \
    # File system monitoring
    inotify-tools \
    # Network monitoring
    tcpdump \
    iptables \
    # Process monitoring
    strace \
    # Python for orchestration
    python3.12 \
    python3-pip \
    # Utilities
    curl \
    jq \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip3 install --no-cache-dir \
    boto3 \
    aws-lambda-powertools

# Create directories for execution
RUN mkdir -p /app/binaries \
    /app/input \
    /app/output \
    /app/logs \
    /app/side-effects

# Copy executor script
COPY executor.py /app/executor.py
COPY capture_side_effects.sh /app/capture_side_effects.sh

# Make scripts executable
RUN chmod +x /app/executor.py /app/capture_side_effects.sh

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV CAPTURE_SIDE_EFFECTS=true

# Entry point
ENTRYPOINT ["python3", "/app/executor.py"]
