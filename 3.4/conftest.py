import time
import uuid

import docker
import pytest
from docker.errors import NotFound


@pytest.fixture(scope="session")
def client():
    cli = docker.from_env()
    return cli


@pytest.fixture
def unique_suffix():
    return uuid.uuid4().hex[:8]


@pytest.fixture
def cleanup_containers(client):
    created = []

    yield created

    for container in reversed(created):
        try:
            container.remove(force=True)
        except NotFound:
            pass
        except Exception:
            pass


@pytest.fixture
def cleanup_networks(client):
    created = []

    yield created

    for network in reversed(created):
        try:
            network.remove()
        except NotFound:
            pass
        except Exception:
            pass


@pytest.fixture
def cleanup_volumes(client):
    created = []

    yield created

    for volume in reversed(created):
        try:
            volume.remove(force=True)
        except NotFound:
            pass
        except Exception:
            pass


def wait_container_running(container, timeout=15):
    deadline = time.time() + timeout
    while time.time() < deadline:
        container.reload()
        if container.status == "running":
            return
        time.sleep(0.5)
    raise AssertionError(f"Container {container.name} did not become running in time")