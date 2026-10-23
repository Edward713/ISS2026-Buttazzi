package it.unibo.cargo.model;

/** Parametri condivisi fra processi tramite proprieta JVM (-D) o task Gradle (-P). */
public final class CargoConfig {
    private CargoConfig() { }
    public static long waitMillis() { return positive("cargo.waitMillis", 30000); }
    public static long presenceMillis() { return positive("cargo.presenceMillis", 3000); }
    public static long markerMillis() { return positive("cargo.markerMillis", 5000); }
    public static long navigationMillis() { return positive("cargo.navigationMillis", 120000); }
    public static long sampleGapMillis() { return positive("cargo.sampleGapMillis", 1000); }
    public static long stepMillis() { return positive("cargo.stepMillis", 335); }
    public static boolean testMode() { return Boolean.getBoolean("cargo.testMode"); }
    public static boolean mockRobot() { return Boolean.getBoolean("cargo.mockRobot"); }
    public static double freeDistance() { return Double.parseDouble(System.getProperty("cargo.dfree", "100")); }
    private static long positive(String key, long fallback) {
        long value = Long.parseLong(System.getProperty(key, Long.toString(fallback)));
        if (value <= 0) throw new IllegalArgumentException(key + " must be positive");
        return value;
    }
}
