# PRForge test sandbox.
# A minimal, network-disabled environment for running a repo's test suite.
#
# Build:  docker build -t prforge-sandbox:latest -f sandbox/Dockerfile .
# The agent runs tests here with --network none so it cannot exfiltrate data.

FROM python:3.11-slim

# Common test/build tools. Add language runtimes (node, go, rust) as needed.
RUN apt-get update && apt-get install -y --no-install-recommends \
        git curl build-essential ripgrep \
    && rm -rf /var/lib/apt/lists/*

# A baseline set of Python test tooling. Per-repo deps are installed at runtime
# by the test command (e.g. `pip install -e . && pytest`).
RUN pip install --no-cache-dir pytest tox

WORKDIR /workspace
CMD ["bash", "-lc", "echo 'prforge sandbox ready'"]
