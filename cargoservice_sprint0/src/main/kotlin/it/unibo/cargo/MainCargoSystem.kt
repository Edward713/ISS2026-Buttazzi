package it.unibo.cargo

import it.unibo.kactor.QakContext
import it.unibo.kactor.sysUtil
import kotlinx.coroutines.runBlocking

/** Avvio locale di Sprint0: quattro contesti distinti nello stesso processo. */
fun main() = runBlocking {
    QakContext.createContexts("localhost", this, "cargoservice_term.pl", "sysRules.pl")
    val contexts = listOf("ctxcargoservice", "ctxioport", "ctxrobot", "ctxsensor")
        .map { requireNotNull(sysUtil.getContext(it)) }
    for (context in contexts) {
        for (peer in contexts) {
            if (peer != context) context.addCtxProxy(peer)
        }
    }
    for (context in contexts) sysUtil.createTheActors(context, this)
    println("[CARGO] I quattro contesti sono avviati e pronti a ricevere messaggi.")
}
