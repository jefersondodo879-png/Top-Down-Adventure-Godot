from pathlib import Path

src = Path('tools/integrate_project.py').read_text(encoding='utf-8')
workflow = Path('.github/workflows/build-godot-project.yml').read_text(encoding='utf-8')

assert 'RPG_Essentials_Free.zip' in src or 'RPG_Essentials_Free.zip' in workflow, 'Pack RPG Essentials ainda nao faz parte do build.'
assert 'integrate_audio_pack' in src, 'Integrador ainda nao possui rotina dedicada de audio.'
assert 'patch_audio_manager' in src, 'AudioManager ainda nao e atualizado pelo integrador.'
assert 'attack' in src and 'hit' in src and 'inventory' in src and 'potion' in src, 'Mapeamento basico de SFX incompleto.'
assert 'buy' in src and 'equip' in src and 'confirm' in src, 'Mapeamento de UI/loja/equipamento incompleto.'
assert 'Top_Down_Adventure_V1_8_7_AUDIO_PERFORMANCE_ANIMATIONS.zip' in src, 'Nome de saida da V1.8.7 nao configurado.'

print('v1.8.7 audio integration guard: OK')
