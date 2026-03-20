from conftest import run_command_and_assert, wait_http_ready, create_running_container, logger


def test_containers_can_communicate_in_user_defined_network(
    client, unique_suffix, cleanup_containers, cleanup_networks
):
    network_name = f"test-network-{unique_suffix}"
    c1_name = f"container1-{unique_suffix}"
    c2_name = f"container2-{unique_suffix}"

    logger.info("Creating network: %s", network_name)
    network = client.networks.create(network_name, driver="bridge")
    cleanup_networks.append(network)

    c1 = create_running_container(
        client=client,
        cleanup_containers=cleanup_containers,
        image="alpine",
        name=c1_name,
        command=["sh", "-c", "sleep 300"],
        network=network_name,
        tty=True,
    )

    c2 = create_running_container(
        client=client,
        cleanup_containers=cleanup_containers,
        image="alpine",
        name=c2_name,  # исправлен баг: было c1_name
        command=["sh", "-c", "sleep 300"],
        network=network_name,
        tty=True,
    )

    decoded = run_command_and_assert(
        c1,
        ["ping", "-c", "3", c2_name],
        "Ping between containers failed",
    )

    assert "3 packets transmitted" in decoded or "bytes from" in decoded


def test_data_persists_in_docker_volume(
    client, unique_suffix, cleanup_containers, cleanup_volumes
):
    volume_name = f"test-volume-{unique_suffix}"
    first_container_name = f"volume-test-{unique_suffix}"
    second_container_name = f"volume-test-2-{unique_suffix}"
    file_path = "/data/file.txt"
    expected_text = "test-data"

    logger.info("Creating volume: %s", volume_name)
    volume = client.volumes.create(name=volume_name)
    cleanup_volumes.append(volume)

    c1 = create_running_container(
        client=client,
        cleanup_containers=cleanup_containers,
        image="alpine",
        name=first_container_name,
        command=["sh", "-c", "sleep 300"],
        volumes={volume_name: {"bind": "/data", "mode": "rw"}},
        tty=True,
    )

    decoded = run_command_and_assert(
        c1,
        ["sh", "-c", f'echo "{expected_text}" > {file_path} && cat {file_path}'],
        "Write/read in first container failed",
    )
    assert expected_text in decoded

    logger.info("Removing first container manually: %s", c1.name)
    c1.remove(force=True)
    cleanup_containers.remove(c1)

    c2 = create_running_container(
        client=client,
        cleanup_containers=cleanup_containers,
        image="alpine",
        name=second_container_name,
        command=["sh", "-c", "sleep 300"],
        volumes={volume_name: {"bind": "/data", "mode": "rw"}},
        tty=True,
    )

    decoded = run_command_and_assert(
        c2,
        ["cat", file_path],
        "Could not read persisted file from second container",
    )
    assert decoded == expected_text


def test_tk3_nginx_is_available_via_published_port(
    client, unique_suffix, cleanup_containers
):
    container_name = f"nginx-port-test-{unique_suffix}"

    container = create_running_container(
        client=client,
        cleanup_containers=cleanup_containers,
        image="nginx",
        name=container_name,
        ports={"80/tcp": ("127.0.0.1", None)},
    )

    host_port = container.attrs["NetworkSettings"]["Ports"]["80/tcp"][0]["HostPort"]
    url = f"http://127.0.0.1:{host_port}"

    logger.info("Checking nginx availability at %s", url)
    response = wait_http_ready(url)

    assert response.status_code == 200
    assert "nginx" in response.text.lower()