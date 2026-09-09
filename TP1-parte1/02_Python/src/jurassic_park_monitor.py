import argparse
import os
import random
import time
from multiprocessing import Process


ZONES = {
    "Sector del Tiranosaurio": [
        ("Todo normal", 0.80, False),
        ("Tiranosaurio fuera del recinto", 0.10, True),
        ("Falla en el cerco electrico", 0.10, True),
    ],
    "Area de Velociraptores": [
        ("Todo normal", 0.70, False),
        ("Perdida de visibilidad", 0.20, False),
        ("Falla en el cerco electrico", 0.10, True),
    ],
    "Recinto de los Triceratops": [
        ("Todo normal", 0.60, False),
        ("Comportamiento inusual", 0.30, False),
        ("Estampida", 0.10, False),
    ],
    "Centro de Visitantes": [
        ("Todo normal", 0.80, False),
        ("Perdida de comunicacion", 0.15, True),
        ("Alerta de seguridad", 0.05, True),
    ],
    "Laboratorio Genetico": [
        ("Todo normal", 0.80, False),
        ("Falla del sistema", 0.10, False),
        ("Perdida de comunicacion", 0.05, True),
        ("Acceso no autorizado", 0.05, False),
    ],
}


def monitor_zone(zone_name, events, duration, interval):
    random.seed()  # cada proceso necesita su propia semilla de azar

    print(f"[{zone_name}] proceso iniciado (PID={os.getpid()})", flush=True)

    names = [e[0] for e in events]
    weights = [e[1] for e in events]
    is_critical = {e[0]: e[2] for e in events}

    total_events = 0
    total_critical = 0
    start_time = time.time()

    while time.time() - start_time < duration:
        time.sleep(interval)
        event = random.choices(names, weights=weights, k=1)[0]
        total_events += 1
        if is_critical[event]:
            total_critical += 1
        print(f"[{zone_name}] - {event}", flush=True)

    print(
        f"[{zone_name}] >> Monitoreo finalizado | "
        f"Total de eventos: {total_events} | Eventos criticos: {total_critical}",
        flush=True,
    )


def main():
    parser = argparse.ArgumentParser(description="Monitor concurrente de zonas de Jurassic Park")
    parser.add_argument("-d", "--duration", type=float, default=15.0,
                         help="Duracion total del monitoreo, en segundos")
    parser.add_argument("-i", "--interval", type=float, default=2.0,
                         help="Segundos entre reportes de cada zona")
    args = parser.parse_args()

    processes = [
        Process(target=monitor_zone, args=(zone, events, args.duration, args.interval))
        for zone, events in ZONES.items()
    ]


    for p in processes:
        p.start()

    for p in processes:
        p.join()

    print("Todos los sistemas de vigilancia finalizaron.")


if __name__ == "__main__":
    main()
