#!/usr/bin/env python3
"""
Project Invisible v3 - Decoder
Decodes invisible Unicode text (v1, v2, and v3 formats).
v3 auto-detects and handles compression. Supports --media flag.
"""

import sys
import os
import gzip
import getpass
import select
import time

CHARS = [
    '\u200b',
    '\u200c',
    '\u200d',
    '\u2060',
]
CHAR_TO_IDX = {ch: i for i, ch in enumerate(CHARS)}

ZERO = '\u200b'
ONE = '\u200c'
V2_MARKER = '\u200d'
DEFAULT_INPUT = "en_file.txt"
DEFAULT_OUTPUT = "decoded"

try:
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.exceptions import InvalidTag
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

V3_MAGIC = b'\xFE\xCE\x03'
ALGO_GZIP = 0
ALGO_BROTLI = 1
ALGO_LZMA = 2
ALGO_NONE = 0xFF
FLAG_MEDIA = 1

SALT_LENGTH = 16
NONCE_LENGTH = 12
KEY_LENGTH = 32
PBKDF2_ITERATIONS = 1_000_000

BINARY_EXTENSIONS = [
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.svg', '.webp',
    '.zip', '.tar', '.gz', '.rar', '.7z', '.bz2',
    '.exe', '.dll', '.so', '.bin', '.deb', '.rpm',
    '.mp3', '.wav', '.flac', '.mp4', '.avi', '.mov', '.mkv'
]


class C:
    RESET   = '\033[0m'
    BOLD    = '\033[1m'
    ITALIC  = '\033[3m'
    DIM     = '\033[2m'
    UNDER   = '\033[4m'
    RED     = '\033[91m'
    GREEN   = '\033[92m'
    YELLOW  = '\033[93m'
    BLUE    = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN    = '\033[96m'
    WHITE   = '\033[97m'

    TITLE   = BOLD + CYAN
    HEADER  = BOLD + YELLOW
    SUCCESS = BOLD + GREEN
    ERROR   = BOLD + RED
    INFO    = DIM + CYAN
    HINT    = ITALIC + DIM
    BOLD_WHITE = BOLD + WHITE
    BOLD_MAGENTA = BOLD + MAGENTA


class Progress:
    def __init__(self, label: str = 'Processing'):
        self.label = label
        self._start_time = 0.0
        self._current = 0
        self._total = 0
        self._last_update = 0.0
        self._enabled = sys.stdout.isatty()
        self._has_started = False

    def start(self, total: int):
        if not self._enabled or total < 100:
            return
        self._start_time = time.time()
        self._current = 0
        self._total = total
        self._last_update = 0.0
        self._has_started = True
        self._render()

    def update(self, n: int = 1):
        if not self._has_started:
            return
        self._current += n
        now = time.time()
        if now - self._last_update >= 0.1:
            self._render()
            self._last_update = now

    def _render(self):
        pct = self._current / self._total if self._total > 0 else 0
        elapsed = time.time() - self._start_time
        bar_len = 18
        filled = int(bar_len * pct)
        bar = '█' * filled + '░' * (bar_len - filled)
        sys.stdout.write(f'\r  [{C.CYAN}{bar}{C.RESET}] {pct * 100:3.0f}%  {C.DIM}{elapsed:.1f}s{C.RESET}')
        sys.stdout.flush()

    def done(self):
        if not self._has_started:
            return
        self._current = self._total
        self._render()
        sys.stdout.write(f'  Done.\n')
        sys.stdout.flush()


def color_print(text: str, color: str = '') -> None:
    print(f"{color}{text}{C.RESET}")


def color_input(prompt: str, color: str = C.BOLD_MAGENTA) -> str:
    return input(f"{color}{prompt}{C.RESET}")


BOX_HLINE = '─'
BOX_VLINE = '│'
BOX_TL = '╭'
BOX_TR = '╮'
BOX_BL = '╰'
BOX_BR = '╯'


def draw_box(lines: list, width: int = 60, color: str = C.CYAN, title: str = '') -> None:
    inner_width = width - 2
    top_line = BOX_TL + BOX_HLINE * (inner_width) + BOX_TR
    color_print(f"  {top_line}", color)
    if title:
        title_line = BOX_VLINE + f" {title} "
        title_line = title_line.ljust(inner_width + 1) + BOX_VLINE
        color_print(f"  {title_line}", C.BOLD + color)
        sep_line = BOX_TL + BOX_HLINE * (inner_width) + BOX_TR
        color_print(f"  {sep_line}", color)
    for line in lines:
        padded = BOX_VLINE + f" {line}"
        padded = padded.ljust(inner_width + 2) + BOX_VLINE
        color_print(f"  {padded}", C.WHITE)
    bot_line = BOX_BL + BOX_HLINE * (inner_width) + BOX_BR
    color_print(f"  {bot_line}", color)


def _decode_v1(encoded: str) -> bytes:
    binary = []
    for ch in encoded:
        if ch == ZERO:
            binary.append('0')
        elif ch == ONE:
            binary.append('1')
    binary_str = ''.join(binary)
    data = bytearray()
    for i in range(0, len(binary_str), 8):
        byte_bits = binary_str[i:i+8]
        if len(byte_bits) == 8:
            data.append(int(byte_bits, 2))
    return bytes(data)


def _decode_v2_chars(chars: str, prog: Progress = None) -> bytes:
    binary = []
    if prog:
        prog.start(len(chars))
    for ch in chars:
        if ch in CHAR_TO_IDX:
            v = CHAR_TO_IDX[ch]
            binary.append('1' if v & 2 else '0')
            binary.append('1' if v & 1 else '0')
        if prog:
            prog.update(1)
    if prog:
        prog.done()
    binary_str = ''.join(binary)
    data = bytearray()
    for i in range(0, len(binary_str), 8):
        byte_bits = binary_str[i:i+8]
        if len(byte_bits) == 8:
            data.append(int(byte_bits, 2))
    return bytes(data)


def invisible_to_bytes(encoded: str, prog: Progress = None) -> tuple:
    if not encoded:
        return b'', None
    first = encoded[0]
    if first == CHARS[3] or first == CHARS[2]:
        raw = _decode_v2_chars(encoded[1:], prog)
        if not raw:
            return b'', None

        if len(raw) >= 3 and raw[:3] == V3_MAGIC:
            return raw, None
        elif first == CHARS[3]:
            name_len = raw[0]
            name = raw[1:1+name_len].decode('utf-8', errors='replace') if name_len > 0 else None
            return raw[1+name_len:], name
        else:
            return raw, None
    return _decode_v1(encoded), None


def decompress_v3(data: bytes, algo: int) -> bytes:
    if algo == ALGO_NONE:
        return data
    elif algo == ALGO_GZIP:
        return gzip.decompress(data)
    elif algo == ALGO_BROTLI:
        try:
            import brotli
            return brotli.decompress(data)
        except ImportError:
            raise ValueError("brotli is required to decode this file. Install with: pip install brotli")
    elif algo == ALGO_LZMA:
        try:
            import lzma
            return lzma.decompress(data)
        except ImportError:
            raise ValueError("lzma is required to decode this file.")
    else:
        raise ValueError(f"Unknown compression algorithm: {algo}")


def bytes_to_text(data: bytes) -> str:
    return data.decode('utf-8', errors='ignore')


def decrypt(encrypted_blob: bytes, password: str) -> bytes:
    if len(encrypted_blob) < SALT_LENGTH + NONCE_LENGTH + 16:
        raise ValueError("Data too short for decryption")
    salt = encrypted_blob[:SALT_LENGTH]
    nonce = encrypted_blob[SALT_LENGTH:SALT_LENGTH+NONCE_LENGTH]
    tag = encrypted_blob[-16:]
    ciphertext = encrypted_blob[SALT_LENGTH+NONCE_LENGTH:-16]
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=KEY_LENGTH, salt=salt, iterations=PBKDF2_ITERATIONS)
    key = kdf.derive(password.encode('utf-8'))
    return AESGCM(key).decrypt(nonce, ciphertext + tag, None)


def validate_file_exists(path: str) -> None:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"File not found: {path}")


def get_file_extension(filepath: str) -> str:
    _, ext = os.path.splitext(filepath)
    return ext.lower()


def is_binary_output(filepath: str) -> bool:
    return get_file_extension(filepath) in BINARY_EXTENSIONS


def get_password(prompt: str = "Enter password: ") -> str:
    return getpass.getpass(prompt)


def show_help() -> None:
    color_print("\n", C.RESET)
    draw_box([], width=62, color=C.CYAN, title=f" {C.BOLD_WHITE}Project Invisible v3 - Decoder{C.CYAN} ")
    color_print("", C.RESET)

    color_print(f"  {C.HEADER}📖 USAGE{C.RESET}", C.HEADER)
    color_print(f"  {C.BOLD}1.{C.RESET} Decode from file:", C.WHITE)
    draw_box(['python3 de.py <file> [options]'], width=62, color=C.GREEN)
    color_print("", C.RESET)
    color_print(f"  {C.BOLD}2.{C.RESET} Decode from pipe:", C.WHITE)
    draw_box(['cat en_file.txt | python3 de.py [options]'], width=62, color=C.GREEN)
    color_print("", C.RESET)

    color_print(f"  {C.HEADER}⚙️  OPTIONS{C.RESET}", C.HEADER)
    options = [
        f"{C.BOLD}--save <file>{C.RESET}      Save output (auto-detects text or binary)",
        f"{C.BOLD}--decrypt{C.RESET}          Decrypt data with AES-256-GCM {C.DIM}(prompts for password){C.RESET}",
        f"{C.BOLD}--media{C.RESET}             Decode media-encoded files {C.DIM}(required for images, video, etc.){C.RESET}",
        f"{C.BOLD}--help{C.RESET}              Show this help message",
    ]
    for opt in options:
        color_print(f"  {BOX_VLINE} {opt}", C.WHITE)
    color_print(f"  {BOX_VLINE}", C.WHITE)

    color_print(f"\n  {C.HEADER}💡 EXAMPLES{C.RESET}", C.HEADER)
    examples = [
        (f"{C.GREEN}#{C.RESET} Decode text to stdout", f'python3 de.py en_file.txt'),
        (f"{C.GREEN}#{C.RESET} Save decoded text", f'python3 de.py en_file.txt --save output.txt'),
        (f"{C.GREEN}#{C.RESET} Restore embedded file", f'python3 de.py encoded.txt --save restored.pdf'),
        (f"{C.GREEN}#{C.RESET} Decode media file", f'python3 de.py encoded.txt --media --save restored.jpg'),
        (f"{C.GREEN}#{C.RESET} Decrypt & restore", f'python3 de.py secret.txt --decrypt --save restored.pdf'),
        (f"{C.GREEN}#{C.RESET} Pipe input", f'cat en_file.txt | python3 de.py'),
    ]
    for label, cmd in examples:
        color_print(f"  {BOX_VLINE} {label}", C.WHITE)
        color_print(f"  {BOX_VLINE}   {C.BOLD_WHITE}{cmd}{C.RESET}", C.DIM)

    color_print(f"\n  {C.HEADER}📝 NOTES{C.RESET}", C.HEADER)
    notes = [
        f"  {BOX_VLINE}  Default output: print to {C.CYAN}stdout{C.RESET} (use --save to write file)",
        f"  {BOX_VLINE}  Auto-detects v1, v2, and v3 encoding formats",
        f"  {BOX_VLINE}  v3 files auto-decompress (no separate flag needed)",
        f"  {BOX_VLINE}  Media-encoded files require {C.BOLD}--media{C.RESET} flag",
        f"  {BOX_VLINE}  Wrong password will abort with error",
        f"  {BOX_VLINE}  Decryption requires {C.CYAN}cryptography{C.RESET} package",
    ]
    for note in notes:
        color_print(f"  {BOX_VLINE} {note}", C.WHITE)

    color_print(f"\n  {C.DIM}{'─' * 50}{C.RESET}", C.RESET)
    credits = [
        f"  {C.DIM}Made by {C.BOLD}DarkSahdow{C.RESET}",
        f"  {C.DIM}X: {C.CYAN}https://x.com/darkshadow2bd{C.RESET}",
        f"  {C.DIM}Telegram: {C.CYAN}https://t.me/ShellSec{C.RESET}",
    ]
    for credit in credits:
        color_print(credit, C.DIM)
    color_print(f"  {C.DIM}{'─' * 50}{C.RESET}", C.RESET)
    color_print("", C.RESET)


def parse_arguments(args: list) -> dict:
    result = {'input_file': None, 'output_file': None, 'decrypt': False, 'media': False, 'help': False}
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ('--help', '-h'):
            result['help'] = True
            return result
        elif arg == '--save':
            if i + 1 >= len(args):
                color_print("[!] Error: --save requires a filename.", C.ERROR)
                sys.exit(1)
            result['output_file'] = args[i + 1]
            i += 1
        elif arg == '--decrypt':
            result['decrypt'] = True
        elif arg == '--media':
            result['media'] = True
        elif not arg.startswith('--'):
            if result['input_file'] is None:
                result['input_file'] = arg
            else:
                color_print(f"[!] Unexpected argument: {arg}", C.ERROR)
                sys.exit(1)
        else:
            color_print(f"[!] Unknown option: {arg}", C.ERROR)
            sys.exit(1)
        i += 1
    return result


def read_input(config: dict) -> str:
    if config['input_file']:
        try:
            validate_file_exists(config['input_file'])
            with open(config['input_file'], 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError as e:
            color_print(f"[!] {e}", C.ERROR)
            sys.exit(1)
        except UnicodeDecodeError:
            color_print(f"[!] Error: Cannot decode '{config['input_file']}' as text.", C.ERROR)
            color_print("    The file may be a binary file. This tool only decodes text files", C.HINT)
            color_print("    that were encoded with de.py.", C.HINT)
            sys.exit(1)
    if select.select([sys.stdin], [], [], 0.0)[0]:
        return sys.stdin.read()
    return ""


def write_output(filepath: str, data: bytes) -> None:
    if is_binary_output(filepath):
        with open(filepath, 'wb') as f:
            f.write(data)
        color_print(f"[+] Saved file -> {filepath} ({len(data)} bytes)", C.SUCCESS)
    else:
        text = bytes_to_text(data)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(text)
        color_print(f"[+] Saved text -> {filepath}", C.SUCCESS)


def main():
    args = sys.argv[1:]
    if not args:
        if not select.select([sys.stdin], [], [], 0.0)[0]:
            show_help()
            return
    config = parse_arguments(args)
    if config['help']:
        show_help()
        return
    if config['decrypt'] and not HAS_CRYPTO:
        color_print("[!] Error: 'cryptography' package is required for decryption.", C.ERROR)
        color_print("    Install it with: pip install cryptography", C.HINT)
        sys.exit(1)

    encoded = read_input(config)
    if config['input_file']:
        color_print(f"[*] Reading from file: {config['input_file']}", C.INFO)
    if not encoded:
        color_print("[!] Error: No input provided. Use --help for usage.", C.ERROR)
        sys.exit(1)

    try:
        prog = Progress('Decoding')
        raw_data, output_name = invisible_to_bytes(encoded, prog)
    except Exception as e:
        color_print(f"[!] Error decoding invisible characters: {e}", C.ERROR)
        sys.exit(1)

    color_print(f"[*] Decoded {len(encoded)} invisible characters to {len(raw_data)} bytes", C.INFO)

    # Check for v3 format
    if len(raw_data) >= 3 and raw_data[:3] == V3_MAGIC:
        algo = raw_data[3]
        flags = raw_data[4]
        name_len = raw_data[5]
        name_bytes = raw_data[6:6+name_len]

        if name_len > 0:
            output_name = name_bytes.decode('utf-8', errors='replace')

        payload = raw_data[6+name_len:]

        if (flags & FLAG_MEDIA) and not config['media']:
            color_print(f"[!] Error: This file was encoded with media compression.", C.ERROR)
            color_print(f"    Use {C.BOLD}--media{C.RESET} flag to decode it.", C.HINT)
            sys.exit(1)

        if config['decrypt']:
            password = get_password("Enter password: ")
            try:
                payload = decrypt(payload, password)
                color_print("[+] Password correct. Decryption successful!", C.SUCCESS)
            except (InvalidTag, ValueError) as e:
                color_print("[!] Error: Wrong password or corrupted data.", C.ERROR)
                sys.exit(1)

        compressed_size = len(payload)
        try:
            raw_data = decompress_v3(payload, algo)
            color_print(f"[*] Decompressed: {compressed_size} -> {len(raw_data)} bytes ({compressed_size/len(raw_data)*100 if len(raw_data) > 0 else 0:.1f}%)", C.SUCCESS)
        except Exception as e:
            color_print(f"[!] Decompression error: {e}", C.ERROR)
            sys.exit(1)
    elif config['decrypt']:
        try:
            password
        except NameError:
            password = get_password("Enter password: ")
        try:
            raw_data = decrypt(raw_data, password)
            color_print("[+] Password correct. Decryption successful!", C.SUCCESS)
        except (InvalidTag, ValueError) as e:
            color_print("[!] Error: Wrong password or corrupted data.", C.ERROR)
            sys.exit(1)

    save_path = config['output_file']

    if save_path and output_name and output_name != save_path:
        color_print(f"[?] This file has a preset save name: {C.GREEN}{output_name}{C.RESET}", C.YELLOW)
        answer = color_input(f"    Save as {C.BOLD}{output_name}{C.RESET}? [Y/n] ", C.YELLOW)
        if answer.lower() in ('', 'y', 'yes'):
            save_path = output_name

    if save_path:
        write_output(save_path, raw_data)
    elif output_name:
        write_output(output_name, raw_data)
    else:
        text = bytes_to_text(raw_data)
        color_print(f"\n{'='*50}", C.DIM)
        print(text)
        color_print(f"{'='*50}", C.DIM)


if __name__ == "__main__":
    main()
