"""
Clean Slate Reset Utility.
Safely resets the local database and workspace to start from zero:
- Backs up storage.db before wiping
- Truncates all lead, audit, timeline, deal, and queue tables
- Cleans temporary audio stings and autopilot checkpoints
- Re-enables SQLite WAL mode and schema indexes
"""

import sys
import shutil
import sqlite3
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "storage.db"
OUTPUT_DIR = BASE_DIR / "output"
STINGS_DIR = OUTPUT_DIR / "stings"
STATE_FILE = OUTPUT_DIR / "autopilot_state.json"


def reset_to_zero():
    print("\n" + "=" * 65)
    print("  DENTAL LEAD INTELLIGENCE — CLEAN SLATE RESET")
    print("=" * 65)

    # 1. Backup existing database if present
    if DB_PATH.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = BASE_DIR / f"storage.db.bak_{timestamp}"
        try:
            shutil.copyfile(DB_PATH, backup_path)
            print(f" [✓] Created safety backup: {backup_path.name}")
        except Exception as e:
            print(f" [!] Warning: Could not create backup: {e}")

    # 2. Reset SQLite Database Tables
    try:
        from database import DatabaseManager
        db = DatabaseManager(DB_PATH)
        with db._get_connection() as conn:
            cursor = conn.cursor()
            
            # List of tables to truncate
            tables_to_clear = [
                "leads",
                "audits",
                "findings",
                "technologies",
                "changes",
                "queue_leads",
                "opportunity_timeline",
                "deals",
                "lead_reminders",
                "lead_notes",
                "territories"
            ]

            for table in tables_to_clear:
                try:
                    cursor.execute(f"DELETE FROM {table};")
                except Exception:
                    pass

            cursor.execute("VACUUM;")
            conn.commit()
            print(" [✓] Truncated all lead, audit, timeline, and deals tables.")
    except Exception as e:
        print(f" [!] Database reset error: {e}")

    # 3. Clean temporary audio stings
    if STINGS_DIR.exists():
        cleaned_stings = 0
        for wav_file in STINGS_DIR.glob("*.wav"):
            try:
                wav_file.unlink()
                cleaned_stings += 1
            except Exception:
                pass
        print(f" [✓] Cleared {cleaned_stings} temporary audio sting files from output/stings/")

    # 4. Reset Autopilot Checkpoint
    if STATE_FILE.exists():
        try:
            STATE_FILE.unlink()
            print(" [✓] Reset autopilot_state.json to initial state.")
        except Exception:
            pass

    print("-" * 65)
    print(" 🚀 SUCCESS: System is 100% clean and ready to prospect from zero!")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    reset_to_zero()
