from pathlib import Path

src_path = Path('tools/integrate_audio_v187.py')
assert src_path.exists(), 'Integrador modular da V1.8.7 nao existe.'
src = src_path.read_text(encoding='utf-8')
workflow = Path('.github/workflows/build-godot-project.yml').read_text(encoding='utf-8')

assert 'RPG_Essentials_Free.zip' in src, 'Pack RPG Essentials ainda nao faz parte do build.'
assert 'integrate_audio_pack' in src, 'Integrador ainda nao possui rotina dedicada de audio.'
assert 'patch_audio_manager' in src, 'AudioManager ainda nao e atualizado pelo integrador.'
assert 'patch_gameplay_audio' in src, 'Eventos de gameplay ainda nao recebem os novos SFX.'
assert 'attack' in src and 'hit' in src and 'inventory' in src and 'potion' in src, 'Mapeamento basico de SFX incompleto.'
assert 'buy' in src and 'equip' in src and 'confirm' in src, 'Mapeamento de UI/loja/equipamento incompleto.'
assert 'boss_attack' in src and 'boss_hit' in src and 'enemy_death' in src, 'Mapeamento de bosses incompleto.'
assert 'footstep_timer' in src and 'step_grass' in src, 'Passos com limitacao de frequencia nao foram implementados.'
assert 'Top_Down_Adventure_V1_8_7_AUDIO_PERFORMANCE_ANIMATIONS.zip' in src, 'Nome de saida da V1.8.7 nao configurado.'
assert 'integrate_audio_v187.py' in workflow, 'Workflow nao executa o integrador de audio.'
assert 'dist_artifact' in workflow, 'Workflow nao prepara artefato direto do projeto.'

print('v1.8.7 audio integration guard: OK')
