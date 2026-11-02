package it.unibo.cargo

import it.unibo.kactor.sysUtil
import it.unibo.cargo.model.CargoConfig
import kotlinx.coroutines.runBlocking
import java.nio.file.Files
import java.nio.file.Path

/** Un attore applicativo per processo, secondo la distribuzione dello Sprint1. */
fun main(args: Array<String>) = runBlocking {
    it.unibo.cargo.tools.RuntimeCompatibility.initialize()
    val name = args.single()
    require(name in listOf("ctxcargoservice", "ctxcargorobot", "ctxioport", "ctxsensor"))
    System.setProperty("cargo.context", name)
    val portOffset = Integer.getInteger("cargo.portOffset", 0)
    // Il runtime 5.0 non crea proxy fra contesti dichiarati tutti su localhost.
    // Nel descrittore di ogni processo solo il contesto selezionato e locale;
    // gli altri usano 127.0.0.1 e comunicano quindi realmente via TCP.
    val descriptor = Files.readString(Path.of("cargoservice_term.pl"))
        .lineSequence().filter { line ->
            !(line.contains("ctxrobotsmart") && (CargoConfig.mockRobot() || name != "ctxcargorobot")) &&
                !(line.contains("external(robotsmart)") && (CargoConfig.mockRobot() || name != "ctxcargorobot"))
        }.joinToString("\n") { original ->
            val line = if (original.startsWith("context(")) {
                Regex("\"(\\d+)\"(?=\\)\\.)").replace(original) { match ->
                    "\"${match.groupValues[1].toInt() + portOffset}\""
                }
            } else original
            if (line.startsWith("context(") && !line.startsWith("context($name,"))
                line.replace("\"localhost\"", "\"127.0.0.1\"") else line
        }
    val output = Path.of("build", "contexts", if (portOffset == 0) "prototype" else "test-$portOffset", "$name.pl")
    Files.createDirectories(output.parent)
    Files.writeString(output, descriptor)
    sysUtil.createContexts("localhost", output.toString(), "sysRules.pl")
    sysUtil.createTheActors(requireNotNull(sysUtil.getContext(name)), this)
}
