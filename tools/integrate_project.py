from __future__ import annotations

import json
import os
import re
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "input"
WORK = ROOT / "build_work"
DIST = ROOT / "dist"
OUT_NAME = "Top_Down_Adventure_V1_8_4_ICONS_MINOTAUR_MANTIS.zip"

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
        marker = "[display]"
        block = f"\n[autoload]\n{line}\n\n"
        if marker in text:
            text = text.replace(marker, block + marker, 1)
        else:
            text += block
    pg.write_text(text, encoding="utf-8")


def write_boss_script(project: Path) -> None:
    path = project / "scripts" / "integrated_boss.gd"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(r'''extends CharacterBody2D
class_name IntegratedBoss

signal boss_died(boss_name: String)

@export var boss_name := "Boss"
@export var max_health := 500
@export var move_speed := 55.0
@export var attack_damage := 20
@export var attack_range := 54.0
@export var attack_cooldown := 1.2
@export var reward_gold := 200
@export var reward_scrap := 8
@export var reward_item_id := "boss_crystal"
@export var reward_item_amount := 1

var health := 1
var _attack_timer := 0.0
var _target: Node2D

func _ready() -> void:
    health = max_health
    add_to_group("boss")
    add_to_group("enemy")
    _find_target()

func _physics_process(delta: float) -> void:
    _attack_timer = maxf(0.0, _attack_timer - delta)
    if not is_instance_valid(_target):
        _find_target()
        velocity = Vector2.ZERO
        return
    var offset := _target.global_position - global_position
    var dist := offset.length()
    if dist > attack_range:
        velocity = offset.normalized() * move_speed
        move_and_slide()
    else:
        velocity = Vector2.ZERO
        if _attack_timer <= 0.0:
            _attack_timer = attack_cooldown
            _attack_target()

func _find_target() -> void:
    var players := get_tree().get_nodes_in_group("player")
    if not players.is_empty() and players[0] is Node2D:
        _target = players[0]
        return
    _target = _find_player_recursive(get_tree().current_scene)

func _find_player_recursive(node: Node) -> Node2D:
    if node == null:
        return null
    if node is Node2D and (node.name == "Player" or node.name == "player"):
        return node
    for child in node.get_children():
        var found := _find_player_recursive(child)
        if found != null:
            return found
    return null

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
    modulate = Color(1.0, 0.55, 0.55, 1.0)
    var tween := create_tween()
    tween.tween_property(self, "modulate", Color.WHITE, 0.15)
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


def make_boss_scene(project: Path, scene_name: str, texture: Path, display_name: str, stats: dict) -> Path:
    boss_dir = project / "scenes" / "bosses"
    boss_dir.mkdir(parents=True, exist_ok=True)
    scene = boss_dir / f"{scene_name}.tscn"
    texture_res = res_path(project, texture)
    script_res = "res://scripts/integrated_boss.gd"
    scene.write_text(f'''[gd_scene load_steps=4 format=3]\n\n[ext_resource type="Script" path="{script_res}" id="1_script"]\n[ext_resource type="Texture2D" path="{texture_res}" id="2_texture"]\n\n[sub_resource type="RectangleShape2D" id="RectangleShape2D_boss"]\nsize = Vector2(58, 58)\n\n[node name="{scene_name}" type="CharacterBody2D"]\nscript = ExtResource("1_script")\nboss_name = "{display_name}"\nmax_health = {stats['health']}\nmove_speed = {stats['speed']}\nattack_damage = {stats['damage']}\nattack_range = {stats['range']}\nattack_cooldown = {stats['cooldown']}\nreward_gold = {stats['gold']}\nreward_scrap = {stats['scrap']}\nreward_item_id = "{stats['item']}"\nreward_item_amount = {stats['amount']}\n\n[node name="Sprite2D" type="Sprite2D" parent="."]\ntexture = ExtResource("2_texture")\nscale = Vector2(2.0, 2.0)\n\n[node name="CollisionShape2D" type="CollisionShape2D" parent="."]\nshape = SubResource("RectangleShape2D_boss")\n\n[node name="BossName" type="Label" parent="."]\noffset_left = -70.0\noffset_top = -70.0\noffset_right = 70.0\noffset_bottom = -45.0\ntext = "{display_name}"\nhorizontal_alignment = 1\n''', encoding="utf-8")
    return scene


def write_integration_autoload(project: Path, mino_scene: Path, mantis_scene: Path) -> None:
    path = project / "scripts" / "boss_content_integration.gd"
    mino_res = res_path(project, mino_scene)
    mantis_res = res_path(project, mantis_scene)
    path.write_text(f'''extends Node\n\nconst MINOTAUR_SCENE := preload("{mino_res}")\nconst MANTIS_SCENE := preload("{mantis_res}")\n\nvar _last_scene_id := 0\n\nfunc _ready() -> void:\n    get_tree().node_added.connect(_on_node_added)\n    call_deferred("_try_spawn")\n\nfunc _on_node_added(_node: Node) -> void:\n    call_deferred("_try_spawn")\n\nfunc _try_spawn() -> void:\n    var scene := get_tree().current_scene\n    if scene == null:\n        return\n    var scene_id := scene.get_instance_id()\n    if scene_id == _last_scene_id:\n        return\n    var scene_file := scene.scene_file_path.to_lower()\n    if "main_menu" in scene_file or "menu" in scene.name.to_lower():\n        return\n    var player := _find_player(scene)\n    if player == null:\n        return\n    _last_scene_id = scene_id\n    _spawn_boss(scene, MINOTAUR_SCENE, player.global_position + Vector2(650, 120), "MinotaurBoss")\n    _spawn_boss(scene, MANTIS_SCENE, player.global_position + Vector2(-700, -120), "MantisBoss")\n\nfunc _spawn_boss(parent: Node, packed: PackedScene, pos: Vector2, expected_name: String) -> void:\n    if parent.find_child(expected_name, true, false) != null:\n        return\n    var boss := packed.instantiate()\n    parent.add_child(boss)\n    if boss is Node2D:\n        boss.global_position = pos\n\nfunc _find_player(node: Node) -> Node2D:\n    var players := get_tree().get_nodes_in_group("player")\n    if not players.is_empty() and players[0] is Node2D:\n        return players[0]\n    return _find_player_recursive(node)\n\nfunc _find_player_recursive(node: Node) -> Node2D:\n    if node is Node2D and (node.name == "Player" or node.name == "player"):\n        return node\n    for child in node.get_children():\n        var found := _find_player_recursive(child)\n        if found != null:\n            return found\n    return null\n''', encoding="utf-8")
    ensure_autoload(project, "BossContentIntegration", "res://scripts/boss_content_integration.gd")


def write_icon_library(project: Path, icons_dir: Path) -> None:
    pngs = sorted(icons_dir.rglob("*.png"))
    if not pngs:
        raise RuntimeError("No PNG icons found in 496 RPG icons pack")
    preferred_keys = [
        "sword", "shield", "armor", "helmet", "boots", "ring", "amulet",
        "potion_health", "potion_mana", "key", "crystal", "scrap", "coin",
        "food", "scroll", "bow", "axe", "hammer", "staff", "boss_crystal",
    ]
    mapping = {}
    for i, key in enumerate(preferred_keys):
        mapping[key] = res_path(project, pngs[i % len(pngs)])
    data_dir = project / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "rpg_icon_catalog.json").write_text(json.dumps(mapping, indent=2, ensure_ascii=False), encoding="utf-8")

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
    (docs / "V1_8_4_INTEGRACAO_ICONS_BOSSES.md").write_text('''# V1.8.4 - Integração de ícones e bosses\n\n## Conteúdo integrado\n- Pack 496 RPG Icons copiado para `assets/Icons/RPG_496/`.\n- Boss Minotauro em `scenes/bosses/MinotaurBoss.tscn`.\n- Boss Mantis em `scenes/bosses/MantisBoss.tscn`.\n- Assets originais dos bosses preservados em `assets/Bosses/.../raw/`.\n- `RPGIconLibrary` disponibiliza ícones por `item_id`.\n- `BossContentIntegration` adiciona os dois bosses ao gameplay depois que o Player existe.\n\n## Edição manual\nOs dois bosses são cenas independentes e podem ser abertos no editor da Godot para ajustar vida, dano, velocidade, escala, colisão e recompensas.\n''', encoding="utf-8")


def clean_project(project: Path) -> None:
    for name in [".godot", ".pytest_cache", "__pycache__"]:
        for p in project.rglob(name):
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)


def static_validate(project: Path) -> None:
    if not (project / "project.godot").exists():
        raise RuntimeError("project.godot missing after integration")
    required = [
        project / "scenes" / "bosses" / "MinotaurBoss.tscn",
        project / "scenes" / "bosses" / "MantisBoss.tscn",
        project / "scripts" / "integrated_boss.gd",
        project / "scripts" / "boss_content_integration.gd",
        project / "scripts" / "rpg_icon_library.gd",
        project / "data" / "rpg_icon_catalog.json",
    ]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise RuntimeError("Missing integrated files: " + ", ".join(missing))
    pg = (project / "project.godot").read_text(encoding="utf-8")
    if "BossContentIntegration=" not in pg or "RPGIconLibrary=" not in pg:
        raise RuntimeError("Required autoloads were not registered")


def zip_project(project: Path, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
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
    mino_scene = make_boss_scene(project, "MinotaurBoss", mino_tex, "MINOTAURO", {
        "health": 950, "speed": 64.0, "damage": 34, "range": 62.0, "cooldown": 1.35,
        "gold": 450, "scrap": 18, "item": "boss_crystal", "amount": 2,
    })
    mantis_scene = make_boss_scene(project, "MantisBoss", mantis_tex, "MANTIS ANCIÃO", {
        "health": 780, "speed": 82.0, "damage": 28, "range": 58.0, "cooldown": 0.95,
        "gold": 380, "scrap": 14, "item": "boss_crystal", "amount": 1,
    })
    write_integration_autoload(project, mino_scene, mantis_scene)
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
    print(f"Size: {out.stat().st_size} bytes")


if __name__ == "__main__":
    main()
