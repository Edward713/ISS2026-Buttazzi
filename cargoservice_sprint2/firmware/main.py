
import asyncio
import binascii
import json
import machine
import network
import os
import rp2
import time
from umqtt.simple import MQTTClient
import config

led = machine.Pin(config.LED_PIN, machine.Pin.OUT, value=0)
trigger = machine.Pin(config.TRIGGER_PIN, machine.Pin.OUT, value=0)
echo = machine.Pin(config.ECHO_PIN, machine.Pin.IN)
mode = 'off'


@rp2.asm_pio(set_init=rp2.PIO.OUT_LOW)
def blink_program():
    wrap_target()
    set(pins, 1)
    set(x, 15)
    label('high')
    jmp(x_dec, 'high')[30]
    set(pins, 0)
    set(x, 15)
    label('low')
    jmp(x_dec, 'low')[30]
    wrap()

blinker = rp2.StateMachine(0, blink_program, freq=int(498000 / config.BLINK_MS), set_base=led)


def command(topic, payload):
    global mode
    try:
        value = json.loads(payload)['mode']
        if value in ('off', 'blink') and value != mode:
            mode = value  # idempotente: non riavvia il lampeggio per comandi QoS 1 duplicati
            if mode == 'off':
                blinker.active(0)
                blinker.exec('set(pins, 0)')
            else:
                blinker.active(1)
    except (ValueError, KeyError, TypeError):
        pass


def distance_cm():
    trigger.off()
    time.sleep_us(2)
    trigger.on()
    time.sleep_us(10)
    trigger.off()
    pulse = machine.time_pulse_us(echo, 1, 25000)
    return round(pulse / 58.0, 2) if pulse > 0 else None


async def acquire():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    while True:
        client = None
        try:
            if not wlan.isconnected():
                wlan.connect(config.WIFI_SSID, config.WIFI_PASSWORD)
                for _ in range(150):
                    if wlan.isconnected():
                        break
                    await asyncio.sleep_ms(100)
                if not wlan.isconnected():
                    raise OSError('Wi-Fi non disponibile')
            # Una nuova sessione anche alla riconnessione: nessuna continuita oltre una disconnessione.
            session = binascii.hexlify(os.urandom(12)).decode()
            print("Connessione Wi-Fi in corso...")
            client = MQTTClient(b'cargo-pico-' + binascii.hexlify(machine.unique_id()), config.MQTT_HOST,
                                port=config.MQTT_PORT, keepalive=10)
            client.set_callback(command)
            client.connect(clean_session=True)
            client.subscribe(b'cargo/picow/led/set', qos=1)
            seq = 0
            while wlan.isconnected():
                began = time.ticks_ms()
                client.check_msg()
                distance = distance_cm()
                payload = json.dumps({'session': session, 'seq': seq, 'distance': distance,
                                      'valid': distance is not None})
                client.publish(b'cargo/picow/sonar', payload.encode(), retain=False, qos=0)
                seq += 1
                if seq % 30 == 0:
                    client.ping()
                await asyncio.sleep_ms(max(1, config.SAMPLE_MS - time.ticks_diff(time.ticks_ms(), began)))
        except (OSError, ValueError) as ex:
            print('MQTT/Wi-Fi:', ex)
        finally:
            if client is not None:
                try:
                    client.sock.close()
                except OSError:
                    pass
        await asyncio.sleep_ms(1000)


async def main():
    await acquire()


try:
    asyncio.run(main())
finally:
    blinker.active(0)
    blinker.exec('set(pins, 0)')
