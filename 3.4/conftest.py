import logging
import time
import uuid

import docker
import pytest
import requests
from docker.errors import APIError, NotFound


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def client():
    try:
        cli = docker.from_env()
        cli.ping()
        logger.info("Docker client initialized successfully")
        return cli
    except Exception as exc:
        logger.exception("Failed to initialize Docker client")
        pytest.fail(f"Could not connect to Docker daemon: {exc}")


@pytest.fixture
def unique_suffix():
    return uuid.uuid4().hex[:8]


@pytest.fixture
def cleanup_containers():
    created = []
    yield created

    for container in reversed(created):
        try:
            logger.info("Removing container: %s", container.name)
            container.remove(force=True)
        except NotFound:
            logger.warning("Container already removed: %s", getattr(container, "name", "unknown"))
        except APIError as exc:
            logger.error(
                "Docker API error while removing container %s: %s",
                getattr(container, "name", "unknown"),
                exc,
            )
        except Exception as exc:
            logger.exception(
                "Unexpected error while removing container %s: %s",
                getattr(container, "name", "unknown"),
                exc,
            )


@pytest.fixture
def cleanup_networks():
    created = []
    yield created

    for network in reversed(created):
        try:
            logger.info("Removing network: %s", network.name)
            network.remove()
        except NotFound:
            logger.warning("Network already removed: %s", getattr(network, "name", "unknown"))
        except APIError as exc:
            logger.error(
                "Docker API error while removing network %s: %s",
                getattr(network, "name", "unknown"),
                exc,
            )
        except Exception as exc:
            logger.exception(
                "Unexpected error while removing network %s: %s",
                getattr(network, "name", "unknown"),
                exc,
            )


@pytest.fixture
def cleanup_volumes():
    created = []
    yield created

    for volume in reversed(created):
        try:
            logger.info("Removing volume: %s", volume.name)
            volume.remove(force=True)
        except NotFound:
            logger.warning("Volume already removed: %s", getattr(volume, "name", "unknown"))
        except APIError as exc:
            logger.error(
                "Docker API error while removing volume %s: %s",
                getattr(volume, "name", "unknown"),
                exc,
            )
        except Exception as exc:
            logger.exception(
                "Unexpected error while removing volume %s: %s",
                getattr(volume, "name", "unknown"),
                exc,
            )

def wait_container_running(container, timeout=15):
    deadline = time.time() + timeout

    while time.time() < deadline:
        container.reload()
        logger.info("Waiting for container %s, current status: %s", container.name, container.status)

        if container.status == "running":
            logger.info("Container %s is running", container.name)
            return

        time.sleep(0.5)

    raise AssertionError(f"Container {container.name} did not become running in time")


def wait_http_ready(url, timeout=15, interval=1):
    deadline = time.time() + timeout
    last_error = None

    while time.time() < deadline:
        try:
            response = requests.get(url, timeout=2)
            logger.info("HTTP check %s returned status %s", url, response.status_code)
            return response
        except Exception as exc:
            last_error = exc
            logger.info("HTTP check failed for %s: %s", url, exc)
            time.sleep(interval)

    raise AssertionError(f"Service did not become available at {url}: {last_error}")


def decode_output(output):
    return output.decode(errors="ignore").strip()


def run_command_and_assert(container, command, error_message):
    exit_code, output = container.exec_run(command)
    decoded = decode_output(output)

    logger.info(
        "Executed command in container %s: %s | exit_code=%s | output=%s",
        container.name,
        command,
        exit_code,
        decoded,
    )

    assert exit_code == 0, f"{error_message}\nOutput:\n{decoded}"
    return decoded


def create_running_container(client, cleanup_containers, image, name, **kwargs):
    logger.info("Creating container: %s (image=%s)", name, image)

    container = client.containers.run(
        image=image,
        name=name,
        detach=True,
        **kwargs,
    )
    cleanup_containers.append(container)

    wait_container_running(container)
    return container