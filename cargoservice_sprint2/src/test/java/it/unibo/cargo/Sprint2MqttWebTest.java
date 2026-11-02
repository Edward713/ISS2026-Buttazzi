package it.unibo.cargo;

import it.unibo.cargo.tools.QakTcpClient;
import java.net.*;
import java.net.http.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.time.Duration;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.function.Predicate;
import org.eclipse.paho.client.mqttv3.*;
import org.eclipse.paho.client.mqttv3.persist.MemoryPersistence;
import org.json.*;
import org.junit.*;
import static org.junit.Assert.*;

/** Richiede un broker vero: -Pcargo.mqttTests=true -Pcargo.mqtt=tcp://127.0.0.1:18883. */
public class Sprint2MqttWebTest {
    private Process web;
    private MqttClient device;
    private final ScheduledExecutorService publisher = Executors.newSingleThreadScheduledExecutor();
    private final AtomicReference<String> reading = new AtomicReference<>("100");
    private final AtomicInteger seq = new AtomicInteger();
    private final BlockingQueue<String> leds = new LinkedBlockingQueue<>();
    private final String session = "test_" + UUID.randomUUID().toString().replace("-", "");
    private final HttpClient http = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(3)).build();
    private QakTcpClient cargo, robot, sensor;
    private static final int WEB_PORT = 18080;
    @BeforeClass public static void contexts() throws Exception {
        Assume.assumeTrue(Boolean.getBoolean("cargo.mqttTests"));
        try (MqttClient retained = new MqttClient(System.getProperty("cargo.mqtt"), "retained-fixture", new MemoryPersistence())) {
            retained.connect();
            try {
                retained.publish("cargo/picow/sonar", "{\"session\":\"old\",\"seq\":0,\"distance\":100,\"valid\":true}".getBytes(StandardCharsets.UTF_8), 0, true);
                CargoSystemTcpTest.startContexts(true, true);
                try (var sensor = new QakTcpClient(CargoSystemTcpTest.testPort(8023), "sensorservice");
                     var cargo = new QakTcpClient(CargoSystemTcpTest.testPort(8020), "cargoservice")) {
                    long end = System.nanoTime() + TimeUnit.SECONDS.toNanos(10);
                    while (!sensor.json("get_sensor_status").getBoolean("mqttConnected")) {
                        assertTrue("MQTT non collegato", System.nanoTime() < end); Thread.sleep(50);
                    }
                    Thread.sleep(300);
                    assertFalse("Il campione retained non e una nuova misura", cargo.json("get_hold_status").getBoolean("sensorAvailable"));
                }
            } finally { retained.publish("cargo/picow/sonar", new byte[0], 0, true); retained.disconnect(); }
        }
    }
    @AfterClass public static void stopContexts() throws Exception { CargoSystemTcpTest.stopContexts(); }
    @Before public void setup() throws Exception {
        cargo = new QakTcpClient(CargoSystemTcpTest.testPort(8020), "cargoservice");
        robot = new QakTcpClient(CargoSystemTcpTest.testPort(8021), "cargorobot");
        sensor = new QakTcpClient(CargoSystemTcpTest.testPort(8023), "sensorservice");
        cargo.json("get_hold_status");
        assertTrue(cargo.request("setup_hold", "empty").contains("preset_ack(ok)"));
        robot.request("mock_control", "none,350");
        sensor.request("reset_sensor", "none");
        device = new MqttClient(System.getProperty("cargo.mqtt"), session, new MemoryPersistence());
        device.setCallback(new MqttCallback() {
            public void connectionLost(Throwable cause) { }
            public void deliveryComplete(IMqttDeliveryToken token) { }
            public void messageArrived(String topic, MqttMessage message) { leds.add(new JSONObject(message.toString()).getString("mode")); }
        });
        device.connect(); device.subscribe("cargo/picow/led/set", 1);
        publisher.scheduleAtFixedRate(() -> {
            String value = reading.get();
            if (value.equals("silent")) return;
            try {
                JSONObject sample = new JSONObject().put("session", session).put("seq", seq.incrementAndGet())
                    .put("distance", value.equals("invalid") ? -1 : Double.parseDouble(value)).put("valid", !value.equals("invalid"));
                device.publish("cargo/picow/sonar", sample.toString().getBytes(StandardCharsets.UTF_8), 0, false);
            } catch (Exception ex) { throw new RuntimeException(ex); }
        }, 0, 100, TimeUnit.MILLISECONDS);
        await(s -> s.getBoolean("sensorAvailable"), 10000);
        Path root = Path.of(System.getProperty("cargo.projectDir"));
        web = new ProcessBuilder("python", "-u", "web/server.py", "--port", Integer.toString(WEB_PORT), "--qak-port", Integer.toString(CargoSystemTcpTest.testPort(8022)))
            .directory(root.toFile()).redirectErrorStream(true).redirectOutput(root.resolve("build/test-contexts/web.log").toFile()).start();
        long end = System.nanoTime() + TimeUnit.SECONDS.toNanos(10);
        while (true) {
            try { if (get("/api/state").statusCode() == 200) break; } catch (Exception notReady) { }
            if (System.nanoTime() > end) fail("Web adapter non avviato");
            Thread.sleep(100);
        }
    }
    @After public void close() throws Exception {
        publisher.shutdownNow(); publisher.awaitTermination(2, TimeUnit.SECONDS);
        if (device != null) { if (device.isConnected()) device.disconnect(); device.close(); }
        if (web != null) { web.destroy(); web.waitFor(5, TimeUnit.SECONDS); }
        for (QakTcpClient client : new QakTcpClient[]{cargo, robot, sensor}) if (client != null) client.close();
    }
    private URI uri(String path) { return URI.create("http://127.0.0.1:" + WEB_PORT + path); }
    private HttpResponse<String> get(String path) throws Exception {
        return http.send(HttpRequest.newBuilder(uri(path)).timeout(Duration.ofSeconds(12)).build(), HttpResponse.BodyHandlers.ofString());
    }
    private JSONObject load() throws Exception {
        var result = http.send(HttpRequest.newBuilder(uri("/api/load")).timeout(Duration.ofSeconds(12)).POST(HttpRequest.BodyPublishers.noBody()).build(), HttpResponse.BodyHandlers.ofString());
        assertEquals(result.body(), 200, result.statusCode()); return new JSONObject(result.body());
    }
    private JSONObject await(Predicate<JSONObject> condition, long millis) throws Exception {
        long end = System.nanoTime() + millis * 1_000_000;
        JSONObject last;
        do { last = cargo.json("get_hold_status"); if (condition.test(last)) return last; Thread.sleep(50); }
        while (System.nanoTime() < end);
        throw new AssertionError("Stato atteso assente: " + last);
    }
    private void led(String expected) throws Exception {
        long end = System.nanoTime() + TimeUnit.SECONDS.toNanos(5);
        while (System.nanoTime() < end) if (expected.equals(leds.poll(200, TimeUnit.MILLISECONDS))) return;
        fail("Comando LED MQTT non ricevuto: " + expected);
    }
    @Test public void guiWebSocketConcurrentRequestsAndFullCycleUseRealMqtt() throws Exception {
        assertTrue(get("/").body().contains("Richiedi un carico"));
        var states = new LinkedBlockingQueue<String>();
        WebSocket ws = http.newWebSocketBuilder().buildAsync(URI.create("ws://127.0.0.1:" + WEB_PORT + "/ws/state"), new WebSocket.Listener() {
            private final StringBuilder buffer = new StringBuilder();
            public void onOpen(WebSocket socket) { socket.request(1); }
            public CompletionStage<?> onText(WebSocket socket, CharSequence data, boolean last) {
                buffer.append(data);
                if (last) { states.add(buffer.toString()); buffer.setLength(0); }
                socket.request(1); return null;
            }
        }).get(5, TimeUnit.SECONDS);
        assertNotNull(states.poll(5, TimeUnit.SECONDS));
        List<CompletableFuture<HttpResponse<String>>> requests = new ArrayList<>();
        for (int i = 0; i < 6; i++) requests.add(http.sendAsync(HttpRequest.newBuilder(uri("/api/load")).POST(HttpRequest.BodyPublishers.noBody()).build(), HttpResponse.BodyHandlers.ofString()));
        int accepted = 0;
        for (var request : requests) {
            var response = request.get(12, TimeUnit.SECONDS); assertEquals(response.body(), 200, response.statusCode());
            String result = new JSONObject(response.body()).getString("response");
            if (result.equals("load_accepted")) accepted++; else assertEquals("retrylater", result);
        }
        assertEquals(1, accepted); led("blink");
        reading.set("40");
        await(s -> s.getString("phase").equals("RETURN_HOME"), 12000);
        assertEquals("blink", sensor.json("get_sensor_status").getString("led"));
        JSONObject done = await(s -> s.getString("phase").equals("DISENGAGED"), 5000);
        assertEquals("OCCUPIED", done.getJSONArray("slots").getJSONObject(0).getString("state"));
        led("off"); reading.set("100");
        ws.sendClose(WebSocket.NORMAL_CLOSURE, "done").get(5, TimeUnit.SECONDS);
        JSONObject fresh = new JSONObject(get("/api/state").body());
        assertEquals(done.getJSONArray("slots").toString(), fresh.getJSONArray("slots").toString());
        assertEquals("[\"ioport\",\"slot5\",\"slot1\",\"home\"]", robot.json("get_robot_status").getJSONArray("history").toString());
    }
    @Test public void unavailableRecoversAndDistanceAnomalyLatches() throws Exception {
        reading.set("silent");
        await(s -> !s.getBoolean("sensorAvailable"), 5000);
        assertEquals("retrylater", load().getString("response"));
        assertEquals("WORKING", cargo.json("get_hold_status").getString("serviceStatus"));
        reading.set("100"); await(s -> s.getBoolean("sensorAvailable"), 3000);
        reading.set("invalid"); await(s -> !s.getBoolean("sensorAvailable"), 3000);
        reading.set("110"); await(s -> s.getString("serviceStatus").equals("OUT_OF_SERVICE"), 6000);
        reading.set("100"); Thread.sleep(300);
        assertEquals("retrylater", load().getString("response"));
        assertEquals("OUT_OF_SERVICE", new JSONObject(get("/api/state").body()).getString("serviceStatus"));
    }
    @Test public void anomalyDuringLegKeepsLedUntilArrivalAndStartsNoFurtherLeg() throws Exception {
        robot.request("mock_control", "none,5000");
        assertEquals("load_accepted", load().getString("response"));
        reading.set("40"); await(s -> s.getString("phase").equals("TO_IOPORT"), 6000);
        led("blink"); reading.set("110");
        JSONObject moving = await(s -> s.getString("serviceStatus").equals("OUT_OF_SERVICE"), 4500);
        assertTrue(moving.getBoolean("engaged"));
        assertEquals("blink", sensor.json("get_sensor_status").getString("led"));
        assertEquals("retrylater", load().getString("response"));
        JSONObject stopped = await(s -> s.getString("phase").equals("SUSPENDED"), 4000);
        assertFalse(stopped.getBoolean("engaged")); led("off");
        assertEquals("RESERVED", stopped.getJSONArray("slots").getJSONObject(0).getString("state"));
        Thread.sleep(400);
        assertEquals("[\"ioport\"]", robot.json("get_robot_status").getJSONArray("history").toString());
    }
}
