package it.unibo.cargo.model;
/** Vista in sola lettura del layout; la mappa concreta sara definita negli sprint successivi. */
public interface Layout {
    int rows();
    int columns();
    boolean isTraversable(Position position);
    Destination destination(Target target);
}
