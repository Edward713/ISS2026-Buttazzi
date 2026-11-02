package it.unibo.cargo.model;
/** Vista in sola lettura del layout condiviso con la configurazione del navigatore. */
public interface Layout {
    int rows();
    int columns();
    boolean isTraversable(Position position);
    Destination destination(Target target);
}
