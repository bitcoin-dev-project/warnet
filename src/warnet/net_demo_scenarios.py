from typing import NamedTuple

cond = NamedTuple("description", "command")

network_scenarios = {
    1: cond("Normal Latency", "tc qdisc add dev eth0 root netem delay 1000ms"),
    2: cond("Variable Latency", "tc qdisc add dev eth0 root netem delay 1000ms 500ms"),
    3: cond("Packet Loss", "tc qdisc add dev eth0 root netem loss 15%"),
    4: cond("Packet Duplication", "tc qdisc add dev eth0 root netem duplicate 10%"),
    5: cond("Packet Reordering", "tc qdisc add dev eth0 root netem delay 100ms reorder 25% 50%"),
    6: cond("Packet Corruption", "tc qdisc add dev eth0 root netem corrupt 5%"),
    7: cond("Combination of Latency, Loss, and Reordering", "tc qdisc add dev eth0 root netem delay 500ms loss 10% reorder 25% 50%"),
    8: cond("Rate Control (Bandwidth Limiting)", "tc qdisc add dev eth0 root netem rate 1mbit"),
    9: cond("Packet Delay with Distribution", "tc qdisc add dev eth0 root netem delay 100ms 20ms distribution normal"),
    10: cond("Combination of Latency, Loss, Duplication, and Corruption", "tc qdisc add dev eth0 root netem delay 50ms loss 5% duplicate 2% corrupt 0.5%")
}

# scenario_id = 3
# description, command = network_scenarios[scenario_id]
# print(f"Description: {description}\nCommand: {command}")

