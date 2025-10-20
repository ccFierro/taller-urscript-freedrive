"""
Taller_FreeDrive (versión organizada y limpia)
------------------------------------------------
Propósito: GUI simple para manipular un UR (Freedrive, guardar poses, acciones de gripper y ejecutar rutina).

Cambios respecto al original (SIN modificar lógica/flujo):
- Limpieza de librerías no utilizadas: se removió matplotlib, numpy, json, scrolledtext y duplicados de messagebox/ttk.
- Orden del archivo por secciones claras (config, helpers, URScript, RTDE, GUI).
- Comentarios y docstrings en puntos clave para facilitar mantenimiento.
- Nombres de variables de botones más consistentes (evitar sobrescribir `btn_on`).
- Mantiene compatibilidad con `urscripts.py` y `control_loop_configuration.xml` sin tocarlos.
"""
# -*- coding: utf-8 -*-


# ▼▼========================================================▼▼
#   ⮞ 01 Librerías y módulos
# ------------------------------------------------------------

import os
import sys
import time
import socket
import threading
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
import ttkbootstrap as tb
from ttkbootstrap.constants import *  # DANGER, etc.

import rtde.rtde as rtde
import rtde.rtde_config as rtde_config

import urscripts  # contexto externo: NO modificar

# ▲▲========================================================▲▲





# ▼▼========================================================▼▼
#   ⮞ 02 Contexto de rutas / archivos externos
# ------------------------------------------------------------

# Fijar directorio base al del script (útil para PyInstaller)
os.chdir(os.path.dirname(os.path.abspath(__file__)))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def resource_path(relative_path: str) -> str:
    """
    ============================================================
    FUNCIÓN: resource_path(relative_path)
    ------------------------------------------------------------
    Devuelve la ruta absoluta de un recurso (archivo o imagen),
    compatible con empaquetado mediante PyInstaller.

        Parámetros:
            relative_path (str): ruta relativa al archivo dentro del proyecto.
        Retorna:
            str: ruta absoluta al recurso.
        Notas:
            - Usa sys._MEIPASS cuando el programa está empaquetado.
            - Permite acceder a imágenes y archivos XML externos.
    ============================================================
    """
    try:
        base_path = sys._MEIPASS 
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


CONFIG_FILE = resource_path("control_loop_configuration.xml")
FONDO_IMG  = resource_path("fondo.png")

# ▲▲========================================================▲▲





# ▼▼========================================================▼▼
#   ⮞ 03 Configuración del robot
# ------------------------------------------------------------
ROBOT_IP      = "192.168.1.20"
PORT_URSCRIPT = 30002
PORT_RTDE     = 30004

# Estado RTDE / datos compartidos
tcp_pos = [0, 0, 0, 0, 0, 0]        # posición TCP (VECTOR6D)
posiciones_guardadas = []           # histórico de poses guardadas
gripper_status = True               # True=Abierto / False=Cerrado (para registrar acción)
lista_instrucciones = []            # secuencia combinada de {tipo:"pose"|"gripper", ...}

con_rtde = None                     # conexión RTDE
rtde_ok  = False                    # flag de conexión

# ▲▲========================================================▲▲





# ▼▼========================================================▼▼
#   ⮞ 04 Helpers URScripts
# ------------------------------------------------------------
def send_urscript(command: str) -> None:
    """
    ============================================================
    FUNCIÓN: send_urscript(command)
    ------------------------------------------------------------
    Envía un comando URScript al robot mediante un socket TCP 
    en el puerto 30002 (puerto estándar de ejecución directa).

        Parámetros:
            command (str): texto URScript a ejecutar en el robot.
        Retorna:
            None
        Errores:
            Muestra un messagebox en caso de fallo de conexión o envío.
    ============================================================
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((ROBOT_IP, PORT_URSCRIPT))
            s.send((command + "\n").encode("utf-8"))
    except Exception as e:
        messagebox.showerror("Error URScript", f"No se pudo enviar comando: {e}")


# Acciones directas
def activar_freedrive():
    """
    ============================================================
    FUNCIÓN: activar_freedrive()
    ------------------------------------------------------------
    Activa el modo Freedrive del cobot, permitiendo moverlo 
    manualmente sin resistencia en los ejes.

        Parámetros:
            Ninguno
        Retorna:
            None
        Notas:
            Envía el comando definido en `urscripts.s_liberar_motores`.
    ============================================================
    """
    send_urscript(urscripts.s_liberar_motores)


def alinear():
    """
    ============================================================
    FUNCIÓN: alinear()
    ------------------------------------------------------------
    Ejecuta un movimiento que orienta el eje Z del TCP hacia 
    una posición predefinida (alineación estándar).

        Parámetros:
            Ninguno
        Retorna:
            None
        Notas:
            Usa el script `urscripts.s_alinear_z`.
    ============================================================
    """
    send_urscript(urscripts.s_alinear_z)


def detener():
    """
    ============================================================
    FUNCIÓN: detener()
    ------------------------------------------------------------
    Detiene el movimiento actual del robot de forma segura.

        Parámetros:
            Ninguno
        Retorna:
            None
        Notas:
            Envía `urscripts.s_detener` al puerto URScript.
    ============================================================
    """

    send_urscript(urscripts.s_detener)


def abrir_pinza():
    """
    ============================================================
    FUNCIÓN: abrir_pinza()
    ------------------------------------------------------------
    Abre la pinza Robotiq e-Hand y actualiza la etiqueta 
    visual en la interfaz.

        Parámetros:
            Ninguno
        Retorna:
            None
        Notas:
            - Envía `urscripts.s_abrir_pinza`.
            - Cambia el estado global `gripper_status` a True.
    ============================================================
    """

    global gripper_status
    send_urscript(urscripts.s_abrir_pinza)
    estadoGrippper.configure(text="Abierto", bootstyle="inverse-info")
    gripper_status = True


def cerrar_pinza():
    """
    ============================================================
    FUNCIÓN: cerrar_pinza()
    ------------------------------------------------------------
    Cierra la pinza Robotiq e-Hand y actualiza la etiqueta 
    visual en la interfaz.

        Parámetros:
            Ninguno
        Retorna:
            None
        Notas:
            - Envía `urscripts.s_cerrar_pinza`.
            - Cambia el estado global `gripper_status` a False.
    ============================================================
    """

    global gripper_status
    send_urscript(urscripts.s_cerrar_pinza)
    estadoGrippper.configure(text="Cerrado", bootstyle="inverse-warning")
    gripper_status = False


# ▲▲========================================================▲▲






# ▼▼========================================================▼▼
#   ⮞ 05 Conexión RTDE
# ------------------------------------------------------------
def rtde_connect() -> bool:
    """
    ============================================================
    FUNCIÓN: rtde_connect()
    ------------------------------------------------------------
    Establece la conexión RTDE con el robot, configurando la 
    receta 'state' para recibir datos de posición TCP y estado.

        Parámetros:
            Ninguno
        Retorna:
            bool: True si la conexión fue exitosa, False en caso contrario.
        Errores:
            Muestra un messagebox en caso de fallo de conexión o configuración.
    ============================================================
    """

    global con_rtde, rtde_ok
    try:
        conf = rtde_config.ConfigFile(CONFIG_FILE)
        state_names, state_types = conf.get_recipe("state")

        con_rtde = rtde.RTDE(ROBOT_IP, PORT_RTDE)
        con_rtde.connect()

        if not con_rtde.send_output_setup(state_names, state_types, frequency=125):
            messagebox.showerror("Error", "No se pudo configurar la salida RTDE")
            con_rtde.disconnect(); con_rtde = None; rtde_ok = False
            return False

        if not con_rtde.send_start():
            messagebox.showerror("Error", "No se pudo iniciar la sincronización RTDE")
            con_rtde.disconnect(); con_rtde = None; rtde_ok = False
            return False

        rtde_ok = True
        return True

    except Exception as e:
        messagebox.showerror("Error de conexión", f"No se pudo conectar con el robot:\n{e}")
        con_rtde = None; rtde_ok = False
        return False


def read_rtde_thread():
    """
    ============================================================
    FUNCIÓN: read_rtde_thread()
    ------------------------------------------------------------
    Hilo en segundo plano que lee continuamente el estado RTDE 
    del robot, actualizando posición TCP y estado Freedrive.

        Parámetros:
            Ninguno
        Retorna:
            None
        Notas:
            - Ejecuta en bucle con retardo corto (0.01 s).
            - Actualiza visualmente el color del botón Freedrive 
            y la etiqueta de estado del cobot.
    ============================================================
    """

    global tcp_pos
    while True:
        if con_rtde is None:
            time.sleep(0.2)
            continue

        state = con_rtde.receive()
        if state:
            tcp_pos = state.actual_TCP_pose
            s = state.robot_status_bits
            # 1/3 -> freedrive off ; 5/7 -> freedrive on (heurística simple)
            if (s == 1 or s == 3):
                estadoCobot.configure(text="   Freedrive desactivado ", bootstyle="inverse-danger")
                style.configure("Free.TButton", font=("Arial", font1, "bold"), foreground="#404040", background="#ffffff", borderwidth=0)
            if (s == 7 or s == 5):
                estadoCobot.configure(text="   Freedrive activado    ", bootstyle="inverse-info")
                style.configure("Free.TButton", font=("Arial", font1, "bold"), foreground="#404040", background="#6cc3d5", borderwidth=0)
        time.sleep(0.01)  # evitar saturar CPU

# ▲▲========================================================▲▲






# ▼▼========================================================▼▼
#   ⮞ 06 Gestión de poses y acciones
# ------------------------------------------------------------
def guardar_posicion():
    """
    ============================================================
    FUNCIÓN: guardar_posicion()
    ------------------------------------------------------------
    Guarda la posición actual del TCP leída desde RTDE y la 
    agrega a la secuencia de instrucciones.

        Parámetros:
            Ninguno
        Retorna:
            None
        Notas:
            - Llama `urscripts.s_no_liberar` para salir de Freedrive.
            - Convierte la pose a milímetros para visualización.
    ============================================================
    """

    global tcp_pos, posiciones_guardadas, lista_instrucciones
    send_urscript(urscripts.s_no_liberar)

    # Guardado interno
    pos_actual = list(tcp_pos)
    posiciones_guardadas.append(pos_actual)
    lista_instrucciones.append({"tipo": "pose", "pose": pos_actual})

    # Formateo para mostrar (mm y rad)
    pos_fmt = [round(pos_actual[0]*1000, 1),
               round(pos_actual[1]*1000, 1),
               round(pos_actual[2]*1000, 1),
               round(pos_actual[3], 3),
               round(pos_actual[4], 3),
               round(pos_actual[5], 3)]
    txt_posiciones.insert(tk.END, f". -> {pos_fmt}\n")
    txt_posiciones.see(tk.END)


def guardar_accion_gripper():
    """
    ============================================================
    FUNCIÓN: guardar_accion_gripper()
    ------------------------------------------------------------
    Registra una acción de apertura o cierre de pinza según el 
    estado actual del gripper y la agrega a la secuencia.

        Parámetros:
            Ninguno
        Retorna:
            None
        Notas:
            - Inserta {"tipo":"gripper","accion":"ABRIR|CERRAR"}.
            - Muestra el paso en el cuadro de texto principal.
    ============================================================
    """

    global gripper_status, lista_instrucciones
    accion = "Abrir" if gripper_status else "Cerrar"
    estadoCobot.configure(text=("Abierto" if accion == "Abrir" else "Cerrado"),
                          bootstyle=("inverse-info" if accion == "Abrir" else "inverse-warning"))
    lista_instrucciones.append({"tipo": "gripper", "accion": accion})
    txt_posiciones.insert(tk.END, f". -> {accion} gripper\n")
    txt_posiciones.see(tk.END)


def ejecutar_rutina():
    """
    ============================================================
    FUNCIÓN: ejecutar_rutina()
    ------------------------------------------------------------
    Construye un programa URScript completo a partir de la lista 
    de instrucciones (poses + acciones) y lo envía al robot.

        Parámetros:
            Ninguno
        Retorna:
            None
        Notas:
            - Cada pose genera un bloque `movej()`.
            - Cada acción de gripper genera un comando `rq_*()`.
            - Inserta pausas cortas entre pasos.
    ============================================================
    """

    if not lista_instrucciones:
        messagebox.showwarning("Atención", "No hay pasos guardados (poses/acciones)." )
        return

    script_lines = []
    for paso in lista_instrucciones:
        if paso.get("tipo") == "pose":
            x, y, z, Rx, Ry, Rz = paso["pose"]
                                    # Modificar aqui  si se quiere que los moviemientos sean movej o movel
            script_lines.append(f"    movej(p[{x}, {y}, {z}, {Rx}, {Ry}, {Rz}], a=0.6, v=0.6)")
            script_lines.append("    sleep(0.05)")  # pequeña pausa útil en taller
        elif paso.get("tipo") == "gripper":
            if paso["accion"] == "Abrir":
                script_lines.append("    rq_open_and_classify()")
            else:
                script_lines.append("    rq_close_and_classify()")
            script_lines.append("    sleep(0.05)")

    script_lines.append("end")
    script_lines.append("cearInacap()")

    full_script = urscripts.s_cobotStart + "\n" + "\n".join(script_lines)
    send_urscript(full_script)


def borrar_posiciones():
    """
    ============================================================
    FUNCIÓN: borrar_posiciones()
    ------------------------------------------------------------
    Limpia completamente la lista de poses y acciones guardadas, 
    así como el texto mostrado en la interfaz.

        Parámetros:
            Ninguno
        Retorna:
            None
    ============================================================
    """

    global posiciones_guardadas, lista_instrucciones
    posiciones_guardadas.clear()
    lista_instrucciones.clear()
    txt_posiciones.delete("1.0", tk.END)


def borrar_ultimalinea():
    """
    ============================================================
    FUNCIÓN: borrar_ultimalinea()
    ------------------------------------------------------------
    Elimina la última línea o instrucción registrada en la 
    secuencia y actualiza el texto visible en la GUI.

        Parámetros:
            Ninguno
        Retorna:
            None
    ============================================================
    """

    global lista_instrucciones
    if not lista_instrucciones:
        return
    lista_instrucciones = lista_instrucciones[:-1]
    lines = txt_posiciones.get("1.0", tk.END).strip().split("\n")
    if lines:
        lines = lines[:-1]
        txt_posiciones.delete("1.0", tk.END)
        txt_posiciones.insert(tk.END, "\n".join(lines) + "\n")


# ▲▲========================================================▲▲






# ▼▼========================================================▼▼
#   ⮞ 07 Utilidades GUI
# ------------------------------------------------------------
def obtener_factor_escala(ventana) -> float:
    """
    ============================================================
    FUNCIÓN: obtener_factor_escala(ventana)
    ------------------------------------------------------------
    Calcula el factor de escala del monitor basado en los DPI 
    para ajustar tamaños de fuente y elementos gráficos.

        Parámetros:
            ventana (tk.Tk): ventana principal.
        Retorna:
            float: factor de escala relativo a 96 DPI.
    ============================================================
    """
    dpi = ventana.winfo_fpixels('1i')
    return dpi / 96


def al_cerrar():
    """Cerrar ventana limpiamente."""
    ventana.destroy()
    sys.exit()


# ▲▲========================================================▲▲






# ▼▼========================================================▼▼
#   ⮞ 08 Arranque de la app y GUI
# ------------------------------------------------------------
# Conectar RTDE y activar gripper
rtde_connect()
send_urscript(urscripts.s_activar_gripper)

# Ventana
ventana = tb.Window(themename="lumen")
ventana.title("Cliente")
ventana.resizable(False, False)
ventana.bind("<Escape>", lambda e: ventana.destroy())

ANCHO, ALTO = 1100, 820
ventana.geometry(f"{ANCHO}x{ALTO}")

# Escalas / tipografías dependientes de DPI
fe = obtener_factor_escala(ventana)
font1 = max(8, int(16 / fe))
font2 = max(8, int(12 / fe))
font3 = max(8, int(10 / fe))

# Fondo
img = Image.open(os.path.join(BASE_DIR, FONDO_IMG)).resize((ANCHO, ALTO))
fondo_D = ImageTk.PhotoImage(img)
canvas = tk.Canvas(ventana, width=ANCHO, height=ALTO, bg="white", highlightthickness=0)
canvas.pack()
canvas.create_image(0, 0, anchor=tk.NW, image=fondo_D)

# Estilos
global style, estadoCobot, estadoGrippper, txt_posiciones  # widgets usados por funciones
style = tb.Style()
style.configure("Btn1.TButton", font=("Arial", font1, "bold"), foreground="#404040", background="#ffffff", borderwidth=0)
style.configure("Free.TButton", font=("Arial", font1, "bold"), foreground="#404040", background="#ffffff", borderwidth=0)
style.configure("Btn2.TButton", font=("Arial", font2, "bold"), foreground="#404040", background="#ffffff", borderwidth=0)
style.configure("Btn3.TButton", font=("Arial", font3, "bold"), foreground="#404040", background="#dedede", borderwidth=0)
style.map("Btn1.TButton", background=[("active", "#e6e6e6"), ("pressed", "#cccccc")], foreground=[("disabled", "#a0a0a0")])
style.map("Btn2.TButton", background=[("active", "#e6e6e6"), ("pressed", "#cccccc")], foreground=[("disabled", "#a0a0a0")])
style.map("Btn3.TButton", background=[("active", "#e6e6e6"), ("pressed", "#cccccc")], foreground=[("disabled", "#a0a0a0")])
style.map("Free.TButton", background=[("active", "#e6e6e6"), ("pressed", "#cccccc")], foreground=[("disabled", "#a0a0a0")])

# --- Botones de movimiento / freedrive / poses ---
btn_freedrive = tb.Button(ventana, text="Freedrive", command=activar_freedrive, style="Free.TButton")
btn_freedrive.place(x=100, y=200, width=160, height=60)

btn_alinear = tb.Button(ventana, text="Alinear", command=alinear, bootstyle=DANGER, style="Btn1.TButton")
btn_alinear.place(x=295, y=200, width=160, height=60)

btn_guardar_pose = tb.Button(ventana, text="Guardar\nPosición", command=guardar_posicion, bootstyle=DANGER, style="Btn2.TButton")
btn_guardar_pose.place(x=490, y=200, width=160, height=60)

# --- Botones de gripper ---
btn_abrir = tb.Button(ventana, text="Abrir pinza", command=abrir_pinza, style="Btn1.TButton")
btn_abrir.place(x=100, y=370, width=160, height=60)

btn_cerrar = tb.Button(ventana, text="Cerrar pinza", command=cerrar_pinza, bootstyle=DANGER, style="Btn1.TButton")
btn_cerrar.place(x=295, y=370, width=160, height=60)

btn_guardar_accion = tb.Button(ventana, text="Guardar\n Acción", command=guardar_accion_gripper, bootstyle=DANGER, style="Btn2.TButton")
btn_guardar_accion.place(x=490, y=370, width=160, height=60)

# --- Ejecución y utilitarios ---
btn_ejecutar = tb.Button(ventana, text="Ejecutar", command=ejecutar_rutina, bootstyle=DANGER, style="Btn1.TButton")
btn_ejecutar.place(x=731, y=550, width=300, height=60)

btn_detener = tb.Button(ventana, text="Detener", command=detener, bootstyle=DANGER, style="Btn1.TButton")
btn_detener.place(x=730, y=621, width=300, height=60)

btn_borrar_todo = tb.Button(ventana, text="Borrar Todo", command=borrar_posiciones, bootstyle=DANGER, style="Btn3.TButton")
btn_borrar_todo.place(x=875, y=506, width=150, height=32)

btn_borrar_ultima = tb.Button(ventana, text="Borrar ultima linea", command=borrar_ultimalinea, bootstyle=DANGER, style="Btn3.TButton")
btn_borrar_ultima.place(x=725, y=506, width=150, height=32)

# Cuadro principal de la rutina
txt_posiciones = tk.Text(ventana, width=44, height=20)
txt_posiciones.place(x=743, y=170)

# Estados
estadoConexion = tb.Label(ventana, text=" Conectado ", font=("Arial", font3, "bold"), style="inverse-success", anchor="center")
estadoConexion.place(x=74, y=511, height=28, width=180)

estadoCobot = tb.Label(ventana, text=" Cobot Normal ", font=("Arial", font3, "bold"), style="inverse-primary", anchor="center")
estadoCobot.place(x=285, y=511, height=28, width=180)

estadoGrippper = tb.Label(ventana, text=" Abierto ", font=("Arial", font3, "bold"), style="inverse-primary", anchor="center")
estadoGrippper.place(x=496, y=511, height=28, width=180)

# Thread de actualización RTDE
threading.Thread(target=read_rtde_thread, daemon=True).start()

# Cierre seguro
ventana.protocol("WM_DELETE_WINDOW", al_cerrar)
ventana.mainloop()


# ▲▲========================================================▲▲