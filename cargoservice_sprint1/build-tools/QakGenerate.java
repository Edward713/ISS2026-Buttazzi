import java.nio.file.Path;
import com.google.inject.Injector;
import org.eclipse.emf.common.util.URI;
import org.eclipse.emf.ecore.resource.Resource;
import org.eclipse.xtext.resource.XtextResourceSet;
import org.eclipse.xtext.generator.JavaIoFileSystemAccess;
import org.eclipse.xtext.generator.GeneratorContext;
import org.eclipse.xtext.util.CancelIndicator;

/** Usa il generatore UniBo per gli attori; i main delegano al bootstrap TCP distribuito. */
public class QakGenerate {
    public static void main(String[] args) throws Exception {
        Path source = Path.of(args[0]).toAbsolutePath();
        Path output = Path.of(args[1]).toAbsolutePath();
        Injector injector = new it.unibo.QactorkStandaloneSetup().createInjectorAndDoEMFRegistration();
        XtextResourceSet set = injector.getInstance(XtextResourceSet.class);
        Resource resource = set.getResource(URI.createFileURI(source.toString()), true);
        org.eclipse.emf.ecore.util.EcoreUtil.resolveAll(resource);
        if (!resource.getErrors().isEmpty()) {
            resource.getErrors().forEach(System.err::println);
            throw new IllegalStateException("QAK parsing/linking failed");
        }
        JavaIoFileSystemAccess access = new JavaIoFileSystemAccess() {
            @Override public void generateFile(String name, String configuration, CharSequence content) {
                String normalized = name.replace('\\', '/').replaceAll("/+", "/");
                System.out.println("QAK output: " + normalized);
                // The stock generator also emits Gradle templates. Preserve our tested build configuration.
                if ((normalized.contains("/src/it/unibo/") && normalized.endsWith(".kt"))
                    || normalized.endsWith("/cargoservice_term.pl")) {
                    String generated = normalized.endsWith(".kt")
                            // Il nero ANSI del generatore e invisibile sui terminali con sfondo nero.
                            ? content.toString().replace("CommUtils.outblack(", "kotlin.io.println(")
                            : content.toString();
                    var contextMain = java.util.regex.Pattern.compile(".*/src/it/unibo/(ctx[^/]+)/Main[^/]+\\.kt").matcher(normalized);
                    if (contextMain.matches()) {
                        String contextName = contextMain.group(1);
                        generated = "/* Main QAK: avvio distribuito tramite il bootstrap Sprint1. */\n"
                            + "package it.unibo." + contextName + "\n\n"
                            + "fun main() = it.unibo.cargo.main(arrayOf(\"" + contextName + "\"))\n";
                    }
                    super.generateFile(name, configuration, generated);
                }
            }
        };
        injector.injectMembers(access);
        access.setOutputPath(output.toString());
        GeneratorContext context = new GeneratorContext();
        context.setCancelIndicator(CancelIndicator.NullImpl);
        injector.getInstance(it.unibo.generator.QactorkGenerator.class).doGenerate(resource, access, context);
        System.out.println("Original QAK generator completed: " + source);
    }
}
