package arbolprocesos;

/**
 * Cualquier nodo del arbol que no sea la raiz. Recibe su nombre por parametro
 * (args[0]) y segun ese nombre sabe a que hijos tiene que crear:
 * B crea a C y D, C crea a E, D crea a F y G, E crea a H e I.
 * F, G, H e I no tienen case propio: son las hojas del arbol.
 */
public final class ChildProcess
{
    private static final String PROCESS_B = "B";
    private static final String PROCESS_C = "C";
    private static final String PROCESS_D = "D";
    private static final String PROCESS_E = "E";
    private static final String PROCESS_F = "F";
    private static final String PROCESS_G = "G";
    private static final String PROCESS_H = "H";
    private static final String PROCESS_I = "I";

    private static final int POSICION_NOMBRE = 0;

    private ChildProcess()
    {
    }

    public static void main(String[] args)
    {
        if (args.length <= POSICION_NOMBRE)
        {
            System.out.println("Falta el nombre del proceso. Uso: ChildProcess <nombre>");
            return;
        }

        String nombre = args[POSICION_NOMBRE];
        System.out.println(ProcessInfo.describir(nombre));
        crearHijos(nombre);
        ProcessInfo.mantenerVivo();
    }

    private static void crearHijos(String nombre)
    {
        switch (nombre)
        {
            case PROCESS_B:
                ProcessLauncher.crearHijosYEsperar(PROCESS_C, PROCESS_D);
                break;
            case PROCESS_C:
                ProcessLauncher.crearHijosYEsperar(PROCESS_E);
                break;
            case PROCESS_D:
                ProcessLauncher.crearHijosYEsperar(PROCESS_F, PROCESS_G);
                break;
            case PROCESS_E:
                ProcessLauncher.crearHijosYEsperar(PROCESS_H, PROCESS_I);
                break;
            default:
                break;
        }
    }
}
