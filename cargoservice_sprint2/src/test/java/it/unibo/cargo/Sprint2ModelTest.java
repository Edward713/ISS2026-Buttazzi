package it.unibo.cargo;

import it.unibo.cargo.model.*;
import org.json.JSONObject;
import org.junit.Test;
import static org.junit.Assert.*;

public class Sprint2ModelTest {
    private SonarMonitor monitor() { return new SonarMonitor(100, 3000, 500, 2000); }
    private void stream(SonarMonitor m, double distance, int begin, int end) {
        for (int t = begin; t <= end; t += 100) m.sample(distance, t);
    }
    @Test public void strictThresholdsAndContinuousAnomaly() {
        var m = monitor();
        assertEquals("unavailable", m.drain());
        stream(m, 101, 0, 2900); assertEquals("unavailable", m.condition());
        m.sample(100, 3000); assertEquals("free", m.condition());
        stream(m, 101, 3100, 6000); assertEquals("unavailable", m.condition());
        m.sample(101, 6100); assertEquals("anomaly", m.drain());
        m.sample(101, 6200); assertEquals("", m.drain());
        m.sample(50, 6300); assertEquals("free", m.condition());
        stream(m, 49, 6400, 9300); assertEquals("unavailable", m.condition());
        m.sample(49, 9400); assertEquals("present", m.condition());
    }
    @Test public void silenceInvalidValuesAndGapsNeverCompleteCandidates() {
        var m = monitor();
        stream(m, 40, 0, 2000);
        m.tick(4500); assertEquals("unavailable", m.condition());
        stream(m, 40, 4600, 6500); assertEquals("unavailable", m.condition());
        m.sample(Double.NaN, 6600);
        stream(m, 40, 6700, 9600); assertEquals("unavailable", m.condition());
        m.sample(40, 9700); assertEquals("present", m.condition());
        m.sample(40, 10300); assertEquals("unavailable", m.condition());
        m.sample(-1, 10400); assertEquals("unavailable", m.condition());
        m.sample(100, 10500); assertEquals("free", m.condition());
        m.tick(12500); assertEquals("free", m.condition());
        m.tick(12501); assertEquals("unavailable", m.condition());
    }
    private String packet(String session, int seq, double d) {
        return new JSONObject().put("session", session).put("seq", seq).put("distance", d).put("valid", true).toString();
    }
    @Test public void duplicatesOutOfOrderAndOldSessionsCannotConfirmOrRefresh() {
        var m = monitor();
        m.packet(packet("s1", 0, 40), 0);
        for (int t = 100; t <= 3000; t += 100) m.packet(packet("s1", 0, 40), t);
        m.tick(3000); assertEquals("unavailable", m.condition());
        for (int t = 3100; t <= 6100; t += 100) m.packet(packet("s1", t, 40), t);
        assertEquals("present", m.condition());
        m.packet(packet("s2", 0, 40), 6200); assertEquals("unavailable", m.condition());
        m.packet(packet("s1", 99999, 100), 6300); assertEquals("unavailable", m.condition());
        m.packet(packet("s2", 1, 100), 6400); assertEquals("free", m.condition());
        m.packet("{}", 6500); assertEquals("unavailable", m.condition());
    }
    @Test public void startupUnavailableRecoversButAnomalyIsLatchedAndTimersAreInert() {
        var c = new CargoState();
        assertFalse(c.canAccept()); c.sensor("free"); assertTrue(c.canAccept());
        c.unavailable(); assertFalse(c.canAccept()); assertEquals(ServiceStatus.WORKING, c.status());
        c.sensor("free"); assertTrue(c.accept(0, 30000));
        String id = c.operation().id(); c.sensor("anomaly");
        assertFalse(c.engaged()); assertFalse(c.expire(id, 40000));
        assertFalse(c.finishMarking(id)); assertFalse(c.confirmPresence(3000));
        c.sensor("free"); assertFalse(c.canAccept());
        assertEquals("RESERVED", new JSONObject(c.snapshot()).getJSONArray("slots").getJSONObject(0).getString("state"));
    }
    @Test public void anomalyAtEveryLegCompletesOnlyThatLegAndPreservesEffects() {
        for (String leg : new String[]{"ioport", "slot5", "slot1", "home"}) {
            var c = new CargoState(); c.sensor("free"); assertTrue(c.accept(0, 30000));
            assertTrue(c.confirmPresence(3000));
            if (!leg.equals("ioport")) c.arrive("ioport");
            if (leg.equals("slot1") || leg.equals("home")) {
                c.arrive("slot5"); c.finishMarking(c.operation().id());
            }
            if (leg.equals("home")) c.arrive("slot1");
            c.sensor("anomaly"); assertTrue(c.engaged()); assertTrue(c.expects(leg));
            c.arrive(leg); assertFalse(c.engaged());
            assertEquals(LoadOperation.Phase.SUSPENDED, c.phase()); assertFalse(c.expects(leg));
            JSONObject state = new JSONObject(c.snapshot());
            assertEquals(leg.equals("slot1") || leg.equals("home") ? "OCCUPIED" : "RESERVED",
                state.getJSONArray("slots").getJSONObject(0).getString("state"));
            assertEquals(leg.equals("slot5"), !state.getString("slot5").isEmpty());
            assertFalse(c.finishMarking(c.operation().id()));
        }
    }
}
