from pathlib import Path

# Guard for the lag and static-boss regression reported from V1.8.5.
src = Path('tools/integrate_project.py').read_text(encoding='utf-8')

assert 'AnimatedSprite2D' in src, 'Bosses ainda usam Sprite2D estatico.'
assert 'write_minotaur_spriteframes' in src, 'Minotauro ainda nao cria SpriteFrames com idle/walk/attack.'
assert 'mantis_boss' in src and 'insect_enemy.tscn' in src, 'Mantis boss deve reutilizar o sistema animado existente.'
assert 'patch_enemy_performance' in src, 'Integrador ainda nao aplica a otimizacao dos inimigos.'
assert '_cached_player' in src, 'IA dos inimigos ainda busca o player repetidamente em vez de usar cache.'
assert 'sleep_distance' in src, 'Inimigos distantes ainda nao possuem modo leve de processamento.'

print('v1.8.6 performance/animation guard: OK')
