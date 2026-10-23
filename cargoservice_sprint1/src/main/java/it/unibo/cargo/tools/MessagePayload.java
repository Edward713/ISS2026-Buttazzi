package it.unibo.cargo.tools;

import alice.tuprolog.Struct;
import alice.tuprolog.Term;

/** Accesso agli argomenti anche nei blocchi Kotlin QAK senza unificazione onMsg. */
public final class MessagePayload {
    private MessagePayload() { }
    public static String arg(String content, int index) {
        Struct term = (Struct) Term.createTerm(content);
        Term value = term.getArg(index);
        return value instanceof Struct s && s.getArity() == 0 ? s.getName() : value.toString();
    }
}
