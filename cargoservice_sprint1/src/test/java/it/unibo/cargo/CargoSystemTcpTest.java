package it.unibo.cargo;

import it.unibo.cargo.tools.QakTcpClient;
import java.io.*;
import java.net.*;
import java.nio.file.*;
import java.util.*;
import java.util.function.Predicate;
import org.json.*;
import org.junit.*;
import org.junit.runners.MethodSorters;
import static org.junit.Assert.*;

/** T1--T7 del documento, sui quattro contesti QAK reali collegati via TCP. */
@FixMethodOrder(MethodSorters.NAME_ASCENDING)
public class CargoSystemTcpTest {
    static int testPort(int port) { return port + Integer.getInteger("cargo.testPortOffset", 10000); }
    private static final List<Process> PROCESSES = new ArrayList<>();
    static {
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            for (Process process : PROCESSES) process.destroy();
        }, "cargo-test-cleanup"));
    }
    private QakTcpClient cargo, robot, sensor, ioport;

    @BeforeClass public static void startContexts() throws Exception {
        startContexts(true);
    }
    static void startContexts(boolean mockRobot) throws Exception {
        if (Boolean.getBoolean("cargo.externalTests")) return;
        for (int port = 8020; port <= 8023; port++) {
            try (ServerSocket probe = new ServerSocket()) {
                probe.bind(new InetSocketAddress("127.0.0.1", testPort(port)));
            } catch (IOException occupied) {
                throw new IllegalStateException("Porta " + port + " occupata. Fermare i contesti manuali oppure usare -Pcargo.externalTests=true.", occupied);
            }
        }
        Path root = Path.of(System.getProperty("cargo.projectDir"));
        Path logs = root.resolve("build/test-contexts");
        Files.createDirectories(logs);
        String java = Path.of(System.getProperty("java.home"), "bin", "java.exe").toString();
        if (!Files.exists(Path.of(java))) java = Path.of(System.getProperty("java.home"), "bin", "java").toString();
        try {
            for (String ctx : List.of("ctxcargoservice", "ctxcargorobot", "ctxioport", "ctxsensor")) {
                ProcessBuilder builder = new ProcessBuilder(java,
                    "-Dcargo.testMode=true", "-Dcargo.mockRobot=" + mockRobot, "-Dcargo.markerMillis=1000",
                    "-Dcargo.navigationMillis=" + (mockRobot ? 120000 : 2000),
                    "-Dcargo.context=" + ctx,
                    "-Dcargo.portOffset=" + Integer.getInteger("cargo.testPortOffset", 10000),
                    "-cp", System.getProperty("cargo.testClasspath"), "it.unibo.cargo.MainContextKt", ctx);
                builder.directory(root.toFile()).redirectErrorStream(true).redirectOutput(logs.resolve(ctx + ".log").toFile());
                PROCESSES.add(builder.start());
            }
            for (int port = 8020; port <= 8023; port++) {
                long end = System.nanoTime() + 30_000_000_000L;
                boolean ready = false;
                while (System.nanoTime() < end) {
                    try (Socket socket = new Socket()) {
                        socket.connect(new InetSocketAddress("127.0.0.1", testPort(port)), 200);
                        ready = true;
                        break;
                    } catch (IOException notReady) { Thread.sleep(100); }
                }
                if (!ready) throw new IOException("Contesto sulla porta " + port + " non avviato. Consultare " + logs);
            }
        } catch (Exception ex) { stopContexts(); throw ex; }
    }
    @AfterClass public static void stopContexts() throws Exception {
        for (Process process : PROCESSES) process.destroy();
        for (Process process : PROCESSES) {
            if (!process.waitFor(5, java.util.concurrent.TimeUnit.SECONDS)) process.destroyForcibly();
        }
        PROCESSES.clear();
    }
    @Before public void connect() throws Exception {
        cargo = new QakTcpClient(testPort(8020), "cargoservice");
        robot = new QakTcpClient(testPort(8021), "cargorobot");
        ioport = new QakTcpClient(testPort(8022), "ioportservice");
        sensor = new QakTcpClient(testPort(8023), "sensorservice");
        // La porta TCP puo essere aperta prima del completamento dell'inizializzazione QAK.
        awaitState(s -> s.getString("phase").equals("DISENGAGED") || s.getString("serviceStatus").equals("OUT_OF_SERVICE"), 40000);
        preset("empty", "none", 350);
    }
    @After public void close() throws Exception {
        for (QakTcpClient client : new QakTcpClient[]{cargo, robot, ioport, sensor}) if (client != null) client.close();
    }
    private void preset(String mode, String failure, long delay) throws Exception {
        assertTrue(cargo.request("setup_hold", mode).contains("preset_ack(ok)"));
        assertTrue(robot.request("mock_control", failure + "," + delay).contains("mock_ack(ok)"));
        assertTrue(sensor.request("reset_sensor", "none").contains("sensor_reset(ok)"));
        // Barriera sul servizio: attende che il reset del sensore sia stato notificato.
        awaitState(s -> !s.getBoolean("ioportOccupied"), 3000);
    }
    private JSONObject state() throws Exception { return cargo.json("get_hold_status"); }
    private JSONObject slot(JSONObject state, int id) { return state.getJSONArray("slots").getJSONObject(id - 1); }
    private JSONObject awaitState(Predicate<JSONObject> condition, long millis) throws Exception {
        long end = System.nanoTime() + millis * 1_000_000;
        JSONObject last;
        do {
            last = state();
            if (condition.test(last)) return last;
            Thread.sleep(50);
        } while (System.nanoTime() < end);
        fail("Stato atteso non raggiunto: " + last);
        return last;
    }
    private JSONObject phase(String phase, long millis) throws Exception {
        return awaitState(s -> s.getString("phase").equals(phase), millis);
    }
    private void samples(double distance, long duration) throws Exception {
        long end = System.nanoTime() + duration * 1_000_000;
        do {
            sensor.send("sonar_sample", "event", Double.toString(distance));
            Thread.sleep(100);
        } while (System.nanoTime() < end);
    }
    private void finishCycle() throws Exception {
        samples(40, 3300);
        phase("DISENGAGED", 15000);
        samples(100, 150);
    }
    private void awaitLed(String led) throws Exception {
        long end = System.nanoTime() + 3_000_000_000L;
        do {
            if (sensor.json("get_sensor_status").getString("led").equals(led)) return;
            Thread.sleep(50);
        } while (System.nanoTime() < end);
        fail("LED atteso: " + led);
    }

    @Test public void t1_acceptsFirstAvailableSlotAndBlinks() throws Exception {
        preset("slot1_occupied", "none", 350);
        assertTrue(cargo.request("load_request", "none").contains("load_accepted(slot2)"));
        JSONObject state = phase("WAIT_CONTAINER", 2000);
        assertEquals("RESERVED", slot(state, 2).getString("state"));
        assertEquals(0, robot.json("get_robot_status").getJSONArray("history").length());
        awaitLed("blink");
        finishCycle();
    }
    @Test public void t2_busyAndOccupiedPortReturnRetrylater() throws Exception {
        samples(40, 3300);
        awaitState(s -> s.getBoolean("ioportOccupied"), 3000);
        assertTrue(cargo.request("load_request", "none").contains("retrylater(none)"));
        assertEquals("FREE", slot(state(), 1).getString("state"));
        samples(100, 200);
        awaitState(s -> !s.getBoolean("ioportOccupied"), 3000);
        assertTrue(cargo.request("load_request", "none").contains("load_accepted(slot1)"));
        JSONObject before = state();
        for (int i = 0; i < 5; i++) assertTrue(cargo.request("load_request", "none").contains("retrylater(none)"));
        JSONObject after = state();
        assertEquals(before.getJSONObject("operation").getString("id"), after.getJSONObject("operation").getString("id"));
        assertEquals(before.getJSONObject("operation").getLong("deadline"), after.getJSONObject("operation").getLong("deadline"));
        assertEquals("FREE", slot(after, 2).getString("state"));
        assertTrue(cargo.request("setup_hold", "full").contains("preset_ack(busy)"));
        samples(40, 3300);
        phase("TO_SLOT5", 3000);
        assertTrue(cargo.request("load_request", "none").contains("retrylater(none)"));
        phase("DISENGAGED", 15000);
    }
    @Test public void t3_fullHoldRefusesWithoutChangingState() throws Exception {
        preset("full", "none", 350);
        String before = state().getJSONArray("slots").toString();
        assertTrue(cargo.request("load_request", "none").contains("load_refused(none)"));
        JSONObject state = state();
        assertEquals(before, state.getJSONArray("slots").toString());
        assertEquals("DISENGAGED", state.getString("phase"));
    }
    @Test public void t4_navigationFailureOnEveryLegPreservesCargoAndLatchesOutOfService() throws Exception {
        for (String target : List.of("ioport", "slot5", "slot1", "home")) {
            preset("empty", target, 200);
            assertTrue(cargo.request("load_request", "none").contains("load_accepted(slot1)"));
            samples(40, 3300);
            JSONObject state = awaitState(s -> s.getString("serviceStatus").equals("OUT_OF_SERVICE"), 15000);
            assertEquals(target.equals("home") ? "OCCUPIED" : "RESERVED", slot(state, 1).getString("state"));
            if (target.equals("slot1")) assertFalse(state.getString("slot5").isEmpty());
            assertTrue(cargo.request("load_request", "none").contains("retrylater(none)"));
            awaitLed("off");
            long end = System.nanoTime() + 3_000_000_000L;
            while (!ioport.json("get_ioport_status").getString("display").equals("Out_of_service")) {
                assertTrue("Display OOS non aggiornato", System.nanoTime() < end);
                Thread.sleep(50);
            }
            assertEquals("OUT_OF_SERVICE", state().getString("serviceStatus"));
        }
    }
    @Test public void t5_realThirtySecondTimeoutIsNotRestartedByBusyRequests() throws Exception {
        assertTrue(cargo.request("load_request", "none").contains("load_accepted(slot1)"));
        long deadline = state().getJSONObject("operation").getLong("deadline");
        while (System.currentTimeMillis() < deadline - 200) {
            assertTrue(cargo.request("load_request", "none").contains("retrylater(none)"));
            Thread.sleep(700);
        }
        JSONObject state = phase("DISENGAGED", 3000);
        assertEquals("FREE", slot(state, 1).getString("state"));
        assertEquals(0, robot.json("get_robot_status").getJSONArray("history").length());
        awaitLed("off");
    }
    @Test public void t6_presenceMustRemainBelowThresholdForThreeContinuousSeconds() throws Exception {
        assertTrue(cargo.request("load_request", "none").contains("load_accepted(slot1)"));
        samples(40, 1700);
        samples(50, 200); // uguaglianza alla soglia: interrompe il conteggio
        samples(40, 1900);
        assertEquals("WAIT_CONTAINER", state().getString("phase"));
        assertEquals(0, robot.json("get_robot_status").getJSONArray("history").length());
        samples(40, 1400);
        JSONObject marking = phase("WAIT_MARKER", 4000);
        assertEquals("RESERVED", slot(marking, 1).getString("state"));
        assertFalse(marking.getString("slot5").isEmpty());
        assertEquals("[\"ioport\",\"slot5\"]", robot.json("get_robot_status").getJSONArray("history").toString());
        phase("DISENGAGED", 15000);
    }
    @Test public void t7_depositPublishesBarcodeBeforeHomeAndRemainsEngaged() throws Exception {
        preset("empty", "none", 1000);
        ioport.send("button_pressed", "dispatch", "none");
        phase("WAIT_CONTAINER", 3000);
        samples(40, 3300);
        JSONObject marking = phase("WAIT_MARKER", 4000);
        assertEquals("RESERVED", slot(marking, 1).getString("state"));
        JSONObject returning = phase("RETURN_HOME", 5000);
        String barcode = slot(returning, 1).getString("barcode");
        assertTrue(barcode.startsWith("BC_"));
        assertEquals("OCCUPIED", slot(returning, 1).getString("state"));
        assertEquals("", returning.getString("slot5"));
        assertTrue(cargo.request("load_request", "none").contains("retrylater(none)"));
        JSONObject shown;
        long displayDeadline = System.nanoTime() + 900_000_000L;
        do {
            shown = new JSONObject(ioport.json("get_ioport_status").getString("display"));
            if (shown.getString("phase").equals("RETURN_HOME")) break;
            Thread.sleep(25);
        } while (System.nanoTime() < displayDeadline);
        assertEquals("RETURN_HOME", shown.getString("phase"));
        assertEquals(barcode, slot(shown, 1).getString("barcode"));
        JSONObject done = phase("DISENGAGED", 4000);
        assertEquals(barcode, slot(done, 1).getString("barcode"));
        assertEquals("[\"ioport\",\"slot5\",\"slot1\",\"home\"]", robot.json("get_robot_status").getJSONArray("history").toString());
        awaitLed("off");
    }
}
