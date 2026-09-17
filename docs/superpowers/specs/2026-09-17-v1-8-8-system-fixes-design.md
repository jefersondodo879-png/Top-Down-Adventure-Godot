# V1.8.8 — Correções de gameplay, equipamento e Google Play Billing

Data: 2026-09-17

## Objetivo

A V1.8.8 será construída sobre a V1.8.7 e deve preservar bosses, animações, otimizações de performance e áudio já integrados. O foco desta versão é corrigir bugs de gameplay no Android e no fluxo de respawn, reorganizar inventário/equipamentos e substituir a loja simulada por compras reais da Google Play com validação segura.

## Escopo aprovado

### 1. Boss HUD e respawn

Problema atual: quando o jogador morre durante um boss e respawna, o nome/barra do boss pode permanecer visível.

Comportamento desejado:
- Ao morrer, limpar imediatamente a referência ao boss atual.
- Ocultar nome, barra de vida e demais elementos de boss no HUD.
- Ao respawnar, iniciar sem boss ativo.
- Ao sair da região do boss, esconder o HUD do boss.
- Ao boss morrer, esconder o HUD e limpar o estado.
- O HUD só volta a aparecer quando um boss válido estiver ativo novamente.

A lógica de boss deve usar um único estado central para evitar HUD preso ou referências órfãs.

## 2. Controles Android

Problema atual: tocar/arrastar para andar também pode disparar ataque.

Comportamento desejado:
- Joystick/área de movimento controla somente movimento.
- O ataque no touch acontece somente pelo botão ATACAR.
- Arrastar o dedo no joystick nunca chama ataque.
- Multitouch deve permitir segurar o joystick com um dedo e tocar ATACAR com outro.
- Controles de PC permanecem funcionando.

A separação deve ser feita no controlador de entrada, sem duplicar regras de combate.

## 3. Inventário e equipamentos

O inventário continua com 30 slots de mochila.

Ao lado da mochila haverá um painel do personagem com 6 slots de equipamento:
- Arma
- Capacete
- Peitoral
- Luvas
- Calças
- Botas

Regras:
- Apenas 1 arma pode ficar equipada.
- Cada armadura ocupa exatamente seu slot correspondente.
- Ao equipar, o item sai da grade da mochila e passa ao slot do personagem.
- Ao desequipar, o item volta para a primeira vaga livre da mochila.
- Se a mochila estiver cheia, o desequipamento é bloqueado sem perda do item.
- Equipamentos ativos não podem ser vendidos, quebrados ou descartados pela mochila.
- Armaduras não alteram visualmente o sprite do personagem no gameplay nem no inventário.
- O personagem exibido ao lado do inventário é apenas uma prévia visual.

## 4. Modelo de dados de itens

Cada item equipável passa a ter metadados consistentes, incluindo:
- `item_type`
- `equipment_slot`
- `icon_path`
- atributos de combate relevantes

Valores esperados de `equipment_slot`:
- `weapon`
- `helmet`
- `chest`
- `gloves`
- `pants`
- `boots`

O cálculo de atributos deve considerar apenas itens realmente equipados.

Diretriz inicial de atributos:
- Arma: ataque/dano.
- Armaduras: defesa e/ou vida, conforme os dados específicos de cada item.

Inventário, mercado, ferreiro, drops, save e HUD devem consultar a mesma fonte de dados de item/equipamento.

## 5. Correção dos ícones

Problema atual: armas/armaduras podem aparecer com um ícone genérico de mão.

Comportamento desejado:
- O ícone deve ser resolvido por item/tipo real, usando o pack RPG 496 já integrado.
- Armas devem usar ícones de arma.
- Capacetes, peitorais, luvas, calças e botas devem usar ícones compatíveis.
- Consumíveis e materiais devem manter seus próprios ícones.
- O mesmo ícone deve ser usado de forma consistente no inventário, loja, mercado, ferreiro, baús e drops.
- O fallback genérico de mão não deve ser usado para equipamentos válidos.

## 6. Google Play Billing real

A loja usará GodotGooglePlayBilling 3.3.0, compatível com Godot 4.2+ e baseado em Google Play Billing Library 9.1.0.

O projeto Android deverá usar Gradle Build.

Produtos aprovados:
- `gems_100`
- `gems_550`
- `gems_1200`
- `gems_3000`
- `starter_pack`

Conteúdo do `starter_pack`:
- 500 Gemas
- 50 Cristais

Todos os cinco produtos serão consumíveis.

Os preços não serão fixados no código. A interface mostrará preço e moeda retornados pela Google Play.

## 7. Fluxo de compra

Fluxo esperado:
1. Inicializar conexão com Google Play Billing.
2. Consultar detalhes dos produtos configurados no Play Console.
3. Exibir os preços retornados pela loja.
4. Jogador solicita compra.
5. Abrir checkout oficial da Google Play.
6. Receber estado da compra.
7. Para compra pendente: não entregar recursos.
8. Para compra cancelada/falha: não entregar recursos.
9. Para compra aprovada: enviar dados da compra ao backend.
10. Backend valida a compra e impede reaproveitamento do token.
11. Somente após resposta válida do backend, entregar Gemas/Cristais.
12. Consumir/confirmar a compra conforme o fluxo exigido pelo produto consumível.
13. Registrar localmente o identificador já processado para proteção adicional contra entrega duplicada.

Na inicialização do jogo, compras pendentes ou não finalizadas devem ser consultadas e retomadas.

## 8. PlayBillingManager

A integração de billing ficará em um gerenciador separado da interface.

Responsabilidades:
- inicializar conexão com Google Play;
- consultar catálogo;
- iniciar compra por `product_id`;
- receber atualização de compra;
- diferenciar sucesso, pendência, cancelamento e erro;
- enviar token ao backend;
- processar resposta de validação;
- entregar recompensa uma única vez;
- consumir/acknowledge a compra quando aplicável;
- restaurar compras incompletas após reabrir o jogo.

A UI deve chamar uma interface simples, por exemplo `purchase_product(product_id)`, sem conhecer detalhes internos do Billing Client.

## 9. Backend PHP/MySQL

O backend será incluído na entrega em uma pasta separada do projeto Godot.

Objetivos:
- validar compra na Google Play antes de liberar moeda premium;
- impedir entrega duplicada;
- manter segredos e credenciais fora do APK.

Configuração prevista:
- package name do aplicativo;
- credenciais da Google Play API;
- dados do MySQL;
- lista permitida de produtos e respectivas recompensas.

A tabela de compras deverá registrar no mínimo:
- identificador interno;
- product_id;
- purchase token ou hash seguro dele;
- estado de validação;
- data/hora;
- recompensa concedida;
- identificador do jogador quando disponível.

O backend deve tratar o token de compra como único. Uma compra já processada nunca pode conceder recompensa novamente.

Nenhuma chave privada ou credencial de servidor ficará dentro do projeto exportado para Android.

## 10. Save e migração da V1.8.7

A V1.8.8 deve manter compatibilidade com saves da V1.8.7.

Migração:
- Ler estrutura antiga.
- Criar estrutura nova de equipamentos.
- Reclassificar equipamento antigo para os novos slots quando possível.
- Itens sem tipo de slot válido voltam para a mochila.
- Nenhum item deve ser apagado silenciosamente.
- Se não houver espaço suficiente durante uma migração, preservar os dados de forma recuperável em vez de descartar itens.

O save novo deve persistir:
- inventário;
- equipamento por slot;
- moedas;
- progresso existente;
- identificadores de compras localmente processadas como proteção auxiliar.

## 11. UI do inventário

Layout funcional esperado:
- painel de personagem ao lado da grade;
- 1 slot de arma;
- 5 slots de armadura;
- ícones e estados visuais claros;
- destaque de item selecionado;
- ações de equipar/desequipar coerentes;
- sem representação visual das armaduras no sprite.

A estrutura deve continuar editável no Godot Editor, evitando construir toda a interface apenas em código.

## 12. Compatibilidade com sistemas existentes

A V1.8.8 deve preservar:
- Minotaur e Mantis;
- animações atuais dos bosses;
- otimizações de performance da V1.8.6;
- RPG Essentials SFX da V1.8.7;
- música existente;
- quests e progressão já presentes;
- mercado e ferreiro, adaptados ao novo sistema de equipamentos;
- PC e Android.

## 13. Casos de teste obrigatórios

### Boss/respawn
- Morrer para Minotaur -> respawn sem nome/barra presa.
- Morrer para Mantis -> respawn sem nome/barra presa.
- Sair da área do boss -> HUD escondido.
- Matar boss -> HUD escondido.

### Android input
- Mover joystick -> não ataca.
- Arrastar joystick continuamente -> não ataca.
- Botão ATACAR -> ataca.
- Joystick + ATACAR simultaneamente -> movimento e ataque funcionam com multitouch.

### Equipamentos
- Equipar arma -> sai da mochila e ocupa slot de arma.
- Equipar cada uma das 5 armaduras -> ocupa slot correto.
- Trocar item no mesmo slot -> estado permanece consistente.
- Desequipar -> retorna para primeira vaga livre.
- Mochila cheia -> desequipar bloqueado sem perder item.
- Item equipado -> não pode ser vendido/quebrado/descartado pela mochila.

### Ícones
- Armas não usam ícone de mão.
- Cada classe de armadura usa ícone apropriado.
- Mesmo item mostra o mesmo ícone em todos os sistemas.

### Billing
- Produto inexistente -> erro tratado sem recompensa.
- Compra cancelada -> sem recompensa.
- Compra pendente -> sem recompensa.
- Compra aprovada e backend válido -> recompensa concedida uma vez.
- Mesmo token reapresentado -> recompensa não duplicada.
- Falha de rede após compra -> retomada segura na próxima inicialização.
- Reiniciar o jogo durante compra -> consulta e retomada do estado.

### Regressão
- Áudio da V1.8.7 continua funcionando.
- Bosses continuam animados.
- Otimizações da V1.8.6 permanecem.
- Save antigo migra sem perda silenciosa de itens.

## 14. Entrega prevista

A entrega da V1.8.8 deve conter:
- projeto Godot atualizado;
- integração do plugin de Google Play Billing;
- inventário/equipamentos revisados;
- touch corrigido;
- boss HUD corrigido;
- ícones corrigidos;
- pasta separada de backend PHP/MySQL;
- SQL necessário para criação das tabelas;
- arquivo de configuração de exemplo sem credenciais reais;
- instruções para cadastrar os cinco produtos no Play Console;
- instruções para configurar Gradle Build e plugin no export Android;
- testes de regressão do pipeline;
- ZIP final com uma única pasta raiz, evitando problemas de importação.

## Fora de escopo desta versão

- Exibir armaduras vestidas visualmente no sprite.
- Mais de uma arma equipada simultaneamente.
- Assinaturas recorrentes.
- Venda de produtos não consumíveis.
- Sistema de contas completo novo, salvo o mínimo necessário para vincular/validar compras.
- Refatoração não relacionada aos bugs e sistemas acima.

## Critérios de aceite

A V1.8.8 será considerada pronta para teste quando:
1. todos os casos estáticos/regressivos automatizáveis passarem;
2. o build gerar o ZIP final corretamente;
3. a estrutura de billing real estiver integrada sem credenciais privadas no APK;
4. inventário/equipamento estiver consistente entre mochila, slots, save, mercado e ferreiro;
5. touch não disparar ataque através da área de movimento;
6. boss HUD for limpo corretamente em morte/respawn/saída/morte do boss;
7. nenhuma regressão conhecida for introduzida nos sistemas preservados.

Observação: a validação final de compra real precisa ser feita em um app distribuído por uma faixa de teste do Google Play, com os produtos cadastrados no Play Console e uma conta de teste/licença configurada. Testes estáticos e de integração local não substituem esse teste real da Google Play.
