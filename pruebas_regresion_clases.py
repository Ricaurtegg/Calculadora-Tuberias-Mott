from clasificar_problema import identificar_clase_automaticamente

CASOS = [
    ("Clase I", "Agua a 20 °C circula con Q = 0.010 m3/s por una tubería de acero comercial de longitud 50 m y diámetro 100 mm. P1=0 kPa, z1=10 m, z2=2 m. Determine la presión P2."),
    ("Clase II-A", "Agua a 20 °C circula desde un depósito abierto a otro por una tubería de acero comercial de longitud 80 m y diámetro 75 mm. z1=12 m, z2=0 m. Determine el caudal. Desprecie las pérdidas menores."),
    ("Clase II-B", "Agua a 20 °C circula desde un depósito a otro por una tubería de acero comercial de 80 m de longitud y 75 mm de diámetro. Existe una válvula de compuerta totalmente abierta. Determine el caudal. Las pérdidas menores son relativamente pequeñas y pueden incluirse como corrección."),
    ("Clase II-C", "Agua a 20 °C circula desde un depósito a otro. Tramo 1: longitud 50 m, diámetro 100 mm, acero comercial, con una válvula de globo. Tramo 2: longitud 30 m, diámetro 75 mm, acero comercial, con dos codos de 90°. Determine el caudal incluyendo todas las pérdidas menores."),
    ("Clase III-A", "Agua a 20 °C debe circular con Q=0.010 m3/s por una tubería de acero comercial de longitud 100 m. Determine el diámetro mínimo requerido para una pérdida de carga disponible de 8 m."),
    ("Clase III-B", "Se seleccionó una tubería comercial de diámetro interior 100 mm para conducir agua a 20 °C con Q=0.010 m3/s a lo largo de 100 m. Verifique el diámetro comercial y determine si satisface la presión mínima requerida en el punto 2."),
]


def main():
    for esperado, enunciado in CASOS:
        r = identificar_clase_automaticamente(enunciado)
        obtenido = r.get("clase")
        print(f"{esperado}: obtenido={obtenido}, confianza={r.get('confianza')} %")
        if obtenido != esperado:
            raise AssertionError(f"Esperado {esperado}, obtenido {obtenido}")
    print("\nRegresión de clasificación I / II-A / II-B / II-C / III-A / III-B: OK")

if __name__ == "__main__":
    main()
