#!/usr/bin/env python3
"""
Project Invisible v3 - Encoder
2-bit encoding using {U+200B, U+200C, U+200D, U+2060}.
Always auto-compresses before encoding. Supports AES-256-GCM encryption.
"""

import sys
import os
import gzip
import getpass
import time
import threading

CHARS = [
    '\u200b',
    '\u200c',
    '\u200d',
    '\u2060',
]

ZERO = '\u200b'
ONE = '\u200c'
CHAR_TO_IDX = {ch: i for i, ch in enumerate(CHARS)}
DEFAULT_FILE = "en_file.txt"

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

COMPRESSED_EXTENSIONS = [
    '.jpg', '.jpeg', '.png', '.gif', '.webp', '.avif', '.heic', '.jxl',
    '.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv',
    '.mp3', '.flac', '.aac', '.ogg', '.opus', '.m4a', '.wma',
    '.zip', '.gz', '.tgz', '.rar', '.7z', '.bz2', '.xz', '.zst',
    '.pdf', '.docx', '.xlsx', '.pptx', '.odt', '.ods', '.odp',
]

TEXT_EXTENSIONS = ['.txt', '.md', '.csv', '.log', '.json', '.xml', '.html', '.css', '.js', '.py', '.sh', '.yml', '.yaml', '.ini', '.cfg']


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
    BG_RED  = '\033[41m'
    BG_GREEN= '\033[42m'
    BG_YELLOW='\033[43m'
    BG_BLUE = '\033[44m'
    BG_MAGENTA='\033[45m'
    BG_CYAN = '\033[46m'
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
BOX_TEE_LEFT = '├'
BOX_TEE_RIGHT = '┤'
BOX_CROSS = '┼'


def draw_box(lines: list, width: int = 60, color: str = C.CYAN, title: str = '') -> None:
    inner_width = width - 2
    top_line = BOX_TL + BOX_HLINE * (inner_width) + BOX_TR
    color_print(f"  {top_line}", color)
    if title:
        title_line = BOX_VLINE + f" {title} "
        title_line = title_line.ljust(inner_width + 1) + BOX_VLINE
        color_print(f"  {title_line}", C.BOLD + color)
        sep_line = BOX_TEE_LEFT + BOX_HLINE * (inner_width) + BOX_TEE_RIGHT
        color_print(f"  {sep_line}", color)
    for line in lines:
        padded = BOX_VLINE + f" {line}"
        padded = padded.ljust(inner_width + 2) + BOX_VLINE
        color_print(f"  {padded}", C.WHITE)
    bot_line = BOX_BL + BOX_HLINE * (inner_width) + BOX_BR
    color_print(f"  {bot_line}", color)




def try_best_compression(data: bytes, verbose: bool = False) -> tuple:
    best = data
    best_algo = ALGO_NONE
    was_compressed = False

    _has_lzma = False
    try:
        import lzma as _lzma_mod
        _has_lzma = True
    except ImportError:
        pass

    _has_brotli = False
    try:
        import brotli as _brotli_mod
        _has_brotli = True
    except ImportError:
        pass

    done_flag = threading.Event()
    if verbose:
        prog = Progress('Analyzing compression')
        if prog._enabled:
            expected_secs = max(3, len(data) / 300000)
            t_start = time.time()
            prog.start(100)
            def _timer_filler():
                while not done_flag.is_set():
                    elapsed = time.time() - t_start
                    pct = min(elapsed / expected_secs * 100, 99.5)
                    if pct > prog._current:
                        prog._current = int(pct)
                        prog._render()
                    time.sleep(0.05)
            filler = threading.Thread(target=_timer_filler, daemon=True)
            filler.start()

    try:
        c = gzip.compress(data)
        if len(c) < len(best):
            best, best_algo, was_compressed = c, ALGO_GZIP, True
        if verbose and prog._enabled and prog._current < 10:
            prog._current = 10
            prog._render()
    except Exception:
        pass

    gzip_ratio = len(best) / len(data) if was_compressed else 1.0
    if gzip_ratio < 0.90:
        if _has_lzma:
            try:
                c = _lzma_mod.compress(data)
                if len(c) < len(best):
                    best, best_algo, was_compressed = c, ALGO_LZMA, True
                if verbose and prog._enabled and prog._current < 50:
                    prog._current = 50
                    prog._render()
            except Exception:
                pass
        if _has_brotli:
            try:
                c = _brotli_mod.compress(data)
                if len(c) < len(best):
                    best, best_algo, was_compressed = c, ALGO_BROTLI, True
            except Exception:
                pass

    if verbose and prog._enabled:
        done_flag.set()
        filler.join(0.3)
        prog.done()

    if not was_compressed or len(best) >= len(data) * 0.99:
        return data, best_algo, False
    return best, best_algo, True


ALGO_NAMES = {ALGO_GZIP: 'gzip', ALGO_BROTLI: 'brotli', ALGO_LZMA: 'lzma'}


def build_v3_header(algo: int, flags: int, name: str) -> bytes:
    name_bytes = name.encode('utf-8') if name else b''
    name_len = len(name_bytes)
    if name_len > 255:
        raise ValueError("Name too long (max 255 bytes)")
    return V3_MAGIC + bytes([algo, flags, name_len]) + name_bytes


def bytes_to_invisible(data: bytes, name: str = '', algo: int = ALGO_GZIP, flags: int = 0, prog: Progress = None) -> str:
    header = build_v3_header(algo, flags, name)
    payload = header + data
    binary = ''.join(format(b, '08b') for b in payload)
    marker = CHARS[2]
    result = [marker]
    if prog:
        prog.start(len(binary) // 2)
    for i in range(0, len(binary), 2):
        idx = int(binary[i:i+2], 2)
        result.append(CHARS[idx])
        if prog:
            prog.update(1)
    if prog:
        prog.done()
    return ''.join(result)


def encrypt(plaintext: bytes, password: str) -> bytes:
    salt = os.urandom(SALT_LENGTH)
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=KEY_LENGTH, salt=salt, iterations=PBKDF2_ITERATIONS)
    key = kdf.derive(password.encode('utf-8'))
    aesgcm = AESGCM(key)
    nonce = os.urandom(NONCE_LENGTH)
    return salt + nonce + aesgcm.encrypt(nonce, plaintext, None)


def read_file_binary(path: str) -> bytes:
    with open(path, 'rb') as f:
        return f.read()


def write_file_binary(path: str, data: bytes) -> None:
    with open(path, 'wb') as f:
        f.write(data)


def read_file_text(path: str) -> str:
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def write_file_text(path: str, data: str) -> None:
    with open(path, 'w', encoding='utf-8') as f:
        f.write(data)


def validate_file_exists(path: str) -> None:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"File not found: {path}")


def get_file_extension(filepath: str) -> str:
    _, ext = os.path.splitext(filepath)
    return ext.lower()


def is_compressed_extension(filepath: str) -> bool:
    return get_file_extension(filepath) in COMPRESSED_EXTENSIONS


def get_password(prompt: str = "Enter password: ") -> str:
    while True:
        pw1 = getpass.getpass(prompt)
        pw2 = getpass.getpass("Confirm password: ")
        if pw1 == pw2:
            return pw1
        color_print("[!] Passwords do not match. Please try again.", C.ERROR)


def show_help() -> None:
    color_print("\n", C.RESET)
    draw_box([], width=62, color=C.CYAN, title=f" {C.BOLD_WHITE}Project Invisible v3 - Encoder{C.CYAN} ")
    color_print("", C.RESET)

    color_print(f"  {C.HEADER}📖 USAGE{C.RESET}", C.HEADER)
    color_print(f"  {C.BOLD}1.{C.RESET} Direct text input:", C.WHITE)
    draw_box(['python3 en.py "your text" [options]'], width=62, color=C.GREEN)
    color_print("", C.RESET)
    color_print(f"  {C.BOLD}2.{C.RESET} From any file (text or binary):", C.WHITE)
    draw_box(['python3 en.py --file document.pdf [options]'], width=62, color=C.GREEN)
    color_print("", C.RESET)

    color_print(f"  {C.HEADER}⚙️  OPTIONS{C.RESET}", C.HEADER)
    options = [
        f"{C.BOLD}--save <file>{C.RESET}    Save output to file (default: {DEFAULT_FILE})",
        f"{C.BOLD}--name <file>{C.RESET}    Preset output name for auto-save on decode",
        f"{C.BOLD}--encrypt{C.RESET}         Encrypt data with AES-256-GCM {C.DIM}(prompts for password){C.RESET}",
        f"{C.BOLD}--notime{C.RESET}           Skip estimation prompt, encode immediately",
        f"{C.BOLD}--help{C.RESET}             Show this help message",
    ]
    for opt in options:
        color_print(f"  {BOX_VLINE} {opt}", C.WHITE)
    color_print(f"  {BOX_VLINE}", C.WHITE)

    color_print(f"  {C.HEADER}📦 COMPRESSION{C.RESET}", C.HEADER)
    color_print(f"  {BOX_VLINE} {C.SUCCESS}✓ Auto-compression is always on{C.RESET}", C.WHITE)
    color_print(f"  {BOX_VLINE}   Tries gzip, brotli, lzma → picks the smallest", C.WHITE)
    color_print(f"  {BOX_VLINE}   Text & uncompressed files: ~70-95% smaller", C.WHITE)
    color_print(f"  {BOX_VLINE}   Media files (jpg, mp4, etc.): ~0-20% smaller", C.WHITE)
    color_print(f"  {BOX_VLINE}", C.WHITE)
    color_print(f"  {BOX_VLINE} {C.YELLOW}? Media files require confirmation before encoding{C.RESET}", C.WHITE)
    color_print(f"  {BOX_VLINE}   (estimated output size is shown, you type y/n)", C.WHITE)
    color_print(f"  {BOX_VLINE}", C.WHITE)
    color_print(f"  {BOX_VLINE} {C.HINT}💡 Decoding uses {C.BOLD}--media{C.RESET}{C.HINT} flag for media-encoded files{C.RESET}", C.WHITE)

    color_print(f"\n  {C.HEADER}💡 EXAMPLES{C.RESET}", C.HEADER)
    examples = [
        (f"{C.GREEN}#{C.RESET} Encode text", f'python3 en.py "hello world"'),
        (f"{C.GREEN}#{C.RESET} Encode text to file", f'python3 en.py "secret" --save secret.txt'),
        (f"{C.GREEN}#{C.RESET} Encode any file", f'python3 en.py --file document.pdf'),
        (f"{C.GREEN}#{C.RESET} Encode & encrypt", f'python3 en.py --file secret.pdf --encrypt'),
        (f"{C.GREEN}#{C.RESET} Encode with preset name", f'python3 en.py --file image.png --name restored.png'),
        (f"{C.GREEN}#{C.RESET} Encode a text file", f'python3 en.py --file mynotes.txt'),
        (f"{C.GREEN}#{C.RESET} Skip size estimate, encode now", f'python3 en.py --file video.mp4 --notime'),
    ]
    for label, cmd in examples:
        color_print(f"  {BOX_VLINE} {label}", C.WHITE)
        color_print(f"  {BOX_VLINE}   {C.BOLD_WHITE}{cmd}{C.RESET}", C.DIM)

    color_print(f"\n  {C.HEADER}📝 NOTES{C.RESET}", C.HEADER)
    notes = [
        f"  {BOX_VLINE}  Output defaults to {C.BOLD}{DEFAULT_FILE}{C.RESET} if not specified",
        f"  {BOX_VLINE}  --file accepts {C.BOLD}any file type{C.RESET} (text, image, video, etc.)",
        f"  {BOX_VLINE}  Encryption requires {C.CYAN}cryptography{C.RESET} package",
        f"  {BOX_VLINE}  Media files (jpg, mp4, zip...) show size estimate & ask confirmation",
        f"  {BOX_VLINE}  Use {C.BOLD}--notime{C.RESET} to skip estimation and encode immediately",
        f"  {BOX_VLINE}  Decode with {C.BOLD}de.py --media{C.RESET} for media-encoded files",
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
    result = {
        'text': None, 'input_file': None,
        'output_file': DEFAULT_FILE, 'encrypt': False,
        'help': False, 'name': None, 'notime': False
    }
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
        elif arg == '--file':
            if i + 1 >= len(args):
                color_print("[!] Error: --file requires a filename.", C.ERROR)
                sys.exit(1)
            result['input_file'] = args[i + 1]
            i += 1
        elif arg == '--encrypt':
            result['encrypt'] = True
        elif arg == '--name':
            if i + 1 >= len(args):
                color_print("[!] Error: --name requires a filename.", C.ERROR)
                sys.exit(1)
            result['name'] = args[i + 1]
            i += 1
        elif arg == '--notime':
            result['notime'] = True
        elif not arg.startswith('--'):
            if result['text'] is None:
                result['text'] = arg
            else:
                result['text'] += ' ' + arg
        else:
            color_print(f"[!] Unknown option: {arg}", C.ERROR)
            sys.exit(1)
        i += 1
    return result


def main():
    args = sys.argv[1:]
    if not args:
        show_help()
        return
    config = parse_arguments(args)
    if config['help']:
        show_help()
        return
    if config['encrypt'] and not HAS_CRYPTO:
        color_print("[!] Error: 'cryptography' package is required for encryption.", C.ERROR)
        color_print("    Install it with: pip install cryptography", C.HINT)
        sys.exit(1)

    input_count = sum([config['text'] is not None, config['input_file'] is not None])
    if input_count > 1:
        color_print("[!] Error: Cannot use --file and direct text at the same time.", C.ERROR)
        sys.exit(1)
    if input_count == 0:
        color_print("[!] Error: No input provided. Use --help for usage.", C.ERROR)
        sys.exit(1)

    raw_data: bytes = b''
    is_media = False

    if config['input_file']:
        try:
            validate_file_exists(config['input_file'])
            raw_data = read_file_binary(config['input_file'])
            is_media = is_compressed_extension(config['input_file'])
            color_print(f"[*] Reading file: {config['input_file']} ({len(raw_data)} bytes)", C.INFO)
        except FileNotFoundError as e:
            color_print(f"[!] {e}", C.ERROR)
            sys.exit(1)
    else:
        raw_data = config['text'].encode('utf-8')

    original_size = len(raw_data)
    compressed_data, algo, was_compressed = try_best_compression(raw_data, verbose=is_media)

    if was_compressed:
        pct = len(compressed_data) / original_size * 100 if compressed_data != raw_data else 100
        name = ALGO_NAMES.get(algo, '?')
        color_print(f"[*] Using {name}: {original_size} -> {len(compressed_data)} bytes ({pct:.1f}%)", C.SUCCESS)
    else:
        color_print(f"[*] No compression applied \u2014 data is already compact", C.HINT)
        compressed_data = raw_data

    if is_media and not config['notime']:
        payload_size = len(compressed_data)
        if config['encrypt']:
            payload_size += SALT_LENGTH + NONCE_LENGTH + 16
        name_bytes = (config.get('name') or '').encode('utf-8')
        total_bytes = 6 + len(name_bytes) + payload_size
        estimated_chars = 1 + 4 * total_bytes
        estimated_file_bytes = estimated_chars * 3
        est_kb = estimated_file_bytes / 1024
        est_mb = estimated_file_bytes / (1024 * 1024)

        color_print(f"\n  {C.YELLOW}[?] This file is a compressed media type.{C.RESET}", C.YELLOW)
        if est_mb >= 1.0:
            color_print(f"  {C.YELLOW}    Estimated output size: ~{est_mb:.2f} MB{C.RESET}", C.YELLOW)
        else:
            color_print(f"  {C.YELLOW}    Estimated output size: ~{est_kb:.1f} KB{C.RESET}", C.YELLOW)
        answer = color_input("    Continue encoding? [Y/n] ", C.YELLOW)
        if answer.lower() not in ('', 'y', 'yes'):
            color_print("[!] Aborted by user.", C.ERROR)
            sys.exit(0)

    if config['encrypt']:
        color_print("[*] Encrypting data...", C.INFO)
        password = get_password()
        compressed_data = encrypt(compressed_data, password)
        color_print("[+] Encryption complete!", C.SUCCESS)

    flags = FLAG_MEDIA if is_media else 0
    prog = Progress('Encoding')
    encoded = bytes_to_invisible(compressed_data, config.get('name', '') or '', algo, flags, prog)
    write_file_text(config['output_file'], encoded)
    color_print(f"[+] Saved encoded text -> {config['output_file']}", C.SUCCESS)
    color_print(f"[*] Output length: {len(encoded)} invisible characters", C.DIM)

    if is_media:
        color_print(f"  {C.YELLOW}[!] Note: Use {C.BOLD}--media{C.RESET}{C.YELLOW} flag in de.py to decode this file.{C.RESET}", C.YELLOW)


if __name__ == "__main__":
    main()
