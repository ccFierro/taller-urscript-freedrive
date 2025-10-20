s_activar_gripper="""
def activarPinza():
    #> Conexión y activación de Robotiq e-Hand 
    SOCK = "1"

    #_ Conectar al driver Robotiq (loopback interno del UR)
    socket_open("127.0.0.1", 63352, SOCK)
    sleep(0.2)

    #> set_var + esperar ACK
    def rq_set_var(var, value, socket=SOCK):
        socket_set_var(var, value, socket)
        socket_read_byte_list(3, socket)
    end

    #> Reset y activación
    rq_set_var("ACT", 0, SOCK)
    rq_set_var("GTO", 0, SOCK)
    sleep(0.1)
    rq_set_var("ACT", 1, SOCK)
    sleep(0.5)

    #> Configurar fuerza y velocidad
    rq_set_var("FOR", 128, SOCK)
    rq_set_var("SPE", 200, SOCK)

    #> Dejar lista la pinza para comandos POS
    rq_set_var("GTO", 1, SOCK)
    rq_set_var("FOR", 200, SOCK)
    rq_set_var("SPE", 150, SOCK)
    rq_set_var("GTO", 1, SOCK)
    rq_set_var("POS", 5, SOCK)
    sleep(0.03)
    rq_set_var("GTO", 1, SOCK)
    sleep(0.06)
    
end

activarPinza()
"""

s_liberar_motores = """
def liberarMotores():
  freedrive_mode()
  sleep(3600)
end
liberarMotores()
"""

s_alinear_z = """
def alinearZ():
  end_freedrive_mode()
  pose = get_actual_tcp_pose()
  px = pose[0]
  py = pose[1]
  pz = pose[2]
  new_pose = p[px, py, pz, 0, 0, pose[5]]
  movel(new_pose, a=0.2, v=0.05)
end
"""

s_no_liberar = """
def endFree():
  end_freedrive_mode()    
end
"""

s_detener="""
stopl(1.0)
"""

s_abrir_pinza = """
def abrirPinza():
    SOCK = "1"
    socket_open("127.0.0.1", 63352, SOCK)
    
    # === Helper: set_var + ACK ===
    def rq_set_var(var, value, socket=SOCK):
        socket_set_var(var, value, socket)
        socket_read_byte_list(3, socket)
    end

    # Config base
    rq_set_var("FOR", 200, SOCK)
    rq_set_var("SPE", 150, SOCK)
    rq_set_var("GTO", 1, SOCK)

    # === WAIT por posición (no usa OBJ para terminar) ===
    # True si |POS_actual - objetivo| <= tol antes de timeout y FLT==0
    def rq_wait_pos_reached(goal, tol=5, max_s=12.0, poll=0.02, socket=SOCK):
        # clamp del objetivo (márgenes anti-extremo)
        g = goal
        if g < 10:
            g = 10
        end
        if g > 245:
            g = 245
        end

        t = 0.0
        while t < max_s:
            flt = socket_get_var("FLT", socket)
            if flt != 0:
                return False
            end
            pos = socket_get_var("POS", socket)
            d = pos - g
            if d < 0:
                d = -d
            end
            if d <= tol:
                return True
            end
            sleep(poll)
            t = t + poll
        end
        # Último intento: si no hay fallo y quedó cerca, aceptar
        if socket_get_var("FLT", socket) == 0:
            pos2 = socket_get_var("POS", socket)
            d2 = pos2 - g
            if d2 < 0:
                d2 = -d2
            end
            return (d2 <= tol + 2)
        end
        return False
    end

    # Movimiento + wait por posición (con pulso GTO y márgenes)
    def rq_move_to_pos_and_wait(target, tol=5, max_s=12.0, socket=SOCK):
        p = target
        if p < 10:
            p = 10
        end
        if p > 245:
            p = 245
        end

        rq_set_var("GTO", 0, socket)
        sleep(0.03)
        rq_set_var("POS", p, socket)
        sleep(0.03)
        rq_set_var("GTO", 1, socket)
        sleep(0.06)

        return rq_wait_pos_reached(p, tol, max_s, 0.02, socket)
    end

    # === HÍBRIDO: espera por POS y luego clasifica por OBJ ===
    # Devuelve:
    #  -1 = fallo (FLT!=0)
    #   0 = no llegó a tolerancia (sin fallo)
    #   1 = objeto detectado tipo 1
    #   2 = objeto detectado tipo 2
    #   3 = pos alcanzada sin objeto (estable)
    def rq_move_and_classify(target, tol=5, max_s=12.0, socket=SOCK):
        okpos = rq_move_to_pos_and_wait(target, tol, max_s, socket)
        flt = socket_get_var("FLT", socket)
        if flt != 0:
            return -1
        end
        if not okpos:
            return 0
        end
        obj = socket_get_var("OBJ", socket)
        if obj == 1:
            return 1
        elif obj == 2:
            return 2
        else:
            return 3
        end
    end

    # Atajos abrir/cerrar usando híbrido
    def rq_open_and_classify(max_s=12.0, tol=5, socket=SOCK):
        return rq_move_and_classify(10, tol, max_s, socket)
    end
    def rq_close_and_classify(max_s=12.0, tol=5, socket=SOCK):
        return rq_move_and_classify(245, tol, max_s, socket)
    end


    rq_open_and_classify()
end
"""

s_cerrar_pinza = """
def cerrarPinza():
    SOCK = "1"
    socket_open("127.0.0.1", 63352, SOCK)

    # === Helper: set_var + ACK ===
    def rq_set_var(var, value, socket=SOCK):
        socket_set_var(var, value, socket)
        socket_read_byte_list(3, socket)
    end

    # Config base
    rq_set_var("FOR", 200, SOCK)
    rq_set_var("SPE", 150, SOCK)
    rq_set_var("GTO", 1, SOCK)

    # === WAIT por posición (no usa OBJ para terminar) ===
    # True si |POS_actual - objetivo| <= tol antes de timeout y FLT==0
    def rq_wait_pos_reached(goal, tol=5, max_s=12.0, poll=0.02, socket=SOCK):
        # clamp del objetivo (márgenes anti-extremo)
        g = goal
        if g < 10:
            g = 10
        end
        if g > 245:
            g = 245
        end

        t = 0.0
        while t < max_s:
            flt = socket_get_var("FLT", socket)
            if flt != 0:
                return False
            end
            pos = socket_get_var("POS", socket)
            d = pos - g
            if d < 0:
                d = -d
            end
            if d <= tol:
                return True
            end
            sleep(poll)
            t = t + poll
        end
        # Último intento: si no hay fallo y quedó cerca, aceptar
        if socket_get_var("FLT", socket) == 0:
            pos2 = socket_get_var("POS", socket)
            d2 = pos2 - g
            if d2 < 0:
                d2 = -d2
            end
            return (d2 <= tol + 2)
        end
        return False
    end

    # Movimiento + wait por posición (con pulso GTO y márgenes)
    def rq_move_to_pos_and_wait(target, tol=5, max_s=12.0, socket=SOCK):
        p = target
        if p < 10:
            p = 10
        end
        if p > 245:
            p = 245
        end

        rq_set_var("GTO", 0, socket)
        sleep(0.03)
        rq_set_var("POS", p, socket)
        sleep(0.03)
        rq_set_var("GTO", 1, socket)
        sleep(0.06)

        return rq_wait_pos_reached(p, tol, max_s, 0.02, socket)
    end

    # === HÍBRIDO: espera por POS y luego clasifica por OBJ ===
    # Devuelve:
    #  -1 = fallo (FLT!=0)
    #   0 = no llegó a tolerancia (sin fallo)
    #   1 = objeto detectado tipo 1
    #   2 = objeto detectado tipo 2
    #   3 = pos alcanzada sin objeto (estable)
    def rq_move_and_classify(target, tol=5, max_s=12.0, socket=SOCK):
        okpos = rq_move_to_pos_and_wait(target, tol, max_s, socket)
        flt = socket_get_var("FLT", socket)
        if flt != 0:
            return -1
        end
        if not okpos:
            return 0
        end
        obj = socket_get_var("OBJ", socket)
        if obj == 1:
            return 1
        elif obj == 2:
            return 2
        else:
            return 3
        end
    end

    # Atajos abrir/cerrar usando híbrido
    def rq_open_and_classify(max_s=12.0, tol=5, socket=SOCK):
        return rq_move_and_classify(10, tol, max_s, socket)
    end
    def rq_close_and_classify(max_s=12.0, tol=5, socket=SOCK):
        return rq_move_and_classify(245, tol, max_s, socket)
    end


    rq_close_and_classify()
end
"""

s_cobotStart = """
def cearInacap():
    SOCK = "1"
    socket_open("127.0.0.1", 63352, SOCK)
    
    # === Helper: set_var + ACK ===
    def rq_set_var(var, value, socket=SOCK):
        socket_set_var(var, value, socket)
        socket_read_byte_list(3, socket)
    end

    # Config base
    rq_set_var("FOR", 200, SOCK)
    rq_set_var("SPE", 150, SOCK)
    rq_set_var("GTO", 1, SOCK)

    # === WAIT por posición (no usa OBJ para terminar) ===
    # True si |POS_actual - objetivo| <= tol antes de timeout y FLT==0
    def rq_wait_pos_reached(goal, tol=5, max_s=12.0, poll=0.02, socket=SOCK):
        # clamp del objetivo (márgenes anti-extremo)
        g = goal
        if g < 10:
            g = 10
        end
        if g > 245:
            g = 245
        end

        t = 0.0
        while t < max_s:
            flt = socket_get_var("FLT", socket)
            if flt != 0:
                return False
            end
            pos = socket_get_var("POS", socket)
            d = pos - g
            if d < 0:
                d = -d
            end
            if d <= tol:
                return True
            end
            sleep(poll)
            t = t + poll
        end
        # Último intento: si no hay fallo y quedó cerca, aceptar
        if socket_get_var("FLT", socket) == 0:
            pos2 = socket_get_var("POS", socket)
            d2 = pos2 - g
            if d2 < 0:
                d2 = -d2
            end
            return (d2 <= tol + 2)
        end
        return False
    end

    # Movimiento + wait por posición (con pulso GTO y márgenes)
    def rq_move_to_pos_and_wait(target, tol=5, max_s=12.0, socket=SOCK):
        p = target
        if p < 10:
            p = 10
        end
        if p > 245:
            p = 245
        end

        rq_set_var("GTO", 0, socket)
        sleep(0.03)
        rq_set_var("POS", p, socket)
        sleep(0.03)
        rq_set_var("GTO", 1, socket)
        sleep(0.06)

        return rq_wait_pos_reached(p, tol, max_s, 0.02, socket)
    end

    # === HÍBRIDO: espera por POS y luego clasifica por OBJ ===
    # Devuelve:
    #  -1 = fallo (FLT!=0)
    #   0 = no llegó a tolerancia (sin fallo)
    #   1 = objeto detectado tipo 1
    #   2 = objeto detectado tipo 2
    #   3 = pos alcanzada sin objeto (estable)
    def rq_move_and_classify(target, tol=5, max_s=12.0, socket=SOCK):
        okpos = rq_move_to_pos_and_wait(target, tol, max_s, socket)
        flt = socket_get_var("FLT", socket)
        if flt != 0:
            return -1
        end
        if not okpos:
            return 0
        end
        obj = socket_get_var("OBJ", socket)
        if obj == 1:
            return 1
        elif obj == 2:
            return 2
        else:
            return 3
        end
    end

    # Atajos abrir/cerrar usando híbrido
    def rq_open_and_classify(max_s=12.0, tol=5, socket=SOCK):
        return rq_move_and_classify(10, tol, max_s, socket)
    end
    def rq_close_and_classify(max_s=0.5, tol=5, socket=SOCK):
        return rq_move_and_classify(245, tol, max_s, socket)
    end
"""