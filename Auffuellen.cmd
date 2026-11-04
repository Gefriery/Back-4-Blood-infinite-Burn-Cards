@echo off
setlocal
where py >nul 2>nul
if not errorlevel 1 (
  py -3 "%~dp0burn_cards.py" --apply %*
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo Python was not found. Please install 64-bit Python. See README.md.
  ) else (
    python "%~dp0burn_cards.py" --apply %*
  )
)
echo.
echo Press any key to close this window...
pause >nul
