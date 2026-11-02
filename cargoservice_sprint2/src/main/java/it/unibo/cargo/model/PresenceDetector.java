package it.unibo.cargo.model;

/** Conferma basata sui campioni: silenzio, dati invalidi o soglia interrompono la continuita. */
public final class PresenceDetector {
    private final double freeDistance;
    private final long presenceMillis;
    private final long maxSampleGapMillis;
    private long belowSince = -1;
    private long lastSample = -1;
    private boolean present;

    public PresenceDetector(double freeDistance, long presenceMillis, long maxSampleGapMillis) {
        if (!Double.isFinite(freeDistance) || freeDistance <= 0 || presenceMillis <= 0 || maxSampleGapMillis <= 0)
            throw new IllegalArgumentException("Invalid sonar configuration");
        this.freeDistance = freeDistance;
        this.presenceMillis = presenceMillis;
        this.maxSampleGapMillis = maxSampleGapMillis;
    }
    /** Restituisce present/free solo quando cambia lo stato confermato. */
    public String sample(double distance, long now) {
        boolean gap = lastSample >= 0 && (now < lastSample || now - lastSample > maxSampleGapMillis);
        lastSample = now;
        if (gap) belowSince = -1;
        if (!Double.isFinite(distance) || distance < 0 || distance >= freeDistance / 2) {
            belowSince = -1;
            boolean changed = present;
            present = false;
            return changed ? "free" : "";
        }
        if (gap && present) { present = false; belowSince = now; return "free"; }
        if (belowSince < 0) belowSince = now;
        if (!present && now - belowSince >= presenceMillis) { present = true; return "present"; }
        return "";
    }
    public boolean present() { return present; }
}
