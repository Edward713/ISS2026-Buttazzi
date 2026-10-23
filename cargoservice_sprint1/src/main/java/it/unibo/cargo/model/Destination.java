package it.unibo.cargo.model;

import java.util.Set;

/** Area e punto di accesso di una destinazione logica della stiva. */
public interface Destination {
    Set<Position> area();
    Position accessPoint();
}
