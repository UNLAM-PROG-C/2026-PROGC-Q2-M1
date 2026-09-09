package arbolprocesos;

import java.io.IOException;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

/**
 * Crea los procesos hijos de un nodo. Primero los lanza a todos con start()
 * y recien despues espera a cada uno con waitFor(): asi los hermanos de un
 * mismo nivel corren de forma concurrente y no en cadena.
 */
public final class ProcessLauncher
{
    private static final String CLASE_HIJO = ChildProcess.class.getName();
    private static final String OPCION_CLASSPATH = "-cp";
    private static final String DIRECTORIO_BINARIOS = "bin";
    private static final String EJECUTABLE_JAVA = "java";

    private ProcessLauncher()
    {
    }

    public static void crearHijosYEsperar(String... nombresHijos)
    {
        List<Process> hijos = iniciarTodos(nombresHijos);
        esperarATodos(hijos);
    }

    private static List<Process> iniciarTodos(String[] nombresHijos)
    {
        List<Process> hijos = new ArrayList<>();
        for (String nombreHijo : nombresHijos)
        {
            iniciar(nombreHijo).ifPresent(hijos::add);
        }
        return hijos;
    }

    private static Optional<Process> iniciar(String nombreHijo)
    {
        try
        {
            return Optional.of(construirProceso(nombreHijo).start());
        }
        catch (IOException ex)
        {
            System.out.println("Error al iniciar Proceso Hijo " + nombreHijo
                    + ". Mensaje de error: " + ex.getMessage());
            return Optional.empty();
        }
    }

    private static ProcessBuilder construirProceso(String nombreHijo)
    {
        ProcessBuilder processBuilder = new ProcessBuilder(
                rutaDeJava(), OPCION_CLASSPATH, classpathActual(), CLASE_HIJO, nombreHijo);
        processBuilder.redirectErrorStream(true);
        processBuilder.inheritIO();
        return processBuilder;
    }

    private static void esperarATodos(List<Process> hijos)
    {
        for (Process hijo : hijos)
        {
            esperar(hijo);
        }
    }

    private static void esperar(Process hijo)
    {
        try
        {
            hijo.waitFor();
        }
        catch (InterruptedException ex)
        {
            System.out.println("Error en realizar waitFor sobre el proceso hijo. "
                    + "Mensaje de error: " + ex.getMessage());
            Thread.currentThread().interrupt();
        }
    }

    private static String rutaDeJava()
    {
        return Paths.get(System.getProperty("java.home"), DIRECTORIO_BINARIOS, EJECUTABLE_JAVA)
                .toString();
    }

    private static String classpathActual()
    {
        return System.getProperty("java.class.path");
    }
}
