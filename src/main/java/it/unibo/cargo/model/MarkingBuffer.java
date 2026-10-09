package it.unibo.cargo.model;
import java.util.Optional;
/** Slot5 is never part of HoldInventory. Used by the later deposit protocol. */
public final class MarkingBuffer {
    private String container;
    public Optional<String> containerId() { return Optional.ofNullable(container); }
    public void confirmDeposit(String id) {
        if (id == null || id.isBlank()) throw new IllegalArgumentException("Empty container ID");
        if (container != null) throw new IllegalStateException("Marking buffer occupied");
        container = id;
    }
    public String confirmCollection() {
        if (container == null) throw new IllegalStateException("Marking buffer empty");
        String id=container; container=null; return id;
    }
}
