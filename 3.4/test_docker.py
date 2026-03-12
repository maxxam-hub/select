import time

import requests


def test_containers_can_communicate_in_user_defined_network(
    client, unique_suffix, cleanup_containers, cleanup_networks
):
    network_name = f"test-network-{unique_suffix}"
    c1_name = f"container1-{unique_suffix}"
    c2_name = f"container2-{unique_suffix}"

    network = client.networks.create(network_name, driver="bridge")
    cleanup_networks.append(network)

    c1 = client.containers.run(image="alpine",command=["sh", "-c", "sleep 300"],
        name=c1_name, network=network_name, detach=True, tty=True,)
    cleanup_containers.append(c1)

    c2 = client.containers.run(image="alpine",command=["sh", "-c", "sleep 300"],
        name=c1_name, network=network_name, detach=True, tty=True,)
    cleanup_containers.append(c2)

    exit_code, output = c1.exec_run(["ping", "-c", "3", c2_name])

    assert exit_code == 0, f"Ping failed. Output:\n{output.decode(errors='ignore')}"
    decoded = output.decode(errors="ignore")
    assert "3 packets transmitted" in decoded or "bytes from" in decoded


def test_data_persists_in_docker_volume(
    client, unique_suffix, cleanup_containers, cleanup_volumes
):
    volume_name = f"test-volume-{unique_suffix}"
    first_container_name = f"volume-test-{unique_suffix}"
    second_container_name = f"volume-test-2-{unique_suffix}"
    file_path = "/data/file.txt"
    expected_text = "test-data"

    volume = client.volumes.create(name=volume_name)
    cleanup_volumes.append(volume)

    c1 = client.containers.run(image="alpine", command=["sh", "-c", "sleep 300"],
        name=first_container_name, volumes={volume_name: {"bind": "/data", "mode": "rw"}},
        detach=True, tty=True,)
    cleanup_containers.append(c1)

    exit_code, output = c1.exec_run(
        ["sh", "-c", f'echo "{expected_text}" > {file_path} && cat {file_path}']
    )
    assert exit_code == 0, f"Write/read failed:\n{output.decode(errors='ignore')}"
    assert expected_text in output.decode(errors="ignore")

    c1.remove(force=True)
    cleanup_containers.remove(c1)

    c2 = client.containers.run(image="alpine", command=["sh", "-c", "sleep 300"],
        name=second_container_name, volumes={volume_name: {"bind": "/data", "mode": "rw"}},
        detach=True, tty=True,)
    cleanup_containers.append(c2)

    exit_code, output = c2.exec_run(["cat", file_path])
    assert exit_code == 0, f"Could not read persisted file:\n{output.decode(errors='ignore')}"
    assert output.decode(errors="ignore").strip() == expected_text


def test_tk3_nginx_is_available_via_published_port(
    client, unique_suffix, cleanup_containers
):
    container_name = f"nginx-port-test-{unique_suffix}"

    container = client.containers.run(image="nginx", name=container_name,
        detach=True, ports={"80/tcp": ("127.0.0.1", None)},
    )
    cleanup_containers.append(container)

    container.reload()
    host_port = container.attrs["NetworkSettings"]["Ports"]["80/tcp"][0]["HostPort"]

    deadline = time.time() + 15
    last_error = None

    while time.time() < deadline:
        try:
            response = requests.get(f"http://127.0.0.1:{host_port}", timeout=2)
            assert response.status_code == 200
            assert "nginx" in response.text.lower()
            return
        except Exception as exc:
            last_error = exc
            time.sleep(1)

    raise AssertionError(f"Nginx did not become available via published port: {last_error}")