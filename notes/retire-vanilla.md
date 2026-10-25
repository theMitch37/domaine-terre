# Registre : ce que Terre retire de la génération vanilla

Règle (Maxime, 25/10/2026) : **fidélité à la vraie Terre**, deux mondes = même carte et mêmes biomes, seuls les
minerais restent aléatoires. Tout ce qui est retiré ici sera **réimplanté à notre façon** plus tard.
Ces retraits valent pour les nouveaux mondes (Terre 0.3.2 et suivantes).

| Retiré | Depuis | Où | Pourquoi | À réimplanter comment (idées) |
|---|---|---|---|---|
| Îles et bancs inventés par le relief vanilla en mer | 0.3.2 | `Terrain.plafond` (densité) | Îlots parasites le long des côtes | — (seules les vraies îles GSHHG émergent) |
| Mares et lagunes inventées au bord de la mer | 0.3.2 | `Terrain.plancher` (densité) | Eau là où il n'y en a pas | Vraies lagunes et marais d'après les données |
| Bruit qui déplaçait le trait de côte (±8 blocs) | 0.3.2 | `Terrain.distanceCote` | Criques et pointes inventées | — (vraie côte GSHHG au bloc près) |
| Lave sous y -54 en mer | 0.3.2 | `FluidesMixin` | Les fosses descendent jusqu'à y -61 | Volcanisme sous-marin réel (dorsales, fosses) |
| Lacs de lave (surface et souterrains) | 0.3.2 | biomes du mod, `copies_biomes.py`, biome modifier `sans_hasard_features` | Hasard visible en surface | Lave des volcans réels (Etna, Hawaï, Islande…) |
| Sources d'eau et de lave (`spring_*`) | 0.3.2 | idem | Filets d'eau qui coulent des falaises au hasard | Vraies sources, résurgences (Fontaine de Vaucluse…) |
| Donjons (`monster_room`) | 0.3.2 | idem | Aléatoires, et sans grottes ils seraient emmurés | Nos propres souterrains |
| Grottes de bruit (fromages, spaghettis, entrées, piliers) et nouilles | 0.3.2 | `noise_settings/overworld.json` (densité finale = `sloped_cheese`) | Percent les falaises, les lieux, les cuvettes des lacs | Vrais réseaux karstiques (Padirac, gouffres, grottes célèbres) |
| Carvers (grottes, ravins) | 0.3.2 | biomes du mod, `FluidesMixin.applyCarvers` (tous les biomes) | Idem | Idem ; vrais canyons via les lieux |
| Structures vanilla (villages, temples, épaves, avant-postes, ruines, monuments, manoirs, cités antiques, mines…) | 0.3.2 | `StructuresMixin` (Terre) | Posées au hasard, sans rapport avec la géographie | Villes et villages réels (suite de mods « structures ») |

Gardé exprès : forteresses (`stronghold`, accès à l'End) ; minerais et géodes ; structures des autres mods.
Toujours là, à traiter : lacs et rivières en altitude (étape C), arbres et végétation aléatoires, ordre de génération
qui fait varier ~0,15 % des blocs d'un monde à l'autre.
