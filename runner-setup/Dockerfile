FROM ubuntu:22.04

# 1. Install Basic Tools & Python
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y \
    curl jq git unzip \
    python3 python3-pip python3-venv \
    libicu-dev \
    && rm -rf /var/lib/apt/lists/*

# 2. Create a non-root user for the runner (Security Best Practice)
RUN useradd -m runner
USER runner
WORKDIR /home/runner

# 3. Install GH Runner (ARM64 for Raspberry Pi)
# Note: Changing architecture to 'x64' if testing on Intel/AMD Mac
ARG RUNNER_VERSION="2.311.0"
ARG RUNNER_ARCH="arm64" 

RUN curl -o actions-runner-linux-${RUNNER_ARCH}-${RUNNER_VERSION}.tar.gz -L \
    https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-${RUNNER_ARCH}-${RUNNER_VERSION}.tar.gz \
    && tar xzf ./actions-runner-linux-${RUNNER_ARCH}-${RUNNER_VERSION}.tar.gz \
    && rm ./actions-runner-linux-${RUNNER_ARCH}-${RUNNER_VERSION}.tar.gz

# 4. Install Runner Dependencies
USER root
RUN ./bin/installdependencies.sh
USER runner

# 5. Pre-install Python Dependencies (to speed up runs)
# We install these globally in the container for the runner user
RUN pip3 install --user google-generativeai python-frontmatter gitpython

# 6. Copy Application Source Code
COPY --chown=runner:runner src ./src

# 7. Create debug log directory (as runner user)
RUN mkdir -p /home/runner/.cursor

# 8. Copy Startup Script
COPY --chown=runner:runner entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]
