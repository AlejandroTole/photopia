"""
PHOTOIA - Safe XMP Manipulation Utilities
Provides atomic writing, backup/rollback, and targeted parameter replacement.
"""
from pathlib import Path
import datetime
import os
import re
import shutil
from typing import Dict, List, Optional, Tuple, Any


def read_xmp(path: Path) -> str:
    path = Path(path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"No existe el archivo XMP: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def find_operation_modules(xmp_content: str, operation: str) -> List[Dict[str, Any]]:
    """
    Finds all entries for a given operation in the XMP history stack.
    """
    pattern = re.compile(
        rf'<rdf:li\b(?P<attrs1>[^>]*)darktable:operation="{re.escape(operation)}"(?P<attrs2>[^>]*)>',
        re.S,
    )

    results = []
    for match in pattern.finditer(xmp_content):
        attrs = match.group("attrs1") + match.group("attrs2")

        num_match = re.search(r'darktable:num="(\d+)"', attrs)
        enabled_match = re.search(r'darktable:enabled="(\d+)"', attrs)
        modversion_match = re.search(r'darktable:modversion="(\d+)"', attrs)
        params_match = re.search(r'darktable:params="(?P<params>[0-9a-fA-F]+)"', attrs)

        num = int(num_match.group(1)) if num_match else -1
        enabled = int(enabled_match.group(1)) if enabled_match else 1
        modversion = int(modversion_match.group(1)) if modversion_match else 0
        params = params_match.group("params") if params_match else ""

        results.append({
            "num": num,
            "enabled": enabled,
            "modversion": modversion,
            "params": params,
            "operation": operation,
            "match": match,
            "params_span": params_match.span("params") if params_match else None,
            "raw_tag": match.group(0),
        })

    return results


def select_target_module(
    modules: List[Dict[str, Any]],
    requested_num: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Selects the target module. By default, picks the highest darktable:num.
    """
    if not modules:
        raise ValueError("No se encontraron módulos para la operación especificada.")

    if requested_num is not None:
        matches = [m for m in modules if m["num"] == requested_num]
        if not matches:
            raise ValueError(f"No se encontró el módulo con darktable:num={requested_num}")
        return matches[0]

    # Highest num is the latest history entry
    return max(modules, key=lambda m: m["num"])


def replace_module_params(
    xmp_content: str,
    target_module: Dict[str, Any],
    new_hex_params: str,
) -> str:
    """
    Safely replaces only darktable:params="..." for the target module.
    """
    old_params = target_module["params"]
    if not old_params:
        raise ValueError("El módulo destino no tiene darktable:params reconocible.")

    raw_tag = target_module["raw_tag"]
    if f'darktable:params="{old_params}"' not in raw_tag:
        raise ValueError("La etiqueta original no coincide con los parámetros esperados.")

    new_tag = raw_tag.replace(
        f'darktable:params="{old_params}"',
        f'darktable:params="{new_hex_params}"',
        1,
    )

    # Splice into content
    match = target_module["match"]
    start, end = match.span()
    return xmp_content[:start] + new_tag + xmp_content[end:]


def create_backup(xmp_path: Path) -> Path:
    """
    Creates a timestamped backup copy: file.xmp.backup.YYYYMMDD_HHMMSS
    """
    xmp_path = Path(xmp_path).resolve()
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = Path(f"{xmp_path}.backup.{timestamp}")
    shutil.copy2(xmp_path, backup_path)
    return backup_path


def restore_backup(backup_path: Path, xmp_path: Path) -> None:
    """
    Restores the backup file onto xmp_path.
    """
    shutil.copy2(backup_path, xmp_path)


def atomic_write(path: Path, content: str) -> None:
    """
    Writes file atomically via temporary file and os.replace with fsync.
    """
    path = Path(path).resolve()
    temp_path = Path(f"{path}.photoia_tmp")

    with open(temp_path, "w", encoding="utf-8") as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())

    os.replace(temp_path, path)
