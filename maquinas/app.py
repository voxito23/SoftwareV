def pedir_int(mensaje: str, minimo: int = 1) -> int:
    while True:
        try:
            x = int(input(mensaje).strip())
            if x < minimo:
                print(f"Error: debe ser un entero >= {minimo}.")
                continue
            return x
        except ValueError:
            print("Error: escribe un número entero válido.")

def pedir_float_pct(mensaje: str) -> float:
    while True:
        try:
            s = input(mensaje).strip().replace("%", "")
            x = float(s)
            if x < 0 or x > 100:
                print("Error: el porcentaje debe estar entre 0.00 y 100.")
                continue
            return x
        except ValueError:
            print("Error: escribe un número válido (ej: 50 o 1.2).")

def capturar_maquinas():
    while True:
        n = pedir_int("Cuántas máquinas quieres ejecutar? ", minimo=1)

        nombres = []
        p_prod = []
        p_def = []

        for i in range(n):
            while True:
                nombre = input(f"Nombre de la máquina {i+1}: ").strip()
                if not nombre:
                    print("Error: el nombre no puede estar vacío.")
                    continue
                if nombre in nombres:
                    print("Error: ese nombre ya existe, usa uno distinto.")
                    continue
                break

            prod = pedir_float_pct(f"% producido por {nombre}: ")
            defect = pedir_float_pct(f"% error (defectuoso) de {nombre}: ")

            nombres.append(nombre)
            p_prod.append(prod)
            p_def.append(defect)

        suma_prod = sum(p_prod)
        if abs(suma_prod - 100.0) > 1e-9:
            print(f"\nError: La suma de % producidos debe ser 100%. Actualmente es de: {suma_prod:.2f}%")
            print("Vuelve a capturar todos los datos.\n")
            continue

        return n, nombres, p_prod, p_def

def main():
    while True:
        n, nombres, p_prod, p_def = capturar_maquinas()

        term_def = [(p_def[i] * p_prod[i]) / 100.0 for i in range(n)]
        term_no = [((100.0 - p_def[i]) * p_prod[i]) / 100.0 for i in range(n)]

        P_D = sum(term_def)
        P_N = sum(term_no)

        post_D = [(term_def[i] / P_D) * 100.0 if P_D != 0 else 0.0 for i in range(n)]
        post_N = [(term_no[i] / P_N) * 100.0 if P_N != 0 else 0.0 for i in range(n)]

        print("\n_________________________________")
        print("   PROBABILIDAD TOTAL  ")
        print("_________________________________\n")

        print("Datos:")
        for i in range(n):
            print(f"  P({nombres[i]}) = {p_prod[i]:.2f}%")
        print()
        for i in range(n):
            print(f"  P(D|{nombres[i]}) = {p_def[i]:.2f}%   =>   P(N|{nombres[i]}) = {100.0 - p_def[i]:.2f}%")

        print("\n---------------------------------\n")

        print("1) Tornillo DEFECTUOSO de cualquier máquina")
        print("   P(D) = Σ P(D|Mi)P(Mi)")
        print("   P(D) = " + " + ".join(f"({p_def[i]:.2f}%)({p_prod[i]:.2f}%)" for i in range(n)))
        print(f"   P(D) = {P_D:.2f}%\n")

        print("2) Tornillo NO DEFECTUOSO de cualquier máquina")
        print("   P(N) = Σ P(N|Mi)P(Mi)")
        print("   P(N) = " + " + ".join(f"({100.0 - p_def[i]:.2f}%)({p_prod[i]:.2f}%)" for i in range(n)))
        print(f"   P(N) = {P_N:.2f}%\n")

        print("3) Si el tornillo es DEFECTUOSO, ¿de qué máquina proviene?\n")
        for i in range(n):
            print(f"   P({nombres[i]}|D) = (P(D|{nombres[i]})P({nombres[i]})) / P(D)")
            print(f"             = ({p_def[i]:.2f}%)({p_prod[i]:.2f}%) / ({P_D:.2f}%)")
            print(f"             = {term_def[i]:.2f}% / {P_D:.2f}% = {post_D[i]:.2f}%\n")
        print(f"   Comprobación: Σ P(Mi|D) = {sum(post_D):.2f}%\n")

        print("Si el tornillo es NO DEFECTUOSO, ¿de qué máquina proviene?\n")
        for i in range(n):
            print(f"   P({nombres[i]}|N) = (P(N|{nombres[i]})P({nombres[i]})) / P(N)")
            print(f"             = ({100.0 - p_def[i]:.2f}%)({p_prod[i]:.2f}%) / ({P_N:.2f}%)")
            print(f"             = {term_no[i]:.2f}% / {P_N:.2f}% = {post_N[i]:.2f}%\n")
        print(f"   Comprobación: Σ P(Mi|N) = {sum(post_N):.2f}%\n")

        otra = input("¿Quieres calcular otro caso? (si/no): ").strip().lower()
        if otra != "si":
            break

if __name__ == "__main__":
    main()
