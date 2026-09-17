"""Tests for driver behaviour not covered by the getter fixtures."""

import inspect

from napalm.base.base import NetworkDriver

from napalm_f5.exceptions import ReadOnlyModeException
from napalm_f5.f5 import BASE_GET_CONFIG_TAKES_FORMAT, F5Driver

import pytest


class RecordingDevice:
    """Stand-in for bigrest's BIGIP that records the calls made against it."""

    def __init__(self):
        """Start with an empty call log."""
        self.commands = []

    def command(self, path, data=None):
        """Record a command and return empty output."""
        self.commands.append((path, data))
        return ""


def build_driver(optional_args=None):
    """Return a driver wired to a recording device instead of a real BIG-IP."""
    driver = F5Driver("device.example.net", "admin", "admin", optional_args=optional_args)
    driver.device = RecordingDevice()
    return driver


@pytest.mark.parametrize("optional_args", [None, {}, {"port": 443}, {"read_only": False}])
def test_config_methods_allowed_when_read_only_is_unset(optional_args):
    """read_only is optional, so omitting it must leave the device writable."""
    driver = build_driver(optional_args)

    driver.cli(["show sys version"])
    driver.commit_config()
    driver.discard_config()

    assert len(driver.device.commands) == 3


def test_cli_keys_results_by_command():
    """cli() returns each command's output keyed by the command itself."""
    driver = build_driver()

    assert driver.cli(["show sys version"]) == {"show sys version": ""}


def test_get_config_signature_matches_installed_napalm():
    """The override must match whichever base class NAPALM 4.x or 5.x installed."""
    assert inspect.getfullargspec(F5Driver.get_config)[:4] == inspect.getfullargspec(NetworkDriver.get_config)[:4]


def test_get_config_returns_running_config():
    """get_config() works on both supported NAPALM versions."""
    driver = build_driver()

    assert driver.get_config() == {"running": "", "candidate": "", "startup": ""}


@pytest.mark.parametrize("retrieve", ["startup", "candidate"])
def test_get_config_rejects_unsupported_retrieve(retrieve):
    """Only running-config can be read off a BIG-IP."""
    driver = build_driver()

    with pytest.raises(NotImplementedError):
        driver.get_config(retrieve=retrieve)


@pytest.mark.skipif(
    not BASE_GET_CONFIG_TAKES_FORMAT,
    reason="NAPALM 4.x get_config takes no format argument",
)
def test_get_config_rejects_non_text_format():
    """F5 only returns text configuration, so other formats are refused."""
    driver = build_driver()

    with pytest.raises(NotImplementedError):
        driver.get_config(format="json")


def test_interfaces_counters_convert_bits_to_octets():
    """Octet counters are derived from the device's bit counters."""
    driver = build_driver()
    driver._get_interfaces_all_statistics = lambda: {  # pylint: disable=protected-access
        "entries": {
            "https://localhost/mgmt/tm/net/interface/1.1/stats": {
                "nestedStats": {
                    "entries": {
                        "tmName": {"description": "1.1"},
                        "counters.bitsIn": {"value": 800},
                        "counters.bitsOut": {"value": 80},
                        "counters.pktsIn": {"value": 7},
                        "counters.pktsOut": {"value": 3},
                        "counters.dropsAll": {"value": 5},
                        "counters.errorsAll": {"value": 9},
                    }
                }
            }
        }
    }

    counters = driver.get_interfaces_counters()["1.1"]

    assert counters["rx_octets"] == 100
    assert counters["tx_octets"] == 10
    assert counters["rx_unicast_packets"] == 7
    assert counters["tx_unicast_packets"] == 3
    # dropsAll and errorsAll are totals the device cannot split by direction.
    for unavailable in ("rx_errors", "tx_errors", "rx_discards", "tx_discards"):
        assert counters[unavailable] == -1


@pytest.mark.parametrize(
    "method, args",
    [
        ("cli", (["show sys version"],)),
        ("commit_config", ()),
        ("discard_config", ()),
        ("load_replace_candidate", ()),
        ("load_merge_candidate", ()),
    ],
)
def test_read_only_mode_blocks_changes(method, args):
    """Every config-changing entry point refuses to run in read-only mode."""
    driver = build_driver({"read_only": True})

    with pytest.raises(ReadOnlyModeException):
        getattr(driver, method)(*args)

    assert driver.device.commands == []
