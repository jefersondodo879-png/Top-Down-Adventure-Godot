from __future__ import annotations

import json
import re
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "input"
WORK = ROOT / "build_work"
DIST = ROOT / "dist"
OUT_NAME = "Top_Down_Adventure_V1_8_6_PERFORMANCE_ANIMATIONS.zip"

BASE_ZIP = INPUT / "Top_Down_Adventure_V1_8_3.zip"
ICONS_ZIP = INPUT / "496_RPG_icons.zip"
MINO_ZIP = INPUT / "mino_v1.1_free(1).zip"
INSECTS_ZIP = INPUT / "Animated insect enemy assets(1).zip"


def safe_extract(zpath: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zpath, "r") as zf:
        base = dest.resolve()
        for member in zf.infolist():
            target = (dest / member.filename).resolve()
            if base not in target.parents and target != base:
                raise RuntimeError(f"Unsafe path in {zpath.name}: {member.filename}")
        zf.extractall(dest)


def project_root(extracted: Path) -> Path:
    if (extracted / "project.godot").exists():
        return extracted
    candidates = list(extracted.rglob("project.godot"))
    if not candidates:
        raise RuntimeError("project.godot not found in base project ZIP")
    candidates.sort(key=lambda p: len(p.parts))
    return candidates[0].parent


def copy_tree_contents(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for p in src.rglob("*"):
        rel = p.relative_to(src)
        out = dst / rel
        if p.is_dir():
            out.mkdir(parents=True, exist_ok=True)
        else:
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, out)


def res_path(project: Path, p: Path) -> str:
    return "res://" + p.relative_to(project).as_posix()


def ensure_autoload(project: Path, name: str, script_res: str) -> None:
    pg = project / "project.godot"
    text = pg.read_text(encoding="utf-8")
    line = f'{name}="*{script_res}"'
    if line in text:
        return
    if "[autoload]" in text:
        text = text.replace("[autoload]", "[autoload]\n" + line, 1)
    else:
        text += f"\n[autoload]\n{line}\n"
    pg.write_text(text, encoding="utf-8")


def natural_key(path: Path) -> list[object]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", path.name)]


def _animation_pngs(root: Path, folder_name: str) -> list[Path]:
    matches = [p for p in root.rglob("*.png") if p.parent.name.lower() == folder_name.lower()]
    matches.sort(key=natural_key)
    return matches


def write_minotaur_spriteframes(project: Path, mino_dir: Path) -> Path:
    animations = {
        "idle": (_animation_pngs(mino_dir, "idle"), 8.0, True),
        "walk": (_animation_pngs(mino_dir, "walk"), 10.0, True),
        "attack": (_animation_pngs(mino_dir, "atk_1"), 12.0, False),
    }
    for name, (frames, _, _) in animations.items():
        if not frames:
            raise RuntimeError(f"Minotaur animation frames not found: {name}")

    resources: list[tuple[str, Path]] = []
    animation_entries: list[str] = []
    resource_index = 1

    for anim_name, (frames, speed, loop) in animations.items():
        frame_entries: list[str] = []
        for frame in frames:
            ext_id = f"{resource_index}_{anim_name}_{frame.stem}"
            resources.append((ext_id, frame))
            frame_entries.append(
                '{\n"duration": 1.0,\n"texture": ExtResource("%s")\n}' % ext_id
            )
            resource_index += 1
        animation_entries.append(
            '{\n"frames": [%s],\n"loop": %s,\n"name": &"%s",\n"speed": %.1f\n}'
            % (",\n".join(frame_entries), str(loop).lower(), anim_name, speed)
        )

    out = project / "resources" / "animations" / "minotaur_integrated_frames.tres"
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [f'[gd_resource type="SpriteFrames" load_steps={len(resources) + 1} format=3]', ""]
    for ext_id, frame in resources:
        lines.append(
            f'[ext_resource type="Texture2D" path="{res_path(project, frame)}" id="{ext_id}"]'
        )
    lines += ["", "[resource]", "animations = [%s]" % ",\n".join(animation_entries), ""]
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def write_boss_script(project: Path) -> None:
    path = project / "scripts" / "integrated_boss.gd"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(r'''extends CharacterBody2D
class_name IntegratedBoss

signal boss_died(boss_name: String)

@export var boss_name: String = "Boss"
@export var max_health: int = 500
@export var move_speed: float = 55.0
@export var attack_damage: int = 20
@export var attack_range: float = 54.0
@export var attack_cooldown: float = 1.2
@export var aggro_radius: float = 420.0
@export var leash_radius: float = 620.0
@export var reward_gold: int = 200
@export var reward_scrap: int = 8
@export var reward_item_id: String = "boss_crystal"
@export var reward_item_amount: int = 1

var health: int = 1
var _attack_timer: float = 0.0
var _attack_anim_timer: float = 0.0
var _target_refresh_timer: float = 0.0
var _cached_player: Node2D = null
var _home_position: Vector2
var _engaged: bool = false

@onready var sprite: AnimatedSprite2D = $AnimatedSprite2D

func _ready() -> void:
    health = max_health
    _home_position = global_position
    add_to_group("boss")
    add_to_group("bosses")
    add_to_group("enemies")
    _cached_player = get_tree().get_first_node_in_group("player") as Node2D
    _play_anim("idle")

func _physics_process(delta: float) -> void:
    if health <= 0:
        return
    _attack_timer = maxf(0.0, _attack_timer - delta)
    _attack_anim_timer = maxf(0.0, _attack_anim_timer - delta)
    _target_refresh_timer = maxf(0.0, _target_refresh_timer - delta)

    if _attack_anim_timer > 0.0:
        velocity = Vector2.ZERO
        return

    _refresh_target()
    if not is_instance_valid(_cached_player) or not _engaged:
        _return_home()
        return

    if global_position.distance_to(_home_position) > leash_radius:
        _engaged = false
        _return_home()
        return

    var offset: Vector2 = _cached_player.global_position - global_position
    var dist: float = offset.length()
    if dist > aggro_radius:
        _engaged = false
        _return_home()
        return

    if dist > attack_range:
        velocity = offset.normalized() * move_speed
        sprite.flip_h = velocity.x < 0.0
        move_and_slide()
        _play_anim("walk")
    else:
        velocity = Vector2.ZERO
        _play_anim("idle")
        if _attack_timer <= 0.0:
            _attack_timer = attack_cooldown
            _attack_target()

func _refresh_target() -> void:
    if is_instance_valid(_cached_player):
        if global_position.distance_to(_cached_player.global_position) <= aggro_radius:
            _engaged = true
        return
    if _target_refresh_timer > 0.0:
        return
    _target_refresh_timer = 0.25
    _cached_player = get_tree().get_first_node_in_group("player") as Node2D
    if is_instance_valid(_cached_player):
        _engaged = global_position.distance_to(_cached_player.global_position) <= aggro_radius

func _return_home() -> void:
    var distance_home := global_position.distance_to(_home_position)
    if distance_home <= 6.0:
        velocity = Vector2.ZERO
        _play_anim("idle")
        return
    velocity = global_position.direction_to(_home_position) * move_speed
    sprite.flip_h = velocity.x < 0.0
    move_and_slide()
    _play_anim("walk")

func _attack_target() -> void:
    if not is_instance_valid(_cached_player):
        return
    _attack_anim_timer = minf(0.62, attack_cooldown * 0.65)
    _play_anim("attack", true)
    if _cached_player.has_method("take_damage"):
        _cached_player.call("take_damage", attack_damage)
    elif _cached_player.has_method("apply_damage"):
        _cached_player.call("apply_damage", attack_damage)
    elif _cached_player.has_method("damage"):
        _cached_player.call("damage", attack_damage)

func _play_anim(anim_name: String, restart: bool = false) -> void:
    if not sprite.sprite_frames.has_animation(anim_name):
        return
    if restart or sprite.animation != anim_name or not sprite.is_playing():
        sprite.play(anim_name)

func take_damage(amount: int) -> void:
    if amount <= 0 or health <= 0:
        return
    health = maxi(0, health - amount)
    _engaged = true
    modulate = Color(1.0, 0.62, 0.62, 1.0)
    var tween := create_tween()
    tween.tween_property(self, "modulate", Color.WHITE, 0.14)
    if health <= 0:
        _die()

func apply_damage(amount: int) -> void:
    take_damage(amount)

func _die() -> void:
    velocity = Vector2.ZERO
    _grant_rewards()
    boss_died.emit(boss_name)
    queue_free()

func _grant_rewards() -> void:
    var gs := get_node_or_null("/root/GameState")
    if gs == null:
        return
    if gs.has_method("add_coins"):
        gs.call("add_coins", reward_gold)
    elif "coins" in gs:
        gs.set("coins", int(gs.get("coins")) + reward_gold)
    if gs.has_method("add_item"):
        if reward_scrap > 0:
            gs.call("add_item", "scrap", reward_scrap)
        if reward_item_amount > 0:
            gs.call("add_item", reward_item_id, reward_item_amount)

func get_boss_name() -> String:
    return boss_name

func get_boss_health_ratio() -> float:
    if max_health <= 0:
        return 0.0
    return clampf(float(health) / float(max_health), 0.0, 1.0)

func get_boss_health_text() -> String:
    return "%d / %d" % [health, max_health]

func is_boss_active() -> bool:
    return _engaged and health > 0 and visible
''', encoding="utf-8")


def make_minotaur_scene(project: Path, frames: Path) -> Path:
    scene = project / "scenes" / "bosses" / "MinotaurBoss.tscn"
    scene.parent.mkdir(parents=True, exist_ok=True)
    scene.write_text(f'''[gd_scene load_steps=4 format=3]\n\n[ext_resource type="Script" path="res://scripts/integrated_boss.gd" id="1_script"]\n[ext_resource type="SpriteFrames" path="{res_path(project, frames)}" id="2_frames"]\n\n[sub_resource type="RectangleShape2D" id="RectangleShape2D_boss"]\nsize = Vector2(72, 58)\n\n[node name="MinotaurBoss" type="CharacterBody2D"]\nscript = ExtResource("1_script")\nboss_name = "MINOTAURO"\nmax_health = 950\nmove_speed = 58.0\nattack_damage = 34\nattack_range = 58.0\nattack_cooldown = 1.35\naggro_radius = 430.0\nleash_radius = 620.0\nreward_gold = 450\nreward_scrap = 18\nreward_item_id = "boss_crystal"\nreward_item_amount = 2\n\n[node name="AnimatedSprite2D" type="AnimatedSprite2D" parent="."]\nsprite_frames = ExtResource("2_frames")\nanimation = &"idle"\nautoplay = "idle"\nscale = Vector2(0.65, 0.65)\n\n[node name="CollisionShape2D" type="CollisionShape2D" parent="."]\nposition = Vector2(0, 18)\nshape = SubResource("RectangleShape2D_boss")\n''', encoding="utf-8")
    return scene


def make_mantis_scene(project: Path) -> Path:
    # Reuse the existing animated insect system from the base project.
    scene = project / "scenes" / "bosses" / "MantisBoss.tscn"
    scene.parent.mkdir(parents=True, exist_ok=True)
    scene.write_text('''[gd_scene load_steps=2 format=3]\n\n[ext_resource type="PackedScene" path="res://scenes/enemies/insect_enemy.tscn" id="1_insect"]\n\n[node name="MantisBoss" instance=ExtResource("1_insect")]\nenemy_type = "mantis_boss"\nrespawn_delay = 999999.0\n''', encoding="utf-8")
    return scene


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"Performance patch pattern not found: {label}")
    return text.replace(old, new, 1)


def patch_enemy_performance(project: Path) -> None:
    enemy_path = project / "scripts" / "enemy.gd"
    insect_path = project / "scripts" / "insect_enemy.gd"

    enemy = enemy_path.read_text(encoding="utf-8")
    enemy = _replace_once(
        enemy,
        '@export var respawn_delay: float = 10.0\n',
        '@export var respawn_delay: float = 10.0\n@export var sleep_distance: float = 460.0\n',
        'enemy sleep_distance',
    )
    enemy = _replace_once(
        enemy,
        'var initial_collision_mask: int\n',
        'var initial_collision_mask: int\nvar _cached_player: Node2D = null\n',
        'enemy cached player var',
    )
    enemy = _replace_once(
        enemy,
        'func _ready() -> void:\n    add_to_group("enemies")\n',
        'func _ready() -> void:\n    add_to_group("enemies")\n    _cached_player = get_tree().get_first_node_in_group("player") as Node2D\n',
        'enemy cache ready',
    )
    enemy = _replace_once(
        enemy,
        '''    var player := get_tree().get_first_node_in_group("player") as Node2D\n    if player == null:\n        return\n    var distance := global_position.distance_to(player.global_position)\n    if distance > detection_range:\n        velocity = velocity.move_toward(Vector2.ZERO, 8.0)\n        move_and_slide()\n        _play_state("idle")\n        return\n''',
        '''    if not is_instance_valid(_cached_player):\n        _cached_player = get_tree().get_first_node_in_group("player") as Node2D\n    var player := _cached_player\n    if player == null:\n        return\n    var distance := global_position.distance_to(player.global_position)\n    if distance > sleep_distance:\n        velocity = Vector2.ZERO\n        return\n    if distance > detection_range:\n        velocity = Vector2.ZERO\n        _play_state("idle")\n        return\n''',
        'enemy far processing',
    )
    enemy_path.write_text(enemy, encoding="utf-8")

    insect = insect_path.read_text(encoding="utf-8")
    insect = _replace_once(
        insect,
        '@export var respawn_delay: float = 14.0\n',
        '@export var respawn_delay: float = 14.0\n@export var sleep_distance: float = 480.0\n',
        'insect sleep_distance',
    )
    insect = _replace_once(
        insect,
        'var initial_collision_mask: int\n',
        'var initial_collision_mask: int\nvar _cached_player: Node2D = null\n',
        'insect cached player var',
    )
    insect = _replace_once(
        insect,
        'func _ready() -> void:\n    add_to_group("enemies")\n',
        'func _ready() -> void:\n    add_to_group("enemies")\n    _cached_player = get_tree().get_first_node_in_group("player") as Node2D\n',
        'insect cache ready',
    )
    insect = _replace_once(
        insect,
        '''    var player := get_tree().get_first_node_in_group("player") as Node2D\n    if player == null:\n        return\n    var distance := global_position.distance_to(player.global_position)\n''',
        '''    if not is_instance_valid(_cached_player):\n        _cached_player = get_tree().get_first_node_in_group("player") as Node2D\n    var player := _cached_player\n    if player == null:\n        return\n    var distance := global_position.distance_to(player.global_position)\n    if distance > sleep_distance:\n        velocity = Vector2.ZERO\n        return\n''',
        'insect far processing',
    )
    insect = insect.replace('            scale = Vector2(1.6, 1.6)', '            scale = Vector2(1.25, 1.25)', 1)
    insect_path.write_text(insect, encoding="utf-8")

    # Boss HUD group lookup does not need to happen every rendered frame.
    hud_path = project / "scripts" / "hud.gd"
    hud = hud_path.read_text(encoding="utf-8")
    hud = _replace_once(
        hud,
        'var active_modal: String = ""\n',
        'var active_modal: String = ""\nvar boss_hud_timer: float = 0.0\n',
        'hud boss timer',
    )
    hud = _replace_once(
        hud,
        '    _refresh_boss_hud()\n    if hide_timer > 0.0:\n',
        '    boss_hud_timer -= delta\n    if boss_hud_timer <= 0.0:\n        boss_hud_timer = 0.12\n        _refresh_boss_hud()\n    if hide_timer > 0.0:\n',
        'hud boss refresh throttle',
    )
    hud_path.write_text(hud, encoding="utf-8")


def _region_spawn_position(text: str, fallback: tuple[float, float]) -> tuple[float, float]:
    matches = re.findall(
        r"position\s*=\s*Vector2\(\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)",
        text,
    )
    points = [(float(x), float(y)) for x, y in matches]
    if len(points) < 4:
        return fallback
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    width = max_x - min_x
    height = max_y - min_y
    if width < 300 or height < 220:
        return fallback
    return (max_x - min(180.0, width * 0.12), max_y - min(160.0, height * 0.12))


def embed_boss_in_region(
    project: Path,
    region_rel: str,
    boss_scene: Path,
    node_name: str,
    fallback: tuple[float, float],
) -> None:
    region = project / region_rel
    if not region.exists():
        raise RuntimeError(f"Region scene not found: {region_rel}")
    text = region.read_text(encoding="utf-8")
    if f'name="{node_name}"' in text:
        return
    ext_id = f"boss_{node_name.lower()}"
    boss_res = res_path(project, boss_scene)
    ext_line = f'[ext_resource type="PackedScene" path="{boss_res}" id="{ext_id}"]'
    lines = text.splitlines()
    insert_at = 1
    for i, line in enumerate(lines):
        if line.startswith("[ext_resource"):
            insert_at = i + 1
    lines.insert(insert_at, ext_line)
    text = "\n".join(lines) + "\n"
    header = re.search(r"\[gd_scene([^\]]*)\]", text)
    if header:
        m = re.search(r"load_steps=(\d+)", header.group(1))
        if m:
            old = int(m.group(1))
            text = text.replace(f"load_steps={old}", f"load_steps={old + 1}", 1)
    x, y = _region_spawn_position(text, fallback)
    text += (
        f'\n[node name="{node_name}" parent="." instance=ExtResource("{ext_id}")]\n'
        f'position = Vector2({x:.1f}, {y:.1f})\n'
    )
    region.write_text(text, encoding="utf-8")


def write_icon_library(project: Path, icons_dir: Path) -> None:
    pngs = sorted(icons_dir.rglob("*.png"))
    if not pngs:
        raise RuntimeError("No PNG icons found in 496 RPG icons pack")
    preferred_keys = [
        "sword", "shield", "armor", "helmet", "boots", "ring", "amulet",
        "potion_health", "potion_mana", "key", "crystal", "scrap", "coin",
        "food", "scroll", "bow", "axe", "hammer", "staff", "boss_crystal",
    ]
    mapping: dict[str, str] = {}
    for i, key in enumerate(preferred_keys):
        mapping[key] = res_path(project, pngs[i % len(pngs)])
    data_dir = project / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "rpg_icon_catalog.json").write_text(
        json.dumps(mapping, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    lib = project / "scripts" / "rpg_icon_library.gd"
    lib.write_text(r'''extends Node

var _catalog: Dictionary = {}

func _ready() -> void:
    var path := "res://data/rpg_icon_catalog.json"
    if not FileAccess.file_exists(path):
        return
    var file := FileAccess.open(path, FileAccess.READ)
    if file == null:
        return
    var parsed = JSON.parse_string(file.get_as_text())
    if parsed is Dictionary:
        _catalog = parsed

func get_icon_path(item_id: String) -> String:
    var key := item_id.to_lower()
    if _catalog.has(key):
        return String(_catalog[key])
    for catalog_key in _catalog.keys():
        if String(catalog_key) in key or key in String(catalog_key):
            return String(_catalog[catalog_key])
    return ""

func get_icon(item_id: String) -> Texture2D:
    var path := get_icon_path(item_id)
    if path.is_empty():
        return null
    return load(path) as Texture2D
''', encoding="utf-8")
    ensure_autoload(project, "RPGIconLibrary", "res://scripts/rpg_icon_library.gd")


def write_notes(project: Path) -> None:
    docs = project / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "V1_8_6_PERFORMANCE_ANIMATIONS.md").write_text(
        '''# V1.8.6 - Performance e animações dos bosses\n\n'''
        '''- Minotauro agora usa AnimatedSprite2D com idle, walk e attack.\n'''
        '''- Mantis boss reutiliza o sistema `insect_enemy.tscn` já animado no projeto.\n'''
        '''- IA de inimigos comuns e insetos passa a armazenar referência do Player em cache.\n'''
        '''- Inimigos muito distantes entram em caminho leve e deixam de chamar movimento/animação todo frame.\n'''
        '''- Atualização do HUD de boss foi limitada a aproximadamente 8 vezes por segundo.\n'''
        '''- Mantis permanece na Floresta Sussurrante e Minotauro na Masmorra Antiga.\n''',
        encoding="utf-8",
    )


def clean_project(project: Path) -> None:
    for name in [".godot", ".pytest_cache", "__pycache__"]:
        for p in project.rglob(name):
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)


def static_validate(project: Path) -> None:
    required = [
        project / "project.godot",
        project / "scenes" / "bosses" / "MinotaurBoss.tscn",
        project / "scenes" / "bosses" / "MantisBoss.tscn",
        project / "resources" / "animations" / "minotaur_integrated_frames.tres",
        project / "scripts" / "integrated_boss.gd",
        project / "scripts" / "enemy.gd",
        project / "scripts" / "insect_enemy.gd",
        project / "scripts" / "rpg_icon_library.gd",
        project / "data" / "rpg_icon_catalog.json",
    ]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise RuntimeError("Missing integrated files: " + ", ".join(missing))

    mino = (project / "scenes" / "bosses" / "MinotaurBoss.tscn").read_text(encoding="utf-8")
    mantis = (project / "scenes" / "bosses" / "MantisBoss.tscn").read_text(encoding="utf-8")
    frames = (project / "resources" / "animations" / "minotaur_integrated_frames.tres").read_text(encoding="utf-8")
    enemy = (project / "scripts" / "enemy.gd").read_text(encoding="utf-8")
    insect = (project / "scripts" / "insect_enemy.gd").read_text(encoding="utf-8")

    if 'type="AnimatedSprite2D"' not in mino or 'autoplay = "idle"' not in mino:
        raise RuntimeError("Minotaur is not using AnimatedSprite2D")
    for animation_name in ['&"idle"', '&"walk"', '&"attack"']:
        if animation_name not in frames:
            raise RuntimeError(f"Missing Minotaur animation: {animation_name}")
    if 'insect_enemy.tscn' not in mantis or 'enemy_type = "mantis_boss"' not in mantis:
        raise RuntimeError("Mantis boss is not using the animated insect system")
    if '_cached_player' not in enemy or 'sleep_distance' not in enemy:
        raise RuntimeError("Enemy performance patch missing")
    if '_cached_player' not in insect or 'sleep_distance' not in insect:
        raise RuntimeError("Insect performance patch missing")

    forest = (project / "scenes" / "world" / "regions" / "02_floresta_sussurrante.tscn").read_text(encoding="utf-8")
    dungeon = (project / "scenes" / "world" / "regions" / "06_masmorra_antiga.tscn").read_text(encoding="utf-8")
    if 'name="MantisBoss"' not in forest:
        raise RuntimeError("MantisBoss was not embedded in forest region")
    if 'name="MinotaurBoss"' not in dungeon:
        raise RuntimeError("MinotaurBoss was not embedded in dungeon region")


def zip_project(project: Path, out: Path) -> None:
    if out.exists():
        out.unlink()
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for p in project.rglob("*"):
            if p.is_file():
                zf.write(p, p.relative_to(project).as_posix())


def main() -> None:
    for p in [BASE_ZIP, ICONS_ZIP, MINO_ZIP, INSECTS_ZIP]:
        if not p.exists():
            raise SystemExit(f"Missing input: {p}")

    shutil.rmtree(WORK, ignore_errors=True)
    DIST.mkdir(parents=True, exist_ok=True)

    base_extract = WORK / "base"
    safe_extract(BASE_ZIP, base_extract)
    project = project_root(base_extract)

    icons_unpack = WORK / "icons"
    mino_unpack = WORK / "mino"
    insects_unpack = WORK / "insects"
    safe_extract(ICONS_ZIP, icons_unpack)
    safe_extract(MINO_ZIP, mino_unpack)
    safe_extract(INSECTS_ZIP, insects_unpack)

    icons_dst = project / "assets" / "Icons" / "RPG_496" / "raw"
    mino_dst = project / "assets" / "Bosses" / "Minotaur" / "raw"
    mantis_dst = project / "assets" / "Bosses" / "Mantis" / "raw"
    copy_tree_contents(icons_unpack, icons_dst)
    copy_tree_contents(mino_unpack, mino_dst)
    copy_tree_contents(insects_unpack, mantis_dst)

    patch_enemy_performance(project)
    write_boss_script(project)
    mino_frames = write_minotaur_spriteframes(project, mino_dst)
    mino_scene = make_minotaur_scene(project, mino_frames)
    mantis_scene = make_mantis_scene(project)

    embed_boss_in_region(
        project,
        "scenes/world/regions/02_floresta_sussurrante.tscn",
        mantis_scene,
        "MantisBoss",
        fallback=(1180.0, 760.0),
    )
    embed_boss_in_region(
        project,
        "scenes/world/regions/06_masmorra_antiga.tscn",
        mino_scene,
        "MinotaurBoss",
        fallback=(1120.0, 720.0),
    )

    write_icon_library(project, icons_dst)
    write_notes(project)
    clean_project(project)
    static_validate(project)

    out = DIST / OUT_NAME
    zip_project(project, out)
    with zipfile.ZipFile(out, "r") as zf:
        bad = zf.testzip()
        if bad is not None:
            raise RuntimeError(f"Corrupt ZIP entry: {bad}")

    print(f"Generated: {out}")
    print("Minotaur animations: idle/walk/attack")
    print("Mantis animations: existing mantis_frames.tres through insect_enemy.tscn")
    print("Performance patch: cached player + far-enemy sleep path + throttled boss HUD")
    print(f"Size: {out.stat().st_size} bytes")


if __name__ == "__main__":
    main()
