"""
Napalm driver for F5.
Read https://napalm.readthedocs.io for more information.
"""

import os
from typing import Dict, List, Optional

from bigrest.bigip import BIGIP, RESTAPIError

from napalm.base.base import NetworkDriver
from napalm.base.exceptions import ConnectionException, MergeConfigException, ReplaceConfigException

from napalm_f5.env import ALERT, LIMITS
from napalm_f5.exceptions import CommitConfigException, DiscardConfigException


class F5Driver(NetworkDriver):  # pylint: disable=abstract-method
    """F5 REST API based NAPALM driver."""

    def __init__(  # pylint: disable=too-many-arguments
        self, hostname: str, username: str, password: str, timeout: int = 60, optional_args: Optional[dict] = None
    ):
        """Initialize shared variables for driver.

        Args:
            hostname (str): Hostname for device to connect to.
            username (str): Username to authenticate with against device.
            password (str): Password to authenticate with against device.
            timeout (int, optional): Timeout for requests.. Defaults to 60.
            optional_args (Optional[dict], optional): Optional arguments to use with driver. Defaults to None.
        """
        self.hostname = hostname
        self.username = username
        self.password = password
        self.timeout = timeout

        self.config_replace = False
        self.filename = None
        self.device = None

        if optional_args is None:
            optional_args = {}

    def open(self):
        """F5 version of `open` method, see NAPALM for documentation."""
        try:
            self.device = BIGIP(
                device=self.hostname,
                username=self.username,
                password=self.password,
                session_verify=False,
                timeout=self.timeout,
            )
        except RESTAPIError as err:
            raise ConnectionException(f"F5 API Error ({err})") from err

    def close(self):
        """F5 version of `close` method, see NAPALM for documentation."""
        self.device = None

    def cli(self, commands: List[str], encoding: str = "text") -> Dict[str, str]:
        """F5 version of 'cli' method, see NAPALM for documentation.

        Args:
            commands (List[str]): List of commands to be sent as strings.
            encoding (str, optional): Encoding of results. Defaults to "text".

        Returns:
            Dict[str, str]: Dictionary of commands sent and their associated response.
        """
        results = {}
        for command in commands:
            results[command] = self.device.command(
                "/mgmt/tm/util/bash", {"command": "run", "utilCmdArgs": f'-c "{command}"'}
            )
        return results

    def load_replace_candidate(self, filename=None, config=None):
        """F5 version of 'load_replace_candidate' method, see NAPALM for documentation."""
        self.config_replace = True

        if config:
            raise NotImplementedError

        if filename:
            self.filename = os.path.basename(filename)
            try:
                self._upload_scf(filename)
                data = {
                    "command": "load",
                    "options": [{"file": f"/tmp/{self.filename}", "merge": False}],
                }
                self.device.command("/mgmt/tm/sys/config", data)
            except Exception as err:
                raise ReplaceConfigException(err) from err

    def get_config(  # pylint: disable=redefined-builtin
        self,
        retrieve: str = "all",
        full: bool = False,
        sanitized: bool = False,
        format: str = "text",
    ) -> dict:
        """F5 version of 'get_config' method, see NAPALM for documentation.

        Args:
            retrieve (string): Which configuration type you want to populate, default is full running-config. The rest will be set to “”.
            full (bool): Retrieve all the configuration. For instance, on ios, “sh run all”.
            sanitized (bool): Remove secret data. Default: False.
            format (string): The configuration format style to be retrieved.
        Returns:
            running(string): Representation of the native running configuration
            candidate(string): Representation of the native candidate configuration. If the device doesnt differentiate between running and startup configuration this will an empty string
            startup(string): Representation of the native startup configuration. If the device doesnt differentiate between running and startup configuration this will an empty string
        """
        if sanitized or full:
            raise NotImplementedError("Specified feature for get_config() is not implemented.")

        if retrieve not in ["all", "recursive"]:
            raise NotImplementedError(f"Retrieve type of {retrieve} is not valid. Only running-config can be provided.")

        if format != "text":
            raise NotImplementedError(f"Format of type {format} is not valid.")

        if retrieve == "recursive":
            config = self.device.command(
                "/mgmt/tm/util/bash", {"command": "run", "utilCmdArgs": '-c "tmsh show running-config recursive"'}
            )
        else:
            config = self.device.command(
                "/mgmt/tm/util/bash", {"command": "run", "utilCmdArgs": '-c "tmsh show running-config"'}
            )
        return {"running": config, "candidate": "", "startup": ""}

    def load_merge_candidate(self, filename=None, config=None):
        """F5 version of 'load_merge_candidate' method, see NAPALM for documentation."""
        self.config_replace = False

        if config:
            raise NotImplementedError

        if filename:
            self.filename = os.path.basename(filename)
            try:
                self._upload_scf(filename)
                data = {
                    "command": "load",
                    "options": [{"file": f"/tmp/{self.filename}", "merge": True}],
                }
                self.device.command("/mgmt/tm/sys/config", data)
            except Exception as err:
                raise MergeConfigException(err) from err

    def commit_config(self, message: str = "") -> None:  # pylint: disable=arguments-differ
        """F5 version of 'commit_config' method, see NAPALM for documentation.

        Args:
            message (str): Optional - configuration session commit message
        """
        try:
            config = self.device.load("/mgmt/tm/sys/config")
            self.device.save(config)
        except RESTAPIError as err:
            raise CommitConfigException(err) from err

    def discard_config(self):
        """F5 version of 'discard_config' method, see NAPALM for documentation."""
        try:
            self.device.command(
                "/mgmt/tm/util/bash",
                {"command": "run", "utilCmdArgs": f'-c "rm /var/config/rest/downloads/{self.filename}"'},
            )
        except RESTAPIError as err:
            raise DiscardConfigException(err) from err

    def is_alive(self):
        """F5 version of `is_alive` method, see NAPALM for documentation."""
        if self.device:
            return {"is_alive": True}
        return {"is_alive": False}

    def _get_uptime(self):
        return self.device.command("/mgmt/tm/util/bash", {"command": "run", "utilCmdArgs": "-c 'uptime'"}).lstrip()

    def _get_device_info(self):
        return self.device.load("/mgmt/tm/cm/device/")[0].properties

    def get_facts(self):
        """F5 version of `get_facts` method, see NAPALM for documentation."""
        device_info = self._get_device_info()
        facts = {
            "uptime": self._get_uptime(),
            "vendor": "F5 Networks",
            "model": device_info["marketingName"],
            "hostname": device_info["hostname"],
            "fqdn": device_info["hostname"],
            "os_version": device_info["version"],
            "serial_number": device_info["chassisId"],
            "interface_list": self._get_interfaces_list(query=self.device.load("/mgmt/tm/net/interface/")),
        }
        return facts

    def _get_interfaces_list(self, query) -> List[str]:
        interfaces = [intf.properties["name"] for intf in query]
        return interfaces

    def _get_interfaces_enabled_state(self, query) -> List[bool]:
        enabled_state = [intf.properties["enabled"] for intf in query]
        return enabled_state

    def _get_interfaces_mac_address(self, query) -> List[str]:
        mac_addresses = [intf.properties["macAddress"] for intf in query]
        return mac_addresses

    def _get_interfaces_active_media(self, query) -> List[bool]:
        active_media = [intf.properties["mediaActive"] for intf in query]
        return active_media

    def _get_interfaces_media_status(self, query) -> List[bool]:
        media_status = [not (intf.properties["mediaActive"] == "none") for intf in query]
        return media_status

    def _get_interfaces_description(self, query) -> List[str]:
        description = [intf.properties["description"] if intf.properties.get("description") else "" for intf in query]
        return description

    def _get_interfaces_all_statistics(self) -> dict:
        statistcs = self.device.load("/mgmt/tm/net/interface/stats/").properties
        return statistcs

    def _get_system_information(self) -> dict:
        system_information = self.device.load("/mgmt/tm/sys/snmp/").properties
        return system_information

    def get_snmp_information(self):
        """F5 version of 'get_snmp_information' method, see NAPALM for documentation."""
        sys_info = self._get_system_information()
        device_info = self._get_device_info()
        snmp_info = {
            "contact": sys_info["sysContact"] or "",
            "location": sys_info["sysLocation"] or "",
            "chassis_id": device_info["chassisId"],
            "community": {},
        }
        communities = self.device.load("/mgmt/tm/sys/snmp/communities/")

        for comm in communities:
            snmp_info["community"][comm.properties["communityName"]] = {
                "acl": comm.properties["source"] or "N/A",
                "mode": comm.properties["access"],
            }

        return snmp_info

    def get_mac_address_table(self):
        raise NotImplementedError
        # vlan_list = self.device.Networking.VLAN.get_list()
        # vlan_ids = self.device.Networking.VLAN.get_vlan_id(vlan_list)
        # dynamic_mac_list = self.device.Networking.VLAN.get_dynamic_forwarding(vlan_list)
        # static_mac_list = self.device.Networking.VLAN.get_static_forwarding(vlan_list)

        # mac_list = list()

        # for vlan_id, vlan, dynamic_entry in zip(vlan_ids, vlan_list, dynamic_mac_list):
        #     for fdb in dynamic_entry:
        #         mac_list.append(
        #             {
        #                 "mac": fdb["mac_address"],
        #                 "interface": vlan,
        #                 "vlan": vlan_id,
        #                 "static": False,
        #                 "active": True,
        #                 "moves": 0,
        #                 "last_move": 0.0,
        #             }
        #         )

        # for vlan_id, vlan, static_entry in zip(vlan_ids, vlan_list, static_mac_list):
        #     for fdb in static_entry:
        #         mac_list.append(
        #             {
        #                 "mac": fdb["mac_address"],
        #                 "interface": vlan,
        #                 "vlan": vlan_id,
        #                 "static": True,
        #                 "active": True,
        #                 "moves": 0,
        #                 "last_move": 0.0,
        #             }
        #         )

        # return mac_list

    def get_users(self):
        """F5 version of `get_users` method, see NAPALM for documentation."""
        users_dict = {}
        api_users = self.device.load("/mgmt/tm/auth/user/")
        for user in api_users:
            users_dict = {
                user.properties["name"]: {
                    "level": 15 if user.properties["partitionAccess"][0]["role"] == "admin" else 0,
                    "password": user.properties["encryptedPassword"],
                    "sshkeys": [],
                }
            }
        return users_dict

    def get_ntp_servers(self) -> dict:
        """F5 version of `get_ntp_servers` method, see NAPALM for documentation.

        Returns:
            dict: Dictionary of NTP server hosts as key with empty value.
        """
        result = self.device.load("/mgmt/tm/sys/ntp/").properties
        ntp_servers = result.get("servers")
        return {server: {} for server in ntp_servers}

    def get_interfaces_ip(self):
        result = self.device.load("/mgmt/tm/net/self/")
        interfaces_ip = {}
        for ip in result:
            host, prefix = tuple(ip.properties["address"].split("/"))
            if ":" in ip.properties["address"]:
                interfaces_ip[ip.properties["fullPath"]] = {"ipv6": {host: {"prefix_length": int(prefix)}}}
            else:
                interfaces_ip[ip.properties["fullPath"]] = {"ipv4": {host: {"prefix_length": int(prefix)}}}
        return interfaces_ip

    def get_environment(self):
        raise NotImplementedError
        # temperature_metrics = self.device.System.SystemInfo.get_temperature_metrics()
        # blade_temperature = self.device.System.SystemInfo.get_blade_temperature()
        # fan_metrics = self.device.System.SystemInfo.get_fan_metrics()
        # all_host_statistics = self.device.System.Statistics.get_all_host_statistics()
        # global_cpu = self.device.System.SystemInfo.get_global_cpu_usage_extended_information()
        # power_supply_metrics = self.device.System.SystemInfo.get_power_supply_metrics()
        # system_information = self.device.System.SystemInfo.get_system_information()

        # model = "{}_{}".format(system_information["product_category"], system_information["platform"])

        # # TEMPERATURE metrics
        # temperatures = dict()
        # if model in LIMITS:
        #     # Parse chassis / appliance temperatures
        #     for sensor in temperature_metrics["temperatures"]:
        #         sensor_id = sensor[0]["value"]
        #         sensor_value = sensor[1]["value"]

        #         sensor_max = LIMITS[model][str(sensor_id)][0]
        #         sensor_location = LIMITS[model][str(sensor_id)][1]

        #         temperatures[sensor_location] = {
        #             "temperature": float(sensor_value),
        #             "is_alert": True if sensor_value >= sensor_max * ALERT else False,
        #             "is_critical": True if sensor_value >= sensor_max else False,
        #         }
        #     # Parse blades' temperatures
        #     for sensor in blade_temperature:
        #         sensor_value = sensor["temperature"]
        #         sensor_max = LIMITS[model][sensor["location"]][0]

        #         temperatures[sensor["location"]] = {
        #             "temperature": float(sensor_value),
        #             "is_alert": True if sensor_value >= sensor_max * ALERT else False,
        #             "is_critical": True if sensor_value >= sensor_max else False,
        #         }

        # # FAN metrics
        # # Use fan identifier as a location.
        # # (iControl API doesn't provide fans' locations.)
        # fans = {fan[0]["value"]: {"status": True if fan[1]["value"] == 1 else False} for fan in fan_metrics["fans"]}

        # # CPU metrics
        # cpu_usage = -1
        # for stat in global_cpu["statistics"]:
        #     if stat["type"] == "STATISTIC_CPU_INFO_ONE_MIN_AVG_USAGE_RATIO":
        #         cpu_usage = self.convert_to_64_bit(stat["value"])

        # cpus = {"0": {"%usage": float(cpu_usage)}}

        # # Power Supply metrics
        # power = dict()
        # for ps in power_supply_metrics["power_supplies"]:
        #     for metric in ps:
        #         if metric["metric_type"] == "PS_INDEX":
        #             ps_index = metric["value"]
        #         elif metric["metric_type"] == "PS_STATE":
        #             ps_state = metric["value"]
        #         elif metric["metric_type"] == "PS_INPUT_STATE":
        #             ps_input_state = metric["value"]
        #         elif metric["metric_type"] == "PS_OUTPUT_STATE":
        #             ps_output_state = metric["value"]
        #         elif metric["metric_type"] == "PS_FAN_STATE":
        #             ps_fan_state = metric["value"]

        #     power[ps_index] = {
        #         "status": (
        #             True
        #             if all(v > 0 for v in [ps_index, ps_state, ps_input_state, ps_output_state, ps_fan_state])
        #             else False
        #         ),
        #         "output": -1.0,
        #         "capacity": -1.0,
        #     }

        # total_ram = 0
        # used_ram = 0
        # for host in all_host_statistics["statistics"]:
        #     for stat in host["statistics"]:
        #         if stat["type"] == "STATISTIC_MEMORY_TOTAL_BYTES":
        #             total_ram = total_ram + self.convert_to_64_bit(stat["value"])
        #         elif stat["type"] == "STATISTIC_MEMORY_USED_BYTES":
        #             used_ram = used_ram + self.convert_to_64_bit(stat["value"])

        # memory = {
        #     "available_ram": total_ram - used_ram,
        #     "used_ram": used_ram,
        # }

        # env_dict = {
        #     "memory": memory,
        #     "power": power,
        #     "cpu": cpus,
        #     "temperature": temperatures,
        #     "fans": fans,
        # }

        # return env_dict

    def get_network_instances(self, name=""):
        raise NotImplementedError
        # rd_list = self.device.Networking.RouteDomainV2.get_list()
        # rd_description_list = self.device.Networking.RouteDomainV2.get_description(rd_list)
        # rd_id_list = self.device.Networking.RouteDomainV2.get_identifier(rd_list)
        # rd_vlan_list = self.device.Networking.RouteDomainV2.get_vlan(rd_list)

        # instances = {}

        # for rd, description, rd_id, rd_vlan in zip(rd_list, rd_description_list, rd_id_list, rd_vlan_list):
        #     if rd.split("/")[-1] == "0":
        #         instance_name = "default"
        #     else:
        #         instance_name = rd.split("/")[-1]

        #     instances[instance_name] = {
        #         "interfaces": {"interface": {vlan: {} for vlan in rd_vlan}},
        #         "state": {"route_distinguisher": str(rd_id)},
        #         "name": instance_name,
        #         "type": "DEFAULT_INSTANCE" if instance_name == "default" else "L3VRF",
        #     }

        # return {name: instances.get(name, {})} if name else instances

    def get_interfaces_counters(self):
        raise NotImplementedError
        # try:
        #     icr_statistics = self._get_interfaces_all_statistics()
        # except RESTAPIError as err:
        #     raise ConnectionError(f"get_interfaces: {err}") from err

        # counters = {}
        # for x in icr_statistics["entries"]:
        #     if_name = x["nestedStats"]["entries"]["tmName"]["description"]
        #     counters[if_name] = {}
        #     counters[if_name]["tx_broadcast_packets"] = -1
        #     counters[if_name]["rx_broadcast_packets"] = -1

        #     for stat in x["nestedStats"]["entries"]:
        #         if stat["type"] == "STATISTIC_ERRORS_IN":
        #             counters[if_name]["rx_errors"] = self.convert_to_64_bit(stat["value"])
        #         elif stat["type"] == "STATISTIC_ERRORS_OUT":
        #             counters[if_name]["tx_errors"] = self.convert_to_64_bit(stat["value"])
        #         elif stat["type"] == "STATISTIC_DROPPED_PACKETS_IN":
        #             counters[if_name]["rx_discards"] = self.convert_to_64_bit(stat["value"])
        #         elif stat["type"] == "STATISTIC_DROPPED_PACKETS_OUT":
        #             counters[if_name]["tx_discards"] = self.convert_to_64_bit(stat["value"])
        #         elif stat["type"] == "STATISTIC_BYTES_IN":
        #             counters[if_name]["rx_octets"] = self.convert_to_64_bit(stat["value"])
        #         elif stat["type"] == "STATISTIC_BYTES_OUT":
        #             counters[if_name]["tx_octets"] = self.convert_to_64_bit(stat["value"])
        #         elif stat["type"] == "STATISTIC_PACKETS_IN":
        #             counters[if_name]["rx_unicast_packets"] = self.convert_to_64_bit(stat["value"])
        #         elif stat["type"] == "STATISTIC_PACKETS_OUT":
        #             counters[if_name]["tx_unicast_packets"] = self.convert_to_64_bit(stat["value"])
        #         elif stat["type"] == "STATISTIC_MULTICASTS_IN":
        #             counters[if_name]["rx_multicast_packets"] = self.convert_to_64_bit(stat["value"])
        #         elif stat["type"] == "STATISTIC_MULTICASTS_OUT":
        #             counters[if_name]["tx_multicast_packets"] = self.convert_to_64_bit(stat["value"])

        # return counters

    def get_interfaces(self):
        """F5 version of 'get_interfaces' method, see NAPALM for documentation."""

        def if_speed(active_media):
            if "100000" in active_media:
                return 100000
            elif "40000" in active_media:
                return 40000
            elif "10000" in active_media:
                return 10000
            elif "1000" in active_media:
                return 1000
            elif "100" in active_media:
                return 100
            else:
                return -1

        try:
            intf_query = self.device.load("/mgmt/tm/net/interface/")
            interfaces = self._get_interfaces_list(intf_query)
            active_media = self._get_interfaces_active_media(intf_query)
            description = self._get_interfaces_description(intf_query)
            enabled_state = self._get_interfaces_enabled_state(intf_query)
            mac_address = self._get_interfaces_mac_address(intf_query)
            media_status = self._get_interfaces_media_status(intf_query)
        except RESTAPIError as err:
            raise ConnectionError(f"get_interfaces: {err}") from err

        interfaces_dict = {
            interface_name: {
                "is_up": media_status,
                "is_enabled": enabled_state,
                "description": description,
                "last_flapped": -1.0,
                "speed": if_speed(active_media),
                "mac_address": mac_address,
            }
            for (interface_name, media_status, enabled_state, description, mac_address, active_media) in zip(
                interfaces, media_status, enabled_state, description, mac_address, active_media
            )
        }

        return interfaces_dict

    @staticmethod
    def convert_to_64_bit(value):
        """Converts two 32 bit signed integers to a 64-bit unsigned integer.
        https://devcentral.f5.com/questions/high-and-low-bits-of-64-bit-long-and-c
        by mhite.
        """
        high = value["high"]
        low = value["low"]
        if high < 0:
            high = high + (1 << 32)
        if low < 0:
            low = low + (1 << 32)
        value = int((high << 32) | low)
        assert value >= 0
        return value

    def _upload_scf(self, fp):
        try:
            self.device.upload("/mgmt/shared/file-transfer/uploads", fp)
            # we need to move the file to a whitelisted directory and /tmp is the easiest as it's cleared upon reboot
            self.cli(commands=[f"mv /var/config/rest/downloads/{fp} /tmp/"])
        except RESTAPIError as err:
            raise ConnectionError(f"F5 API Error: {err}") from err
        except EnvironmentError as err:
            raise EnvironmentError(f"Error ({err.errno}): {err.strerror}") from err
