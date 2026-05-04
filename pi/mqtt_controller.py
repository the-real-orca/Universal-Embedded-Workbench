"""
MQTT Controller — manages a mosquitto broker for ESP32 MQTT client testing.

Used by the portal to start/stop a local MQTT broker accessible to devices
on the workbench WiFi AP.
"""

import logging
import os
import subprocess
import threading
import time
import json
from datetime import datetime

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MQTT_PORT = 1883
WORK_DIR = "/tmp/mqtt-tester"
MOSQUITTO_CONF = os.path.join(WORK_DIR, "mosquitto.conf")
MOSQUITTO_LOG = os.path.join(WORK_DIR, "mosquitto.log")

# ---------------------------------------------------------------------------
# Module state
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_active = False
_proc = None

# Internal client for Pub/Sub verification
_internal_client = None
_messages = []  # List of {topic, payload, timestamp}
_max_messages = 1000

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_work_dir():
    os.makedirs(WORK_DIR, exist_ok=True)


def _kill_proc(proc, timeout=5.0):
    """Terminate a subprocess, SIGKILL if it won't die."""
    if proc is None or proc.poll() is not None:
        return
    try:
        proc.terminate()
    except OSError:
        return
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            proc.kill()
        except OSError:
            pass


def _kill_existing():
    """Kill any existing mosquitto process (best effort)."""
    try:
        subprocess.run(
            ["pkill", "-f", "mosquitto"],
            capture_output=True, timeout=5, check=False,
        )
        time.sleep(0.3)
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Internal Client Logic
# ---------------------------------------------------------------------------

def _on_message(client, userdata, msg):
    global _messages
    try:
        payload = msg.payload.decode(errors='replace')
        entry = {
            "topic": msg.topic,
            "payload": payload,
            "timestamp": datetime.now().isoformat()
        }
        with _lock:
            _messages.append(entry)
            if len(_messages) > _max_messages:
                _messages.pop(0)
    except Exception as e:
        logger.error("Error in MQTT on_message: %s", e)

def _start_internal_client():
    global _internal_client
    if not mqtt:
        logger.warning("paho-mqtt not installed, internal client disabled")
        return

    try:
        # Use newer API if available
        try:
            _internal_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        except AttributeError:
            _internal_client = mqtt.Client()
            
        _internal_client.on_message = _on_message
        _internal_client.connect("127.0.0.1", MQTT_PORT, 60)
        _internal_client.loop_start()
        logger.info("Internal MQTT client started")
    except Exception as e:
        logger.error("Failed to start internal MQTT client: %s", e)

def _stop_internal_client():
    global _internal_client
    if _internal_client:
        _internal_client.loop_stop()
        _internal_client.disconnect()
        _internal_client = None
        logger.info("Internal MQTT client stopped")

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def start():
    """Start the mosquitto MQTT broker. Returns dict with port."""
    global _active, _proc

    with _lock:
        if _active and _proc is not None and _proc.poll() is None:
            return {"port": MQTT_PORT}

        _ensure_work_dir()
        _kill_existing()

        # Write mosquitto config — open broker, no auth, listen on all interfaces
        conf_lines = [
            f"listener {MQTT_PORT}",
            "allow_anonymous true",
            f"log_dest file {MOSQUITTO_LOG}",
            "log_type all",
        ]
        with open(MOSQUITTO_CONF, "w") as f:
            f.write("\n".join(conf_lines) + "\n")

        # Start mosquitto
        _proc = subprocess.Popen(
            ["mosquitto", "-c", MOSQUITTO_CONF],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )

        # Wait for it to initialise
        time.sleep(1.0)
        if _proc.poll() is not None:
            out = _proc.stdout.read().decode(errors="replace")
            _active = False
            raise RuntimeError(f"mosquitto failed to start: {out[:500]}")

        _active = True
        logger.info("MQTT broker started on port %d", MQTT_PORT)
        
        # Reset message buffer and start internal client
        global _messages
        _messages = []
        _start_internal_client()
        
        return {"port": MQTT_PORT}


def stop():
    """Stop the mosquitto broker."""
    global _active, _proc

    with _lock:
        _stop_internal_client()
        _kill_proc(_proc)
        _proc = None
        _active = False
        logger.info("MQTT broker stopped")


def status():
    """Return broker status dict."""
    global _active

    with _lock:
        running = _active and _proc is not None and _proc.poll() is None
        # If process died unexpectedly, update state
        if _active and not running:
            _active = False
            _stop_internal_client()
        return {
            "running": running,
            "port": MQTT_PORT if running else None,
            "internal_client": {
                "running": _internal_client is not None,
                "library_available": mqtt is not None
            }
        }

def publish(topic, payload, qos=0, retain=False):
    """Publish a message using the internal client."""
    if not _internal_client:
        raise RuntimeError("MQTT internal client not running")
    
    info = _internal_client.publish(topic, payload, qos=qos, retain=retain)
    info.wait_for_publish()
    return {"ok": True}

def subscribe(topic):
    """Subscribe to a topic using the internal client."""
    if not _internal_client:
        raise RuntimeError("MQTT internal client not running")
    
    _internal_client.subscribe(topic)
    return {"ok": True}

def get_messages(topic_filter=None, content_filter=None, limit=100, use_regex=False):
    """Get buffered messages with optional filters.
    
    Filters use substring match by default, or regex if use_regex=True.
    """
    import re
    with _lock:
        filtered = _messages
        
        if topic_filter:
            if use_regex:
                try:
                    r = re.compile(topic_filter)
                    filtered = [m for m in filtered if r.search(m["topic"])]
                except re.error as e:
                    logger.error("Invalid topic regex: %s", e)
            else:
                filtered = [m for m in filtered if topic_filter in m["topic"]]
            
        if content_filter:
            if use_regex:
                try:
                    r = re.compile(content_filter)
                    filtered = [m for m in filtered if r.search(m["payload"])]
                except re.error as e:
                    logger.error("Invalid content regex: %s", e)
            else:
                filtered = [m for m in filtered if content_filter in m["payload"]]
            
        return filtered[-limit:]

def clear_messages():
    """Clear the message buffer."""
    global _messages
    with _lock:
        _messages = []
    return {"ok": True}
