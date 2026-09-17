from pathlib import Path

src = Path('tools/integrate_project.py').read_text(encoding='utf-8')

assert 'player.global_position + Vector2(650, 120)' not in src, (
    'Boss Minotauro ainda esta sendo spawnado perto do Player.'
)
assert 'player.global_position + Vector2(-700, -120)' not in src, (
    'Boss Mantis ainda esta sendo spawnado perto do Player.'
)
assert 'scale = Vector2(2.0, 2.0)' not in src, (
    'Boss ainda usa escala fixa 2.0 e pode ficar gigante.'
)
assert 'ensure_autoload(project, "BossContentIntegration"' not in src, (
    'Integracao de boss ainda esta como autoload global e pode invadir qualquer mapa.'
)

print('boss layout guard: OK')
