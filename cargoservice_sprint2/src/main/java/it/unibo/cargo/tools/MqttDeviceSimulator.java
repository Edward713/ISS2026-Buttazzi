package it.unibo.cargo.tools;

import it.unibo.cargo.model.CargoConfig;
import java.nio.charset.StandardCharsets;
import java.util.UUID;
import org.eclipse.paho.client.mqttv3.*;
import org.eclipse.paho.client.mqttv3.persist.MemoryPersistence;
import org.json.JSONObject;

/** Ogni elemento e distanza:millisecondi; silent e invalid esercitano A3/A4. */
public final class MqttDeviceSimulator {
    public static void main(String[] args) throws Exception {
        String session = "sim_" + UUID.randomUUID().toString().replace("-", "");
        long seq = 0;
        try (MqttClient client = new MqttClient(CargoConfig.broker(), session, new MemoryPersistence())) {
            client.setCallback(new MqttCallback() {
                public void connectionLost(Throwable cause) { System.err.println(cause); }
                public void deliveryComplete(IMqttDeliveryToken token) { }
                public void messageArrived(String topic, MqttMessage message) { System.out.println("LED " + message); }
            });
            client.connect(); client.subscribe("cargo/picow/led/set", 1);
            for (String step : args[0].split(",")) {
                String[] fields = step.split(":");
                long end = System.nanoTime() + Long.parseLong(fields[1]) * 1_000_000;
                do {
                    if (!fields[0].equals("silent")) {
                        boolean valid = !fields[0].equals("invalid");
                        JSONObject p = new JSONObject().put("session", session).put("seq", seq++)
                            .put("distance", valid ? Double.parseDouble(fields[0]) : -1).put("valid", valid);
                        client.publish("cargo/picow/sonar", p.toString().getBytes(StandardCharsets.UTF_8), 0, false);
                    }
                    Thread.sleep(100);
                } while (System.nanoTime() < end);
            }
            client.disconnect();
        }
    }
}
