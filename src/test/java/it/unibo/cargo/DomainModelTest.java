package it.unibo.cargo;

import it.unibo.cargo.model.*;
import org.junit.Test;
import static org.junit.Assert.*;

/** Verifiche dei soli vincoli del modello; i test funzionali sono piani futuri. */
public class DomainModelTest {
    @Test public void firstFreeSlotIsReservedAndCanBeReleased() {
        var inventory = new HoldInventory();
        int first = inventory.reserveFirstAvailable().orElseThrow();
        inventory.confirmDeposit(first, "container1");
        int reserved = inventory.reserveFirstAvailable().orElseThrow();
        assertEquals(2, reserved);
        assertEquals(SlotState.OCCUPIED, inventory.stateOf(1));
        assertEquals(SlotState.RESERVED, inventory.stateOf(2));
        inventory.releaseReservation(reserved);
        assertEquals(2, inventory.reserveFirstAvailable().orElseThrow());
        assertEquals("container1", inventory.containerId(1).orElseThrow());
    }

    @Test public void slot5IsIndependentFromTheFourStorageSlots() {
        var inventory = new HoldInventory();
        for (int n = 0; n < 4; n++) {
            int slot = inventory.reserveFirstAvailable().orElseThrow();
            inventory.confirmDeposit(slot, "container" + slot);
        }
        assertTrue(inventory.reserveFirstAvailable().isEmpty());
        var buffer = new MarkingBuffer();
        buffer.confirmDeposit("temporary");
        assertEquals("temporary", buffer.confirmCollection());
        assertTrue(buffer.containerId().isEmpty());
        assertTrue(inventory.reserveFirstAvailable().isEmpty());
        // Compatibile anche con il JUnit incorporato nella libreria tuProlog.
        try {
            inventory.stateOf(5);
            fail("Slot5 must not be part of the final storage inventory");
        } catch (IllegalArgumentException expected) {
            // Il dominio ammette soltanto gli slot finali 1..4.
        }
        try {
            new HoldInventory().confirmDeposit(1, "unreserved");
            fail("Deposit must require a reservation");
        } catch (IllegalStateException expected) {
            // Non si puo depositare in uno slot non prenotato.
        }
    }

}
