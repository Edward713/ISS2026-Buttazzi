package it.unibo.cargo;

import it.unibo.cargo.model.*;
import org.junit.Test;
import static org.junit.Assert.*;

public class DomainModelTest {
    @Test public void reserveReleaseDepositAndBarcode() {
        HoldInventory inventory = new InMemoryHoldInventory();
        assertEquals(1, inventory.reserveFirstAvailable().orElseThrow());
        inventory.confirmDeposit(1, "BC_1");
        assertEquals(2, inventory.reserveFirstAvailable().orElseThrow());
        inventory.releaseReservation(2);
        assertEquals(2, inventory.reserveFirstAvailable().orElseThrow());
        assertEquals(SlotState.OCCUPIED, inventory.stateOf(1));
        assertEquals("BC_1", inventory.containerId(1).orElseThrow());
    }
    @Test public void fullHoldDoesNotOccupyMarkingBuffer() {
        HoldInventory inventory = new InMemoryHoldInventory();
        for (int i = 1; i <= 4; i++) inventory.confirmDeposit(inventory.reserveFirstAvailable().orElseThrow(), "BC_" + i);
        assertTrue(inventory.reserveFirstAvailable().isEmpty());
        MarkingBuffer buffer = new InMemoryMarkingBuffer();
        buffer.confirmDeposit("load1");
        assertEquals("load1", buffer.confirmCollection());
        assertTrue(buffer.containerId().isEmpty());
    }
    @Test(expected = IllegalStateException.class) public void depositRequiresReservation() {
        new InMemoryHoldInventory().confirmDeposit(1, "barcode");
    }
    @Test(expected = IllegalArgumentException.class) public void slot5IsNotFinalStorage() {
        new InMemoryHoldInventory().stateOf(5);
    }
    @Test public void sonarThresholdContinuityAndOneNotification() {
        var detector = new PresenceDetector(100, 3000, 1000);
        for (int time = 0; time < 3000; time += 500) assertEquals("", detector.sample(40, time));
        assertEquals("present", detector.sample(40, 3000));
        assertEquals("", detector.sample(40, 3500));
        assertEquals("free", detector.sample(50, 4000));
        for (int time = 4500; time < 7500; time += 500) assertEquals("", detector.sample(40, time));
        assertEquals("present", detector.sample(40, 7500));
    }
    @Test public void silenceAndInvalidSamplesCannotConfirmPresence() {
        var detector = new PresenceDetector(100, 3000, 1000);
        assertEquals("", detector.sample(40, 0));
        assertEquals("", detector.sample(40, 3000));
        assertFalse(detector.present());
        detector.sample(Double.NaN, 3100);
        detector.sample(-1, 3200);
        for (int time = 3300; time < 6300; time += 500) assertEquals("", detector.sample(40, time));
        assertEquals("present", detector.sample(40, 6300));
    }
    @Test public void deadlineDoesNotMoveAndStaleTimersCannotReleaseNextLoad() {
        var state = new CargoState();
        assertTrue(state.accept(1000, 30000));
        String first = state.operation().id();
        assertFalse(state.accept(2000, 30000));
        assertEquals(31000, state.operation().arrivalDeadlineMillis());
        assertFalse(state.confirmPresence(31001));
        assertTrue(state.expire(first, 31001));
        state.sensor("free");
        assertTrue(state.accept(32000, 30000));
        assertFalse(state.expire(first, 100000));
        assertEquals(LoadOperation.Phase.WAIT_CONTAINER, state.phase());
    }
    @Test public void failurePreservesReservationAndRequiresTestMaintenance() {
        var state = new CargoState();
        state.accept(0, 30000);
        state.confirmPresence(3000);
        state.fail("navigation_failed_ioport");
        assertFalse(state.canAccept());
        assertTrue(state.snapshot().contains("RESERVED"));
        assertEquals("busy", state.setup("empty", false));
        assertEquals("ok", state.setup("empty", true));
        assertEquals(ServiceStatus.WORKING, state.status());
    }
    @Test public void inventorySetupCannotClearAnOccupiedPortInProduction() {
        var state = new CargoState();
        state.sensor("present");
        assertEquals("ok", state.setup("empty", false));
        assertFalse(state.canAccept());
        state.sensor("free");
        assertTrue(state.canAccept());
    }
}
