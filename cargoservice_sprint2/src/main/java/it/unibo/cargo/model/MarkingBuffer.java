package it.unibo.cargo.model;

import java.util.Optional;

public interface MarkingBuffer {
    Optional<String> containerId();
    void confirmDeposit(String containerId);
    String confirmCollection();
}
