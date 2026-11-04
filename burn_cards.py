"""Refill only offline Burn Cards. Standard library only; no network or injection.

The game uses custom AES, with the Steam ID repeated to 32 bytes as its key.
For compatibility this tool calls the original game's two key expansion and
single-block crypto routines in its OWN process. It never starts the game or
opens another process. Only the specified, hash-checked game build is supported.
"""
import argparse
import copy
import ctypes as C
from ctypes import wintypes as W
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import sys

HERE = Path(__file__).resolve().parent
GAME = HERE.parent
EXE = GAME / 'Gobi/Binaries/Win64/Back4Blood.exe'
EXPECTED_SHA256 = 'e75df3383d7eb9c55ccd9f437260a5dc13fbce8fdfea093f40b3141ea7a573ea'
SAVE_DIR = Path.home() / 'AppData/Local/Back4Blood/Steam/Saved/SaveGames'
SAVE = SAVE_DIR / 'PlayerProfileSettings.sav'
MAGIC = b'AESSAV\0'


def resolve_paths(game_dir=None, save_dir=None):
    candidates = [Path(game_dir)] if game_dir else [HERE, HERE.parent]
    if not game_dir:
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam') as key:
                steam = Path(winreg.QueryValueEx(key, 'SteamPath')[0])
            libraries = [steam]
            vdf = steam/'steamapps/libraryfolders.vdf'
            if vdf.is_file():
                libraries.extend(Path(p.replace('\\\\', '\\')) for p in re.findall(
                    r'"path"\s*"([^"]+)"', vdf.read_text(encoding='utf-8')))
            candidates.extend(p/'steamapps/common/Back 4 Blood' for p in libraries)
        except OSError:
            pass
    game = next((p.resolve() for p in candidates if
                 (p/'Gobi/Binaries/Win64/Back4Blood.exe').is_file()), None)
    if game is None:
        raise RuntimeError('Game not found. Specify the installation folder with --game-dir.')
    saves = (Path(save_dir).expanduser() if save_dir else
             Path.home()/'AppData/Local/Back4Blood/Steam/Saved/SaveGames').resolve()
    if saves == HERE or HERE in saves.parents:
        raise RuntimeError('Private saves must not be stored inside the publishable package.')
    return game, saves


def game_running():
    class ENTRY(C.Structure):
        _fields_ = [('dwSize', W.DWORD), ('cntUsage', W.DWORD),
                    ('th32ProcessID', W.DWORD), ('th32DefaultHeapID', C.c_size_t),
                    ('th32ModuleID', W.DWORD), ('cntThreads', W.DWORD),
                    ('th32ParentProcessID', W.DWORD), ('pcPriClassBase', W.LONG),
                    ('dwFlags', W.DWORD), ('szExeFile', W.WCHAR * 260)]
    k = C.WinDLL('kernel32', use_last_error=True)
    k.CreateToolhelp32Snapshot.restype = W.HANDLE
    k.Process32FirstW.argtypes = [W.HANDLE, C.POINTER(ENTRY)]
    k.Process32NextW.argtypes = [W.HANDLE, C.POINTER(ENTRY)]
    k.CloseHandle.argtypes = [W.HANDLE]
    handle = k.CreateToolhelp32Snapshot(2, 0)
    if handle == C.c_void_p(-1).value:
        raise C.WinError(C.get_last_error())
    try:
        entry = ENTRY(); entry.dwSize = C.sizeof(entry)
        ok = k.Process32FirstW(handle, C.byref(entry))
        while ok:
            if entry.szExeFile.lower() in ('back4blood.exe', 'start_protected_game.exe'):
                return True
            ok = k.Process32NextW(handle, C.byref(entry))
        return False
    finally:
        k.CloseHandle(handle)


class GameCrypto:
    def __init__(self):
        data = EXE.read_bytes()
        if hashlib.sha256(data).hexdigest() != EXPECTED_SHA256:
            raise RuntimeError('Unsupported game executable: the tool must be reviewed for this build.')
        pe = struct.unpack_from('<I', data, 0x3c)[0]
        if data[pe:pe+4] != b'PE\0\0' or struct.unpack_from('<H', data, pe+4)[0] != 0x8664:
            raise RuntimeError('Not a supported 64-bit game executable.')
        count = struct.unpack_from('<H', data, pe+6)[0]
        opt_size = struct.unpack_from('<H', data, pe+20)[0]
        optional = pe+24
        size = struct.unpack_from('<I', data, optional+56)[0]
        k = C.WinDLL('kernel32', use_last_error=True)
        k.VirtualAlloc.argtypes = [C.c_void_p, C.c_size_t, W.DWORD, W.DWORD]
        k.VirtualAlloc.restype = C.c_void_p
        k.VirtualFree.argtypes = [C.c_void_p, C.c_size_t, W.DWORD]
        self.kernel = k
        self.memory = k.VirtualAlloc(None, size, 0x3000, 0x40)
        if not self.memory:
            raise C.WinError(C.get_last_error())
        for i in range(count):
            pos = optional+opt_size+i*40
            _, rva, raw_size, raw = struct.unpack_from('<IIII', data, pos+8)
            C.memmove(self.memory+rva, data[raw:raw+raw_size], raw_size)
        # All four addresses are relative to this hash-checked game executable.
        # No imports, game initialization, anti-cheat code, or save functions run.
        schedule = C.WINFUNCTYPE(C.c_int, C.c_void_p, C.c_void_p)
        block = C.WINFUNCTYPE(None, C.c_void_p, C.c_int, C.c_void_p, C.c_void_p)
        self.encrypt_schedule = schedule(self.memory+0x2433810)
        self.decrypt_schedule = schedule(self.memory+0x2433d10)
        self.encrypt_block = block(self.memory+0x2433f50)
        self.decrypt_block = block(self.memory+0x24351c0)
        account = re.search(r'"accountid"\s*"(\d+)"', (SAVE_DIR/'steam_autocloud.vdf').read_text())
        if not account:
            raise RuntimeError('Steam account identifier not found.')
        steam_id = str(76561197960265728+int(account[1]))
        self.key = C.create_string_buffer((steam_id*32).encode('ascii')[:32], 32)

    def transform(self, data, encrypt=False):
        if len(data) % 16:
            raise RuntimeError('Invalid block length.')
        context = C.create_string_buffer(240)
        rounds = (self.encrypt_schedule if encrypt else self.decrypt_schedule)(context, self.key)
        routine = self.encrypt_block if encrypt else self.decrypt_block
        source = C.create_string_buffer(data)
        result = C.create_string_buffer(len(data))
        try:
            for off in range(0, len(data), 16):
                routine(context, rounds, C.byref(source, off), C.byref(result, off))
            return result.raw
        finally:
            C.memset(C.addressof(context), 0, C.sizeof(context))
            C.memset(C.addressof(source), 0, C.sizeof(source))
            C.memset(C.addressof(result), 0, C.sizeof(result))

    def close(self):
        C.memset(C.addressof(self.key), 0, C.sizeof(self.key))
        self.kernel.VirtualFree(self.memory, 0, 0x8000)


def refill(original, crypto):
    if not original.startswith(MAGIC):
        raise RuntimeError('Unknown save format.')
    plain = crypto.transform(original[len(MAGIC):])
    profile = json.loads(plain.decode('utf-8'))
    if MAGIC+crypto.transform(plain, True) != original:
        raise RuntimeError('Lossless encryption roundtrip check failed.')
    before = copy.deepcopy(profile)
    consumables = profile['offlineData']['consumables']
    if not isinstance(consumables, dict):
        raise RuntimeError('Unknown card data format.')
    cards = json.loads((HERE/'burn-cards.json').read_text())
    if len(cards) != 27 or len({c['guid'] for c in cards}) != 27:
        raise RuntimeError('Unexpected card list.')
    counts = []
    for card in cards:
        pattern = 'RowName="'+card['guid']+'"'
        matches = [k for k in consumables if pattern in k]
        if len(matches) > 1:
            raise RuntimeError('Duplicate card entry.')
        key = matches[0] if matches else (
            '(DataTable=GuidDataTable\'"/Game/Progression/Products/Products_DT.Products_DT"\','
            'RowName="'+card['guid']+'",RowDisplayName="'+card['product']+'")')
        value = consumables.setdefault(key, {'acquired': 0, 'spent': 0})
        if set(value) != {'acquired', 'spent'}:
            raise RuntimeError('Unexpected counter fields: '+card['product'])
        if any(type(value[n]) is not int or value[n] < 0 for n in value):
            raise RuntimeError('Invalid card counter.')
        if value['spent'] > 2147483647-999:
            raise RuntimeError('Card counter would exceed the 32-bit range.')
        counts.append((card['product'], value['acquired']-value['spent'], 999))
        value['acquired'] = value['spent']+999
    # Preserve the entire original JSON except the offline consumables object.
    text = plain.decode('utf-8').rstrip(' ')
    marker = '"consumables":'
    start = text.index(marker)+len(marker)
    current, length = json.JSONDecoder().raw_decode(text[start:])
    if current != before['offlineData']['consumables']:
        raise RuntimeError('Could not identify the card section unambiguously.')
    replacement = json.dumps(consumables, ensure_ascii=False, separators=(',', ':'))
    updated_text = text[:start]+replacement+text[start+length:]
    updated = json.loads(updated_text)
    control = copy.deepcopy(updated)
    control['offlineData']['consumables'] = before['offlineData']['consumables']
    if control != before:
        raise RuntimeError('Detected a change outside the offline card data.')
    raw = updated_text.encode('utf-8')
    raw += b' '*((-len(raw)) % 16)
    result = MAGIC+crypto.transform(raw, True)
    if json.loads(crypto.transform(result[7:]).decode()) != updated:
        raise RuntimeError('New save validation failed.')
    return result, counts


def main():
    global GAME, EXE, SAVE_DIR, SAVE
    parser = argparse.ArgumentParser(description='Refill all 27 offline Burn Card types to 999 copies each.')
    parser.add_argument('--apply', action='store_true', help='Create a backup and write the updated save.')
    parser.add_argument('--game-dir', help='Game installation folder; otherwise detect it through Steam.')
    parser.add_argument('--save-dir', help='Your own SaveGames folder; otherwise use the default Windows location.')
    args = parser.parse_args()
    if sys.platform != 'win32' or C.sizeof(C.c_void_p) != 8:
        raise RuntimeError('Windows and 64-bit Python are required.')
    GAME, SAVE_DIR = resolve_paths(args.game_dir, args.save_dir)
    EXE = GAME/'Gobi/Binaries/Win64/Back4Blood.exe'
    SAVE = SAVE_DIR/'PlayerProfileSettings.sav'
    if game_running():
        raise RuntimeError('Please close Back 4 Blood completely and try again.')
    original = SAVE.read_bytes()
    crypto = GameCrypto()
    try:
        result, counts = refill(original, crypto)
        for name, old, new in counts:
            print(f'{name}: {old} -> {new}')
        if not args.apply:
            print('Check passed. No changes made; use --apply to apply the refill.')
            return
        if SAVE.read_bytes() != original or game_running():
            raise RuntimeError('The save or game status changed during validation.')
        folder = SAVE_DIR/'B4B_exploit_backups'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        folder.mkdir(parents=True)
        (folder/SAVE.name).write_bytes(original)
        temporary = SAVE.with_name(SAVE.name+'.burncards-tmp')
        try:
            with temporary.open('xb') as f:
                f.write(result); f.flush(); os.fsync(f.fileno())
            if SAVE.read_bytes() != original or game_running():
                raise RuntimeError('The save or game status changed before writing.')
            os.replace(temporary, SAVE)
        finally:
            if temporary.exists(): temporary.unlink()
        if SAVE.read_bytes() != result:
            raise RuntimeError('File verification after writing failed; a backup is available.')
        print('Done: all 27 offline Burn Card types now have 999 copies each.')
        print('Backup created in the B4B_exploit_backups subfolder of SaveGames.')
    finally:
        crypto.close()


if __name__ == '__main__':
    try:
        main()
    except (OSError, UnicodeError, json.JSONDecodeError):
        print('ERROR: Local files could not be processed. '
              'Check paths, permissions, and your save. Do not upload private files.', file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print('ERROR:', str(exc) if isinstance(exc, RuntimeError) else
              'Unexpected error. Do not publish saves or memory dumps.', file=sys.stderr)
        sys.exit(1)
