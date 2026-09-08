package arbolprocesos;

/**
 * Datos de identidad del proceso actual (PID / PPID) y tiempo de vida minimo,
 * para que el arbol completo quede visible con pstree antes de terminar.
 */
public final class ProcessInfo
{
    private static final long TIEMPO_DE_VIDA_MS = 10_000L;
    private static final String FORMATO = "Proceso %s | PID: %s | PPID: %s";
    private static final String SIN_PADRE = "N/D";

    private ProcessInfo()
    {
    }

    public static String describir(String nombre)
    {
        ProcessHandle procesoActual = ProcessHandle.current();
        String ppid = procesoActual.parent()
                .map(padre -> String.valueOf(padre.pid()))
                .orElse(SIN_PADRE);
        return String.format(FORMATO, nombre, procesoActual.pid(), ppid);
    }

    public static void mantenerVivo()
    {
        try
        {
            Thread.sleep(TIEMPO_DE_VIDA_MS);
        }
        catch (InterruptedException ex)
        {
            System.out.println("Error en el sleep. Mensaje de error: " + ex.getMessage());
            Thread.currentThread().interrupt();
        }
    }
}
