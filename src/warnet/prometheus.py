import yaml
import logging

def generate_prometheus_config(node_count):
    """
    Generate a prometheus.yml file based on the number of Bitcoin nodes.

    :param node_count: The number of Bitcoin nodes
    """
    config = {
        "global": {
            "scrape_interval": "15s"
        },
        "scrape_configs": [
            {
                "job_name": "prometheus",
                "scrape_interval": "5s",
                "static_configs": [{"targets": ["localhost:9090"]}]
            },
            {
                "job_name": "node-exporter",
                "scrape_interval": "5s",
                "static_configs": [{"targets": ["node-exporter:9100"]}]
            },
            {
                "job_name": "cadvisor",
                "scrape_interval": "5s",
                "static_configs": [{"targets": ["cadvisor:8080"]}]
            }
        ]
    }

    for i in range(node_count):
        config["scrape_configs"].append({
            "job_name": f"bitcoin-node-{i}",
            "scrape_interval": "5s",
            "static_configs": [{"targets": [f"exporter-node-{i}:9332"]}]
        })

    try:
        with open("prometheus.yml", "w") as file:
            yaml.dump(config, file)
    except Exception as e:
        logging.error(f"An error occurred while writing to prometheus.yml: {e}")

