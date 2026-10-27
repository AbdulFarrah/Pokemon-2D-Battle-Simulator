import os
import sys
import textwrap

# PyInstaller's Windows windowed build leaves standard streams unset.
# The game uses print() for diagnostics, so safely discard that output there.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from src.game import ConnectionLost, Game, RuntimeDataError
from src.network import ProtocolError
from src.base import run_ui_setup
from src.restart import show_restart_prompt


def show_error_message(message):
    print(message)
    screen = pygame.display.set_mode((900, 260))
    pygame.display.set_caption("Pokémon Battle Simulator - Startup Error")
    screen.fill((20, 20, 20))
    font = pygame.font.SysFont("DejaVu Sans", 22)
    lines = textwrap.wrap(message, width=74) or [message]
    for index, line in enumerate(lines[:7]):
        screen.blit(font.render(line, True, (255, 220, 220)), (24, 24 + index * 30))
    screen.blit(font.render("Press any key or close the window to exit.", True, (220, 220, 220)), (24, 230))
    pygame.display.flip()
    clock = pygame.time.Clock()
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT or event.type == pygame.KEYDOWN:
                return
        clock.tick(30)


def close_connection(conn):
    if conn is not None:
        try:
            conn.close()
        except OSError:
            pass


def main():
    pygame.init()
    try:
        runtime_data = Game.load_runtime_data()
    except RuntimeDataError as exc:
        show_error_message(str(exc))
        pygame.quit()
        return 1

    try:
        while True:
            screen, settings = run_ui_setup()
            conn = settings.get("conn")
            try:
                game = Game(settings, screen, runtime_data=runtime_data)
                game.game_loop()
                close_connection(conn)
                if game.forfeit_by is not None:
                    continue
                if not show_restart_prompt(screen):
                    break
            except ConnectionLost:
                close_connection(conn)
                if not show_restart_prompt(screen):
                    break
            except (RuntimeDataError, ProtocolError, ConnectionError, OSError) as exc:
                close_connection(conn)
                show_error_message(f"The match could not continue: {exc}")
                break
    finally:
        pygame.quit()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
