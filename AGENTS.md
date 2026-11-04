# Working instructions for coding assistants

These instructions apply to the entire repository folder. User instructions take
precedence.

## Purpose and scope

This tool refills only the 27 Burn Card counters in the user's own offline save
to 999 each. Do not add online functionality, process injection, anti-cheat
modifications, or automatic downloads. The tool must not require a network
connection, telemetry, or uploads. Keep it limited to the Python standard library.


## Modifying the tool

- Read `README.md` and `burn_cards.py` first.
- The default invocation must remain read-only; only `--apply` may modify a save.
- Do not launch or modify the real game for testing without a user request.
  Run `--apply` only when the user has requested that specific save modification.
- Preserve the running-game check, original-file comparison before writing,
  backup, controlled temporary file, and complete result validation.
- Preserve version verification before executing any native code. For another
  game build, do not simply change the hash or addresses. First analyze the
  cryptographic routines and relevant tables again and perform lossless tests.
- The four native routines must run exclusively inside the tool's own process.
- Do not distribute third-party EXE, DLL, or PAK files.
- Error output must not contain personal paths or decrypted data.
- Update documentation and tests when behavior changes.

## Verification

From the repository folder, run `py -3 -B -m unittest -v`.
A read-only integration test using the user's own local save should be performed
only when requested by the user; keep its results anonymous. Do not create test
reports containing personal data in the repository.

Before delivery, allow only the public package files listed in the README.
Do not publish or communicate through GitHub without a user request.
