#pragma once

#include "esp_err.h"

/**
 * @brief Initialize MQTT client and start connection to broker.
 * 
 * Uses the default workbench broker address (192.168.4.1 if in AP mode, 
 * or the gateway address if in STA mode).
 */
esp_err_t mqtt_test_init(void);

/**
 * @brief Publish a message to a topic.
 */
esp_err_t mqtt_test_publish(const char *topic, const char *data);
