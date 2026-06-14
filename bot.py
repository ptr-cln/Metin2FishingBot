import argparse
import json
import os
import platform
import random
import sys
import time

import cv2
import numpy as np
import pyautogui

try:
    import pygetwindow as gw
except ImportError:
    gw = None

try:
    import pydirectinput as directinput
except ImportError:
    directinput = None

CONFIG_PATH = "config.json"
TEMPLATES_DIR = "templates"
BAIT_TEMPLATE = os.path.join(TEMPLATES_DIR, "bait_icon.png")
FISH_TEMPLATE = os.path.join(TEMPLATES_DIR, "fishing_window.png")
DEFAULT_CONFIG = {
    "window_title": "METIN2",
    "window_process_name": "metin2client",
    "use_window_detection": False,
    "bait_point": {"x": 0, "y": 0},
    "fishing_roi": {"left": 0, "top": 0, "width": 320, "height": 320},
    "dark_threshold": 100,
    "min_fish_area": 160,
}

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.08


def load_config():
    if not os.path.exists(CONFIG_PATH):
        print(f"Config file '{CONFIG_PATH}' non trovato. Usa --calibrate per creare le coordinate.")
        sys.exit(1)

    with open(CONFIG_PATH, "r", encoding="utf-8") as handle:
        config = json.load(handle)

    for key in DEFAULT_CONFIG:
        if key not in config:
            config[key] = DEFAULT_CONFIG[key]
    return config


def save_config(config):
    with open(CONFIG_PATH, "w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2)
    print(f"Configurazione salvata in {CONFIG_PATH}")


def human_sleep(min_seconds=0.15, max_seconds=0.4):
    delay = random.uniform(min_seconds, max_seconds)
    time.sleep(delay)


def find_metin2_window(title=None, process_name=None):
    if title is None:
        title = DEFAULT_CONFIG["window_title"]
    if process_name is None:
        process_name = DEFAULT_CONFIG.get("window_process_name")

    if gw is not None:
        windows = [win for win in gw.getAllWindows() if title.lower() in win.title.lower() and win.width > 0 and win.height > 0]
        if windows:
            win = windows[0]
            return {"left": win.left, "top": win.top, "width": win.width, "height": win.height}
        if process_name:
            try:
                import win32process
                import psutil
                for win in gw.getAllWindows():
                    if win.width <= 0 or win.height <= 0:
                        continue
                    try:
                        _, pid = win32process.GetWindowThreadProcessId(win._hWnd)
                        proc = psutil.Process(pid)
                        if proc.name().lower() == process_name.lower():
                            return {"left": win.left, "top": win.top, "width": win.width, "height": win.height}
                    except Exception:
                        pass
            except ImportError:
                pass

    if platform.system() == "Windows":
        try:
            import win32con
            import win32gui
            import win32process
            import psutil

            def enum_windows(hwnd, result):
                if not win32gui.IsWindowVisible(hwnd):
                    return
                left, top, right, bottom = win32gui.GetWindowRect(hwnd)
                title_text = win32gui.GetWindowText(hwnd)
                if title.lower() in title_text.lower():
                    result.append({"left": left, "top": top, "width": right - left, "height": bottom - top})
                    return
                if process_name:
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    try:
                        proc = psutil.Process(pid)
                        if proc.name().lower() == process_name.lower():
                            result.append({"left": left, "top": top, "width": right - left, "height": bottom - top})
                            return
                    except Exception:
                        pass

            results = []
            win32gui.EnumWindows(enum_windows, results)
            if results:
                return results[0]
        except ImportError:
            pass

    return None


def capture_window(config):
    window = config.get("window_rect")
    if window and window["width"] > 0 and window["height"] > 0:
        screenshot = pyautogui.screenshot(region=(window["left"], window["top"], window["width"], window["height"]))
    else:
        screenshot = pyautogui.screenshot()
    return cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)


def match_template(frame, template_path, threshold=0.78):
    if not os.path.exists(template_path):
        return None
    template = cv2.imread(template_path, cv2.IMREAD_UNCHANGED)
    if template is None:
        return None
    if template.shape[2] == 4:
        template = cv2.cvtColor(template, cv2.COLOR_BGRA2BGR)

    result = cv2.matchTemplate(frame, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    if max_val >= threshold:
        h, w = template.shape[:2]
        return max_loc[0] + w // 2, max_loc[1] + h // 2
    return None


def default_bait_point(window):
    return {
        "x": window["left"] + int(window["width"] * 0.88),
        "y": window["top"] + int(window["height"] * 0.55),
    }


def default_fishing_roi(window):
    left = window["left"] + int(window["width"] * 0.18)
    top = window["top"] + int(window["height"] * 0.14)
    width = int(window["width"] * 0.50)
    height = int(window["height"] * 0.48)
    return {"left": left, "top": top, "width": width, "height": height}


def detect_fishing_roi(config):
    window = config.get("window_rect")
    if not window:
        return config.get("fishing_roi")

    frame = capture_window(config)
    match = match_template(frame, FISH_TEMPLATE, threshold=0.70)
    if match is not None:
        x, y = match
        w, h = 320, 320
        return {"left": window["left"] + x - w // 2, "top": window["top"] + y - h // 2, "width": w, "height": h}

    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (85, 40, 50), (135, 255, 255))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return config.get("fishing_roi")

    best = max(contours, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(best)
    x = max(0, x - 20)
    y = max(0, y - 20)
    w = min(window["width"] - x, w + 40)
    h = min(window["height"] - y, h + 40)
    if w < 120 or h < 120:
        return default_fishing_roi(window)
    return {"left": window["left"] + x, "top": window["top"] + y, "width": w, "height": h}


def find_bait_point(config):
    window = config.get("window_rect")
    if not window:
        return config.get("bait_point")

    frame = capture_window(config)
    start_x = int(window["width"] * 0.70)
    region = frame[int(window["height"] * 0.25) : int(window["height"] * 0.70), start_x:window["width"]]
    match = match_template(region, BAIT_TEMPLATE, threshold=0.75)
    if match is not None:
        x, y = match
        return {"x": window["left"] + start_x + x, "y": window["top"] + int(window["height"] * 0.25) + y}

    return default_bait_point(window)


def setup_auto_config(config):
    window = find_metin2_window(config.get("window_title"))
    if not window:
        return False
    config["window_rect"] = window
    config["bait_point"] = find_bait_point(config)
    config["fishing_roi"] = detect_fishing_roi(config)
    return True


def prompt_point(message):
    print(message)
    print("Posiziona il mouse sulla posizione desiderata e premi Invio.")
    input()
    point = pyautogui.position()
    print(f"Coordinate registrate: {point.x}, {point.y}")
    return {"x": point.x, "y": point.y}


def prompt_roi():
    print("Calibrazione area pesca.")
    print("Primo punto: angolo in alto a sinistra della finestra di pesca.")
    left_top = prompt_point("Posiziona il mouse sul primo angolo e premi Invio.")
    print("Secondo punto: angolo in basso a destra della finestra di pesca.")
    right_bottom = prompt_point("Posiziona il mouse sul secondo angolo e premi Invio.")

    left = min(left_top["x"], right_bottom["x"])
    top = min(left_top["y"], right_bottom["y"])
    width = abs(right_bottom["x"] - left_top["x"])
    height = abs(right_bottom["y"] - left_top["y"])

    if width < 120 or height < 120:
        print("Area troppo piccola. Usa un'area più grande e riprova.")
        sys.exit(1)

    return {"left": left, "top": top, "width": width, "height": height}


def human_move_and_click(x, y, button="left", duration=None):
    duration = duration or random.uniform(0.18, 0.4)
    jitter_x = random.randint(-5, 5)
    jitter_y = random.randint(-5, 5)
    target_x = x + jitter_x
    target_y = y + jitter_y
    if directinput is not None:
        try:
            directinput.moveTo(target_x, target_y, duration=duration)
            human_sleep(0.05, 0.18)
            directinput.click(button=button)
            return
        except Exception:
            pass
    pyautogui.moveTo(target_x, target_y, duration=duration)
    human_sleep(0.05, 0.18)
    pyautogui.click(button=button)


def human_right_click(x, y, duration=None):
    human_move_and_click(x, y, button="right", duration=duration)


def human_left_click(x, y, duration=None):
    human_move_and_click(x, y, button="left", duration=duration)


def activate_window(config):
    window = config.get("window_rect")
    title = config.get("window_title")
    process_name = config.get("window_process_name")

    if gw is not None:
        for win in gw.getAllWindows():
            if title and title.lower() in win.title.lower():
                try:
                    win.activate()
                    return True
                except Exception:
                    pass
            if window and win.left == window["left"] and win.top == window["top"] and win.width == window["width"] and win.height == window["height"]:
                try:
                    win.activate()
                    return True
                except Exception:
                    pass
        if process_name:
            try:
                import win32process
                import psutil
                for win in gw.getAllWindows():
                    if win.width <= 0 or win.height <= 0:
                        continue
                    try:
                        _, pid = win32process.GetWindowThreadProcessId(win._hWnd)
                        proc = psutil.Process(pid)
                        if proc.name().lower() == process_name.lower():
                            try:
                                win.activate()
                                return True
                            except Exception:
                                pass
                    except Exception:
                        pass
            except ImportError:
                pass

    if platform.system() == "Windows":
        try:
            import win32con
            import win32gui
            import win32process
            import psutil

            def enum_windows(hwnd, results):
                if not win32gui.IsWindowVisible(hwnd):
                    return
                title_text = win32gui.GetWindowText(hwnd)
                left, top, right, bottom = win32gui.GetWindowRect(hwnd)
                if title and title.lower() in title_text.lower():
                    results.append(hwnd)
                    return
                if process_name:
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    try:
                        proc = psutil.Process(pid)
                        if proc.name().lower() == process_name.lower():
                            results.append(hwnd)
                            return
                    except Exception:
                        pass
                if window and left == window["left"] and top == window["top"] and right - left == window["width"] and bottom - top == window["height"]:
                    results.append(hwnd)

            results = []
            win32gui.EnumWindows(enum_windows, results)
            if results:
                handle = results[0]
                win32gui.ShowWindow(handle, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(handle)
                return True
        except ImportError:
            pass
    return False


def ensure_active_window(config, retries=3):
    for attempt in range(retries):
        if activate_window(config):
            human_sleep(0.2, 0.5)
            return True
        human_sleep(0.4, 0.8)
    return False


def press_space():
    if directinput is not None:
        directinput.press("space")
    else:
        pyautogui.press("space")


def click_bait(config):
    if not ensure_active_window(config):
        print("Attenzione: non sono riuscito a mettere Metin2 in primo piano prima di cliccare l'esca.")
    bait = config["bait_point"]
    print(f"Cliccare esca in {bait['x']}, {bait['y']}")
    human_right_click(bait["x"], bait["y"])


def get_fishing_roi(config):
    roi = config.get("fishing_roi", {})
    return roi


def capture_roi(config):
    roi = get_fishing_roi(config)
    screenshot = pyautogui.screenshot(region=(roi["left"], roi["top"], roi["width"], roi["height"]))
    frame = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
    return frame


def find_fish_shadow(config):
    frame = capture_roi(config)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (11, 11), 0)
    _, thresh = cv2.threshold(blurred, config.get("dark_threshold", 100), 255, cv2.THRESH_BINARY_INV)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)

    height, width = thresh.shape
    mask = np.zeros_like(thresh)
    radius = min(width, height) // 2 - 12
    cv2.circle(mask, (width // 2, height // 2), radius, 255, -1)
    thresh = cv2.bitwise_and(thresh, thresh, mask=mask)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    best = max(contours, key=cv2.contourArea)
    if cv2.contourArea(best) < config.get("min_fish_area", 160):
        return None

    x, y, w, h = cv2.boundingRect(best)
    center_x = x + w // 2
    center_y = y + h // 2
    return center_x, center_y


def is_fishing_window_open(config):
    frame = capture_roi(config)
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)
    mean_h = np.mean(h)
    mean_s = np.mean(s)
    mean_v = np.mean(v)
    return mean_s > 40 and 80 <= mean_h <= 140 and mean_v > 60


def wait_for_fishing_window(config, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_fishing_window_open(config):
            return True
        human_sleep(0.2, 0.5)
    return False


def click_fish(config, fish_point):
    roi = config["fishing_roi"]
    x = roi["left"] + fish_point[0]
    y = roi["top"] + fish_point[1]
    print(f"Clicco sul pesce a {x}, {y}")
    human_move_and_click(x, y, button="left")


def validate_config(config):
    bait = config.get("bait_point", {})
    roi = config.get("fishing_roi", {})
    if bait.get("x", 0) <= 0 or bait.get("y", 0) <= 0:
        print("Coordinate esca non valide nel config. Esegui --calibrate o --auto.")
        sys.exit(1)
    if roi.get("width", 0) < 120 or roi.get("height", 0) < 120:
        print("Area pesca non valida nel config. Esegui --calibrate o --auto.")
        sys.exit(1)


def run_bot(config, rounds):
    if config.get("use_window_detection", False) and not config.get("window_rect"):
        if not setup_auto_config(config):
            print("Impossibile rilevare la finestra Metin2 automaticamente. Assicurati che il gioco sia aperto e visibile.")
            sys.exit(1)
    validate_config(config)
    print("Avvio bot pesca automatico. Assicurati che Metin2 sia in primo piano.")

    for round_index in range(1, rounds + 1):
        print(f"\n=== Round {round_index}/{rounds} ===")
        if not activate_window(config):
            print("Attenzione: non sono riuscito a portare Metin2 in primo piano.")
        human_sleep(0.3, 0.6)
        click_bait(config)
        human_sleep(0.6, 1.1)

        if not activate_window(config):
            print("Attenzione: non sono riuscito a portare Metin2 in primo piano prima di premere spazio.")
        press_space()
        human_sleep(0.6, 0.9)

        if not wait_for_fishing_window(config, timeout=10):
            print("Attenzione: la finestra di pesca non è apparsa. Riprovare il round.")
            continue

        click_count = 0
        timeout = time.time() + 90
        while time.time() < timeout:
            if not is_fishing_window_open(config):
                print("Finestra pesca chiusa, round terminato.")
                break

            fish_point = find_fish_shadow(config)
            if fish_point is not None:
                click_fish(config, fish_point)
                click_count += 1
                human_sleep(0.9, 1.2)
            else:
                human_sleep(0.18, 0.4)

        if click_count < 3:
            print("Attenzione: non ho trovato tutti i 3 colpi. Riprovare la prossima volta.")
        else:
            print("Pesca completata correttamente.")

        human_sleep(2.0, 3.2)


def create_default_config():
    if os.path.exists(CONFIG_PATH):
        print(f"Il file {CONFIG_PATH} esiste già. Non viene sovrascritto.")
        return
    save_config(DEFAULT_CONFIG)


def main():
    parser = argparse.ArgumentParser(description="Bot di pesca per Metin2 con calibratura manuale e auto-detection.")
    parser.add_argument("--calibrate", action="store_true", help="Configura le coordinate della finestra di pesca e dell'esca.")
    parser.add_argument("--auto", action="store_true", help="Trova automaticamente Metin2 e l'area di pesca.")
    parser.add_argument("--rounds", type=int, default=10, help="Numero di round di pesca da eseguire.")
    parser.add_argument("--show-config", action="store_true", help="Mostra la configurazione corrente.")
    args = parser.parse_args()

    if args.calibrate:
        config = DEFAULT_CONFIG.copy()
        config["use_window_detection"] = False
        print("Calibrazione dell'esca:")
        config["bait_point"] = prompt_point("Posiziona il mouse sull'icona dell'esca e premi Invio.")
        config["fishing_roi"] = prompt_roi()
        config["dark_threshold"] = 100
        config["min_fish_area"] = 160
        save_config(config)
        return

    if args.auto:
        config = DEFAULT_CONFIG.copy()
        config["use_window_detection"] = True
        success = setup_auto_config(config)
        if not success:
            print("Impossibile rilevare la finestra Metin2 automaticamente. Assicurati che il gioco sia aperto e visibile.")
            sys.exit(1)
        save_config(config)
        print("Configurazione automatica salvata. Avvio il bot ora.")
        run_bot(config, args.rounds)
        return

    if args.show_config:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as handle:
                print(handle.read())
        else:
            print(f"Nessun config trovato. Crea {CONFIG_PATH} con --calibrate o --auto.")
        return

    if not os.path.exists(CONFIG_PATH):
        create_default_config()
        print("Esegui --calibrate o --auto prima di avviare il bot.")
        sys.exit(1)

    config = load_config()
    if config.get("use_window_detection", False):
        roi = config.get("fishing_roi", {})
        bait = config.get("bait_point", {})
        needs_auto = (
            not config.get("window_rect")
            or roi.get("width", 0) < 120
            or roi.get("height", 0) < 120
            or bait.get("x", 0) <= 0
            or bait.get("y", 0) <= 0
        )
        if needs_auto:
            if not setup_auto_config(config):
                print("Impossibile rigenerare la configurazione automatica. Assicurati che il gioco sia aperto e visibile.")
                sys.exit(1)
    run_bot(config, args.rounds)


if __name__ == "__main__":
    main()
