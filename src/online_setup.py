import socket
import pygame
import threading
import base64

PORT = 5000  
BUFFER_SIZE = 1024

def ip_to_code(ip_str):
    ip_bytes = bytes(map(int, ip_str.split('.')))
    code = base64.b85encode(ip_bytes).decode()
    return code

def code_to_ip(code):
    ip_bytes = base64.b85decode(code.encode())
    ip_str = '.'.join(map(str, ip_bytes))
    return ip_str

def online_setup(screen, host):
    connected_msg = None
    WIDTH, HEIGHT = screen.get_size()
    BLACK = (0, 0, 0)
    FONT_LARGE = pygame.font.SysFont("arial", 48)
    WHITE = (255, 255, 255)
    input_box = pygame.Rect(WIDTH // 2 - 150, HEIGHT // 2 + 100, 300, 50)
    input_text = ""
    is_host = host
    conn = None

    def draw_centered_text(text, y, font, color=WHITE):
        surface = font.render(text, True, color)
        rect = surface.get_rect(center=(WIDTH // 2, y))
        screen.blit(surface, rect)

    clock = pygame.time.Clock()

    if is_host:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(('', PORT))
        server_socket.listen(1)
        local_ip = socket.gethostbyname(socket.gethostname())
        invite_code = ip_to_code(local_ip)
        waiting = True
        def wait_for_connection():
            nonlocal conn, waiting, connected_msg
            conn, addr = server_socket.accept()
            connected_msg = f"Connected by {addr}"
            waiting = False
        threading.Thread(target=wait_for_connection, daemon=True).start()
        while waiting:
            screen.fill(BLACK)
            draw_centered_text("Waiting for a player to join...", HEIGHT // 2 - 60, FONT_LARGE)
            draw_centered_text(f"Your Invite Code: {invite_code}", HEIGHT // 2 + 10, FONT_LARGE)
            draw_centered_text(f"Port: {PORT}", HEIGHT // 2 + 80, FONT_LARGE)
            pygame.display.update()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    exit()
            clock.tick(30)
        screen.fill(BLACK)
        draw_centered_text(connected_msg, HEIGHT // 2 - 40, FONT_LARGE)
        pygame.display.update()
        pygame.time.delay(2500)
        server_socket.close()
    else:
        inputting_code = True
        while inputting_code:
            screen.fill(BLACK)
            draw_centered_text("Enter Invite Code", 100, FONT_LARGE)
            pygame.draw.rect(screen, WHITE, input_box, border_radius=10)
            ip_surface = FONT_LARGE.render(input_text + "|", True, BLACK)
            screen.blit(ip_surface, ip_surface.get_rect(center=input_box.center))
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    exit()
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_BACKSPACE:
                        input_text = input_text[:-1]
                    elif event.key == pygame.K_RETURN:
                        code = input_text.strip()
                        try:
                            if len(code) == 0:
                                raise ValueError("Code must be more than 1 character")
                            host_ip = code_to_ip(code)
                            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            client_socket.connect((host_ip, PORT))
                            conn = client_socket
                            inputting_code = False
                        except (ConnectionRefusedError, socket.gaierror, TimeoutError, OSError, ValueError, base64.binascii.Error) as e:
                            input_text = ""
                            screen.fill(BLACK)
                            draw_centered_text("Failed to connect. Try again.", 40, FONT_LARGE, color=(255, 0, 0))
                            pygame.display.update()
                            pygame.time.delay(1500)
                    else:
                        if len(input_text) < 15:
                            input_text += event.unicode

            pygame.display.update()
            clock.tick(30)

    return conn
