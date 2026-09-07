"""
Automated Database Backup & Disaster Recovery Engine.
Provides point-in-time consistent SQLite snapshots with gzip compression,
30-day retention management, and 1-click disaster recovery restoration.
"""

import gzip
import os
import shutil
import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from config import BASE_DIR, OUTPUT_DIR

logger = logging.getLogger("backup_manager")

BACKUP_DIR = OUTPUT_DIR / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)


class BackupManager:
    """Manages zero-lock SQLite point-in-time backups and restorations."""

    def __init__(
        self,
        db_path: Optional[Path] = None,
        backup_dir: Path = BACKUP_DIR,
        keep_days: int = 30
    ):
        self.db_path = Path(db_path) if db_path else None
        self.backup_dir = Path(backup_dir)
        self.keep_days = keep_days

    def create_backup(
        self,
        label: str = "manual",
        db_path: Optional[Path] = None,
        backup_dir: Optional[Path] = None,
        keep_days: Optional[int] = None
    ) -> Dict[str, Any]:
        target_db = Path(db_path) if db_path else self.db_path
        target_dir = Path(backup_dir) if backup_dir else self.backup_dir
        retention = keep_days or self.keep_days
        return self._create_backup_impl(target_db, target_dir, retention, label)

    def list_backups(self, backup_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
        target_dir = Path(backup_dir) if backup_dir else self.backup_dir
        return self._list_backups_impl(target_dir)

    def restore_backup(
        self,
        archive_name: str,
        target_db_path: Optional[Path] = None,
        backup_dir: Optional[Path] = None
    ) -> Dict[str, Any]:
        target_db = Path(target_db_path) if target_db_path else self.db_path
        target_dir = Path(backup_dir) if backup_dir else self.backup_dir
        return self._restore_backup_impl(archive_name, target_db, target_dir)

    @classmethod
    def create(cls, db_path: Path, backup_dir: Path = BACKUP_DIR, keep_days: int = 30) -> Dict[str, Any]:
        return cls._create_backup_impl(Path(db_path), Path(backup_dir), keep_days, "manual")

    @classmethod
    def list(cls, backup_dir: Path = BACKUP_DIR) -> List[Dict[str, Any]]:
        return cls._list_backups_impl(Path(backup_dir))

    @classmethod
    def restore(cls, archive_name: str, target_db_path: Path, backup_dir: Path = BACKUP_DIR) -> Dict[str, Any]:
        return cls._restore_backup_impl(archive_name, Path(target_db_path), Path(backup_dir))

    @staticmethod
    def _create_backup_impl(
        db_path: Optional[Path],
        backup_dir: Path,
        keep_days: int,
        label: str = "manual"
    ) -> Dict[str, Any]:
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_snapshot = backup_dir / f"snapshot_{timestamp_str}.db"
        archive_name = f"backup_{timestamp_str}.db.gz"
        final_archive = backup_dir / archive_name

        if not db_path or not db_path.exists():
            return {
                "success": False,
                "error": f"Database file not found: {db_path}",
                "archive_name": None
            }

        try:
            # 1. Zero-lock point-in-time online SQLite backup
            src_conn = sqlite3.connect(db_path)
            dst_conn = sqlite3.connect(temp_snapshot)
            with dst_conn:
                src_conn.backup(dst_conn, pages=250, sleep=0.01)
            dst_conn.close()
            src_conn.close()

            # 2. Compress with gzip
            raw_size = temp_snapshot.stat().st_size
            with open(temp_snapshot, "rb") as f_in:
                with gzip.open(final_archive, "wb", compresslevel=9) as f_out:
                    shutil.copyfileobj(f_in, f_out)

            compressed_size = final_archive.stat().st_size

            # Clean up uncompressed snapshot
            if temp_snapshot.exists():
                temp_snapshot.unlink()

            # 3. Auto-prune older backups beyond retention
            pruned_count = BackupManager.prune_old_backups(backup_dir, keep_days=keep_days)

            return {
                "success": True,
                "archive_name": archive_name,
                "label": label,
                "path": str(final_archive),
                "created_at": datetime.now().isoformat(),
                "raw_size_bytes": raw_size,
                "compressed_size_bytes": compressed_size,
                "compression_ratio_pct": round((1 - (compressed_size / max(1, raw_size))) * 100, 1),
                "pruned_count": pruned_count
            }

        except Exception as e:
            logger.error(f"Backup failed: {e}")
            if temp_snapshot.exists():
                temp_snapshot.unlink()
            return {
                "success": False,
                "error": str(e),
                "archive_name": None
            }

    @staticmethod
    def _list_backups_impl(backup_dir: Path) -> List[Dict[str, Any]]:
        if not backup_dir.exists():
            return []

        backups = []
        for p in backup_dir.glob("backup_*.db.gz"):
            stat = p.stat()
            size_kb = round(stat.st_size / 1024, 1)
            backups.append({
                "filename": p.name,
                "size_bytes": stat.st_size,
                "size_formatted": f"{size_kb} KB" if size_kb < 1024 else f"{round(size_kb / 1024, 2)} MB",
                "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "created_at_formatted": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            })

        backups.sort(key=lambda x: x["created_at"], reverse=True)
        return backups

    @staticmethod
    def _restore_backup_impl(
        archive_name: str,
        target_db_path: Optional[Path],
        backup_dir: Path
    ) -> Dict[str, Any]:
        if not target_db_path:
            return {"success": False, "error": "Target database path not specified"}

        archive_path = backup_dir / archive_name
        if not archive_path.exists():
            return {"success": False, "error": f"Backup archive {archive_name} does not exist"}

        # 1. Create safety snapshot of current database
        safety_path = backup_dir / f"safety_pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        if target_db_path.exists():
            try:
                shutil.copyfile(target_db_path, safety_path)
            except Exception as e:
                logger.warning(f"Could not create safety snapshot: {e}")

        # 2. Decompress archive to temporary target
        temp_restored = backup_dir / "temp_restored.db"
        try:
            with gzip.open(archive_path, "rb") as f_in:
                with open(temp_restored, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)

            # 3. Verify SQLite integrity of restored database before replacing
            conn = sqlite3.connect(temp_restored)
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check;")
            integrity = cursor.fetchone()[0]
            conn.close()

            if integrity.lower() != "ok":
                temp_restored.unlink()
                return {"success": False, "error": f"Integrity check failed: {integrity}"}

            # 4. Atomically swap restored file into place
            target_db_path.parent.mkdir(parents=True, exist_ok=True)
            if target_db_path.exists():
                target_db_path.unlink()
            shutil.move(temp_restored, target_db_path)

            return {
                "success": True,
                "restored_from": archive_name,
                "safety_backup": safety_path.name if safety_path.exists() else None,
                "restored_at": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Restore failed: {e}")
            if temp_restored.exists():
                temp_restored.unlink()
            return {"success": False, "error": str(e)}

    @staticmethod
    def prune_old_backups(backup_dir: Path = BACKUP_DIR, keep_days: int = 30) -> int:
        """Removes archives older than keep_days or keeps at minimum the last 5 backups."""
        if not backup_dir.exists():
            return 0

        archives = sorted(backup_dir.glob("backup_*.db.gz"), key=lambda p: p.stat().st_mtime, reverse=True)
        if len(archives) <= 5:
            return 0  # Keep at least 5 snapshots regardless of age

        pruned = 0
        now_ts = datetime.now().timestamp()
        max_age_sec = keep_days * 86400

        for p in archives[5:]:
            if (now_ts - p.stat().st_mtime) > max_age_sec:
                try:
                    p.unlink()
                    pruned += 1
                except Exception:
                    pass

        return pruned
