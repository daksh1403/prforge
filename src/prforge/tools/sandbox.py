"""Sandboxed test execution.

Runs the repo's test command inside a Docker container with the network
disabled and the working directory mounted read-write. Falls back to running
locally (with a warning) when Docker is unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass

from prforge.utils import run


@dataclass
class TestResult:
    ok: bool
    output: str
    ran_in_sandbox: bool


def docker_available(image: str = "prforge-sandbox:latest") -> bool:
    res = run(["docker", "image", "inspect", image])
    return res.ok


def run_in_sandbox(workdir: str, command: str, image: str, timeout: int = 300) -> TestResult:
    """Run `command` in a Docker container with no network, workdir mounted."""
    res = run(
        [
            "docker", "run", "--rm",
            "--network", "none",
            "--memory", "1g",
            "--cpus", "2",
            "-v", f"{workdir}:/workspace",
            "-w", "/workspace",
            image,
            "bash", "-lc", command,
        ],
        timeout=timeout,
    )
    output = (res.stdout + ("\n--- stderr ---\n" + res.stderr if res.stderr.strip() else "")).strip()
    return TestResult(ok=res.ok, output=output, ran_in_sandbox=True)


def run_locally(workdir: str, command: str, timeout: int = 300) -> TestResult:
    """Fallback: run the command directly in the workdir (NOT isolated)."""
    res = run(["bash", "-lc", command], cwd=workdir, timeout=timeout)
    output = (res.stdout + ("\n--- stderr ---\n" + res.stderr if res.stderr.strip() else "")).strip()
    return TestResult(ok=res.ok, output=output, ran_in_sandbox=False)


def run_tests(workdir: str, command: str, image: str, prefer_sandbox: bool = True) -> TestResult:
    """Run tests, preferring the Docker sandbox, falling back to local."""
    if prefer_sandbox and docker_available(image):
        return run_in_sandbox(workdir, command, image)
    return run_locally(workdir, command)
