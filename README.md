# NAPALM F5

[![PyPI](https://img.shields.io/pypi/v/napalm-f5.svg)](https://pypi.python.org/pypi/napalm-f5)
[![PyPI](https://img.shields.io/pypi/dm/napalm-f5.svg)](https://pypi.python.org/pypi/napalm-f5)
[![Build Status](https://travis-ci.org/napalm-automation/napalm-f5.svg?branch=master)](https://travis-ci.org/napalm-automation/napalm-f5)
[![Coverage Status](https://coveralls.io/repos/github/napalm-automation/napalm-napalm-f5/badge.svg?branch=master)](https://coveralls.io/github/napalm-automation/napalm-napalm-f5)

This is a community version of [NAPALM](https://napalm.readthedocs.io/) for the F5 BIG-IP operating system. It is intended for use with the REST API starting in version 11.5. For standard tutorials and an overview of NAPALM, please review their documentation.

# Configuration Support

This table identifies the currently available configuration methods supported:

| Feature                   | Supported |
| ------------------------- | --------- |
| Config Replace            | ✅        |
| Commit Confirm            | ❌        |
| Config Merge              | ❌        |
| Compare Config            | ✅        |
| Atomic Changes            | ❌        |
| Rollback                  | ❌        |

> Commit Confirm is not supported by the vendor at the time of this writing.

```python
from napalm import get_network_driver

f5_device = "nyc-f5"
f5_user = "admin"
f5_password = "pass123"
driver = get_network_driver("f5")
optional_args = {}

with driver(f5_device, f5_user, f5_password, optional_args=optional_args) as device:
    device.load_replace_candidate(filename="2024-01-01-intended-config.scf")
    device.commit_config()

```

As shown in the example above, the use of NAPALM's context manager is supported and is recommended for use.

# Supported Getters

This table identifies the currently available getters and the support for each:

| Getter                    | Supported |
| ------------------------- | --------- |
| get_arp_table             | ❌        |
| get_bgp_config            | ❌        |
| get_bgp_neighbors         | ❌        |
| get_bgp_neighbors_detail  | ❌        |
| get_config                | ✅        |
| get_environment           | ❌        |
| get_facts                 | ✅        |
| get_firewall_policies     | ❌        |
| get_interfaces            | ✅        |
| get_interfaces_counters   | ❌        |
| get_interfaces_ip         | ✅        |
| get_ipv6_neighbors_table  | ❌        |
| get_lldp_neighbors        | ✅        |
| get_lldp_neighbors_detail | ❌        |
| get_mac_address_table     | ❌        |
| get_network_instances     | ❌        |
| get_ntp_peers             | ❌        |
| get_ntp_servers           | ✅        |
| get_ntp_stats             | ❌        |
| get_optics                | ❌        |
| get_probes_config         | ❌        |
| get_probes_results        | ❌        |
| get_route_to              | ❌        |
| get_snmp_information      | ✅        |
| get_users                 | ✅        |
| get_vlans                 | ✅        |
| is_alive                  | ✅        |
| ping                      | ❌        |
| traceroute                | ❌        |
