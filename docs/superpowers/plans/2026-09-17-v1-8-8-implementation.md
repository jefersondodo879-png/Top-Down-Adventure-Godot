# V1.8.8 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar a V1.8.8 sobre a V1.8.7 corrigindo boss HUD/respawn, touch Android, inventário/equipamentos/ícones e adicionando compras consumíveis reais da Google Play com backend PHP/MySQL seguro.

**Architecture:** A V1.8.8 será aplicada como uma nova etapa modular `tools/integrate_v188.py` sobre o ZIP gerado pela V1.8.7, preservando os integradores anteriores. Dentro do projeto Godot, estado de boss, input mobile, equipamentos e billing terão responsabilidades separadas e interfaces simples; o backend PHP valida e consome compras no Google Play antes de autorizar recompensas.

**Tech Stack:** Godot 4.7.2 / GDScript, GodotGooglePlayBilling 3.3.0 (Google Play Billing Library 9.1.0), Android Gradle Build, Python 3 integrator/tests, PHP 8+, MySQL 8+, Google Play Developer API v3.

**Spec:** `docs/superpowers/specs/2026-09-17-v1-8-8-system-fixes-design.md`

## Global Constraints

- Base obrigatória: saída final da V1.8.7 `Top_Down_Adventure_V1_8_7_AUDIO_PERFORMANCE_ANIMATIONS.zip`.
- Preservar Minotaur, Mantis, áudio RPG Essentials, música, quests e otimizações da V1.8.6/V1.8.7.
- Android: movimento touch não pode disparar ataque; ataque touch somente pelo botão ATACAR.
- Equipamento: exatamente 1 arma + 5 armaduras (`helmet`, `chest`, `gloves`, `pants`, `boots`).
- Armaduras não alteram visualmente o sprite do personagem.
- Todos os cinco produtos Google Play são consumíveis: `gems_100`, `gems_550`, `gems_1200`, `gems_3000`, `starter_pack`.
- `starter_pack` concede 500 Gemas + 50 Cristais.
- Preços devem vir da Google Play; não codificar preços fixos no jogo.
- Nenhuma credencial Google/MySQL privada dentro do APK/ZIP do projeto Godot; apenas `config.example.php` no backend.
- Para compras consumíveis, o backend deve verificar o token e usar `purchases.products:consume` após conceder o entitlement; não conceder em estado PENDING.
- Save da V1.8.7 deve migrar sem perda silenciosa de itens.
- ZIP final deve conter uma única pasta raiz.

---

### Task 1: Criar o estágio modular V1.8.8 e guardas de regressão

**Files:**
- Create: `tools/integrate_v188.py`
- Create: `tests/test_v188_integration_guard.py`
- Modify: `.github/workflows/build-godot-project.yml`

**Interfaces:**
- Consumes: `dist/Top_Down_Adventure_V1_8_7_AUDIO_PERFORMANCE_ANIMATIONS.zip` produzido por `tools/integrate_audio_v187.py`.
- Produces: `dist/Top_Down_Adventure_V1_8_8_GAMEPLAY_EQUIPMENT_BILLING.zip` e `dist_artifact/Top_Down_Adventure_V1_8_8_GAMEPLAY_EQUIPMENT_BILLING/`.
- Entrypoint Python: `main() -> None`.

- [ ] **Step 1: Escrever o teste inicialmente vermelho**

```python
from pathlib import Path

src = Path("tools/integrate_v188.py")
workflow = Path(".github/workflows/build-godot-project.yml").read_text(encoding="utf-8")

assert src.exists(), "Integrador V1.8.8 ainda não existe"
text = src.read_text(encoding="utf-8")
assert 'BASE_NAME = "Top_Down_Adventure_V1_8_7_AUDIO_PERFORMANCE_ANIMATIONS.zip"' in text
assert 'OUT_NAME = "Top_Down_Adventure_V1_8_8_GAMEPLAY_EQUIPMENT_BILLING.zip"' in text
assert "patch_boss_lifecycle" in text
assert "patch_mobile_input" in text
assert "patch_equipment_inventory" in text
assert "integrate_google_play_billing" in text
assert "copy_backend" in text
assert "integrate_v188.py" in workflow
```

- [ ] **Step 2: Rodar o teste e verificar falha**

Run: `python3 tests/test_v188_integration_guard.py`
Expected: FAIL em `src.exists()`.

- [ ] **Step 3: Criar esqueleto do integrador com extração segura e empacotamento de uma raiz**

```python
ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "build_work" / "v188"
DIST = ROOT / "dist"
ARTIFACT_DIR = ROOT / "dist_artifact"
BASE_NAME = "Top_Down_Adventure_V1_8_7_AUDIO_PERFORMANCE_ANIMATIONS.zip"
OUT_NAME = "Top_Down_Adventure_V1_8_8_GAMEPLAY_EQUIPMENT_BILLING.zip"
PROJECT_FOLDER = "Top_Down_Adventure_V1_8_8_GAMEPLAY_EQUIPMENT_BILLING"


def patch_boss_lifecycle(project: Path) -> None: ...
def patch_mobile_input(project: Path) -> None: ...
def patch_equipment_inventory(project: Path) -> None: ...
def integrate_google_play_billing(project: Path) -> None: ...
def copy_backend(project: Path) -> None: ...
```

Implementar `safe_extract()`, `project_root()` e empacotamento seguindo o padrão seguro já usado em `tools/integrate_audio_v187.py`.

- [ ] **Step 4: Atualizar workflow para executar a V1.8.8 depois da V1.8.7**

Adicionar após `python3 tools/integrate_audio_v187.py`:

```yaml
      - name: Regression test - V1.8.8 integration guard
        run: python3 tests/test_v188_integration_guard.py

      - name: Integrate V1.8.8 gameplay equipment and billing
        run: python3 tools/integrate_v188.py
```

Trocar o artifact final para:

```yaml
name: Top_Down_Adventure_V1_8_8_GAMEPLAY_EQUIPMENT_BILLING
path: dist_artifact/
```

- [ ] **Step 5: Rodar guarda e confirmar verde**

Run: `python3 tests/test_v188_integration_guard.py`
Expected: PASS e mensagem `v1.8.8 integration guard: OK`.

- [ ] **Step 6: Commit**

```bash
git add tools/integrate_v188.py tests/test_v188_integration_guard.py .github/workflows/build-godot-project.yml
git commit -m "build: add V1.8.8 integration stage"
```

---

### Task 2: Corrigir ciclo de vida do boss HUD em morte, respawn, saída e morte do boss

**Files:**
- Modify through integrator: `scripts/hud.gd`
- Modify through integrator: `scripts/player.gd`
- Modify through integrator: `scripts/integrated_boss.gd`
- Modify through integrator: `scripts/insect_enemy.gd`
- Test: `tests/test_v188_boss_respawn.py`

**Interfaces:**
- Produces no HUD: `func clear_active_boss() -> void`.
- Produces no HUD: `func set_active_boss(boss: Node, display_name: String, max_hp: float) -> void`.
- Boss scripts call `clear_active_boss()` on death; Player calls it before respawn.

- [ ] **Step 1: Escrever teste vermelho para os hooks obrigatórios**

```python
from pathlib import Path
src = Path("tools/integrate_v188.py").read_text(encoding="utf-8")
assert "func clear_active_boss() -> void:" in src
assert "active_boss = null" in src
assert "boss_panel.visible = false" in src
assert "clear_active_boss()" in src
assert "respawn" in src.lower()
assert "boss" in src.lower()
print("v1.8.8 boss respawn guard: OK")
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `python3 tests/test_v188_boss_respawn.py`
Expected: FAIL porque o patch ainda não contém a API.

- [ ] **Step 3: Implementar estado único no HUD**

Patch esperado em `hud.gd`:

```gdscript
var active_boss: Node = null

func set_active_boss(boss: Node, display_name: String, max_hp: float) -> void:
    active_boss = boss
    boss_name_label.text = display_name
    boss_health_bar.max_value = max_hp
    boss_health_bar.value = max_hp
    boss_panel.visible = true

func clear_active_boss() -> void:
    active_boss = null
    boss_name_label.text = ""
    boss_health_bar.value = 0.0
    boss_panel.visible = false
```

`_process()`/atualização do HUD deve sair cedo se `active_boss == null` ou `not is_instance_valid(active_boss)` e chamar `clear_active_boss()` uma única vez nesse caso.

- [ ] **Step 4: Limpar HUD antes do respawn e ao morrer boss**

No fluxo de morte/respawn de `player.gd`, antes de reposicionar/reviver:

```gdscript
var hud := get_tree().get_first_node_in_group("hud")
if hud != null and hud.has_method("clear_active_boss"):
    hud.clear_active_boss()
```

Nos bosses, antes/depois de `queue_free()`:

```gdscript
var hud := get_tree().get_first_node_in_group("hud")
if hud != null and hud.has_method("clear_active_boss"):
    hud.clear_active_boss()
```

Também limpar ao detectar que Player saiu da área/raio de encontro.

- [ ] **Step 5: Rodar guarda**

Run: `python3 tests/test_v188_boss_respawn.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tools/integrate_v188.py tests/test_v188_boss_respawn.py
git commit -m "fix: clear boss HUD across death and respawn"
```

---

### Task 3: Separar movimento touch do ataque e garantir multitouch

**Files:**
- Modify through integrator: `scripts/player.gd`
- Modify through integrator: `scripts/hud.gd` ou script do controle mobile existente
- Modify through integrator: `scenes/ui/hud.tscn`
- Test: `tests/test_v188_mobile_input.py`

**Interfaces:**
- Produces: `func set_mobile_move_vector(value: Vector2) -> void`.
- Produces: `func request_mobile_attack() -> void`.
- Player consumes `mobile_move_vector` for movimento; ataque é acionado por `mobile_attack_requested`/ação dedicada apenas do botão ATACAR.

- [ ] **Step 1: Escrever teste vermelho**

```python
from pathlib import Path
src = Path("tools/integrate_v188.py").read_text(encoding="utf-8")
assert "set_mobile_move_vector" in src
assert "request_mobile_attack" in src
assert "mobile_move_vector" in src
assert "mobile_attack_requested" in src
assert "gui_input" in src or "InputEventScreenTouch" in src
assert "InputEventScreenDrag" in src
print("v1.8.8 mobile input guard: OK")
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `python3 tests/test_v188_mobile_input.py`
Expected: FAIL antes do patch.

- [ ] **Step 3: Implementar API de input mobile no Player**

```gdscript
var mobile_move_vector: Vector2 = Vector2.ZERO
var mobile_attack_requested: bool = false

func set_mobile_move_vector(value: Vector2) -> void:
    mobile_move_vector = value.limit_length(1.0)

func request_mobile_attack() -> void:
    mobile_attack_requested = true
```

No `_physics_process`, mesclar teclado/gamepad com `mobile_move_vector`, mas nunca derivar ataque da presença de toque/drag.

- [ ] **Step 4: Fazer o botão ATACAR ser a única origem de ataque touch**

O botão deve chamar somente:

```gdscript
func _on_attack_button_pressed() -> void:
    var player := get_tree().get_first_node_in_group("player")
    if player != null and player.has_method("request_mobile_attack"):
        player.request_mobile_attack()
```

Joystick/drag deve chamar somente `set_mobile_move_vector(...)`.

- [ ] **Step 5: Preservar multitouch por índice de toque**

Guardar o índice do dedo do joystick separadamente:

```gdscript
var move_touch_index: int = -1
```

Aceitar `ScreenDrag` apenas quando `event.index == move_touch_index`; o botão ATACAR continua recebendo outro índice simultaneamente.

- [ ] **Step 6: Rodar guarda**

Run: `python3 tests/test_v188_mobile_input.py`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add tools/integrate_v188.py tests/test_v188_mobile_input.py
git commit -m "fix: separate Android movement from attack"
```

---

### Task 4: Criar equipamento real com 6 slots, migração de save e ícones corretos

**Files:**
- Create through integrator: `scripts/equipment_manager.gd`
- Create through integrator: `scripts/item_catalog_v188.gd`
- Modify through integrator: `scripts/player.gd`
- Modify through integrator: script de save atual
- Modify through integrator: `data/rpg_icon_catalog.json`
- Test: `tests/test_v188_equipment_inventory.py`

**Interfaces:**
- Equipment slots: `weapon`, `helmet`, `chest`, `gloves`, `pants`, `boots`.
- `EquipmentManager.equip_from_inventory(index: int) -> Dictionary`.
- `EquipmentManager.unequip(slot: String) -> Dictionary`.
- `EquipmentManager.get_equipped(slot: String) -> Dictionary`.
- `EquipmentManager.get_total_bonuses() -> Dictionary` returning at least `attack`, `defense`, `max_hp`.
- `ItemCatalogV188.resolve_icon(item: Dictionary) -> String`.

- [ ] **Step 1: Escrever teste vermelho com invariantes de equipamento**

```python
from pathlib import Path
src = Path("tools/integrate_v188.py").read_text(encoding="utf-8")
for slot in ["weapon", "helmet", "chest", "gloves", "pants", "boots"]:
    assert f'"{slot}"' in src
assert "equip_from_inventory" in src
assert "unequip" in src
assert "get_total_bonuses" in src
assert "resolve_icon" in src
assert "migration" in src.lower() or "migrate" in src.lower()
print("v1.8.8 equipment guard: OK")
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `python3 tests/test_v188_equipment_inventory.py`
Expected: FAIL.

- [ ] **Step 3: Implementar `equipment_manager.gd` como fonte única do estado equipado**

```gdscript
extends Node

const VALID_SLOTS := ["weapon", "helmet", "chest", "gloves", "pants", "boots"]
var equipped: Dictionary = {
    "weapon": {}, "helmet": {}, "chest": {},
    "gloves": {}, "pants": {}, "boots": {}
}
```

`equip_from_inventory()` deve remover o item da mochila somente depois de validar `equipment_slot`; se já houver item no slot, fazer troca atômica, devolvendo o anterior à mochila antes de concluir.

`unequip()` deve primeiro confirmar uma vaga livre; se não houver, retornar `{ "ok": false, "reason": "inventory_full" }` sem alterar estado.

- [ ] **Step 4: Implementar bônus somente dos itens equipados**

```gdscript
func get_total_bonuses() -> Dictionary:
    var result := {"attack": 0.0, "defense": 0.0, "max_hp": 0.0}
    for slot: String in VALID_SLOTS:
        var item: Dictionary = equipped.get(slot, {})
        result.attack += float(item.get("attack", 0.0))
        result.defense += float(item.get("defense", 0.0))
        result.max_hp += float(item.get("max_hp", 0.0))
    return result
```

- [ ] **Step 5: Implementar catálogo e resolução de ícones**

`resolve_icon()` deve priorizar `icon_path` válido; depois usar mapa por `equipment_slot`/`item_type` para escolher arquivos reais dentro de `assets/Icons/RPG_496/`; somente itens desconhecidos podem usar fallback neutro. Equipamentos válidos nunca podem cair no ícone de mão.

- [ ] **Step 6: Implementar migração do save V1.8.7**

Ao carregar save sem `equipment_v188`, criar os 6 slots vazios, reclassificar itens antigos equipados pelo novo `equipment_slot` e devolver itens inválidos para a mochila. Caso falte espaço, guardar em `migration_overflow` no save para recuperação, nunca descartar.

- [ ] **Step 7: Rodar guarda**

Run: `python3 tests/test_v188_equipment_inventory.py`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add tools/integrate_v188.py tests/test_v188_equipment_inventory.py
git commit -m "feat: add six-slot equipment model and save migration"
```

---

### Task 5: Refazer painel de inventário para personagem + slots e alinhar mercado/ferreiro

**Files:**
- Modify through integrator: `scenes/ui/hud.tscn`
- Modify through integrator: `scripts/hud.gd`
- Modify through integrator: scripts de mercado/ferreiro existentes, ou `hud.gd` se centralizados ali
- Test: `tests/test_v188_inventory_ui.py`

**Interfaces:**
- UI consome `EquipmentManager.get_equipped(slot)` e não mantém cópia própria do equipamento.
- Botão Equipar chama `equip_from_inventory(selected_inventory_index)`.
- Clique em slot ocupado chama `unequip(slot)`.

- [ ] **Step 1: Escrever teste vermelho de estrutura editável**

```python
from pathlib import Path
src = Path("tools/integrate_v188.py").read_text(encoding="utf-8")
for node in ["EquipmentWeapon", "EquipmentHelmet", "EquipmentChest", "EquipmentGloves", "EquipmentPants", "EquipmentBoots", "CharacterPreview"]:
    assert node in src
assert "inventory_full" in src
assert "equipped" in src
print("v1.8.8 inventory UI guard: OK")
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `python3 tests/test_v188_inventory_ui.py`
Expected: FAIL.

- [ ] **Step 3: Adicionar nodes físicos no `hud.tscn`**

Criar no painel de inventário uma coluna `CharacterEquipmentPanel` contendo `CharacterPreview` e seis botões/slots nomeados exatamente:

```text
EquipmentWeapon
EquipmentHelmet
EquipmentChest
EquipmentGloves
EquipmentPants
EquipmentBoots
```

Os nodes devem existir no `.tscn` para permanecerem editáveis no Godot Editor.

- [ ] **Step 4: Atualizar renderização do inventário e slots**

A grade continua com 30 slots apenas para mochila. `_refresh_inventory()` lê somente a mochila; `_refresh_equipment()` lê `EquipmentManager.equipped`. Equipar remove da grade imediatamente; desequipar reintroduz e re-renderiza ambos.

- [ ] **Step 5: Bloquear venda/quebra/drop de equipamento ativo**

Mercado, ferreiro e ações da mochila devem receber `item_instance_id`/referência apenas de itens da mochila. Qualquer tentativa de operar um item ativo deve retornar `false`/mensagem de bloqueio em vez de duplicar ou apagar o item.

- [ ] **Step 6: Rodar guarda**

Run: `python3 tests/test_v188_inventory_ui.py`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add tools/integrate_v188.py tests/test_v188_inventory_ui.py
git commit -m "feat: add editable equipment panel to inventory"
```

---

### Task 6: Integrar GodotGooglePlayBilling 3.3.0 e PlayBillingManager

**Files:**
- Modify: `tools/integrate_v188.py`
- Create through integrator: `scripts/play_billing_manager.gd`
- Modify through integrator: `project.godot`
- Modify through integrator: `export_presets.cfg`
- Modify through integrator: loja/HUD atual
- Test: `tests/test_v188_billing_client.py`

**Interfaces:**
- `PlayBillingManager.purchase_product(product_id: String) -> void`.
- Signals: `catalog_updated(products: Dictionary)`, `purchase_pending(product_id: String)`, `purchase_failed(product_id: String, message: String)`, `purchase_granted(product_id: String)`.
- Product IDs fixos: `gems_100`, `gems_550`, `gems_1200`, `gems_3000`, `starter_pack`.
- Backend endpoint config: `BACKEND_VERIFY_URL` em configuração pública sem segredos.

- [ ] **Step 1: Escrever teste vermelho para versão/plugin/IDs**

```python
from pathlib import Path
src = Path("tools/integrate_v188.py").read_text(encoding="utf-8")
assert "GodotGooglePlayBilling" in src
assert "3.3.0" in src
assert "20d75623d6f337f08d8283c83098b73678d5f575e39247af5a8eb80588b18568" in src
for product in ["gems_100", "gems_550", "gems_1200", "gems_3000", "starter_pack"]:
    assert product in src
assert "purchase_product" in src
assert "query" in src.lower()
assert "PENDING" in src
print("v1.8.8 billing client guard: OK")
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `python3 tests/test_v188_billing_client.py`
Expected: FAIL.

- [ ] **Step 3: Baixar release oficial e verificar SHA-256 antes de extrair**

URL fixa:

```text
https://github.com/godot-sdk-integrations/godot-google-play-billing/releases/download/3.3.0/godot-google-play-billing.zip
```

SHA-256 esperado:

```text
20d75623d6f337f08d8283c83098b73678d5f575e39247af5a8eb80588b18568
```

Abortar build se o digest não coincidir. Copiar somente o plugin necessário para `addons/GodotGooglePlayBilling/`.

- [ ] **Step 4: Habilitar plugin e Gradle Build**

Patch `project.godot` para plugin habilitado e `export_presets.cfg` para `gradle/use_gradle_build=true` no preset Android. Não adicionar chaves privadas, senhas de keystore nem credenciais de serviço.

- [ ] **Step 5: Criar `play_billing_manager.gd`**

Fluxo mínimo:

```gdscript
const PRODUCT_IDS := ["gems_100", "gems_550", "gems_1200", "gems_3000", "starter_pack"]
var product_details: Dictionary = {}
var processed_purchase_tokens: Dictionary = {}

func purchase_product(product_id: String) -> void:
    if not PRODUCT_IDS.has(product_id):
        purchase_failed.emit(product_id, "unknown_product")
        return
    # usar detalhe retornado pela Google Play; não usar preço local
    _launch_google_purchase(product_id)
```

Conectar callbacks do plugin para consulta do catálogo e atualizações de compra. Estado PENDING emite `purchase_pending` e não chama backend para conceder recompensa.

- [ ] **Step 6: Enviar compra PURCHASED ao backend e só liberar após resposta `granted=true`**

Payload mínimo:

```json
{
  "product_id": "gems_100",
  "purchase_token": "<token-da-google>",
  "player_id": "<id-estavel-ou-vazio>"
}
```

Resposta esperada:

```json
{"ok":true,"granted":true,"gems":100,"crystals":0,"transaction_id":"..."}
```

Só depois dessa resposta o cliente incrementa saldo local e registra o token como processado.

- [ ] **Step 7: Fazer a loja renderizar preço/moeda da Google Play**

Cards da loja devem usar `formattedPrice`/campo equivalente retornado pelo ProductDetails do plugin. Em PC/editor sem plugin Android, mostrar `Indisponível fora da Google Play` e nunca simular entrega paga.

- [ ] **Step 8: Rodar guarda**

Run: `python3 tests/test_v188_billing_client.py`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add tools/integrate_v188.py tests/test_v188_billing_client.py
git commit -m "feat: integrate Google Play Billing 3.3.0"
```

---

### Task 7: Implementar backend PHP/MySQL idempotente para validar e consumir compras

**Files:**
- Create: `tools/v188_backend/config.example.php`
- Create: `tools/v188_backend/db.php`
- Create: `tools/v188_backend/google_auth.php`
- Create: `tools/v188_backend/verify_purchase.php`
- Create: `tools/v188_backend/schema.sql`
- Create: `tools/v188_backend/README.md`
- Modify: `tools/integrate_v188.py`
- Test: `tests/test_v188_backend.py`

**Interfaces:**
- HTTP `POST /verify_purchase.php` JSON input: `product_id`, `purchase_token`, `player_id`.
- Success JSON: `{ok:true, granted:true|false, gems:int, crystals:int, transaction_id:string}`.
- Google verify: `GET https://androidpublisher.googleapis.com/androidpublisher/v3/applications/{packageName}/purchases/productsv2/tokens/{token}`.
- Google consume: `POST https://androidpublisher.googleapis.com/androidpublisher/v3/applications/{packageName}/purchases/products/{productId}/tokens/{token}:consume`.

- [ ] **Step 1: Escrever teste vermelho para schema, whitelist e endpoints**

```python
from pathlib import Path
base = Path("tools/v188_backend")
for name in ["config.example.php", "db.php", "google_auth.php", "verify_purchase.php", "schema.sql", "README.md"]:
    assert (base / name).exists(), f"missing {name}"
verify = (base / "verify_purchase.php").read_text(encoding="utf-8")
schema = (base / "schema.sql").read_text(encoding="utf-8")
assert "purchases/productsv2/tokens" in verify
assert ":consume" in verify
assert "starter_pack" in verify
assert "UNIQUE" in schema.upper()
print("v1.8.8 backend guard: OK")
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `python3 tests/test_v188_backend.py`
Expected: FAIL porque os arquivos ainda não existem.

- [ ] **Step 3: Criar schema idempotente**

```sql
CREATE TABLE play_purchases (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  token_hash CHAR(64) NOT NULL,
  product_id VARCHAR(64) NOT NULL,
  player_id VARCHAR(128) NOT NULL DEFAULT '',
  purchase_state VARCHAR(32) NOT NULL,
  granted_gems INT NOT NULL DEFAULT 0,
  granted_crystals INT NOT NULL DEFAULT 0,
  transaction_id CHAR(36) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_token_hash (token_hash),
  UNIQUE KEY uq_transaction_id (transaction_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

- [ ] **Step 4: Criar whitelist de recompensas no servidor**

```php
$PRODUCTS = [
    'gems_100' => ['gems' => 100, 'crystals' => 0],
    'gems_550' => ['gems' => 550, 'crystals' => 0],
    'gems_1200' => ['gems' => 1200, 'crystals' => 0],
    'gems_3000' => ['gems' => 3000, 'crystals' => 0],
    'starter_pack' => ['gems' => 500, 'crystals' => 50],
];
```

Servidor nunca aceita quantidade enviada pelo cliente.

- [ ] **Step 5: Implementar OAuth2 service-account no servidor**

`google_auth.php` lê caminho da credencial somente de configuração/env var no servidor, cria JWT RS256 para scope `https://www.googleapis.com/auth/androidpublisher`, troca por access token e nunca retorna credencial/JWT ao cliente.

- [ ] **Step 6: Implementar transação idempotente em `verify_purchase.php`**

Ordem obrigatória:
1. validar `product_id` contra whitelist;
2. calcular `hash('sha256', purchase_token)`;
3. se `token_hash` já estiver `GRANTED`, retornar a recompensa registrada com `granted=false` para impedir duplicação local;
4. consultar `purchases.productsv2.getproductpurchasev2`;
5. exigir estado PURCHASED e produto correspondente ao solicitado;
6. abrir transação MySQL e inserir token único;
7. definir recompensa pelo servidor;
8. consumir via `purchases.products:consume`;
9. marcar registro `GRANTED`;
10. commit e retornar recompensa.

Em qualquer erro, rollback e `granted=false`.

- [ ] **Step 7: Copiar backend separadamente na entrega**

`integrate_v188.py` deve copiar `tools/v188_backend/` para uma pasta irmã do projeto dentro da raiz do artifact, por exemplo:

```text
Top_Down_Adventure_V1_8_8_GAMEPLAY_EQUIPMENT_BILLING/
  game/...
  backend_play_billing/...
```

O `game/` não contém `config.php` real nem credenciais.

- [ ] **Step 8: Rodar guarda**

Run: `python3 tests/test_v188_backend.py`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add tools/v188_backend tools/integrate_v188.py tests/test_v188_backend.py
git commit -m "feat: add secure Play purchase validation backend"
```

---

### Task 8: Validar pacote final, regressões e documentação operacional

**Files:**
- Create: `tests/test_v188_generated_artifact.py`
- Create through integrator: `docs/V1_8_8_ANDROID_PLAY_BILLING.md`
- Modify: `.github/workflows/build-godot-project.yml`
- Modify: `tools/integrate_v188.py`

**Interfaces:**
- Final ZIP: `dist/Top_Down_Adventure_V1_8_8_GAMEPLAY_EQUIPMENT_BILLING.zip`.
- Artifact upload: `Top_Down_Adventure_V1_8_8_GAMEPLAY_EQUIPMENT_BILLING`.

- [ ] **Step 1: Escrever teste do artifact final**

```python
import zipfile
from pathlib import Path

zpath = Path("dist/Top_Down_Adventure_V1_8_8_GAMEPLAY_EQUIPMENT_BILLING.zip")
assert zpath.exists()
with zipfile.ZipFile(zpath) as zf:
    names = zf.namelist()
    roots = {n.split("/", 1)[0] for n in names if n}
    assert len(roots) == 1
    assert any(n.endswith("scripts/play_billing_manager.gd") for n in names)
    assert any(n.endswith("scripts/equipment_manager.gd") for n in names)
    assert any("addons/GodotGooglePlayBilling" in n for n in names)
    assert any(n.endswith("backend_play_billing/verify_purchase.php") for n in names)
    assert not any(n.endswith("config.php") for n in names)
    assert not any("service-account" in n.lower() for n in names)
print("v1.8.8 generated artifact guard: OK")
```

- [ ] **Step 2: Rodar antes do build e confirmar falha por artifact inexistente/antigo**

Run: `python3 tests/test_v188_generated_artifact.py`
Expected: FAIL.

- [ ] **Step 3: Escrever documentação operacional dentro da entrega**

`V1_8_8_ANDROID_PLAY_BILLING.md` deve conter, sem segredos:
- cadastrar os cinco IDs exatamente no Play Console;
- marcar todos como one-time/consumable;
- criar service account e conceder acesso à Google Play Developer API;
- configurar `backend_play_billing/config.php` no servidor a partir do exemplo;
- importar `schema.sql`;
- definir URL HTTPS do backend no jogo antes da publicação;
- habilitar Gradle Build e plugin GodotGooglePlayBilling;
- publicar primeiro em faixa Internal testing/Closed testing;
- instalar a versão pela Google Play para testar compra real;
- usar conta de teste/licença da Play Console.

- [ ] **Step 4: Executar build completo**

Run:

```bash
python3 tests/test_boss_layout_guard.py
python3 tests/test_v186_performance_animation.py
python3 tests/test_v187_audio_integration.py
python3 tests/test_v188_integration_guard.py
python3 tests/test_v188_boss_respawn.py
python3 tests/test_v188_mobile_input.py
python3 tests/test_v188_equipment_inventory.py
python3 tests/test_v188_inventory_ui.py
python3 tests/test_v188_billing_client.py
python3 tests/test_v188_backend.py
python3 tools/integrate_project.py
python3 tools/integrate_audio_v187.py
python3 tools/integrate_v188.py
python3 tests/test_v188_generated_artifact.py
```

Expected: todos PASS e ZIP final criado.

- [ ] **Step 5: Verificação manual estática do ZIP**

Confirmar no log:
- 48 WAVs da V1.8.7 preservados;
- Minotaur scene/animation preservada;
- Mantis scene preservada;
- `project.godot`, `export_presets.cfg`, plugin billing, scripts V1.8.8 e backend presentes;
- nenhuma `.godot/`, cache Python, credencial privada ou ZIP-fonte do plugin dentro do jogo.

- [ ] **Step 6: Atualizar workflow para rodar teste do artifact depois do integrador V1.8.8**

```yaml
      - name: Regression test - generated V1.8.8 artifact
        run: python3 tests/test_v188_generated_artifact.py
```

- [ ] **Step 7: Commit final do plano implementado**

```bash
git add tests/test_v188_generated_artifact.py tools/integrate_v188.py .github/workflows/build-godot-project.yml
git commit -m "test: validate complete V1.8.8 artifact"
```

---

## Release Verification Checklist

- [ ] `python3 tests/test_boss_layout_guard.py` PASS.
- [ ] `python3 tests/test_v186_performance_animation.py` PASS.
- [ ] `python3 tests/test_v187_audio_integration.py` PASS.
- [ ] Todos os testes `test_v188_*.py` PASS.
- [ ] GitHub Actions completo em verde.
- [ ] Artifact da Actions baixável e com uma única pasta raiz.
- [ ] Projeto abre no Godot sem Recovery Mode.
- [ ] Teste manual Android: joystick não ataca; botão ATACAR ataca; multitouch funciona.
- [ ] Teste manual bosses: morrer/respawnar limpa nome/barra.
- [ ] Teste manual equipamento: 1 arma + 5 armaduras, troca/desequipar/mochila cheia sem perda.
- [ ] Teste manual ícones: nenhum equipamento válido usa ícone de mão.
- [ ] Teste Google Play em faixa de teste: cancelada/pending sem recompensa; aprovada entrega uma vez; recompra funciona após consumo.
- [ ] Confirmar que o preço mostrado é o preço retornado pela Google Play.
- [ ] Confirmar que nenhuma credencial privada foi incluída no APK/ZIP.

## Notes for Executor

A validação automatizada neste repositório é principalmente estática porque o ambiente atual não executa o editor Godot. Não declarar a versão pronta para publicação apenas porque os testes Python passam. O aceite final de touch, respawn visual e Google Play Billing exige teste no Godot/Android e, para compra real, instalação via faixa de teste da Google Play com produtos/conta de teste configurados.