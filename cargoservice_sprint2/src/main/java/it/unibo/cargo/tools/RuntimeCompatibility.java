package it.unibo.cargo.tools;

import org.json.simple.parser.JSONParser;
import org.json.simple.parser.ParseException;
import unibo.basicomm23.utils.CommUtils;

/** Compatibilita con basicomm23-1.0: il parser statico e usato da piu connessioni TCP. */
public final class RuntimeCompatibility {
    private RuntimeCompatibility() { }
    public static void initialize() {
        try {
            var field = CommUtils.class.getDeclaredField("simpleparser");
            field.setAccessible(true);
            field.set(null, new JSONParser() {
                @Override public synchronized Object parse(String text) throws ParseException {
                    return super.parse(text);
                }
            });
        } catch (ReflectiveOperationException ex) {
            throw new IllegalStateException("Runtime basicomm23 incompatibile con il bootstrap Sprint1", ex);
        }
    }
}
