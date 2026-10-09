package it.unibo.cargo.model;

import java.util.Set;

/** Area e punto di accesso di una destinazione logica, come nel contratto di Sprint0. */
public interface Destination {
    Set<Position> area();
    Position accessPoint();
}
