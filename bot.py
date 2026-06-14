import argparse
import json
import os
import random
import sys
import time

import cv2
import numpy as np
import pyautogui

try:
    import pydirectinput as directinput
except ImportError:
    directinput = None

CONFIG_PATH = "config.json"
DEFAULT_CONFIG = {
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
    pyautogui.moveTo(target_x, target_y, duration=duration)
    human_sleep(0.05, 0.18)
    pyautogui.click(button=button)


def press_space():
    if directinput is not None:
        directinput.press("space")
    else:
        pyautogui.press("space")


def click_bait(config):
    bait = config["bait_point"]
    print(f"Cliccare esca in {bait['x']}, {bait['y']}")
    human_move_and_click(bait["x"], bait["y"], button="right")


def capture_roi(config):
    roi = config["fishing_roi"]
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
        print("Coordinate esca non valide nel config. Esegui --calibrate.")
        sys.exit(1)
    if roi.get("width", 0) < 120 or roi.get("height", 0) < 120:
        print("Area pesca non valida nel config. Esegui --calibrate.")
        sys.exit(1)


def run_bot(config, rounds):
    validate_config(config)
    print("Avvio bot pesca automatico. Assicurati che Metin2 sia in primo piano.")
    for round_index in range(1, rounds + 1):
        print(f"\n=== Round {round_index}/{rounds} ===")
        click_bait(config)
        human_sleep(0.6, 1.1)

        press_space()
        human_sleep(1.2, 1.8)

        click_count = 0
        timeout = time.time() + 25
        while click_count < 3 and time.time() < timeout:
            fish_point = find_fish_shadow(config)
            if fish_point is not None:
                click_fish(config, fish_point)
                click_count += 1
                human_sleep(0.35, 0.7)
            else:
                human_sleep(0.18, 0.3)

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
    parser = argparse.ArgumentParser(description="Bot di pesca per Metin2 con calibrazione manuale.")
    parser.add_argument("--calibrate", action="store_true", help="Configura le coordinate della finestra di pesca e dell'esca.")
    parser.add_argument("--rounds", type=int, default=10, help="Numero di round di pesca da eseguire.")
    parser.add_argument("--show-config", action="store_true", help="Mostra la configurazione corrente.")
    args = parser.parse_args()

    if args.calibrate:
        config = DEFAULT_CONFIG.copy()
        print("Calibrazione dell'esca:")
        config["bait_point"] = prompt_point("Posiziona il mouse sull'icona dell'esca e premi Invio.")
        config["fishing_roi"] = prompt_roi()
        config["dark_threshold"] = 100
        config["min_fish_area"] = 160
        save_config(config)
        return

    if args.show_config:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as handle:
                print(handle.read())
        else:
            print(f"Nessun config trovato. Crea {CONFIG_PATH} con --calibrate.")
        return

    if not os.path.exists(CONFIG_PATH):
        create_default_config()
        print("Esegui --calibrate prima di avviare il bot.")
        sys.exit(1)

    config = load_config()
    run_bot(config, args.rounds)


if __name__ == "__main__":
    main()
