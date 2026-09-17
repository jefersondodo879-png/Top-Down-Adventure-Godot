from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "build_work" / "v188"
DIST = ROOT / "dist"
ARTIFACT_DIR = ROOT / "dist_artifact"
BASE_NAME = "Top_Down_Adventure_V1_8_7_AUDIO_PERFORMANCE_ANIMATIONS.zip"
OUT_NAME = "Top_Down_Adventure_V1_8_8_GAMEPLAY_EQUIPMENT_BILLING.zip"
PROJECT_FOLDER = "Top_Down_Adventure_V1_8_8_GAMEPLAY_EQUIPMENT_BILLING"


def safe_extract(zpath: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zpath, "r") as zf:
        base = dest.resolve()
        for member in zf.infolist():
            target = (dest / member.filename).resolve()
            if target != base and base not in target.parents:
                raise RuntimeError(f"Unsafe ZIP path: {member.filename}")
        bad = zf.testzip()
        if bad is not None:
            raise RuntimeError(f"Corrupt ZIP entry: {bad}")
        zf.extractall(dest)


def project_root(extracted: Path) -> Path:
    if (extracted / "project.godot").exists():
        return extracted
    candidates = sorted(extracted.rglob("project.godot"), key=lambda p: len(p.parts))
    if not candidates:
        raise RuntimeError("project.godot not found in V1.8.7 output")
    return candidates[0].parent


def patch_boss_lifecycle(project: Path) -> None:
    """V1.8.8 task hook: boss lifecycle/HUD reset is implemented in a later task."""


def patch_mobile_input(project: Path) -> None:
    """V1.8.8 task hook: touch movement/attack separation is implemented in a later task."""


def patch_equipment_inventory(project: Path) -> None:
    """V1.8.8 task hook: six-slot equipment/inventory is implemented in a later task."""


def integrate_google_play_billing(project: Path) -> None:
    """V1.8.8 task hook: Google Play Billing integration is implemented in a later task."""


def copy_backend(project: Path) -> None:
    """V1.8.8 task hook: backend package is implemented in a later task."""


def static_validate_base(project: Path) -> None:
    required = [
        project / "project.godot",
        project / "scripts" / "player.gd",
        project / "scripts" / "hud.gd",
        project / "scripts" / "audio_manager.gd",
        project / "scenes" / "bosses" / "MinotaurBoss.tscn",
    ]
    missing = [str(path.relative_to(project)) for path in required if not path.exists()]
    if missing:
        raise RuntimeError(f"V1.8.7 base is missing required files: {missing}")

    wavs = list((project / "assets" / "audio" / "RPG_Essentials").rglob("*.wav"))
    if len(wavs) < 48:
        raise RuntimeError(f"V1.8.7 audio regression: expected at least 48 WAVs, found {len(wavs)}")

    boss_scene = (project / "scenes" / "bosses" / "MinotaurBoss.tscn").read_text(encoding="utf-8")
    if "AnimatedSprite2D" not in boss_scene:
        raise RuntimeError("V1.8.6 Minotaur animation scene was lost")


def zip_project(project: Path, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.unlink(missing_ok=True)
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in sorted(project.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(project)
            if any(part in {".godot", ".pytest_cache", "__pycache__"} for part in rel.parts):
                continue
            zf.write(path, f"{PROJECT_FOLDER}/{rel.as_posix()}")
    with zipfile.ZipFile(out, "r") as zf:
        bad = zf.testzip()
        if bad is not None:
            raise RuntimeError(f"Output ZIP corrupt entry: {bad}")
        names = zf.namelist()
        roots = {name.split("/", 1)[0] for name in names if name}
        if roots != {PROJECT_FOLDER}:
            raise RuntimeError(f"Output ZIP must have one top-level folder, got: {sorted(roots)}")
        if f"{PROJECT_FOLDER}/project.godot" not in names:
            raise RuntimeError("Output ZIP does not contain project.godot under expected root")


def build_direct_artifact(project: Path) -> None:
    shutil.rmtree(ARTIFACT_DIR, ignore_errors=True)
    target = ARTIFACT_DIR / PROJECT_FOLDER
    target.mkdir(parents=True, exist_ok=True)
    for source in project.rglob("*"):
        rel = source.relative_to(project)
        if any(part in {".godot", ".pytest_cache", "__pycache__"} for part in rel.parts):
            continue
        dest = target / rel
        if source.is_dir():
            dest.mkdir(parents=True, exist_ok=True)
        elif source.is_file():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)


def main() -> None:
    source = DIST / BASE_NAME
    if not source.exists():
        raise SystemExit(f"Missing V1.8.7 build output: {source}")

    shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True, exist_ok=True)
    extracted = WORK / "project"
    safe_extract(source, extracted)
    project = project_root(extracted)

    static_validate_base(project)
    patch_boss_lifecycle(project)
    patch_mobile_input(project)
    patch_equipment_inventory(project)
    integrate_google_play_billing(project)
    copy_backend(project)
    static_validate_base(project)

    out = DIST / OUT_NAME
    zip_project(project, out)
    build_direct_artifact(project)

    print("V1.8.8 integration stage: OK")
    print("V1.8.7 base/audio/boss regressions preserved")
    print(f"Generated: {out}")
    print(f"Size: {out.stat().st_size} bytes")


if __name__ == "__main__":
    main()
