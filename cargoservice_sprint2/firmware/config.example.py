# Copiare sul Pico W come config.py e impostare i valori della propria LAN.
WIFI_SSID = 'Buttcasa'
WIFI_PASSWORD = 'Ciappetto28!'
MQTT_HOST = '192.168.68.60'  # IP LAN del PC con Mosquitto, mai localhost
#WIFI_SSID = 'TIM-18953968'
#WIFI_PASSWORD = 'YPbDY2sgKyBuiSN9'
#MQTT_HOST = '192.168.1.10'
MQTT_PORT = 1883
TRIGGER_PIN = 16
ECHO_PIN = 17
LED_PIN = 15  # LED esterno su GP15 con resistenza: pilotaggio PIO indipendente dalla rete
SAMPLE_MS = 100
BLINK_MS = 250
