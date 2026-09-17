from __future__ import annotations

import json
import re
import shutil
import struct
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "input"
WORK = ROOT / "build_work"
DIST = ROOT / "dist"
OUT_NAME = "Top_Down_Adventure_V1_8_5_BOSSES_ORGANIZADOS.zip"

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


def pick_png(folder: Path, preferred: list[str]) -> Path:
    pngs = sorted(folder.rglob("*.png"))
    if not pngs:
        raise RuntimeError(f"No PNG found in {folder}")
    lowers = [(p, p.name.lower()) for p in pngs]
    for token in preferred:
        token = token.lower()
        for p, name in lowers:
            if token in name:
                return p
    return pngs[0]


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


def png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as f:
        sig = f.read(24)
    if len(sig) < 24 or sig[:8] != b"\x89PNG\r\n\x1a\n":
        return (64, 64)
    return struct.unpack(">II", sig[16:24])


def frame_rect_for_texture(path: Path) -> tuple[int, int]:
    width, height = png_dimensions(path)
    if width >= height * 2:
        # Horizontal sprite strip/sheet: use the first square-ish frame.
        return (min(height, width), height)
    if height >= width * 2:
        # Vertical sprite strip/sheet.
        return (width, min(width, height))
    return (width, height)


def display_scale(path: Path, target_height: float) -> float:
    _, frame_h = frame_rect_for_texture(path)
    if frame_h <= 0:
        return 1.0
    value = target_height / float(frame_h)
    return max(0.18, min(1.15, value))


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
var _target: Node2D = null
var _home_position: Vector2

func _ready() -> void:
    health = max_health
    _home_position = global_position
    add_to_group("boss")
    add_to_group("enemy")

func _physics_process(delta: float) -> void:
    _attack_timer = maxf(0.0, _attack_timer - delta)
    _refresh_target()

    if not is_instance_valid(_target):
        _return_home()
        return

    if global_position.distance_to(_home_position) > leash_radius:
        _target = null
        _return_home()
        return

    var offset: Vector2 = _target.global_position - global_position
    var dist: float = offset.length()
    if dist > attack_range:
        velocity = offset.normalized() * move_speed
        move_and_slide()
    else:
        velocity = Vector2.ZERO
        if _attack_timer <= 0.0:
            _attack_timer = attack_cooldown
            _attack_target()

func _refresh_target() -> void:
    if is_instance_valid(_target):
        if global_position.distance_to(_target.global_position) <= aggro_radius:
            return
        _target = null

    var players: Array[Node] = get_tree().get_nodes_in_group("player")
    if not players.is_empty() and players[0] is Node2D:
        var candidate := players[0] as Node2D
        if global_position.distance_to(candidate.global_position) <= aggro_radius:
            _target = candidate
            return

    var scene := get_tree().current_scene
    var fallback := _find_player_recursive(scene)
    if fallback != null and global_position.distance_to(fallback.global_position) <= aggro_radius:
        _target = fallback

func _find_player_recursive(node: Node) -> Node2D:
    if node == null:
        return null
    if node is Node2D and (node.name == "Player" or node.name == "player"):
        return node as Node2D
    for child in node.get_children():
        var found := _find_player_recursive(child)
        if found != null:
            return found
    return null

func _return_home() -> void:
    var distance_home := global_position.distance_to(_home_position)
    if distance_home <= 6.0:
        velocity = Vector2.ZERO
        return
    velocity = global_position.direction_to(_home_position) * move_speed
    move_and_slide()

func _attack_target() -> void:
    if not is_instance_valid(_target):
        return
    if _target.has_method("take_damage"):
        _target.call("take_damage", attack_damage)
    elif _target.has_method("apply_damage"):
        _target.call("apply_damage", attack_damage)
    elif _target.has_method("damage"):
        _target.call("damage", attack_damage)

func take_damage(amount: int) -> void:
    if amount <= 0 or health <= 0:
        return
    health = maxi(0, health - amount)
    modulate = Color(1.0, 0.62, 0.62, 1.0)
    var tween := create_tween()
    tween.tween_property(self, "modulate", Color.WHITE, 0.14)
    if health <= 0:
        _die()

func apply_damage(amount: int) -> void:
    take_damage(amount)

func _die() -> void:
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
''', encoding="utf-8")


def make_boss_scene(
    project: Path,
    scene_name: str,
    texture: Path,
    display_name: str,
    stats: dict,
    target_height: float,
) -> Path:
    boss_dir = project / "scenes" / "bosses"
    boss_dir.mkdir(parents=True, exist_ok=True)
    scene = boss_dir / f"{scene_name}.tscn"
    texture_res = res_path(project, texture)
    script_res = "res://scripts/integrated_boss.gd"
    frame_w, frame_h = frame_rect_for_texture(texture)
    scale = display_scale(texture, target_height)

    scene.write_text(f'''[gd_scene load_steps=4 format=3]\n\n[ext_resource type="Script" path="{script_res}" id="1_script"]\n[ext_resource type="Texture2D" path="{texture_res}" id="2_texture"]\n\n[sub_resource type="RectangleShape2D" id="RectangleShape2D_boss"]\nsize = Vector2(52, 44)\n\n[node name="{scene_name}" type="CharacterBody2D"]\nscript = ExtResource("1_script")\nboss_name = "{display_name}"\nmax_health = {stats['health']}\nmove_speed = {stats['speed']}\nattack_damage = {stats['damage']}\nattack_range = {stats['range']}\nattack_cooldown = {stats['cooldown']}\naggro_radius = {stats['aggro']}\nleash_radius = {stats['leash']}\nreward_gold = {stats['gold']}\nreward_scrap = {stats['scrap']}\nreward_item_id = "{stats['item']}"\nreward_item_amount = {stats['amount']}\n\n[node name="Sprite2D" type="Sprite2D" parent="."]\ntexture = ExtResource("2_texture")\nregion_enabled = true\nregion_rect = Rect2(0, 0, {frame_w}, {frame_h})\nscale = Vector2({scale:.4f}, {scale:.4f})\n\n[node name="CollisionShape2D" type="CollisionShape2D" parent="."]\nposition = Vector2(0, 12)\nshape = SubResource("RectangleShape2D_boss")\n''', encoding="utf-8")
    return scene


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

    # Far lower-right corner inside the region, away from common entrance/NPC cluster.
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
        attrs = header.group(1)
        m = re.search(r"load_steps=(\d+)", attrs)
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
    (docs / "V1_8_5_BOSSES_ORGANIZADOS.md").write_text(
        '''# V1.8.5 - Bosses organizados\n\n'''
        '''- Minotauro integrado em `scenes/world/regions/06_masmorra_antiga.tscn`.\n'''
        '''- Mantis Ancião integrado em `scenes/world/regions/02_floresta_sussurrante.tscn`.\n'''
        '''- Não existe mais spawn automático de bosses perto do Player.\n'''
        '''- Escala visual é calculada pelo tamanho real da textura e limitada.\n'''
        '''- Sprite sheets exibem apenas o primeiro frame em vez da imagem inteira.\n'''
        '''- Bosses possuem raio de agressão e limite de perseguição para não invadir outras áreas.\n'''
        '''- As cenas `MinotaurBoss.tscn` e `MantisBoss.tscn` continuam editáveis manualmente.\n''',
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
        project / "scripts" / "integrated_boss.gd",
        project / "scripts" / "rpg_icon_library.gd",
        project / "data" / "rpg_icon_catalog.json",
        project / "scenes" / "world" / "regions" / "02_floresta_sussurrante.tscn",
        project / "scenes" / "world" / "regions" / "06_masmorra_antiga.tscn",
    ]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise RuntimeError("Missing integrated files: " + ", ".join(missing))

    pg = (project / "project.godot").read_text(encoding="utf-8")
    if "BossContentIntegration" in pg:
        raise RuntimeError("Old global BossContentIntegration autoload still present")

    mino = (project / "scenes" / "bosses" / "MinotaurBoss.tscn").read_text(encoding="utf-8")
    mantis = (project / "scenes" / "bosses" / "MantisBoss.tscn").read_text(encoding="utf-8")
    if "Vector2(2.0, 2.0)" in mino or "Vector2(2.0, 2.0)" in mantis:
        raise RuntimeError("Unsafe boss scale 2.0 detected")

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

    mino_tex = pick_png(mino_dst, ["idle", "walk", "run", "attack", "mino"])
    mantis_tex = pick_png(mantis_dst, ["mantismove", "mantisattack", "mantis"])

    write_boss_script(project)
    mino_scene = make_boss_scene(
        project,
        "MinotaurBoss",
        mino_tex,
        "MINOTAURO",
        {
            "health": 950,
            "speed": 58.0,
            "damage": 34,
            "range": 58.0,
            "cooldown": 1.35,
            "aggro": 430.0,
            "leash": 620.0,
            "gold": 450,
            "scrap": 18,
            "item": "boss_crystal",
            "amount": 2,
        },
        target_height=104.0,
    )
    mantis_scene = make_boss_scene(
        project,
        "MantisBoss",
        mantis_tex,
        "MANTIS ANCIÃO",
        {
            "health": 780,
            "speed": 70.0,
            "damage": 28,
            "range": 52.0,
            "cooldown": 0.95,
            "aggro": 390.0,
            "leash": 560.0,
            "gold": 380,
            "scrap": 14,
            "item": "boss_crystal",
            "amount": 1,
        },
        target_height=78.0,
    )

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
    print(f"Minotaur texture: {mino_tex.name}, dimensions={png_dimensions(mino_tex)}, scale={display_scale(mino_tex, 104.0):.4f}")
    print(f"Mantis texture: {mantis_tex.name}, dimensions={png_dimensions(mantis_tex)}, scale={display_scale(mantis_tex, 78.0):.4f}")
    print(f"Size: {out.stat().st_size} bytes")


if __name__ == "__main__":
    main()
