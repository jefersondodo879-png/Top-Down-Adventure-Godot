from __future__ import annotations

import http.cookiejar
import json
import re
import shutil
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "build_work" / "audio_v187"
DIST = ROOT / "dist"
ARTIFACT_DIR = ROOT / "dist_artifact"
BASE_NAME = "Top_Down_Adventure_V1_8_6_PERFORMANCE_ANIMATIONS.zip"
OUT_NAME = "Top_Down_Adventure_V1_8_7_AUDIO_PERFORMANCE_ANIMATIONS.zip"
PROJECT_FOLDER = "Top_Down_Adventure_V1_8_7_AUDIO_PERFORMANCE_ANIMATIONS"
OFFICIAL_PAGE = "https://leohpaz.itch.io/rpg-essentials-sfx-free"


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
        raise RuntimeError("project.godot not found in V1.8.6 output")
    return candidates[0].parent


def _urlopen(opener: urllib.request.OpenerDirector, url: str, data: bytes | None = None, referer: str = ""):
    headers = {"User-Agent": "Mozilla/5.0"}
    if referer:
        headers["Referer"] = referer
    if data is not None:
        headers["X-Requested-With"] = "XMLHttpRequest"
    return opener.open(urllib.request.Request(url, data=data, headers=headers), timeout=120)


def download_rpg_essentials(dest: Path) -> Path:
    """Download the creator's public free archive without storing the source ZIP in the game."""
    base = "https://leohpaz.itch.io"
    slug = "/rpg-essentials-sfx-free"
    purchase_url = base + slug + "/purchase"
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    purchase_html = _urlopen(opener, purchase_url).read().decode("utf-8", "replace")
    csrf_match = re.search(r'<meta name="csrf_token" value="([^"]+)"', purchase_html)
    if csrf_match is None:
        raise RuntimeError("RPG Essentials purchase CSRF token not found")
    csrf = csrf_match.group(1)

    download_url_response = _urlopen(
        opener,
        base + slug + "/download_url",
        urllib.parse.urlencode({"csrf_token": csrf}).encode(),
        purchase_url,
    ).read().decode("utf-8", "replace")
    download_page_url = str(json.loads(download_url_response).get("url", ""))
    if not download_page_url:
        raise RuntimeError("RPG Essentials download page URL was not returned")

    download_page = _urlopen(opener, download_page_url, referer=purchase_url).read().decode("utf-8", "replace")
    upload_match = re.search(r'data-upload_id="(\d+)"', download_page)
    page_csrf_match = re.search(r'<meta name="csrf_token" value="([^"]+)"', download_page)
    if upload_match is None or page_csrf_match is None:
        raise RuntimeError("RPG Essentials upload metadata not found")

    upload_id = upload_match.group(1)
    page_csrf = page_csrf_match.group(1)
    file_endpoint = f"{base}{slug}/file/{upload_id}?source=game_download"
    file_response = _urlopen(
        opener,
        file_endpoint,
        urllib.parse.urlencode({"csrf_token": page_csrf}).encode(),
        download_page_url,
    ).read().decode("utf-8", "replace")
    signed_url = str(json.loads(file_response).get("url", ""))
    if not signed_url:
        raise RuntimeError("RPG Essentials signed file URL was not returned")

    data = _urlopen(opener, signed_url, referer=download_page_url).read()
    if not data.startswith(b"PK"):
        raise RuntimeError("RPG Essentials download is not a ZIP archive")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    with zipfile.ZipFile(dest, "r") as zf:
        bad = zf.testzip()
        if bad is not None:
            raise RuntimeError(f"RPG Essentials corrupt entry: {bad}")
    return dest


def integrate_audio_pack(project: Path) -> Path:
    source_zip = WORK / "RPG_Essentials_Free.zip"
    download_rpg_essentials(source_zip)
    unpacked = WORK / "rpg_essentials_unpack"
    safe_extract(source_zip, unpacked)

    destination = project / "assets" / "audio" / "RPG_Essentials"
    destination.mkdir(parents=True, exist_ok=True)
    wav_files = sorted(unpacked.rglob("*.wav"))
    if len(wav_files) < 48:
        raise RuntimeError(f"Expected 48 RPG Essentials WAV files, found {len(wav_files)}")

    for source in wav_files:
        relative = source.relative_to(unpacked)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    # Never redistribute the source archive itself as a standalone file inside the game.
    source_zip.unlink(missing_ok=True)
    return destination


def patch_audio_manager(project: Path) -> None:
    path = project / "scripts" / "audio_manager.gd"
    if not path.exists():
        raise RuntimeError("scripts/audio_manager.gd not found")

    path.write_text(r'''extends Node

const SFX_STREAMS: Dictionary = {
    "attack": preload("res://assets/audio/RPG_Essentials/12_Player_Movement_SFX/56_Attack_03.wav"),
    "hit": preload("res://assets/audio/RPG_Essentials/12_Player_Movement_SFX/61_Hit_03.wav"),
    "enemy_hit": preload("res://assets/audio/RPG_Essentials/10_Battle_SFX/15_Impact_flesh_02.wav"),
    "enemy_death": preload("res://assets/audio/RPG_Essentials/10_Battle_SFX/69_Enemy_death_01.wav"),
    "boss_attack": preload("res://assets/audio/RPG_Essentials/10_Battle_SFX/03_Claw_03.wav"),
    "boss_hit": preload("res://assets/audio/RPG_Essentials/10_Battle_SFX/77_flesh_02.wav"),
    "block": preload("res://assets/audio/RPG_Essentials/10_Battle_SFX/39_Block_03.wav"),
    "encounter": preload("res://assets/audio/RPG_Essentials/10_Battle_SFX/55_Encounter_02.wav"),
    "pickup": preload("res://assets/audio/RPG_Essentials/10_UI_Menu_SFX/013_Confirm_03.wav"),
    "chest": preload("res://assets/audio/RPG_Essentials/10_UI_Menu_SFX/051_use_item_01.wav"),
    "inventory": preload("res://assets/audio/RPG_Essentials/10_UI_Menu_SFX/013_Confirm_03.wav"),
    "potion": preload("res://assets/audio/RPG_Essentials/8_Buffs_Heals_SFX/02_Heal_02.wav"),
    "heal": preload("res://assets/audio/RPG_Essentials/8_Buffs_Heals_SFX/02_Heal_02.wav"),
    "use_item": preload("res://assets/audio/RPG_Essentials/10_UI_Menu_SFX/051_use_item_01.wav"),
    "hover": preload("res://assets/audio/RPG_Essentials/10_UI_Menu_SFX/001_Hover_01.wav"),
    "confirm": preload("res://assets/audio/RPG_Essentials/10_UI_Menu_SFX/013_Confirm_03.wav"),
    "decline": preload("res://assets/audio/RPG_Essentials/10_UI_Menu_SFX/029_Decline_09.wav"),
    "denied": preload("res://assets/audio/RPG_Essentials/10_UI_Menu_SFX/033_Denied_03.wav"),
    "equip": preload("res://assets/audio/RPG_Essentials/10_UI_Menu_SFX/070_Equip_10.wav"),
    "unequip": preload("res://assets/audio/RPG_Essentials/10_UI_Menu_SFX/071_Unequip_01.wav"),
    "buy": preload("res://assets/audio/RPG_Essentials/10_UI_Menu_SFX/079_Buy_sell_01.wav"),
    "sell": preload("res://assets/audio/RPG_Essentials/10_UI_Menu_SFX/079_Buy_sell_01.wav"),
    "buy_sell": preload("res://assets/audio/RPG_Essentials/10_UI_Menu_SFX/079_Buy_sell_01.wav"),
    "pause": preload("res://assets/audio/RPG_Essentials/10_UI_Menu_SFX/092_Pause_04.wav"),
    "unpause": preload("res://assets/audio/RPG_Essentials/10_UI_Menu_SFX/098_Unpause_04.wav"),
    "step_grass": preload("res://assets/audio/RPG_Essentials/12_Player_Movement_SFX/03_Step_grass_03.wav"),
    "step_rock": preload("res://assets/audio/RPG_Essentials/12_Player_Movement_SFX/08_Step_rock_02.wav"),
    "step_wood": preload("res://assets/audio/RPG_Essentials/12_Player_Movement_SFX/12_Step_wood_03.wav"),
    "step_water": preload("res://assets/audio/RPG_Essentials/12_Player_Movement_SFX/14_Step_water_02.wav"),
    "swim": preload("res://assets/audio/RPG_Essentials/12_Player_Movement_SFX/26_Swim_Submerged_02.wav"),
    "jump": preload("res://assets/audio/RPG_Essentials/12_Player_Movement_SFX/30_Jump_03.wav"),
    "climb": preload("res://assets/audio/RPG_Essentials/12_Player_Movement_SFX/42_Cling_climb_03.wav"),
    "land": preload("res://assets/audio/RPG_Essentials/12_Player_Movement_SFX/45_Landing_01.wav"),
    "dive": preload("res://assets/audio/RPG_Essentials/12_Player_Movement_SFX/52_Dive_02.wav"),
    "teleport": preload("res://assets/audio/RPG_Essentials/12_Player_Movement_SFX/88_Teleport_02.wav"),
    "fire": preload("res://assets/audio/RPG_Essentials/8_Atk_Magic_SFX/04_Fire_explosion_04_medium.wav"),
    "ice": preload("res://assets/audio/RPG_Essentials/8_Atk_Magic_SFX/13_Ice_explosion_01.wav"),
    "thunder": preload("res://assets/audio/RPG_Essentials/8_Atk_Magic_SFX/18_Thunder_02.wav"),
    "water_magic": preload("res://assets/audio/RPG_Essentials/8_Atk_Magic_SFX/22_Water_02.wav"),
    "wind": preload("res://assets/audio/RPG_Essentials/8_Atk_Magic_SFX/25_Wind_01.wav"),
    "earth": preload("res://assets/audio/RPG_Essentials/8_Atk_Magic_SFX/30_Earth_02.wav"),
    "charge": preload("res://assets/audio/RPG_Essentials/8_Atk_Magic_SFX/45_Charge_05.wav"),
    "poison": preload("res://assets/audio/RPG_Essentials/8_Atk_Magic_SFX/46_Poison_01.wav"),
    "attack_buff": preload("res://assets/audio/RPG_Essentials/8_Buffs_Heals_SFX/16_Atk_buff_04.wav"),
    "defense_buff": preload("res://assets/audio/RPG_Essentials/8_Buffs_Heals_SFX/17_Def_buff_01.wav"),
    "debuff": preload("res://assets/audio/RPG_Essentials/8_Buffs_Heals_SFX/21_Debuff_01.wav"),
    "revive": preload("res://assets/audio/RPG_Essentials/8_Buffs_Heals_SFX/30_Revive_03.wav"),
    "absorb": preload("res://assets/audio/RPG_Essentials/8_Buffs_Heals_SFX/39_Absorb_04.wav"),
    "sleep": preload("res://assets/audio/RPG_Essentials/8_Buffs_Heals_SFX/44_Sleep_01.wav"),
    "speed_up": preload("res://assets/audio/RPG_Essentials/8_Buffs_Heals_SFX/48_Speed_up_02.wav"),
}

@onready var music: AudioStreamPlayer = $Music
@onready var sfx1: AudioStreamPlayer = $SFX1
@onready var sfx2: AudioStreamPlayer = $SFX2
@onready var sfx3: AudioStreamPlayer = $SFX3

var sfx_players: Array[AudioStreamPlayer] = []
var sfx_index: int = 0

func _ready() -> void:
    add_to_group("audio_manager")
    sfx_players = [sfx1, sfx2, sfx3]
    for sfx_player: AudioStreamPlayer in sfx_players:
        sfx_player.volume_db = -4.0
    music.finished.connect(_restart_music)
    if not music.playing:
        music.play()

func _restart_music() -> void:
    music.play()

func _stream_for(sound_id: String) -> AudioStream:
    return SFX_STREAMS.get(sound_id) as AudioStream

func play_sfx(sound_id: String) -> void:
    var stream: AudioStream = _stream_for(sound_id)
    if stream == null or sfx_players.is_empty():
        return
    var player: AudioStreamPlayer = sfx_players[sfx_index]
    sfx_index = (sfx_index + 1) % sfx_players.size()
    player.stream = stream
    player.play()
''', encoding="utf-8")


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"Audio patch pattern not found: {label}")
    return text.replace(old, new, 1)


def patch_gameplay_audio(project: Path) -> None:
    player_path = project / "scripts" / "player.gd"
    player = player_path.read_text(encoding="utf-8")
    if "var footstep_timer:" not in player:
        player = _replace_once(
            player,
            "var position_save_timer: float = 0.0\n",
            "var position_save_timer: float = 0.0\nvar footstep_timer: float = 0.0\n",
            "player footstep timer",
        )
        player = _replace_once(
            player,
            "    move_and_slide()\n    _update_animation(input_vec)\n",
            "    move_and_slide()\n    _update_footsteps(delta, input_vec)\n    _update_animation(input_vec)\n",
            "player footstep update",
        )
        marker = "func _unhandled_input(event: InputEvent) -> void:\n"
        footsteps = '''func _update_footsteps(delta: float, input_vec: Vector2) -> void:\n    if input_vec == Vector2.ZERO:\n        footstep_timer = 0.0\n        return\n    footstep_timer -= delta\n    if footstep_timer <= 0.0:\n        footstep_timer = 0.34\n        _play_sfx("step_grass")\n\n'''
        player = _replace_once(player, marker, footsteps + marker, "player footstep function")
    player_path.write_text(player, encoding="utf-8")

    boss_path = project / "scripts" / "integrated_boss.gd"
    boss = boss_path.read_text(encoding="utf-8")
    if 'play_sfx", "boss_attack"' not in boss:
        boss = _replace_once(
            boss,
            '    _play_anim("attack", true)\n',
            '    _play_anim("attack", true)\n    get_tree().call_group("audio_manager", "play_sfx", "boss_attack")\n',
            "minotaur attack sound",
        )
        boss = _replace_once(
            boss,
            "    health = maxi(0, health - amount)\n",
            '    health = maxi(0, health - amount)\n    get_tree().call_group("audio_manager", "play_sfx", "boss_hit")\n',
            "minotaur hit sound",
        )
        boss = _replace_once(
            boss,
            "func _die() -> void:\n    velocity = Vector2.ZERO\n",
            'func _die() -> void:\n    velocity = Vector2.ZERO\n    get_tree().call_group("audio_manager", "play_sfx", "enemy_death")\n',
            "minotaur death sound",
        )
    boss_path.write_text(boss, encoding="utf-8")

    insect_path = project / "scripts" / "insect_enemy.gd"
    insect = insect_path.read_text(encoding="utf-8")
    if 'play_sfx", "boss_attack"' not in insect:
        insect = _replace_once(
            insect,
            '    _play_state("attack")\n    await get_tree().create_timer(0.24).timeout\n',
            '    _play_state("attack")\n    if enemy_type == "mantis_boss":\n        get_tree().call_group("audio_manager", "play_sfx", "boss_attack")\n    await get_tree().create_timer(0.24).timeout\n',
            "mantis attack sound",
        )
        insect = _replace_once(
            insect,
            '    get_tree().call_group("audio_manager", "play_sfx", "hit")\n    if health <= 0:\n',
            '    get_tree().call_group("audio_manager", "play_sfx", "boss_hit" if enemy_type == "mantis_boss" else "hit")\n    if health <= 0:\n',
            "mantis hit sound",
        )
        insect = _replace_once(
            insect,
            "func _die() -> void:\n    dead = true\n",
            'func _die() -> void:\n    dead = true\n    get_tree().call_group("audio_manager", "play_sfx", "enemy_death")\n',
            "insect death sound",
        )
    insect_path.write_text(insect, encoding="utf-8")

    hud_path = project / "scripts" / "hud.gd"
    hud = hud_path.read_text(encoding="utf-8")
    if 'play_sfx", "buy"' not in hud:
        hud = _replace_once(
            hud,
            "    GameState.buy_shop_item(item_id, amount, price)\n    _refresh_shop()\n",
            '    GameState.buy_shop_item(item_id, amount, price)\n    get_tree().call_group("audio_manager", "play_sfx", "buy")\n    _refresh_shop()\n',
            "shop buy sound",
        )
    if 'play_sfx", "unequip"' not in hud:
        hud = _replace_once(
            hud,
            "        GameState.unequip_armor()\n",
            '        GameState.unequip_armor()\n        get_tree().call_group("audio_manager", "play_sfx", "unequip")\n',
            "unequip sound",
        )
        hud = _replace_once(
            hud,
            "        GameState.equip_item(selected_inventory_item)\n",
            '        GameState.equip_item(selected_inventory_item)\n        get_tree().call_group("audio_manager", "play_sfx", "equip")\n',
            "equip sound",
        )
    hud_path.write_text(hud, encoding="utf-8")


def patch_licenses(project: Path) -> None:
    license_path = project / "THIRD_PARTY_ASSETS.md"
    text = license_path.read_text(encoding="utf-8") if license_path.exists() else "# Third-party assets\n"
    if "RPG Essentials SFX - Free!" not in text:
        text += (
            "\n## RPG Essentials SFX - Free! — Leohpaz\n"
            f"Source: {OFFICIAL_PAGE}\n\n"
            "Creator terms on the itch.io page: the free pack may be used in game projects; "
            "the asset pack itself may not be sold or redistributed as a standalone pack. "
            "Credit is not mandatory, but is appreciated by the creator.\n"
        )
    license_path.write_text(text, encoding="utf-8")

    docs = project / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "V1_8_7_AUDIO.md").write_text(
        "# V1.8.7 - RPG Essentials SFX\n\n"
        "- 48 WAVs do pack RPG Essentials SFX - Free! foram integrados em `assets/audio/RPG_Essentials/`.\n"
        "- Ataques, impactos, bosses, poção, inventário, compra, equipar/desequipar e passos usam o novo pack.\n"
        "- Passos são limitados por temporizador (0,34 s), evitando disparos de áudio a cada frame.\n"
        "- O AudioManager usa streams pré-carregados e três players rotativos, sem `load()` por efeito.\n"
        "- O pack não contém música; `music_loop.wav` existente foi preservado.\n"
        f"- Fonte/licença: {OFFICIAL_PAGE}\n",
        encoding="utf-8",
    )


def static_validate(project: Path) -> None:
    audio_dir = project / "assets" / "audio" / "RPG_Essentials"
    wavs = list(audio_dir.rglob("*.wav"))
    if len(wavs) < 48:
        raise RuntimeError(f"Integrated RPG Essentials WAV count is {len(wavs)}, expected at least 48")

    manager = (project / "scripts" / "audio_manager.gd").read_text(encoding="utf-8")
    for sound_id in ["attack", "hit", "inventory", "potion", "buy", "equip", "confirm", "boss_attack", "enemy_death", "step_grass"]:
        if f'"{sound_id}"' not in manager:
            raise RuntimeError(f"AudioManager mapping missing: {sound_id}")
    if "RPG_Essentials" not in manager or "const SFX_STREAMS: Dictionary" not in manager:
        raise RuntimeError("AudioManager is not using preloaded RPG Essentials streams")

    player = (project / "scripts" / "player.gd").read_text(encoding="utf-8")
    boss = (project / "scripts" / "integrated_boss.gd").read_text(encoding="utf-8")
    insect = (project / "scripts" / "insect_enemy.gd").read_text(encoding="utf-8")
    hud = (project / "scripts" / "hud.gd").read_text(encoding="utf-8")
    if "footstep_timer" not in player or 'step_grass' not in player:
        raise RuntimeError("Throttled player footsteps were not integrated")
    if 'boss_attack' not in boss or 'boss_hit' not in boss:
        raise RuntimeError("Minotaur audio hooks missing")
    if 'boss_attack' not in insect or 'boss_hit' not in insect:
        raise RuntimeError("Mantis audio hooks missing")
    if 'play_sfx", "buy"' not in hud or 'play_sfx", "equip"' not in hud:
        raise RuntimeError("Shop/equipment audio hooks missing")

    if any(p.name == "RPG_Essentials_Free.zip" for p in project.rglob("*.zip")):
        raise RuntimeError("Standalone RPG Essentials source ZIP must not be packaged inside the project")

    # Preserve the V1.8.6 performance/animation work.
    enemy = (project / "scripts" / "enemy.gd").read_text(encoding="utf-8")
    if "_cached_player" not in enemy or "sleep_distance" not in enemy:
        raise RuntimeError("V1.8.6 enemy performance patch was lost")
    if "AnimatedSprite2D" not in (project / "scenes" / "bosses" / "MinotaurBoss.tscn").read_text(encoding="utf-8"):
        raise RuntimeError("V1.8.6 Minotaur animation scene was lost")


def zip_project(project: Path, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.unlink(missing_ok=True)
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in sorted(project.rglob("*")):
            if path.is_file():
                zf.write(path, f"{PROJECT_FOLDER}/{path.relative_to(project).as_posix()}")
    with zipfile.ZipFile(out, "r") as zf:
        bad = zf.testzip()
        if bad is not None:
            raise RuntimeError(f"Output ZIP corrupt entry: {bad}")
        if not any(name == f"{PROJECT_FOLDER}/project.godot" for name in zf.namelist()):
            raise RuntimeError("Output ZIP does not contain project.godot under the expected top-level folder")


def build_direct_artifact(project: Path) -> None:
    shutil.rmtree(ARTIFACT_DIR, ignore_errors=True)
    target = ARTIFACT_DIR / PROJECT_FOLDER
    shutil.copytree(project, target)


def main() -> None:
    source = DIST / BASE_NAME
    if not source.exists():
        raise SystemExit(f"Missing V1.8.6 build output: {source}")

    shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True, exist_ok=True)
    extracted = WORK / "project"
    safe_extract(source, extracted)
    project = project_root(extracted)

    audio_dir = integrate_audio_pack(project)
    patch_audio_manager(project)
    patch_gameplay_audio(project)
    patch_licenses(project)
    static_validate(project)

    out = DIST / OUT_NAME
    zip_project(project, out)
    build_direct_artifact(project)

    print(f"RPG Essentials integrated WAVs: {len(list(audio_dir.rglob('*.wav')))}")
    print("Mapped live events: attack/hit/potion/inventory/chest/pickup/buy/equip/unequip/boss attack/boss hit/enemy death/footsteps")
    print("Existing music preserved: assets/audio/music_loop.wav")
    print("V1.8.6 performance and boss animation checks preserved")
    print(f"Generated: {out}")
    print(f"Size: {out.stat().st_size} bytes")


if __name__ == "__main__":
    main()
