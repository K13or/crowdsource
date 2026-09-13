# Имена, где корпус спорит с правилом слоя

Правило CLAUDE.md §1: строку, которую держит слой `pn_*`, батч хранит
ПО-АНГЛИЙСКИ — русскую форму подставляет слой, и только так работает
выключатель имён. По большинству названий корпус это правило держит, и такие
имена возвращаются латиницей обычными партиями.

Здесь собрано обратное: **143 имени, 2 952 строки**, где корпус упорно переводит
название, и переводов больше, чем латиницы. Механически развернуть их можно за
один заход, но это спор с уже сложившейся практикой перевода, а такие решения
принимает владелец, а не партия.

## Как считалось

* «латиница» — строк, где имя в переводе стоит по-английски, как требует правило;
* «перевод» — строк, где линтер видит потерю имени: его нет в переводе ни в
  каком виде;
* «форма» — что стоит вместо имени. Найдена не вручную: в переводах строк с
  потерей посчитаны пары слов, и оставлены те, что встречаются там в двадцать
  и более раз чаще, чем в корпусе вообще. Где формы нет или вместо неё вышел
  служебный оборот («дважды щёлкните» — начало любого описания предмета), стоит
  прочерк: там название либо выброшено из фразы, либо разошлось так, что общей
  формы у переводов не осталось.

Имена, которые уже правятся в открытой очереди (`Lion's Arch`, `Inquest`,
`Drizzlewood Coast` и ещё шесть), из списка исключены.

## Что означает решение

**Вернуть латиницу.** Правило слоя начинает работать: игрок с включённым
выключателем видит русскую форму из `pn_*`, с выключенным — английскую. Цена —
2 952 строки меняются, и в них имя перестаёт склоняться («в Ember Bay» вместо
«в бухте углей»).

**Оставить перевод.** Тогда эти имена надо снять со слоя, иначе линтер будет
вечно показывать их как потерю, а выключатель — молчать. Это правка `pn_*`, а
не корпуса.

**Решить поимённо.** Скорее всего верный путь: у части имён перевод давно
прижился («Оплот божеств»), у части он случаен и держится на десятке строк.

## Список

| имя | латиница | перевод | что стоит вместо имени | где |
|---|---:|---:|---|---|
| `Health Increase` | 1 | 69 | — форма не опознана — | new 69 |
| `United Legions` | 23 | 59 | объединённых легионов | ui 24, misc 13 |
| `Labyrinthine Cliffs` | 33 | 52 | в лабиринтовых | ach 22, ui 12 |
| `Marshal Trahearne` | 26 | 52 | — имя выброшено — | zone 31, main 6 |
| `Signet Passive` | 1 | 51 | печать пассивно | skills 43, discovered 4 |
| `The Pale Tree` | 16 | 51 | бледное дерево | zone 35, misc 9 |
| `Saul D'Alessio` | 5 | 49 | д алессио | zone 42, new 3 |
| `Siren's Landing` | 29 | 48 | пристани сирены | ui 20, new 13 |
| `Ember Bay` | 45 | 46 | в бухте | ui 17, new 10 |
| `Dragonite Ore` | 5 | 43 | — форма не опознана — | items 41, ach 1 |
| `Essence of Llamatic Elegance` | 1 | 43 | — форма не опознана — | items 22, minis 21 |
| `Tangled Depths` | 37 | 42 | запутанных глубинах | ui 30, ach 6 |
| `Domain of Kourna` | 31 | 41 | во владении | ui 12, ach 9 |
| `Central Tyria` | 8 | 40 | центральной тирии | ui 18, items 9 |
| `Straits of Devastation` | 19 | 39 | в проливах | ui 29, ach 4 |
| `Obsidian Shards` | 5 | 38 | — форма не опознана — | items 36, ui 2 |
| `Living World Season 4` | 10 | 36 | — форма не опознана — | ach 22, ui 10 |
| `Shiverpeak Mountains` | 21 | 36 | водах мерцающих | ui 26, main 3 |
| `Jade Maw` | 8 | 36 | нефритовой пасти | ui 30, new 4 |
| `Asura Gate` | 11 | 36 | асура врата | ui 33, items 1 |
| `The Olmakhan` | 6 | 35 | — имя выброшено — | zone 13, ui 10 |
| `Forge Master Hilina` | 6 | 35 | кристалла клейма | items 34, ui 1 |
| `This is my story.` | 1 | 34 | это моя | ui 34 |
| `Lunar New Year` | 20 | 33 | нового года | ach 10, items 9 |
| `Festival of the Four Winds` | 9 | 32 | четырёх ветров | new 9, ach 7 |
| `Draconic Tribute` | 2 | 32 | чтобы создать | items 32 |
| `Reins of Power` | 1 | 32 | мастерства и | ui 32 |
| `Fort Marriner` | 25 | 31 | в форте | ui 15, main 9 |
| `Gem Store` | 6 | 30 | в магазине | ui 19, items 4 |
| `Resonating Sliver` | 1 | 30 | чтобы открыть | items 18, ui 12 |
| `Mist War` | 7 | 30 | войне туманов | zone 16, ui 5 |
| `Subtle Spyglass` | 2 | 30 | для духов | ui 30 |
| `Spirit Containment Unit` | 2 | 30 | для духов | ui 30 |
| `The Shining Blade` | 10 | 29 | — имя выброшено — | zone 21, new 3 |
| `Mystic Clovers` | 9 | 29 | — форма не опознана — | items 29 |
| `Ship's Council` | 19 | 28 | чтобы узнать | main 13, zone 5 |
| `Living World Season 2` | 4 | 27 | завершите миссию | ach 21, ui 3 |
| `Living World Season 1` | 3 | 27 | — форма не опознана — | ui 9, ach 8 |
| `Lunatic Court` | 6 | 27 | безумного двора | items 15, npc 5 |
| `Wizard's Court` | 10 | 26 | неофициальная история | ui 9, main 8 |
| `Gaheron Baelfire` | 14 | 25 | — имя выброшено — | ui 10, new 9 |
| `Pact Commander` | 24 | 25 | — имя выброшено — | zone 13, ui 5 |
| `Living World Season 3` | 6 | 24 | завершите миссию | ach 18, ui 3 |
| `Slayer of Issormir` | 14 | 24 | — имя выброшено — | zone 14, story 6 |
| `Glacial Imbued Jar` | 2 | 24 | ледниковой напитанной | ui 24 |
| `Trader's Forum` | 4 | 22 | торговом форуме | ui 11, new 4 |
| `Scarab Plague` | 6 | 22 | — имя выброшено — | zone 10, misc 8 |
| `Great Hall` | 16 | 20 | в большом | items 4, new 4 |
| `The Tyrian Alliance` | 2 | 20 | — имя выброшено — | misc 4, ui 4 |
| `Old Kaineng` | 13 | 20 | — имя выброшено — | ui 7, main 6 |
| `Unbound Magic` | 14 | 20 | щёлкните чтобы | items 16, ui 4 |
| `Grand Piazza` | 3 | 20 | чтобы узнать | main 10, ui 6 |
| `Hero of Shaemoor` | 8 | 20 | — имя выброшено — | zone 16, story 2 |
| `Eternal Battlegrounds` | 16 | 19 | полей сражений | ui 13, main 3 |
| `No Quarter` | 7 | 19 | без пощады | items 8, ui 5 |
| `Queen's Gauntlet` | 13 | 19 | перчатки королевы | ach 11, ui 4 |
| `Ventari's Tablet` | 3 | 19 | — имя выброшено — | zone 8, npc 3 |
| `Krewe Leader` | 15 | 19 | собрать четыре | items 9, ui 7 |
| `Awakened Inquest` | 11 | 19 | — имя выброшено — | ui 9, new 8 |
| `Distant Memory` | 0 | 19 | далекой памяти | ui 12, zone 5 |

Ещё 83 имени с меньшим счётом:

`Ms. Jeeves` 19, `Eldvin Monastery` 18, `Grandmaster Craftsman Hobbs` 17, `Imperator Smodur` 17, `Dragonsblood Spear` 16, `Temple of the Silent Storm` 16, `Mistlock Observatory` 16, `Tome of Knowledge` 16, `Tyrian Explorers Society` 16, `The Eternal` 16, `Tribulation Mode` 15, `Battle of Kyhlo` 15, `Kalla Scorchrazor` 15, `Druid Runestone` 15, `Captain Ellen Kiel` 15, `Elon River` 15, `The Ringmaster` 15, `Stonemist Castle` 14, `Pristine Fractal Relic` 14, `Fractal Relic` 14, `Scrap of Maguuma Mastery` 14, `Overseer Kuda` 14, `Fractal Incursion` 13, `Legacy of the Foefire` 13, `Mordrem Vinewrath` 13, `Icebrood Saga Mastery Insight` 13, `The Tower of Nightmares` 13, `Vigil Tactician` 13, `Magister Razermane` 13, `Queen Salma` 13, `Sapper's Delve` 13, `Inspector Ellen Kiel` 13, `This glider is dyeable.` 13, `MONSTER ONLY` 13, `Battle of Champion's Dusk` 12, `Forest of Niflhel` 12, `Djinn's Dominion` 12, `Strike Missions` 12, `Infinity Coil` 12, `Lightbringer Ives` 12, `Fractal Attunement` 12, `Operative Selly` 12, `Wychmire Swamp` 12, `Leadfoot Village` 11, `Glint's Lair` 11, `Wolf's Crossing` 11, `Hunter Block` 11, `Warmaster Jofast` 11, `Legionnaire Neverburn` 11, `Crusader D'Stolt` 11, `Writ of Experience` 11, `—Captain Ellen Kiel` 11, `The Unseen` 11, `Itzel Lore` 11, `Division Shrine` 11, `Drooburt's Ghost` 11, `Lighthouse Point` 10, `Ruined City of Arah` 10, `Xunlai Jade Junkyard` 10, `Revenge of the Capricorn` 10, `Riding Skyscales` 10, `House zu Heltzer` 10, `Primeval Steward` 10, `Zildi's Assist-o-Matic` 10, `Tactician Blazefur` 10, `Arcanist Vance` 10, `Braxa Scalehunter` 10, `Explorer Cyara` 10, `Priory Explorer Cyara` 10, `Infinite Mind` 10, `Legionnaire Bladechipper` 10, `Skyscale Trainer Dyanne` 10, `Captain Magnus the Bloody-Handed` 10, `Willbender Flames` 10, `Far Shiverpeaks` 10, `Incendio Templum` 10, `Source of Orr` 10, `Warden Jabari` 10, `Gaheron Baelfire.` 10, `Branded Hydra` 10, `Chamber of Ministers` 10, `Legendary Alliance` 10, `Cliffside Fractal` 10

## Примеры

**`Health Increase`** — new/new_009.csv:250

```
EN  Current Bonus:<br>Increased Chance of Crafting Critical Success = 10%%
RU  Текущий бонус:<br>Повышенный шанс критического успеха в ремесле = 10%%
```

**`United Legions`** — ach/ach_013.csv:110

```
EN  Donate materials to any United Legions quaestor in the Drizzlewood Coa
RU  Пожертвуйте материалы любому квестору Объединённых Легионов на Drizzle
```

**`Labyrinthine Cliffs`** — ach/ach_005.csv:204

```
EN  Collect %num2% master sky crystal[s] in the Labyrinthine Cliffs.
RU  Соберите %num2% [мастер-небесный кристалл|мастер-небесных кристалла|ма
```

**`Marshal Trahearne`** — main/main_008.csv:190

```
EN  Commander,
As we discussed, I'd like you to look into the problems War
RU  Командир,
Как мы и обсуждали, я хочу, чтобы вы разобрались с проблемам
```

**`Signet Passive`** — discovered/discovered_2026-08-05.csv:13

```
EN  <c=@abilitytype>Signet Passive:</c> Faster endurance regeneration.<br>
RU  <c=@abilitytype>Печать (пассивно):</c> Ускоренная регенерация вынослив
```

**`The Pale Tree`** — items/items_005.csv:18

```
EN  <c=@flavor>The Pale Tree Pilsner was inspired by the Pale Tree herself
RU  <c=@flavor>«Пильзнер Pale Tree» вдохновлён самим Pale Tree. Это лёгкий
```

**`Saul D'Alessio`** — main/main_012.csv:265

```
EN  To the kind people of Gavril: I thank you.  
  
I thank you for your h
RU  Добрым людям Гаврила: я благодарю вас.  
  
Я благодарю вас за ваше го
```

**`Siren's Landing`** — ach/ach_002.csv:241

```
EN  After completing the meta-achievement Return to Siren's Landing, visit
RU  После выполнения мета-достижения «Возвращение к Причалу Сирен» посетит
```
