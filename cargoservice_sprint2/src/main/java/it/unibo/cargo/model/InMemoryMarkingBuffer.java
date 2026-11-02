package it.unibo.cargo.model;

import java.util.Optional;

public final class InMemoryMarkingBuffer implements MarkingBuffer {
    private String container;
    public Optional<String> containerId() { return Optional.ofNullable(container); }
    public void confirmDeposit(String id) {
        if (id == null || id.isBlank()) throw new IllegalArgumentException("Empty container ID");
        if (container != null) throw new IllegalStateException("Marking buffer occupied");
        container = id;
    }
    public String confirmCollection() {
        if (container == null) throw new IllegalStateException("Marking buffer empty");
        String id = container;
        container = null;
        return id;
    }
    public void applyBarcode(String barcode) {
        if (container == null) throw new IllegalStateException("Marking buffer empty");
        if (barcode == null || barcode.isBlank()) throw new IllegalArgumentException("Empty barcode");
        container = barcode;
    }
}
