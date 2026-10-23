package it.unibo.cargo.model;

/** Dati del carico corrente. Nessun accesso condiviso fra attori. */
public final class LoadOperation {
    public enum Phase { DISENGAGED, WAIT_CONTAINER, TO_IOPORT, TO_SLOT5, WAIT_MARKER, TO_FINAL, RETURN_HOME }
    public enum NavigationState { IDLE, MOVING, ARRIVED, FAILED }
    private final String id;
    private final int slotId;
    private final long arrivalDeadlineMillis;
    private Phase phase = Phase.WAIT_CONTAINER;
    private NavigationState navigationState = NavigationState.IDLE;
    private Target target;
    private String barcode;

    public LoadOperation(String id, int slotId, long arrivalDeadlineMillis) {
        if (id == null || id.isBlank() || slotId < 1 || slotId > 4)
            throw new IllegalArgumentException("Invalid operation");
        this.id = id;
        this.slotId = slotId;
        this.arrivalDeadlineMillis = arrivalDeadlineMillis;
    }
    public String id() { return id; }
    public int slotId() { return slotId; }
    public long arrivalDeadlineMillis() { return arrivalDeadlineMillis; }
    public Phase phase() { return phase; }
    public NavigationState navigationState() { return navigationState; }
    public Target target() { return target; }
    public String barcode() { return barcode; }
    public void phase(Phase value) { phase = value; }
    public void barcode(String value) { barcode = value; }
    public void moving(Phase next, Target destination) {
        phase = next;
        target = destination;
        navigationState = NavigationState.MOVING;
    }
    public void arrived() { navigationState = NavigationState.ARRIVED; }
    public void failed() { navigationState = NavigationState.FAILED; }
}
