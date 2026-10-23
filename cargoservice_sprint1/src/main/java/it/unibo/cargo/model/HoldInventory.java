package it.unibo.cargo.model;

import java.util.Optional;
import java.util.OptionalInt;

/** Inventario dei soli slot finali 1..4, modificato da cargoservice. */
public interface HoldInventory {
    SlotState stateOf(int slotId);
    OptionalInt reserveFirstAvailable();
    void releaseReservation(int slotId);
    void confirmDeposit(int slotId, String containerId);
    Optional<String> containerId(int slotId);
}
