package arbolprocesos;

/**
 * Proceso A: raiz del arbol. Solo crea al proceso B y espera a que termine.
 */
public final class Main
{
    private static final String PROCESS_A = "A";
    private static final String PROCESS_B = "B";

    private Main()
    {
    }

    public static void main(String[] args)
    {
        System.out.println(ProcessInfo.describir(PROCESS_A));
        ProcessLauncher.crearHijosYEsperar(PROCESS_B);
        ProcessInfo.mantenerVivo();
    }
}
