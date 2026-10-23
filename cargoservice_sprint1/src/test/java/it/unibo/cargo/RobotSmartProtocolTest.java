package it.unibo.cargo;

import alice.tuprolog.Struct;
import alice.tuprolog.Term;
import it.unibo.cargo.model.*;
import it.unibo.cargo.tools.QakTcpClient;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;
import org.junit.*;
import static org.junit.Assert.*;

/** Esercita il ramo reale dell'adattatore contro un peer TCP col protocollo RobotSmart26. */
public class RobotSmartProtocolTest {
    private static ServerSocket server;
    private static final ExecutorService WORKERS = Executors.newCachedThreadPool();
    private static final List<Socket> CONNECTIONS = new CopyOnWriteArrayList<>();
    private static final BlockingQueue<String> REQUESTS = new LinkedBlockingQueue<>();
    private static volatile String outcome = "done";

    @BeforeClass public static void start() throws Exception {
        Assume.assumeFalse("Prova protocollo isolata solo sui contesti autoavviati", Boolean.getBoolean("cargo.externalTests"));
        server = new ServerSocket();
        server.bind(new InetSocketAddress("127.0.0.1", CargoSystemTcpTest.testPort(8019)));
        WORKERS.submit(() -> {
            try {
                while (!server.isClosed()) {
                    Socket socket = server.accept();
                    CONNECTIONS.add(socket);
                    WORKERS.submit(() -> serve(socket));
                }
            } catch (IOException closed) { if (!server.isClosed()) throw new UncheckedIOException(closed); }
        });
        CargoSystemTcpTest.startContexts(false);
    }
    private static void serve(Socket socket) {
        try (socket;
             var reader = new BufferedReader(new InputStreamReader(socket.getInputStream(), StandardCharsets.UTF_8));
             var writer = new BufferedWriter(new OutputStreamWriter(socket.getOutputStream(), StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                Struct message = (Struct) Term.createTerm(line);
                if (!message.getArg(0).toString().equals("moverobot")) continue;
                REQUESTS.add(message.getArg(4).toString().replace(" ", ""));
                String result = outcome;
                if (result.equals("silent")) continue;
                String id = result.equals("done") ? "moverobotdone" : result.equals("failed") ? "failed" : "moverobotfailed";
                String body = result.equals("done") ? "moverobotok(ok)" : result.equals("failed") ? "failed(obstacle)" : "moverobotfailed([],[])";
                writer.write("msg(" + id + ",reply,robotsmart,cargorobot," + body + "," + message.getArg(5) + ")\n");
                writer.flush();
            }
        } catch (IOException closed) {
            if (!server.isClosed()) throw new UncheckedIOException(closed);
        }
    }
    @AfterClass public static void stop() throws Exception {
        CargoSystemTcpTest.stopContexts();
        if (server != null) server.close();
        for (Socket socket : CONNECTIONS) socket.close();
        WORKERS.shutdownNow();
    }
    @Test public void logicalTargetsUseConfiguredCoordinatesAndDecodeAllNavigationOutcomes() throws Exception {
        var layout = new CargoLayout();
        try (var robot = new QakTcpClient(CargoSystemTcpTest.testPort(8021), "cargorobot")) {
            // Barriera di inizializzazione prima della prima navigazione.
            robot.json("get_robot_status");
            for (Target target : Target.values()) {
                outcome = "done";
                String name = target.name().toLowerCase(Locale.ROOT);
                assertTrue(robot.request("reach_target", name).contains("target_reached(" + name + ")"));
                Position access = layout.destination(target).accessPoint();
                assertEquals("moverobot(" + access.row() + "," + access.column() + ",335)", REQUESTS.poll(3, TimeUnit.SECONDS));
            }
            assertEquals(new Position(4, 0), layout.destination(Target.IOPORT).accessPoint());
            for (String result : List.of("obstacle", "failed", "silent")) {
                outcome = result;
                assertTrue(result, robot.request("reach_target", "slot5").contains("target_failed(slot5)"));
                assertEquals("moverobot(2,5,335)", REQUESTS.poll(3, TimeUnit.SECONDS));
            }
            outcome = "done";
            assertTrue(robot.request("reach_target", "unknown").contains("target_failed(unknown)"));
            assertNull(REQUESTS.poll(100, TimeUnit.MILLISECONDS));
        }
    }
}
