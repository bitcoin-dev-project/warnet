FO_CONF_NAME = "fork_observer_config.toml"
GRAFANA_PROVISIONING = "grafana-provisioning"
PROM_CONF_NAME = "prometheus.yml"

services = {
    "cadvisor": {
        "backends": ["compose"],
        "image": "gcr.io/cadvisor/cadvisor:v0.47.2",
        "container_name_suffix": "cadvisor",
        "warnet_port": "23000",
        "container_port": "8080",
        "volumes": [
            "/:/rootfs:ro",
            "/var/run/docker.sock:/var/run/docker.sock:rw",
            "/sys:/sys:ro",
            "/var/lib/docker/:/var/lib/docker:ro",
            "/dev/disk/:/dev/disk:ro",
        ],
        "privileged": True,
        "devices": ["/dev/kmsg"],
        "args": [
            "-housekeeping_interval=30s",
            "-docker_only=true",
            "-storage_duration=1m0s",
            "-disable_metrics=advtcp,cpu_topology,cpuset,hugetlb,memory_numa,process,referenced_memory,resctrl,sched,tcp,udp",
        ]
    },
    "forkobserver": {
        "backends": ["compose"],
        "image": "b10c/fork-observer:latest",
        "container_name_suffix": "fork-observer",
        "warnet_port": "23001",
        "container_port": "2323",
        "config_files": [f"/{FO_CONF_NAME}:/app/config.toml"],
    },
    "grafana": {
        "backends": ["compose"],
        "image": "grafana/grafana:latest",
        "container_name_suffix": "grafana",
        "warnet_port": "23002",
        "container_port": "3000",
        "volumes": [
            "grafana-storage:/var/lib/grafana"
        ],
        "config_files": [
            f"/{GRAFANA_PROVISIONING}/datasources:/etc/grafana/provisioning/datasources",
            f"/{GRAFANA_PROVISIONING}/dashboards:/etc/grafana/provisioning/dashboards",
        ],
        "environment": [
            "GF_LOG_LEVEL=debug",
            "GF_AUTH_ANONYMOUS_ENABLED=true",
            "GF_ORG_NAME=warnet",
            "GF_ORG_ROLE=Admin",
            "GF_AUTH_DISABLE_LOGIN_FORM=true"
        ]
    },
    "nodeexporter": {
        "backends": ["compose"],
        "image": "prom/node-exporter:latest",
        "container_name_suffix": "node-exporter",
        "warnet_port": "23003",
        "container_port": "9100",
        "volumes": [
            "/proc:/host/proc:ro",
            "/sys:/host/sys:ro",
            "/:/rootfs:ro"
        ],
        "args": [
            "--path.procfs=/host/proc",
            "--path.sysfs=/host/sys"
        ]
    },
    "prometheus": {
        "backends": ["compose"],
        "image": "prom/prometheus:latest",
        "container_name_suffix": "prometheus",
        "warnet_port": "23004",
        "container_port": "9090",
        "config_files": [f"/{PROM_CONF_NAME}:/etc/prometheus/prometheus.yml"],
        "args": ["--config.file=/etc/prometheus/prometheus.yml"]
    }
}
