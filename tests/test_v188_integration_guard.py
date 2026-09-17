from pathlib import Path

src = Path("tools/integrate_v188.py")
workflow = Path(".github/workflows/build-godot-project.yml").read_text(encoding="utf-8")

assert src.exists(), "Integrador V1.8.8 ainda nao existe"
text = src.read_text(encoding="utf-8")
assert 'BASE_NAME = "Top_Down_Adventure_V1_8_7_AUDIO_PERFORMANCE_ANIMATIONS.zip"' in text
assert 'OUT_NAME = "Top_Down_Adventure_V1_8_8_GAMEPLAY_EQUIPMENT_BILLING.zip"' in text
assert "patch_boss_lifecycle" in text
assert "patch_mobile_input" in text
assert "patch_equipment_inventory" in text
assert "integrate_google_play_billing" in text
assert "copy_backend" in text
assert "integrate_v188.py" in workflow

print("v1.8.8 integration guard: OK")
