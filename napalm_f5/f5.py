# Originally forked from https://github.com/napalm-automation-community/napalm-f5
# Inroducting support to python3 and get_config method to work w/ Nautobot.

"""
Napalm driver for F5.
Read https://napalm.readthedocs.io for more information.
"""
import base64
import os
from typing import Optional

from bigrest.bigip import BIGIP, RESTAPIError
from napalm.base.base import NetworkDriver
from napalm.base.exceptions import ConnectionException, MergeConfigException, ReplaceConfigException
from napalm_f5.env import LIMITS, ALERT
from napalm_f5.exceptions import CommitConfigException, DiscardConfigException


class F5Driver(NetworkDriver):
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
                device=self.hostname, username=self.username, password=self.password, session_verify=False
            )
        except RESTAPIError as err:
            raise ConnectionException(f"F5 API Error ({err})") from err

    def close(self):
        """F5 version of `close` method, see NAPALM for documentation."""
        self.device = None

    def load_replace_candidate(self, filename=None, config=None):
        self.config_replace = True

        if config:
            raise NotImplementedError

        if filename:
            self.filename = os.path.basename(filename)
            try:
                self._upload_scf(filename)
            except Exception as err:
                raise ReplaceConfigException(err) from err

    def get_config(
        self, retrieve: str = "all", full: bool = False, sanitized: bool = False, format: str = "text"
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
        self.config_replace = False

        if config:
            raise NotImplementedError

        if filename:
            self.filename = os.path.basename(filename)
            try:
                self._upload_scf(filename)
            except Exception as err:
                raise MergeConfigException(err) from err

    def commit_config(self):
        try:
            self.device.System.ConfigSync.install_single_configuration_file(
                filename=self.filename,
                load_flag="LOAD_HIGH_LEVEL_CONFIG",
                passphrase="",
                tarfile="",
                merge=not self.config_replace,
            )
        except bigsuds.OperationFailed as err:
            raise CommitConfigException(err) from err

    def discard_config(self):
        try:
            self.device.System.ConfigSync.delete_single_configuration_file(filename=self.filename)
        except bigsuds.OperationFailed as err:
            raise DiscardConfigException(err) from err

    def is_alive(self):
        if self.device:
            return {"is_alive": True}
        else:
            return {"is_alive": False}

    def _get_uptime(self):
        return self.device.command("/mgmt/tm/util/bash", {"command": "run", "utilCmdArgs": "-c 'uptime'"}).lstrip()

    def _get_device_info(self):
        return self.device.load("/mgmt/tm/cm/device/")[0].properties

    def get_facts(self):
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

    def _get_interfaces_list(self, query):
        interfaces = [intf.properties["name"] for intf in query]
        return interfaces

    def _get_interfaces_enabled_state(self, query):
        enabled_state = [intf.properties["enabled"] for intf in query]
        return enabled_state

    def _get_interfaces_mac_address(self, query):
        mac_addresses = [intf.properties["macAddress"] for intf in query]
        return mac_addresses

    def _get_interfaces_active_media(self, query):
        active_media = [intf.properties["mediaActive"] for intf in query]
        return active_media

    def _get_interfaces_media_status(self, query):
        media_status = [not (intf.properties["mediaActive"] == "none") for intf in query]
        return media_status

    def _get_interfaces_description(self, query):
        description = [intf.properties["description"] if intf.properties.get("description") else "" for intf in query]
        return description

    def _get_interfaces_all_statistics(self):
        statistcs = self.device.Networking.Interfaces.get_all_statistics()
        return statistcs

    def _get_system_information(self):
        system_information = self.device.Management.SNMPConfiguration.get_system_information()
        return system_information

    def get_snmp_information(self):
        sys_info = self._get_system_information()
        snmp_info = {
            "contact": sys_info["sys_contact"] or "",
            "location": sys_info["sys_location"] or "",
            "chassis_id": sys_info["sys_description"] or "",
            "community": {},
        }
        ro_comm = self.device.Management.SNMPConfiguration.get_readonly_community()
        rw_comm = self.device.Management.SNMPConfiguration.get_readwrite_community()

        for x in ro_comm:
            snmp_info["community"][x["community"]] = {
                "acl": x["source"] or "N/A",
                "mode": "ro",
            }

        for x in rw_comm:
            snmp_info["community"][x["community"]] = {
                "acl": x["source"] or "N/A",
                "mode": "rw",
            }

        return snmp_info

    def get_mac_address_table(self):
        vlan_list = self.device.Networking.VLAN.get_list()
        vlan_ids = self.device.Networking.VLAN.get_vlan_id(vlan_list)
        dynamic_mac_list = self.device.Networking.VLAN.get_dynamic_forwarding(vlan_list)
        static_mac_list = self.device.Networking.VLAN.get_static_forwarding(vlan_list)

        mac_list = list()

        for vlan_id, vlan, dynamic_entry in zip(vlan_ids, vlan_list, dynamic_mac_list):
            for fdb in dynamic_entry:
                mac_list.append(
                    {
                        "mac": fdb["mac_address"],
                        "interface": vlan,
                        "vlan": vlan_id,
                        "static": False,
                        "active": True,
                        "moves": 0,
                        "last_move": 0.0,
                    }
                )

        for vlan_id, vlan, static_entry in zip(vlan_ids, vlan_list, static_mac_list):
            for fdb in static_entry:
                mac_list.append(
                    {
                        "mac": fdb["mac_address"],
                        "interface": vlan,
                        "vlan": vlan_id,
                        "static": True,
                        "active": True,
                        "moves": 0,
                        "last_move": 0.0,
                    }
                )

        return mac_list

    def get_users(self):
        api_users = self.device.Management.UserManagement.get_list()
        usernames = [x["name"] for x in api_users]
        passwords = self.device.Management.UserManagement.get_encrypted_password(usernames)
        users_dict = {
            username: {
                "level": 0,
                "password": password,
                "sshkeys": [],
            }
            for (username, password) in zip(usernames, passwords)
        }
        return users_dict

    def get_ntp_servers(self):
        return {server: {} for server in self.device.System.Inet.get_ntp_server_address()}

    def get_interfaces_ip(self):
        def _get_prefix_length(netmask):
            if ":" in netmask:
                if netmask.endswith("::"):
                    netmask = netmask.replace("::", "")
                return sum([bin(int(x, 16)).count("1") for x in netmask.split(":")])
            else:
                return sum([bin(int(x)).count("1") for x in netmask.split(".")])

        net_selfs = self.device.Networking.SelfIPV2.get_list()
        ips = self.device.Networking.SelfIPV2.get_address(net_selfs)
        netmasks = self.device.Networking.SelfIPV2.get_netmask(net_selfs)
        prefixes = list(map(_get_prefix_length, netmasks))

        interfaces_ip = {}

        for net_self in zip(net_selfs, ips, prefixes):
            if ":" in net_self[1]:
                interfaces_ip[net_self[0]] = {"ipv6": {net_self[1]: {"prefix_length": net_self[2]}}}
            else:
                interfaces_ip[net_self[0]] = {"ipv4": {net_self[1]: {"prefix_length": net_self[2]}}}

        return interfaces_ip

    def get_environment(self):
        temperature_metrics = self.device.System.SystemInfo.get_temperature_metrics()
        blade_temperature = self.device.System.SystemInfo.get_blade_temperature()
        fan_metrics = self.device.System.SystemInfo.get_fan_metrics()
        all_host_statistics = self.device.System.Statistics.get_all_host_statistics()
        global_cpu = self.device.System.SystemInfo.get_global_cpu_usage_extended_information()
        power_supply_metrics = self.device.System.SystemInfo.get_power_supply_metrics()
        system_information = self.device.System.SystemInfo.get_system_information()

        model = "{}_{}".format(system_information["product_category"], system_information["platform"])

        # TEMPERATURE metrics
        temperatures = dict()
        if model in LIMITS:
            # Parse chassis / appliance temperatures
            for sensor in temperature_metrics["temperatures"]:
                sensor_id = sensor[0]["value"]
                sensor_value = sensor[1]["value"]

                sensor_max = LIMITS[model][str(sensor_id)][0]
                sensor_location = LIMITS[model][str(sensor_id)][1]

                temperatures[sensor_location] = {
                    "temperature": float(sensor_value),
                    "is_alert": True if sensor_value >= sensor_max * ALERT else False,
                    "is_critical": True if sensor_value >= sensor_max else False,
                }
            # Parse blades' temperatures
            for sensor in blade_temperature:
                sensor_value = sensor["temperature"]
                sensor_max = LIMITS[model][sensor["location"]][0]

                temperatures[sensor["location"]] = {
                    "temperature": float(sensor_value),
                    "is_alert": True if sensor_value >= sensor_max * ALERT else False,
                    "is_critical": True if sensor_value >= sensor_max else False,
                }

        # FAN metrics
        # Use fan identifier as a location.
        # (iControl API doesn't provide fans' locations.)
        fans = {fan[0]["value"]: {"status": True if fan[1]["value"] == 1 else False} for fan in fan_metrics["fans"]}

        # CPU metrics
        cpu_usage = -1
        for stat in global_cpu["statistics"]:
            if stat["type"] == "STATISTIC_CPU_INFO_ONE_MIN_AVG_USAGE_RATIO":
                cpu_usage = self.convert_to_64_bit(stat["value"])

        cpus = {"0": {"%usage": float(cpu_usage)}}

        # Power Supply metrics
        power = dict()
        for ps in power_supply_metrics["power_supplies"]:
            for metric in ps:
                if metric["metric_type"] == "PS_INDEX":
                    ps_index = metric["value"]
                elif metric["metric_type"] == "PS_STATE":
                    ps_state = metric["value"]
                elif metric["metric_type"] == "PS_INPUT_STATE":
                    ps_input_state = metric["value"]
                elif metric["metric_type"] == "PS_OUTPUT_STATE":
                    ps_output_state = metric["value"]
                elif metric["metric_type"] == "PS_FAN_STATE":
                    ps_fan_state = metric["value"]

            power[ps_index] = {
                "status": (
                    True
                    if all(v > 0 for v in [ps_index, ps_state, ps_input_state, ps_output_state, ps_fan_state])
                    else False
                ),
                "output": -1.0,
                "capacity": -1.0,
            }

        total_ram = 0
        used_ram = 0
        for host in all_host_statistics["statistics"]:
            for stat in host["statistics"]:
                if stat["type"] == "STATISTIC_MEMORY_TOTAL_BYTES":
                    total_ram = total_ram + self.convert_to_64_bit(stat["value"])
                elif stat["type"] == "STATISTIC_MEMORY_USED_BYTES":
                    used_ram = used_ram + self.convert_to_64_bit(stat["value"])

        memory = {
            "available_ram": total_ram - used_ram,
            "used_ram": used_ram,
        }

        env_dict = {
            "memory": memory,
            "power": power,
            "cpu": cpus,
            "temperature": temperatures,
            "fans": fans,
        }

        return env_dict

    def get_network_instances(self, name=""):
        rd_list = self.device.Networking.RouteDomainV2.get_list()
        rd_description_list = self.device.Networking.RouteDomainV2.get_description(rd_list)
        rd_id_list = self.device.Networking.RouteDomainV2.get_identifier(rd_list)
        rd_vlan_list = self.device.Networking.RouteDomainV2.get_vlan(rd_list)

        instances = {}

        for rd, description, rd_id, rd_vlan in zip(rd_list, rd_description_list, rd_id_list, rd_vlan_list):
            if rd.split("/")[-1] == "0":
                instance_name = "default"
            else:
                instance_name = rd.split("/")[-1]

            instances[instance_name] = {
                "interfaces": {"interface": {vlan: {} for vlan in rd_vlan}},
                "state": {"route_distinguisher": str(rd_id)},
                "name": instance_name,
                "type": "DEFAULT_INSTANCE" if instance_name == "default" else "L3VRF",
            }

        return {name: instances.get(name, {})} if name else instances

    def get_interfaces_counters(self):
        try:
            icr_statistics = self._get_interfaces_all_statistics()
        except RESTAPIError as err:
            raise ConnectionError(f"get_interfaces: {err}") from err

        counters = {}
        for x in icr_statistics["statistics"]:
            if_name = x["interface_name"]
            counters[if_name] = {}
            counters[if_name]["tx_broadcast_packets"] = -1
            counters[if_name]["rx_broadcast_packets"] = -1

            for stat in x["statistics"]:
                if stat["type"] == "STATISTIC_ERRORS_IN":
                    counters[if_name]["rx_errors"] = self.convert_to_64_bit(stat["value"])
                elif stat["type"] == "STATISTIC_ERRORS_OUT":
                    counters[if_name]["tx_errors"] = self.convert_to_64_bit(stat["value"])
                elif stat["type"] == "STATISTIC_DROPPED_PACKETS_IN":
                    counters[if_name]["rx_discards"] = self.convert_to_64_bit(stat["value"])
                elif stat["type"] == "STATISTIC_DROPPED_PACKETS_OUT":
                    counters[if_name]["tx_discards"] = self.convert_to_64_bit(stat["value"])
                elif stat["type"] == "STATISTIC_BYTES_IN":
                    counters[if_name]["rx_octets"] = self.convert_to_64_bit(stat["value"])
                elif stat["type"] == "STATISTIC_BYTES_OUT":
                    counters[if_name]["tx_octets"] = self.convert_to_64_bit(stat["value"])
                elif stat["type"] == "STATISTIC_PACKETS_IN":
                    counters[if_name]["rx_unicast_packets"] = self.convert_to_64_bit(stat["value"])
                elif stat["type"] == "STATISTIC_PACKETS_OUT":
                    counters[if_name]["tx_unicast_packets"] = self.convert_to_64_bit(stat["value"])
                elif stat["type"] == "STATISTIC_MULTICASTS_IN":
                    counters[if_name]["rx_multicast_packets"] = self.convert_to_64_bit(stat["value"])
                elif stat["type"] == "STATISTIC_MULTICASTS_OUT":
                    counters[if_name]["tx_multicast_packets"] = self.convert_to_64_bit(stat["value"])

        return counters

    def get_interfaces(self):
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
            chunk_size = 512 * 1024
            filename = os.path.basename(fp)
            size = os.path.getsize(fp)
            start = 0
            with open(fp, "rb") as fileobj:
                while True:
                    payload = base64.b64encode(fileobj.read(chunk_size))
                    if not payload:
                        break
                    end = fileobj.tell()

                    if start == 0 and end == size:
                        chain_type = "FILE_FIRST_AND_LAST"
                    elif start == 0 and end < size:
                        chain_type = "FILE_FIRST"
                    elif start > 0 and end < size:
                        chain_type = "FILE_MIDDLE"
                    elif start > 0 and end == size:
                        chain_type = "FILE_LAST"

                    self.device.System.ConfigSync.upload_file(
                        file_name="/var/local/scf/" + filename,
                        file_context=dict(file_data=payload, chain_type=chain_type),
                    )

                    start += len(payload)

        except RESTAPIError as err:
            raise ConnectionError(f"F5 API Error: {err}") from err
        except EnvironmentError as err:
            raise EnvironmentError(f"Error ({err.errno}): {err.strerror}") from err
