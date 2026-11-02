package it.unibo.cargo.tools;

import it.unibo.cargo.model.CargoConfig;
import java.nio.charset.StandardCharsets;
import java.util.UUID;
import java.util.function.Consumer;
import org.eclipse.paho.client.mqttv3.*;
import org.eclipse.paho.client.mqttv3.persist.MemoryPersistence;
import org.json.JSONObject;

/** Confine MQTT: callback brevi, riconnessione anche se il broker non e disponibile all'avvio. */
public final class MqttSensorLink {
    private volatile String led = "off";
    private volatile boolean publishLed = true;
    private volatile boolean connected;
    public boolean connected() { return connected; }
    public void led(String mode) { led = mode; publishLed = true; }
    public void start(Consumer<String> samples) {
        Thread worker = new Thread(() -> {
            while (!Thread.currentThread().isInterrupted()) {
                try (MqttClient client = new MqttClient(CargoConfig.broker(), "cargo-sensor-" + UUID.randomUUID(), new MemoryPersistence())) {
                    client.setCallback(new MqttCallback() {
                        public void connectionLost(Throwable cause) { connected = false; samples.accept("{}"); }
                        public void deliveryComplete(IMqttDeliveryToken token) { }
                        public void messageArrived(String topic, MqttMessage message) {
                            if (message.isRetained()) return;
                            try {
                                JSONObject p = new JSONObject(new String(message.getPayload(), StandardCharsets.UTF_8));
                                // Canonicalizza il payload prima di introdurlo in un termine Prolog.
                                String session = p.getString("session");
                                if (!session.matches("[A-Za-z0-9_:-]{1,100}") || p.getDouble("seq") != p.getLong("seq")) throw new IllegalArgumentException();
                                samples.accept(new JSONObject().put("session", session).put("seq", p.getLong("seq"))
                                    .put("valid", p.getBoolean("valid")).put("distance", p.optDouble("distance", -1)).toString());
                            } catch (RuntimeException ex) { samples.accept("{}"); }
                        }
                    });
                    MqttConnectOptions options = new MqttConnectOptions();
                    options.setCleanSession(true); options.setConnectionTimeout(3); options.setKeepAliveInterval(5);
                    client.connect(options);
                    samples.accept("{}");
                    client.subscribe("cargo/picow/sonar", 0);
                    connected = true;
                    publishLed = true;
                    while (client.isConnected()) {
                        if (publishLed) {
                            publishLed = false;
                            client.publish("cargo/picow/led/set", ("{\"mode\":\"" + led + "\"}").getBytes(StandardCharsets.UTF_8), 1, true);
                        }
                        Thread.sleep(50);
                    }
                } catch (Exception ex) {
                    connected = false;
                    samples.accept("{}");
                    System.err.println("[MQTT] " + ex.getMessage());
                }
                try { Thread.sleep(1000); } catch (InterruptedException stop) { Thread.currentThread().interrupt(); }
            }
        }, "pico-mqtt");
        worker.setDaemon(true); worker.start();
    }
}
