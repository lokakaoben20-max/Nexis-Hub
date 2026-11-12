"""L'application publique (étape 1, PR 5) ne charge ni le bot ni les workers.

Plan : app-mobile/plan-etape1-connexion-api-2026-11-07.md, section 5.
Un import de `backend.app.public` qui tirerait aiogram ou le bot ouvrirait
une surface que l'application mobile n'a pas besoin de voir.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN = ("aiogram", "telegram_bot", "backend.app.tasks", "backend.app.main")


def test_the_public_app_imports_without_the_bot_or_the_workers():
    code = (
        "import sys, backend.app.public as p\n"
        f"loaded = [m for m in sys.modules if m.split('.')[0] in {FORBIDDEN!r} or m in {FORBIDDEN!r}]\n"
        "print(','.join(loaded))\n"
    )
    result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=120)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "", f"modules chargés à tort : {result.stdout.strip()}"
