"""MQTT Broker self-tests (WT-11xx).

These verify the workbench's internal MQTT broker management.
"""

import pytest
import time
from workbench_driver import CommandError

class TestMQTTBroker:
    """WT-11xx: MQTT Broker tests."""

    def test_wt1100_broker_lifecycle(self, workbench):
        """WT-1100: MQTT start/stop lifecycle."""
        # Ensure it's stopped first
        workbench.mqtt_stop()
        status = workbench.mqtt_status()
        assert status["running"] is False

        # Start
        resp = workbench.mqtt_start()
        assert resp["port"] == 1883
        
        status = workbench.mqtt_status()
        assert status["running"] is True
        assert status["port"] == 1883

        # Stop
        workbench.mqtt_stop()
        status = workbench.mqtt_status()
        assert status["running"] is False

    def test_wt1101_broker_idempotency(self, workbench):
        """WT-1101: MQTT start/stop are idempotent."""
        # Start twice
        workbench.mqtt_start()
        workbench.mqtt_start()
        status = workbench.mqtt_status()
        assert status["running"] is True

        # Stop twice
        workbench.mqtt_stop()
        workbench.mqtt_stop()
        status = workbench.mqtt_status()
        assert status["running"] is False

    @pytest.mark.requires_dut
    def test_wt1102_dut_connect_mqtt(self, workbench, wifi_network):
        """WT-1102: DUT can connect to the broker via workbench WiFi.
        
        Note: This requires the DUT to have the test firmware installed
        and properly configured to join the wifi_network.
        """
        # Start broker
        workbench.mqtt_start()
        
        # In a real scenario, we would trigger the DUT to connect here.
        # For now, this is a placeholder showing how the test would look.
        
        status = workbench.mqtt_status()
        assert status["running"] is True
        
        # Clean up
        workbench.mqtt_stop()

    def test_wt1103_pub_sub_api(self, workbench):
        """WT-1103: Advanced MQTT Pub/Sub API verification."""
        workbench.mqtt_start()
        
        # 1. Subscribe to a topic
        workbench.mqtt_subscribe("/test/topic")
        
        # 2. Publish a message
        result = workbench.mqtt_publish("/test/topic", "Hello Workbench")
        
        # 3. Wait a bit for processing and retrieve messages
        time.sleep(1)
        
        msgs = workbench.mqtt_get_messages(topic="/test/topic")
        assert len(msgs) >= 1
        assert msgs[-1]["payload"] == "Hello Workbench"
        
        # 4. Content filter
        msgs = workbench.mqtt_get_messages(payload="Hello")
        assert len(msgs) >= 1
        
        # 5. Clear messages
        workbench.mqtt_clear_messages()
        msgs = workbench.mqtt_get_messages()
        assert len(msgs) == 0
        
        workbench.mqtt_stop()

    def test_wt1104_mqtt_regex_filter(self, workbench):
        """WT-1104: MQTT message filtering with regex."""
        workbench.mqtt_start()
        workbench.mqtt_subscribe("/device/+/sensor")
        
        # Publish messages
        workbench.mqtt_publish("/device/1/sensor", "value: 23.5")
        workbench.mqtt_publish("/device/2/sensor", "value: 42.1")
        workbench.mqtt_publish("/other/topic", "not seen")
        
        import time
        time.sleep(1)
        
        # Filter by topic regex
        msgs = workbench.mqtt_get_messages(topic="/device/[0-9]/sensor", regex=True)
        assert len(msgs) == 2
        
        # Filter by payload regex
        msgs = workbench.mqtt_get_messages(payload="value: [0-9]+\\.[0-9]+", regex=True)
        assert len(msgs) == 2
        
        workbench.mqtt_stop()
