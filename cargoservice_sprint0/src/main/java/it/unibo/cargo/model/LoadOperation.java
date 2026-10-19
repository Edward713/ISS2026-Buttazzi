package it.unibo.cargo.model;

import java.util.Optional;
import java.util.OptionalLong;

/** Dati concettuali del carico; nessun timer o protocollo di movimento implementato. */
public record LoadOperation(String id, int slotId, Phase phase,
                            OptionalLong arrivalDeadlineMillis, Optional<Movement> movement) {
    public enum Phase { DISENGAGED, WAIT_CONTAINER, TO_SLOT5, WAIT_MARKER, TO_FINAL }
    public enum NavigationState { IDLE, MOVING, ARRIVED, FAILED }

    /** Il target e l'esito della navigazione non costituiscono una conferma di deposito. */
    public record Movement(Target target, NavigationState state) {
        public Movement {
            if (target == null || state == null) throw new IllegalArgumentException("Missing movement data");
        }
    }

    public LoadOperation {
        if (id == null || id.isBlank()) throw new IllegalArgumentException("Empty operation ID");
        if (slotId < 1 || slotId > 4) throw new IllegalArgumentException("Storage slot must be 1..4");
        if (phase == null) throw new IllegalArgumentException("Missing phase");
        if (arrivalDeadlineMillis == null || movement == null)
            throw new IllegalArgumentException("Missing optional operation data");
    }
}
