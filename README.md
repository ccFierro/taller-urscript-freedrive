# Taller_FreeDrive — Documentación por secciones

> **Objetivo:** GUI para manipular un UR (URScript + RTDE) en un taller educativo: activar *Freedrive*, guardar poses TCP, registrar acciones del *gripper* Robotiq y ejecutar una rutina combinada.

---

## 0) Mapa rápido del archivo

1. **Imports**  
2. **Contexto de rutas y recursos** (`resource_path`, `BASE_DIR`, archivos externos)  
3. **Configuración del robot** (IP y puertos), **estado global** (TCP, lista de instrucciones, RTDE)  
4. **Helpers URScript** (`send_urscript`, acciones básicas: `activar_freedrive`, `alinear`, `detener`, `abrir_pinza`, `cerrar_pinza`)  
5. **Conexión RTDE** (`rtde_connect`, `read_rtde_thread`)  
6. **Gestión de poses / acciones** (`guardar_posicion`, `guardar_accion_gripper`, `ejecutar_rutina`, `borrar_posiciones`, `borrar_ultimalinea`)  
7. **Utilidades GUI** (`obtener_factor_escala`, `al_cerrar`)  
8. **Arranque de la app y GUI** (ventana, estilos, botones y labels, *thread* RTDE, `mainloop`).  

---

## 1) Imports

**Qué:** librerías estrictamente necesarias (Tkinter + ttkbootstrap, PIL, sockets, threads, RTDE/UR).  
**Por qué:** minimizar dependencias para empaquetado y rendimiento.  
**Cómo:**

```python
import socket, threading, tkinter as tk
from PIL import Image, ImageTk
import ttkbootstrap as tb
from ttkbootstrap.constants import *
import rtde.rtde as rtde
import rtde.rtde_config as rtde_config
import urscripts  # contexto externo
```

**Notas:** evitar `import *` salvo para constantes ttkbootstrap ya que simplifica estilos.

---

## 2) Contexto de rutas y recursos

**Qué:** `resource_path()` + constantes `CONFIG_FILE` y `FONDO_IMG`.  
**Por qué:** compatibilidad con ejecución directa y empaquetado (PyInstaller).  
**Cómo:**
```python
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

CONFIG_FILE = resource_path("control_loop_configuration.xml")
FONDO_IMG  = resource_path("fondo.png")
```
**Buenas prácticas:** fijar `os.chdir()` al directorio del script para rutas relativas estables.

---

## 3) Configuración del robot y estado global

**Qué:** IP/puertos y variables compartidas (pose TCP, lista de pasos, estado *gripper*, conexión RTDE).  
**Por qué:** centralizar *tuning* y el *state* de la app.  
**Cómo:**

```python
ROBOT_IP      = "192.168.0.50"
PORT_URSCRIPT = 30002
PORT_RTDE     = 30004

tcp_pos = [0, 0, 0, 0, 0, 0]
posiciones_guardadas = []
gripper_status = True          # True: abierto; False: cerrado
lista_instrucciones = []       # [{"tipo":"pose","pose":[...]}, {"tipo":"gripper","accion":"ABRIR"}]

con_rtde = None
rtde_ok  = False
```

**Extensión sugerida:** encapsular en una clase liviana `AppState` más adelante, sin cambiar API pública.

---

## 4) Helpers URScript

**Qué:** capa mínima para enviar programas/órdenes URScript y acciones básicas.  
**Por qué:** aislar la comunicación por socket y estandarizar el manejo de errores.  
**Cómo:**

```python
def send_urscript(command:str) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((ROBOT_IP, PORT_URSCRIPT))
        s.send((command + "\n").encode("utf-8"))
```

**Acciones expuestas:**

- `activar_freedrive()` → `urscripts.s_liberar_motores`  
- `alinear()` → `urscripts.s_alinear_z`  
- `detener()` → `urscripts.s_detener`  
- `abrir_pinza()` / `cerrar_pinza()` → `urscripts.s_abrir_pinza` / `s_cerrar_pinza`, actualizan `estadoGrippper` y `gripper_status`.

**Puntos de integración:** `urscripts.py` define `s_cobotStart`, macros del *gripper* (e.g., `rq_open_and_classify()`), etc.

---

## 5) Conexión RTDE

**Qué:** apertura RTDE con receta *state* desde `control_loop_configuration.xml` y lector en *thread*.  
**Por qué:** leer `actual_TCP_pose` y `robot_status_bits` sin bloquear la GUI.  
**Cómo:**

```python
def rtde_connect():
    conf = rtde_config.ConfigFile(CONFIG_FILE)
    state_names, state_types = conf.get_recipe("state")
    con_rtde = rtde.RTDE(ROBOT_IP, PORT_RTDE)
    con_rtde.connect()
    con_rtde.send_output_setup(state_names, state_types, frequency=125)
    con_rtde.send_start()
    rtde_ok = True
```

**`read_rtde_thread()`**  
- `state.actual_TCP_pose` → actualiza `tcp_pos`  
- `state.robot_status_bits` → cambia *label* del cobot y resalta estilo de botón *Freedrive*.

**Ritmo de lectura:** `sleep(0.01)` para no saturar CPU.

**Errores típicos:** `KeyError: 'state'` si la receta no existe o el archivo XML no coincide con la versión de UR/RTDE.

---

## 6) Gestión de poses y acciones

**Objetivo:** construir una **secuencia** combinada de movimientos y órdenes de *gripper* para ejecutar como un solo programa URScript.

### 6.1 `guardar_posicion()`
- Fuerza salida de *freedrive* (`urscripts.s_no_liberar`).
- Copia `tcp_pos` → agrega a `posiciones_guardadas` y a `lista_instrucciones` con `{"tipo":"pose"}`.
- Muestra pose formateada (mm, rad) en el *Text* de rutina.

### 6.2 `guardar_accion_gripper()`
- Usa `gripper_status` actual (controlado por `abrir_pinza`/`cerrar_pinza`).
- Inserta `{"tipo":"gripper","accion":"ABRIR|CERRAR"}` en `lista_instrucciones`.
- Log en el *Text* de rutina.

### 6.3 `ejecutar_rutina()`
- Recorre `lista_instrucciones` y compone URScript:
  - Poses → `movej(p[...], a=0.6, v=0.6)` + `sleep(0.05)`
  - Gripper → `rq_open_and_classify()` o `rq_close_and_classify()` + `sleep(0.05)`
- Prepara `full_script = urscripts.s_cobotStart + ... + "end" + "\n" + "cearInacap()"`  
- Envía con `send_urscript(full_script)`.

### 6.4 Limpieza
- `borrar_posiciones()` vacía listas y *Text*.
- `borrar_ultimalinea()` retira el último paso registrado.

---

## 7) Utilidades GUI

- `obtener_factor_escala(ventana)` → adapta fuentes/medidas a DPI (96 → 100%).  
- `al_cerrar()` → destruye ventana y hace `sys.exit()`.

---

## 8) Arranque de la app y GUI

**Inicio:**  
1. `rtde_connect()`  
2. `send_urscript(urscripts.s_activar_gripper)`  
3. Crea `Window`, fija tamaño (1100x820), fondo `fondo.png` en `Canvas`.  
4. Define estilos ttkbootstrap (`Btn1.TButton`, `Free.TButton`, …).  
5. **Botones clave:** Freedrive, Alinear, Guardar Posición, Abrir/Cerrar Pinza, Guardar Acción, Ejecutar, Detener, Borrar Última/Todo.  
6. **Estados:** `estadoConexion`, `estadoCobot`, `estadoGrippper`.  
7. Lanza `threading.Thread(target=read_rtde_thread, daemon=True).start()`  
8. `mainloop()`

**Layout:** se usa `.place()` con coordenadas absolutas para alinear con la plantilla gráfica.

---

