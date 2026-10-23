package it.unibo.cargo.model;

import java.util.Arrays;
import java.util.Optional;
import java.util.OptionalInt;

public final class InMemoryHoldInventory implements HoldInventory {
    private final SlotState[] slots = new SlotState[4];
    private final String[] containers = new String[4];

    public InMemoryHoldInventory() { Arrays.fill(slots, SlotState.FREE); }
    private int index(int id) {
        if (id < 1 || id > 4) throw new IllegalArgumentException("Storage slot must be 1..4");
        return id - 1;
    }
    public SlotState stateOf(int id) { return slots[index(id)]; }
    public Optional<String> containerId(int id) { return Optional.ofNullable(containers[index(id)]); }
    public OptionalInt reserveFirstAvailable() {
        for (int i = 0; i < slots.length; i++) {
            if (slots[i] == SlotState.FREE) {
                slots[i] = SlotState.RESERVED;
                return OptionalInt.of(i + 1);
            }
        }
        return OptionalInt.empty();
    }
    public void releaseReservation(int id) {
        int i = index(id);
        if (slots[i] != SlotState.RESERVED) throw new IllegalStateException("Slot is not reserved");
        slots[i] = SlotState.FREE;
        containers[i] = null;
    }
    public void confirmDeposit(int id, String barcode) {
        int i = index(id);
        if (barcode == null || barcode.isBlank()) throw new IllegalArgumentException("Empty barcode");
        if (slots[i] != SlotState.RESERVED) throw new IllegalStateException("Deposit requires reservation");
        slots[i] = SlotState.OCCUPIED;
        containers[i] = barcode;
    }
}
