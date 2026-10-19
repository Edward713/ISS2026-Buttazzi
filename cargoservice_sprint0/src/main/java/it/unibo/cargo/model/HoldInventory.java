package it.unibo.cargo.model;
import java.util.*;
/** No coordinates or service state: only the four final storage slots. */
public final class HoldInventory {
    private final SlotState[] slots = {SlotState.FREE,SlotState.FREE,SlotState.FREE,SlotState.FREE};
    private final String[] containers = new String[4];
    private int index(int id) {
        if (id < 1 || id > 4) throw new IllegalArgumentException("Storage slot must be 1..4");
        return id-1;
    }
    public SlotState stateOf(int id) { return slots[index(id)]; }
    public OptionalInt reserveFirstAvailable() {
        for (int i=0;i<4;i++) if (slots[i] == SlotState.FREE) {
            slots[i] = SlotState.RESERVED; return OptionalInt.of(i+1);
        }
        return OptionalInt.empty();
    }
    public void releaseReservation(int id) {
        int i=index(id);
        if (slots[i] != SlotState.RESERVED) throw new IllegalStateException("Slot is not reserved");
        slots[i] = SlotState.FREE;
    }
    public void confirmDeposit(int id,String containerId) {
        int i=index(id);
        if (containerId == null || containerId.isBlank()) throw new IllegalArgumentException("Empty container ID");
        if (slots[i] != SlotState.RESERVED) throw new IllegalStateException("Deposit requires reservation");
        slots[i] = SlotState.OCCUPIED; containers[i] = containerId;
    }
    public Optional<String> containerId(int id) { return Optional.ofNullable(containers[index(id)]); }
    public Map<Integer,SlotState> snapshot() {
        var map=new LinkedHashMap<Integer,SlotState>();
        for(int id=1;id<=4;id++) map.put(id,stateOf(id));
        return Collections.unmodifiableMap(map);
    }
}
