import socket
import pygame
import threading
import base64
import hmac
import ipaddress
import secrets
import shutil
import subprocess
from .network import ProtocolError, receive_message, send_message

PORT = 5000  
BUFFER_SIZE = 1024


def copy_to_clipboard(text):
    try:
        pygame.scrap.init()
        pygame.scrap.put(pygame.SCRAP_TEXT, text.encode("utf-8"))
        return True
    except Exception:
        clip_command = shutil.which("clip.exe")
        if clip_command is None:
            return False
        try:
            subprocess.run(
                [clip_command], input=text.encode("utf-8"), check=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=5,
            )
            return True
        except (OSError, subprocess.SubprocessError):
            return False


def paste_from_clipboard():
    try:
        pygame.scrap.init()
        content = pygame.scrap.get(pygame.SCRAP_TEXT)
        if isinstance(content, bytes):
            return content.decode("utf-8", errors="ignore").rstrip("\0").strip()
        if isinstance(content, str):
            return content.rstrip("\0").strip()
    except Exception:
        pass

    powershell = shutil.which("powershell.exe") or shutil.which("pwsh.exe")
    if powershell is not None:
        try:
            result = subprocess.run(
                [powershell, "-NoProfile", "-NonInteractive", "-Command", "Get-Clipboard -Raw"],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=5,
            )
            raw = result.stdout
            if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
                text = raw.decode("utf-16", errors="ignore")
            else:
                text = raw.decode("utf-8-sig", errors="ignore")
            return text.replace("\0", "").strip()
        except (OSError, subprocess.SubprocessError):
            pass
    return ""


def ip_to_code(ip_str, token=None):
    ip_bytes = socket.inet_aton(ip_str)
    token = token or secrets.token_bytes(16)
    if len(token) != 16:
        raise ValueError("Invite tokens must contain 16 bytes.")
    code = base64.b85encode(ip_bytes + token).decode()
    return code

def code_to_invite(code):
    try:
        invite = base64.b85decode(code.encode('ascii'))
        if len(invite) != 20:
            raise ValueError
        ip = socket.inet_ntoa(invite[:4])
        ipaddress.IPv4Address(ip)
        return ip, invite[4:]
    except (UnicodeEncodeError, ValueError, base64.binascii.Error) as exc:
        raise ValueError("Invalid invite code.") from exc

def code_to_ip(code):
    return code_to_invite(code)[0]

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
        invite_token = secrets.token_bytes(16)
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(('', PORT))
        server_socket.listen(1)
        local_ip = socket.gethostbyname(socket.gethostname())
        invite_code = ip_to_code(local_ip, invite_token)
        copy_button = pygame.Rect(WIDTH // 2 - 100, HEIGHT // 2 + 35, 200, 45)
        copy_status = "Click Copy Code or press Ctrl+C"
        waiting = True
        def wait_for_connection():
            nonlocal conn, waiting, connected_msg
            while waiting:
                candidate = None
                try:
                    candidate, addr = server_socket.accept()
                    candidate.settimeout(0.5)
                    auth = receive_message(candidate, idle_timeout=10)
                    valid = (auth.get('type') == 'auth'
                             and isinstance(auth.get('token'), str)
                             and hmac.compare_digest(auth['token'], invite_token.hex()))
                    if not valid:
                        candidate.close()
                        continue
                    send_message(candidate, {'type': 'auth_ok'})
                    conn = candidate
                    connected_msg = f"Connected by {addr}"
                    waiting = False
                except (socket.timeout, TimeoutError):
                    continue
                except (ConnectionError, OSError, ProtocolError, ValueError):
                    try:
                        candidate.close()
                    except (AttributeError, OSError):
                        pass
                    continue
        threading.Thread(target=wait_for_connection, daemon=True).start()
        while waiting:
            screen.fill(BLACK)
            draw_centered_text("Waiting for a player to join...", HEIGHT // 2 - 60, FONT_LARGE)
            draw_centered_text(f"Your Invite Code: {invite_code}", HEIGHT // 2 + 10, FONT_LARGE)
            pygame.draw.rect(screen, (70, 130, 180), copy_button, border_radius=8)
            copy_label = "Copied!" if copy_status == "Copied to clipboard" else "Copy Code"
            copy_surface = pygame.font.SysFont("arial", 24).render(copy_label, True, WHITE)
            screen.blit(copy_surface, copy_surface.get_rect(center=copy_button.center))
            draw_centered_text(copy_status, HEIGHT // 2 + 92, pygame.font.SysFont("arial", 20))
            draw_centered_text(f"Port: {PORT}", HEIGHT // 2 + 125, pygame.font.SysFont("arial", 24))
            pygame.display.update()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    exit()
                if (event.type == pygame.MOUSEBUTTONDOWN
                        and getattr(event, "button", 0) in (4, 5)):
                    continue
                if event.type == pygame.MOUSEBUTTONDOWN and copy_button.collidepoint(event.pos):
                    copy_status = ("Copied to clipboard" if copy_to_clipboard(invite_code)
                                   else "Clipboard unavailable; copy the code manually")
                elif (event.type == pygame.KEYDOWN and event.key == pygame.K_c
                      and getattr(event, "mod", 0) & pygame.KMOD_CTRL):
                    copy_status = ("Copied to clipboard" if copy_to_clipboard(invite_code)
                                   else "Clipboard unavailable; copy the code manually")
            clock.tick(30)
        screen.fill(BLACK)
        draw_centered_text(connected_msg, HEIGHT // 2 - 40, FONT_LARGE)
        pygame.display.update()
        pygame.time.delay(2500)
        server_socket.close()
    else:
        inputting_code = True
        clipboard_hint = "Paste the invite code with Ctrl+V"
        code_font = pygame.font.SysFont("arial", 20)
        while inputting_code:
            screen.fill(BLACK)
            draw_centered_text("Enter Invite Code", 100, FONT_LARGE)
            pygame.draw.rect(screen, WHITE, input_box, border_radius=10)
            ip_surface = code_font.render(input_text + "|", True, BLACK)
            screen.blit(ip_surface, ip_surface.get_rect(center=input_box.center))
            draw_centered_text(clipboard_hint, HEIGHT // 2 + 165, code_font)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    exit()
                elif event.type == pygame.KEYDOWN:
                    if (event.key == pygame.K_v
                            and getattr(event, "mod", 0) & pygame.KMOD_CTRL):
                        pasted_code = paste_from_clipboard()
                        if pasted_code:
                            input_text = pasted_code[:32]
                    elif event.key == pygame.K_BACKSPACE:
                        input_text = input_text[:-1]
                    elif event.key == pygame.K_RETURN:
                        code = input_text.strip()
                        try:
                            if len(code) == 0:
                                raise ValueError("Code must be more than 1 character")
                            host_ip, invite_token = code_to_invite(code)
                            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            client_socket.settimeout(10)
                            client_socket.connect((host_ip, PORT))
                            send_message(client_socket, {'type': 'auth', 'token': invite_token.hex()})
                            confirmation = receive_message(client_socket, idle_timeout=10)
                            if confirmation.get('type') != 'auth_ok':
                                raise ConnectionError("Host authentication failed.")
                            client_socket.settimeout(0.1)
                            conn = client_socket
                            inputting_code = False
                        except (ConnectionRefusedError, socket.gaierror, TimeoutError, OSError, ValueError, base64.binascii.Error) as e:
                            try:
                                client_socket.close()
                            except (UnboundLocalError, OSError):
                                pass
                            input_text = ""
                            screen.fill(BLACK)
                            draw_centered_text("Failed to connect. Try again.", 40, FONT_LARGE, color=(255, 0, 0))
                            pygame.display.update()
                            pygame.time.delay(1500)
                    else:
                        if len(input_text) < 32 and event.unicode.isprintable():
                            input_text += event.unicode

            pygame.display.update()
            clock.tick(30)

    return conn
