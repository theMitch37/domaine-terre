"""Construit outils/faune/especes.csv (répartition à valider) pour les mods d'animaux réellement présents dans le pack
« Le Domaine d'Aubin v2 » (liste du dossier mods lue le 04/11/2026) :
Untamed Wilds 4.0.4, Naturalist 5.0pre2, Let's Do WilderNature 1.0.6, Let's Do Meadow 1.3.25, Ecologics 2.2.7,
Aquaculture 2.5.7, Savage and Ravage 6.0.1, Guard Villagers 1.6.19 + jeu de base.
Une ligne = une créature (ou une espèce d'Untamed Wilds). Colonnes : voir l'en-tête."""
import csv, os

ICI = os.path.dirname(os.path.abspath(__file__))
L = []  # (id, nom, espece, categorie, milieu, terroirs, groupe, statut, note)
def a(*r): L.append(r)

EUR = "atlantique,mediterranee,continentale,nordique,alpine"
# ------------------------------------------------------------------ JEU DE BASE
a("minecraft:cow","Vache","Bos taurus","ferme","prairie,culture","atlantique,mediterranee,continentale,nordique,alpine,maghreb,afrique_est,afrique_australe,moyen_orient,inde,chine,grandes_plaines,cone_sud,australie,nouvelle_zelande","2-4","garder","zones agricoles et prairies seulement")
a("minecraft:pig","Cochon","Sus domesticus","ferme","culture,foret","atlantique,mediterranee,continentale,nordique,alpine,chine,japon_coree,asie_sud_est,grandes_plaines,amerique_centrale,melanesie","2-4","garder","rare là où l'élevage porcin l'est")
a("minecraft:sheep","Mouton","Ovis aries","ferme","prairie,steppe,montagne","atlantique,mediterranee,continentale,nordique,alpine,maghreb,sahara_sahel,afrique_est,afrique_australe,moyen_orient,steppes_tibet,inde,chine,cone_sud,australie,nouvelle_zelande","3-6","garder","")
a("minecraft:chicken","Poule","Gallus gallus domesticus","ferme","culture","partout_sauf:arctique,antarctique,boreale,siberie","2-4","garder","")
a("minecraft:horse","Cheval","Equus caballus","ferme","prairie,steppe","atlantique,continentale,mediterranee,steppes_tibet,siberie,grandes_plaines,cone_sud,maghreb,moyen_orient","2-6","garder","steppes : chevaux semi-sauvages")
a("minecraft:donkey","Âne","Equus asinus","ferme","steppe,desert","mediterranee,maghreb,sahara_sahel,afrique_est,moyen_orient,inde","1-3","garder","")
a("minecraft:llama","Lama","Lama glama","ferme","montagne,prairie","andes","3-6","garder","seul camélidé des Andes du pack")
a("minecraft:goat","Chèvre de montagne","Capra ibex / Oreamnos americanus","sauvage","montagne","alpine,steppes_tibet,boreale,ouest_mexique,moyen_orient,maghreb","2-4","garder","bouquetin en Europe et Asie, chèvre des Rocheuses en Amérique")
a("minecraft:rabbit","Lapin","Oryctolagus / Lepus","sauvage","prairie,steppe,desert,toundra","partout_sauf:antarctique,melanesie","2-3","garder","variantes blanc (neige) et doré (désert)")
a("minecraft:wolf","Loup","Canis lupus","sauvage","foret,toundra,steppe,montagne","continentale,nordique,alpine,siberie,boreale,steppes_tibet,arctique,moyen_orient,inde","4-8","garder","prédateur")
a("minecraft:fox","Renard","Vulpes vulpes / lagopus","sauvage","foret,prairie,toundra","atlantique,mediterranee,continentale,nordique,alpine,siberie,boreale,grandes_plaines,maghreb,moyen_orient,japon_coree,chine,australie,arctique","1-2","garder","renard polaire (variante neige) en Arctique")
a("minecraft:polar_bear","Ours polaire","Ursus maritimus","sauvage","banquise,toundra","arctique","1-2","garder","")
a("minecraft:panda","Panda géant","Ailuropoda melanoleuca","sauvage","foret (bambou)","chine","1-2","garder","")
a("minecraft:ocelot","Ocelot","Leopardus pardalis","sauvage","foret_tropicale","amerique_centrale,amazonie,ouest_mexique","1","garder","")
a("minecraft:parrot","Perroquet","Psittacidae","sauvage","foret_tropicale","amazonie,amerique_centrale,afrique_tropicale,asie_sud_est,melanesie,australie","1-2","garder","")
a("minecraft:turtle","Tortue marine","Chelonia mydas","sauvage","cote (plage)","mediterranee,amerique_centrale,asie_sud_est,melanesie,australie,inde,afrique_est","2-5","garder","plages chaudes")
a("minecraft:dolphin","Dauphin","Delphinidae","sauvage","mer,large","mers_chaudes_tempérées","2-6","garder","")
a("minecraft:squid","Calmar","Teuthida","sauvage","mer,large","toutes_les_mers","2-4","garder","")
a("minecraft:glow_squid","Calmar luisant","—","fantastique","souterrain (eau)","—","2-4","souterrain","grottes inondées seulement")
a("minecraft:cod","Morue (base)","Gadus morhua","poisson","mer","—","3-7","doublon:aquaculture:atlantic_cod","")
a("minecraft:salmon","Saumon","Salmo salar","poisson","mer,eau_douce","atlantique,nordique,boreale,siberie,japon_coree","3-5","garder","remonte les rivières")
a("minecraft:tropical_fish","Poisson tropical","Pomacentridae etc.","poisson","mer (récifs)","mers_tropicales","4-8","garder","")
a("minecraft:pufferfish","Poisson-globe","Tetraodontidae","poisson","mer","mers_tropicales","1-3","garder","")
a("minecraft:axolotl","Axolotl","Ambystoma mexicanum","sauvage","eau_douce","ouest_mexique","1-2","garder","lac de Xochimilco, remis en surface")
a("minecraft:frog","Grenouille","Anura","sauvage","marais,eau_douce","partout_sauf:arctique,antarctique,sahara_sahel","2-5","garder","variantes froide, tempérée, chaude")
a("minecraft:bee","Abeille","Apis mellifera","insecte","prairie,foret","partout_sauf:arctique,antarctique","nid","garder","")
a("minecraft:bat","Chauve-souris","Chiroptera","sauvage","souterrain","partout","2-8","garder","grottes")
a("minecraft:mooshroom","Champimeuh","—","fantastique","—","—","—","retirer","pas d'îles champignons sur la vraie Terre")

# ------------------------------------------------------------------ UNTAMED WILDS (une ligne par espèce)
U = "untamedwilds:"
def uw(ent, sp, nom, lat, cat, mil, ts, g, st="garder", note=""): a(f"{U}{ent}/{sp}", nom, lat, cat, mil, ts, g, st, note)
uw("bear","brown","Ours brun","Ursus arctos","sauvage","foret,montagne","nordique,alpine,siberie,boreale,continentale","1","garder","grizzli en Amérique ; prédateur")
uw("bear","black","Ours noir","Ursus americanus","sauvage","foret","boreale,grandes_plaines","1")
uw("bear","polar","Ours polaire (UW)","Ursus maritimus","sauvage","banquise","—","1","doublon:minecraft:polar_bear")
uw("bear","panda","Panda (UW)","Ailuropoda melanoleuca","sauvage","foret","—","1","doublon:minecraft:panda")
uw("bear","spectacled","Ours à lunettes","Tremarctos ornatus","sauvage","foret (montagne)","andes","1")
uw("bear","sun","Ours malais","Helarctos malayanus","sauvage","foret_tropicale","asie_sud_est","1")
uw("bear","cave","Ours des cavernes","Ursus spelaeus","fantastique","—","—","—","retirer","espèce disparue")
uw("bear","blind","Ours aveugle","—","fantastique","—","—","—","retirer","inventé")
uw("big_cat","lion","Lion","Panthera leo","sauvage","savane","afrique_est,afrique_australe,sahara_sahel,inde","2-5","garder","troupe ; lion d'Asie au Gujarat")
uw("big_cat","leopard","Léopard","Panthera pardus","sauvage","savane,foret","afrique_tropicale,afrique_est,afrique_australe,inde,moyen_orient","1")
uw("big_cat","tiger","Tigre","Panthera tigris","sauvage","foret","inde,chine,siberie,asie_sud_est","1","garder","tigre de Sibérie à l'Amour")
uw("big_cat","snow_leopard","Léopard des neiges","Panthera uncia","sauvage","montagne","steppes_tibet","1")
uw("big_cat","jaguar","Jaguar","Panthera onca","sauvage","foret_tropicale,marais","amazonie,amerique_centrale","1")
uw("big_cat","puma","Puma","Puma concolor","sauvage","montagne,foret","ouest_mexique,andes,boreale,cone_sud","1")
for s in ("cave_lion","sabertooth","marsupial_lion"): uw("big_cat",s,s.replace("_"," "),"—","fantastique","—","—","—","retirer","espèce disparue")
uw("bison","plains","Bison d'Amérique","Bison bison","sauvage","prairie","grandes_plaines,boreale","4-10")
uw("bison","wisent","Bison d'Europe","Bison bonasus","sauvage","foret","continentale","3-6","garder","Białowieża, Carpates")
uw("boar","eurasian","Sanglier","Sus scrofa","sauvage","foret","atlantique,mediterranee,continentale,alpine,moyen_orient,inde,chine,japon_coree,siberie","3-6")
uw("boar","peccary","Pécari","Pecari tajacu","sauvage","foret_tropicale,desert","amazonie,amerique_centrale,ouest_mexique","3-6")
uw("boar","red_river","Potamochère roux","Potamochoerus porcus","sauvage","foret_tropicale","afrique_tropicale","3-6")
uw("boar","warthog","Phacochère","Phacochoerus africanus","sauvage","savane","afrique_est,afrique_australe,sahara_sahel","2-5")
uw("camel","dromedary","Dromadaire","Camelus dromedarius","sauvage","desert","sahara_sahel,maghreb,moyen_orient,australie","2-6","garder","féral en Australie")
uw("camel","bactrian","Chameau de Bactriane","Camelus bactrianus","ferme","steppe,desert","steppes_tibet","2-4")
uw("camel","wild_bactrian","Chameau sauvage","Camelus ferus","sauvage","desert","steppes_tibet","2-4","garder","désert de Gobi")
uw("rhino","black","Rhinocéros noir","Diceros bicornis","sauvage","savane","afrique_est,afrique_australe","1")
uw("rhino","white","Rhinocéros blanc","Ceratotherium simum","sauvage","savane","afrique_australe,afrique_est","1-3")
uw("rhino","indian","Rhinocéros indien","Rhinoceros unicornis","sauvage","prairie,marais","inde","1")
uw("rhino","javan","Rhinocéros de Java","Rhinoceros sondaicus","sauvage","foret_tropicale","asie_sud_est","1","garder","très rare")
uw("rhino","sumatran","Rhinocéros de Sumatra","Dicerorhinus sumatrensis","sauvage","foret_tropicale","asie_sud_est","1","garder","très rare")
uw("rhino","wooly","Rhinocéros laineux","—","fantastique","—","—","—","retirer","espèce disparue")
uw("hyena","spotted","Hyène tachetée","Crocuta crocuta","sauvage","savane","afrique_est,afrique_australe,afrique_tropicale","3-6","garder","prédateur")
uw("hyena","striped","Hyène rayée","Hyaena hyaena","sauvage","desert,steppe","sahara_sahel,maghreb,moyen_orient,inde","1-2")
uw("hyena","brown","Hyène brune","Parahyaena brunnea","sauvage","desert,savane","afrique_australe","1-2")
uw("hyena","aardwolf","Protèle","Proteles cristata","sauvage","savane","afrique_est,afrique_australe","1")
uw("hyena","shortface","Hyène géante","—","fantastique","—","—","—","retirer","espèce disparue")
uw("wildebeest","blue","Gnou bleu","Connochaetes taurinus","sauvage","savane","afrique_est,afrique_australe","6-12","garder","grande migration")
uw("wildebeest","black","Gnou à queue blanche","Connochaetes gnou","sauvage","prairie","afrique_australe","4-8")
uw("aardvark","common","Oryctérope","Orycteropus afer","sauvage","savane","afrique_est,afrique_australe,afrique_tropicale","1")
uw("hippo","common","Hippopotame","Hippopotamus amphibius","sauvage","eau_douce","afrique_est,afrique_tropicale,afrique_australe","3-8","garder","dangereux")
uw("opossum","virginia","Opossum","Didelphis virginiana","sauvage","foret","grandes_plaines,ouest_mexique,amerique_centrale","1")
uw("large_snake","anaconda","Anaconda","Eunectes murinus","sauvage","eau_douce,marais","amazonie","1","garder","prédateur")
uw("large_snake","reticulated_python","Python réticulé","Malayopython reticulatus","sauvage","foret_tropicale","asie_sud_est","1","garder","prédateur")
uw("giant_salamander","chinese","Salamandre géante de Chine","Andrias davidianus","sauvage","eau_douce","chine","1")
uw("giant_salamander","japanese","Salamandre géante du Japon","Andrias japonicus","sauvage","eau_douce","japon_coree","1")
uw("giant_salamander","hellbender","Ménopome","Cryptobranchus alleganiensis","sauvage","eau_douce","grandes_plaines","1","garder","Appalaches")
uw("monitor","nile","Varan du Nil","Varanus niloticus","sauvage","eau_douce,savane","afrique_tropicale,afrique_est,afrique_australe,sahara_sahel","1")
uw("monitor","desert","Varan du désert","Varanus griseus","sauvage","desert","sahara_sahel,maghreb,moyen_orient","1")
uw("monitor","bengal","Varan du Bengale","Varanus bengalensis","sauvage","foret,culture","inde","1")
uw("monitor","water","Varan malais","Varanus salvator","sauvage","eau_douce,cote","asie_sud_est,inde","1")
uw("monitor","rock","Varan des rochers","Varanus albigularis","sauvage","savane","afrique_australe,afrique_est","1")
for sp,nom,lat,mil,ts,note in [
  ("adder","Vipère péliade","Vipera berus","prairie,foret","atlantique,continentale,nordique,alpine,siberie","venimeux"),
  ("grass_snake","Couleuvre à collier","Natrix natrix","marais,prairie","atlantique,mediterranee,continentale,nordique,maghreb",""),
  ("rattlesnake","Crotale diamantin","Crotalus adamanteus","foret,prairie","grandes_plaines","venimeux"),
  ("western_rattlesnake","Crotale de l'Ouest","Crotalus oreganus / atrox","desert,steppe","ouest_mexique,grandes_plaines","venimeux"),
  ("corn","Serpent des blés","Pantherophis guttatus","foret,culture","grandes_plaines",""),
  ("gray_kingsnake","Serpent-roi gris","Lampropeltis alterna","desert","ouest_mexique",""),
  ("swamp_moccasin","Mocassin d'eau","Agkistrodon piscivorus","marais","grandes_plaines","venimeux"),
  ("coral","Serpent corail","Micrurus","foret_tropicale","amerique_centrale,amazonie,ouest_mexique","venimeux"),
  ("coral_blue","Serpent corail bleu","Calliophis bivirgatus","foret_tropicale","asie_sud_est","venimeux"),
  ("emerald","Boa émeraude","Corallus caninus","foret_tropicale","amazonie",""),
  ("ball_python","Python royal","Python regius","savane","afrique_tropicale",""),
  ("black_mamba","Mamba noir","Dendroaspis polylepis","savane","afrique_est,afrique_australe","venimeux"),
  ("green_mamba","Mamba vert","Dendroaspis viridis","foret_tropicale","afrique_tropicale,afrique_est","venimeux"),
  ("rice_paddy","Serpent des rizières","Hypsiscopus plumbea","marais,culture (rizières)","asie_sud_est,chine,inde",""),
  ("carpet_python","Python tapis","Morelia spilota","foret","australie,melanesie",""),
  ("taipan","Taïpan","Oxyuranus","savane,desert","australie,melanesie","venimeux")]:
    uw("snake",sp,nom,lat,"sauvage",mil,ts,"1","garder",note)
uw("snake","cave_racer","Couleuvre des cavernes","—","fantastique","souterrain","—","1","souterrain","étage couches hautes")
for sp,nom,lat,mil,ts in [("gopher","Gophère","Gopherus polyphemus","prairie,foret","grandes_plaines"),
  ("marginated","Tortue bordée","Testudo marginata","mediterraneen","mediterranee"),
  ("leopard","Tortue léopard","Stigmochelys pardalis","savane","afrique_est,afrique_australe"),
  ("sulcata","Tortue sillonnée","Centrochelys sulcata","desert,savane","sahara_sahel"),
  ("star","Tortue étoilée (UW)","Geochelone elegans","savane","—"),
  ("asian_box","Tortue-boîte d'Asie","Cuora amboinensis","marais,foret_tropicale","asie_sud_est")]:
    uw("tortoise",sp,nom,lat,"sauvage",mil,ts,"1","doublon:aquaculture:starshell_turtle" if sp=="star" else "garder")
for sp,nom,lat,ts in [("chinese","Trionyx de Chine","Pelodiscus sinensis","chine,japon_coree"),
  ("nile","Trionyx du Nil","Trionyx triunguis","sahara_sahel,afrique_tropicale"),
  ("spiny","Trionyx épineux","Apalone spinifera","grandes_plaines"),
  ("black","Trionyx noir","Nilssonia nigricans","inde"),
  ("peacock","Trionyx paon","Nilssonia hurum","inde"),
  ("flapshell","Trionyx à clapets","Lissemys punctata","inde"),
  ("pig_nose","Tortue à nez de cochon","Carettochelys insculpta","melanesie,australie")]:
    uw("softshell_turtle",sp,nom,lat,"sauvage","eau_douce",ts,"1")
for sp,nom,lat,ts in [("fire_salamander","Salamandre tachetée","Salamandra salamandra","atlantique,continentale,mediterranee,alpine"),
  ("crested","Triton crêté","Triturus cristatus","atlantique,continentale,nordique"),
  ("alpine","Triton alpestre","Ichthyosaura alpestris","alpine,continentale"),
  ("marbled","Triton marbré","Triturus marmoratus","atlantique,mediterranee"),
  ("ribbed","Pleurodèle","Pleurodeles waltl","mediterranee,maghreb"),
  ("eastern","Triton vert","Notophthalmus viridescens","grandes_plaines,boreale"),
  ("coastal","Triton du Pacifique","Taricha torosa","ouest_mexique"),
  ("tiger","Salamandre tigrée","Ambystoma tigrinum","grandes_plaines"),
  ("fire_belly","Triton à ventre de feu","Cynops orientalis","chine,japon_coree"),
  ("axolotl","Axolotl (UW)","Ambystoma mexicanum","—")]:
    uw("newt",sp,nom,lat,"sauvage","eau_douce,foret (humide)",ts,"1-3","doublon:minecraft:axolotl" if sp=="axolotl" else "garder")
for sp,nom,lat,ts in [("blue","Poisson-chat bleu","Ictalurus furcatus","grandes_plaines"),
  ("channel","Barbue de rivière","Ictalurus punctatus","grandes_plaines,boreale"),
  ("redtail","Poisson-chat à queue rouge","Phractocephalus hemioliopterus","amazonie")]:
    uw("catfish",sp,nom,lat,"poisson","eau_douce",ts,"1")
for sp,nom,lat,ts in [("silver","Arowana argenté","Osteoglossum bicirrhosum","amazonie"),
  ("black","Arowana noir","Osteoglossum ferreirai","amazonie"),
  ("green","Arowana d'Asie","Scleropages formosus","asie_sud_est"),
  ("jardini","Arowana perlé","Scleropages jardinii","australie,melanesie")]:
    uw("arowana",sp,nom,lat,"poisson","eau_douce",ts,"1")
for sp,nom,lat,ts in [("west","Lamantin des Caraïbes","Trichechus manatus","amerique_centrale,grandes_plaines"),
  ("amazon","Lamantin d'Amazonie","Trichechus inunguis","amazonie"),
  ("african","Lamantin d'Afrique","Trichechus senegalensis","afrique_tropicale,sahara_sahel"),
  ("dugong","Dugong","Dugong dugon","asie_sud_est,australie,melanesie,inde,afrique_est"),
  ("steller","Rhytine de Steller","—","—")]:
    uw("manatee",sp,nom,lat,"sauvage" if sp!="steller" else "fantastique","eau_douce,cote" if sp!="steller" else "—",ts,"1-2" if sp!="steller" else "—","retirer" if sp=="steller" else "garder","espèce disparue" if sp=="steller" else "")
for sp,nom,lat,ts in [("blue","Baleine bleue","Balaenoptera musculus","tous_les_océans"),("fin","Rorqual commun","Balaenoptera physalus","tous_les_océans"),
  ("gray","Baleine grise","Eschrichtius robustus","boreale,ouest_mexique,siberie"),("humpback","Baleine à bosse","Megaptera novaeangliae","tous_les_océans"),
  ("minke","Petit rorqual","Balaenoptera acutorostrata","mers_froides"),("sei","Rorqual boréal","Balaenoptera borealis","tous_les_océans")]:
    uw("baleen_whale",sp,nom,lat,"sauvage","large",ts,"1-2")
for sp,nom,lat,ts,note in [("great_white","Grand requin blanc","Carcharodon carcharias","afrique_australe,australie,nouvelle_zelande,ouest_mexique,mediterranee","prédateur"),
  ("hammerhead","Requin-marteau","Sphyrna","mers_tropicales",""),("tiger","Requin-tigre","Galeocerdo cuvier","mers_tropicales","prédateur"),
  ("bull","Requin-bouledogue","Carcharhinus leucas","mers_tropicales","remonte les fleuves"),("lemon","Requin-citron","Negaprion brevirostris","amerique_centrale","mangroves"),
  ("mako","Requin mako","Isurus oxyrinchus","mers_chaudes_tempérées",""),("bigeye","Requin-renard à gros yeux","Alopias superciliosus","mers_chaudes_tempérées",""),
  ("bluntnose","Requin griset","Hexanchus griseus","mers_profondes",""),("goblin","Requin-lutin","Mitsukurina owstoni","abysses","japon : fosses"),
  ("greenland","Requin du Groenland","Somniosus microcephalus","arctique,nordique","")]:
    uw("shark",sp,nom,lat,"poisson","mer,large",ts,"1","garder",note)
uw("whale_shark","whale_shark","Requin-baleine","Rhincodon typus","poisson","large","mers_tropicales","1")
for sp,nom in [("large_tooth","Poisson-scie commun"),("small_tooth","Poisson-scie tident"),("green","Poisson-scie vert"),("narrow","Poisson-scie à rostre étroit"),("dwarf","Poisson-scie nain")]:
    uw("sawfish",sp,nom,"Pristidae","poisson","cote,eau_douce","mers_tropicales","1")
uw("sunfish","sunfish","Poisson-lune","Mola mola","poisson","large","mers_chaudes_tempérées","1")
uw("sunfish","southern","Poisson-lune du Sud","Mola alexandrini","poisson","large","australie,nouvelle_zelande,cone_sud","1")
uw("football_fish","atlantic","Baudroie abyssale","Himantolophus groenlandicus","poisson","abysses","mers_profondes","1")
for e,n,lat in [("giant_clam","Bénitier géant","Tridacna"),("trevally","Carangue","Carangidae"),("triggerfish","Baliste","Balistidae"),("spadefish","Platax","Ephippidae")]:
    uw(e,"*",n,lat,"poisson" if e!="giant_clam" else "sauvage","mer (récifs)","mers_tropicales","1-4","garder","plusieurs espèces")
uw("king_crab","red","Crabe royal","Paralithodes camtschaticus","sauvage","mer (fond froid)","siberie,boreale,nordique","1-2")
uw("king_crab","centolla","Centolla","Lithodes santolla","sauvage","mer (fond froid)","cone_sud","1-2")
uw("king_crab","spiny","Crabe royal épineux","Paralithodes brevipes","sauvage","mer (fond froid)","japon_coree,siberie","1-2")
for sp,nom,lat,mil,ts in [("monarch","Monarque","Danaus plexippus","prairie","grandes_plaines,ouest_mexique,boreale"),
  ("tiger_swallowtail","Grand porte-queue tigré","Papilio glaucus","foret","grandes_plaines"),("mourning_cloak","Morio","Nymphalis antiopa","foret",EUR+",boreale,grandes_plaines"),
  ("red_admiral","Vulcain","Vanessa atalanta","prairie",EUR+",grandes_plaines"),("peacock","Paon-du-jour","Aglais io","prairie",EUR+",siberie"),
  ("brimstone","Citron","Gonepteryx rhamni","foret",EUR),("cabbage","Piéride du chou","Pieris brassicae","culture",EUR+",maghreb,moyen_orient"),
  ("comma","Robert-le-diable","Polygonia c-album","foret",EUR),("orange_tip","Aurore","Anthocharis cardamines","prairie",EUR),
  ("speckled_wood","Tircis","Pararge aegeria","foret",EUR+",maghreb"),("emperor","Grand mars changeant","Apatura iris","foret","continentale,atlantique"),
  ("morpho","Morpho bleu","Morpho","foret_tropicale","amazonie,amerique_centrale"),("glasswing","Papillon de verre","Greta oto","foret_tropicale","amerique_centrale"),
  ("blue_swallowtail","Porte-queue bleu","Papilio ulysses","foret_tropicale","australie,melanesie"),("birdwing","Ornithoptère","Ornithoptera","foret_tropicale","melanesie,asie_sud_est"),
  ("kite","Voilier","Graphium","foret_tropicale","asie_sud_est,inde"),("leaf","Papillon-feuille","Kallima inachus","foret_tropicale","inde,asie_sud_est,chine"),
  ("malachite","Malachite","Siproeta stelenes","foret_tropicale","amerique_centrale,amazonie"),("narcissus","Narcisse","Ornithoptera / Papilio","foret","japon_coree"),
  ("triangle","Voilier triangle","Graphium sarpedon","foret","asie_sud_est,chine,japon_coree,australie")]:
    uw("butterfly",sp,nom,lat,"insecte",mil,ts,"1-3")
for sp,nom,lat,ts in [("rose","Mygale rose du Chili","Grammostola rosea","cone_sud,andes"),("red_knee","Mygale à genoux rouges","Brachypelma hamorii","ouest_mexique"),
  ("black","Mygale noire","Grammostola pulchra","cone_sud"),("black_and_white","Mygale zébrée","Acanthoscurria geniculata","amazonie"),
  ("cobalt","Mygale bleu cobalt","Cyriopagopus lividus","asie_sud_est"),("king","Mygale roi","Pelinobius muticus","afrique_est"),
  ("regalis","Mygale royale","Poecilotheria regalis","inde"),("tiger","Mygale tigre","Psalmopoeus","amerique_centrale")]:
    uw("tarantula",sp,nom,lat,"insecte","foret,desert",ts,"1")
uw("terror_bird","*","Oiseaux-terreur","—","fantastique","—","—","—","retirer","espèces disparues")
uw("spitter","purple","Cracheur","—","fantastique","souterrain","—","1","souterrain","créature inventée : étage profondeurs")

# ------------------------------------------------------------------ NATURALIST 5.0pre2
N="naturalist:"
a(N+"alligator","Alligator","Alligator mississippiensis","sauvage","marais,eau_douce","grandes_plaines","1-2","garder","Floride, Louisiane ; prédateur")
a(N+"bear","Grizzli (Nat.)","Ursus arctos","sauvage","—","—","—","doublon:untamedwilds:bear/brown","")
a(N+"bluejay","Geai bleu","Cyanocitta cristata","sauvage","foret","grandes_plaines,boreale","1-2","garder","")
a(N+"boar","Sanglier (Nat.)","—","sauvage","—","—","—","doublon:untamedwilds:boar/eurasian","")
a(N+"butterfly","Papillon (Nat.)","—","insecte","—","—","—","doublon:untamedwilds:butterfly","20 espèces réelles chez Untamed Wilds")
a(N+"caterpillar","Chenille","Lepidoptera","insecte","foret","partout_sauf:arctique,antarctique","1","garder","")
a(N+"moth","Papillon de nuit","Heterocera","insecte","foret (nuit)","partout_sauf:arctique,antarctique","1-3","garder","")
a(N+"canary","Canari","Serinus canaria","sauvage","foret","mediterranee,maghreb","1-3","garder","Canaries, Madère, Açores")
a(N+"cardinal","Cardinal rouge","Cardinalis cardinalis","sauvage","foret","grandes_plaines,ouest_mexique","1-2","garder","")
a(N+"catfish","Poisson-chat (Nat.)","—","poisson","—","—","—","doublon:untamedwilds:catfish","")
a(N+"bass","Bar (Nat.)","—","poisson","—","—","—","doublon:aquaculture:smallmouth_bass","")
a(N+"coral_snake","Serpent corail (Nat.)","—","sauvage","—","—","—","doublon:untamedwilds:snake/coral","")
a(N+"rattlesnake","Serpent à sonnettes (Nat.)","—","sauvage","—","—","—","doublon:untamedwilds:snake/western_rattlesnake","")
a(N+"snake","Serpent (Nat.)","—","sauvage","—","—","—","doublon:untamedwilds:snake/grass_snake","")
a(N+"deer","Chevreuil","Capreolus capreolus","sauvage","foret",EUR+",siberie,japon_coree","2-4","garder","cerf de Virginie en Amérique ?")
a(N+"dragonfly","Libellule","Anisoptera","insecte","eau_douce,marais","partout_sauf:arctique,antarctique","1-3","garder","")
a(N+"duck","Canard colvert","Anas platyrhynchos","sauvage","eau_douce,marais","partout_sauf:antarctique,sahara_sahel,amazonie","2-5","garder","")
a(N+"elephant","Éléphant","Loxodonta / Elephas","sauvage","savane,foret_tropicale","afrique_est,afrique_australe,afrique_tropicale,inde,asie_sud_est","3-8","garder","seul éléphant du pack")
a(N+"finch","Pinson des arbres","Fringilla coelebs","sauvage","foret",EUR+",maghreb","2-4","garder","")
a(N+"firefly","Luciole","Lampyridae","insecte","prairie,foret (nuit)","atlantique,continentale,mediterranee,grandes_plaines,japon_coree,chine,asie_sud_est","3-8","garder","")
a(N+"giraffe","Girafe","Giraffa","sauvage","savane","afrique_est,afrique_australe","2-6","garder","")
a(N+"hippo","Hippopotame (Nat.)","—","sauvage","—","—","—","doublon:untamedwilds:hippo/common","")
a(N+"hyena","Hyène (Nat.)","—","sauvage","—","—","—","doublon:untamedwilds:hyena/spotted","")
a(N+"lion","Lion (Nat.)","—","sauvage","—","—","—","doublon:untamedwilds:big_cat/lion","")
a(N+"rhino","Rhinocéros (Nat.)","—","sauvage","—","—","—","doublon:untamedwilds:rhino","")
a(N+"tortoise","Tortue terrestre (Nat.)","Testudo hermanni","sauvage","mediterraneen,steppe","mediterranee,maghreb,moyen_orient","1","garder","tortue d'Hermann / grecque")
a(N+"lizard","Lézard","Lacertidae / Agamidae","sauvage","desert,steppe,mediterraneen","mediterranee,maghreb,sahara_sahel,moyen_orient,australie,ouest_mexique","1-2","garder","")
a(N+"ostrich","Autruche","Struthio camelus","sauvage","savane,desert","afrique_est,afrique_australe,sahara_sahel","2-5","garder","")
a(N+"robin","Rouge-gorge","Erithacus rubecula","sauvage","foret",EUR,"1-2","garder","")
a(N+"snail","Escargot","Helix","insecte","foret,prairie (pluie)","atlantique,continentale,mediterranee,alpine","1-3","garder","")
a(N+"sparrow","Moineau","Passer domesticus","sauvage","culture","partout_sauf:arctique,antarctique,amazonie","3-6","garder","")
a(N+"termite","Termite","Isoptera","insecte","savane,foret_tropicale","afrique_est,afrique_tropicale,afrique_australe,australie,inde,amazonie,asie_sud_est","termitière","garder","")
a(N+"vulture","Vautour","Gyps","sauvage","ciel (savane, montagne)","afrique_est,sahara_sahel,mediterranee,inde,moyen_orient,alpine","1-3","garder","vautour fauve dans les Alpes et les Pyrénées")
a(N+"zebra","Zèbre","Equus quagga","sauvage","savane","afrique_est,afrique_australe","4-10","garder","")

# ------------------------------------------------------------------ LET'S DO WILDERNATURE
W="wildernature:"
a(W+"bison","Bison (WN)","—","sauvage","—","—","—","doublon:untamedwilds:bison/plains","")
a(W+"boar","Sanglier (WN)","—","sauvage","—","—","—","doublon:untamedwilds:boar/eurasian","")
a(W+"cassowary","Casoar","Casuarius","sauvage","foret_tropicale","melanesie,australie","1","garder","dangereux")
a(W+"deer","Cerf élaphe","Cervus elaphus","sauvage","foret,prairie",EUR+",boreale,grandes_plaines,siberie","3-6","garder","wapiti en Amérique")
a(W+"dog","Chien","Canis familiaris","ferme","—","—","—","a_confirmer","animal de compagnie : villages seulement ?")
a(W+"flamingo","Flamant rose","Phoenicopterus","sauvage","cote,marais (lagunes salées)","mediterranee,afrique_est,afrique_australe,amerique_centrale,andes,inde","6-15","garder","Camargue")
a(W+"hedgehog","Hérisson","Erinaceus europaeus","sauvage","foret,prairie",EUR,"1","garder","")
a(W+"minisheep","Mouton nain","Ovis aries","ferme","montagne","alpine","2-4","a_confirmer","race domestique, utile ?")
a(W+"owl","Chouette","Strigiformes","sauvage","foret (nuit)","partout_sauf:antarctique","1","garder","")
a(W+"pelican","Pélican","Pelecanus","sauvage","cote,eau_douce","afrique_est,afrique_tropicale,grandes_plaines,amerique_centrale,australie,inde,mediterranee","3-8","garder","")
a(W+"penguin","Manchot (WN)","—","sauvage","—","—","—","doublon:ecologics:penguin","")
a(W+"raccoon","Raton laveur","Procyon lotor","sauvage","foret","grandes_plaines,boreale,ouest_mexique","1-3","garder","")
a(W+"red_wolf","Loup roux","Canis rufus","sauvage","foret,marais","grandes_plaines","3-6","garder","")
a(W+"squirrel","Écureuil (WN)","—","sauvage","—","—","—","doublon:ecologics:squirrel","")
a(W+"turkey","Dindon sauvage","Meleagris gallopavo","sauvage","foret,prairie","grandes_plaines,ouest_mexique","3-6","garder","")
# ------------------------------------------------------------------ LET'S DO MEADOW (races domestiques)
M="meadow:"
a(M+"wooly_sheep","Mouton laineux","Ovis aries","ferme","montagne,prairie","alpine","3-5","garder","")
a(M+"horned_sheep","Mouton cornu","Ovis aries","ferme","montagne","mediterranee,moyen_orient,alpine","3-5","garder","")
a(M+"wooly_cow","Vache laineuse (Highland)","Bos taurus","ferme","montagne,prairie","alpine,atlantique,nordique","2-4","garder","")
a(M+"water_buffalo","Buffle d'eau","Bubalus bubalis","ferme","marais,culture (rizières)","inde,asie_sud_est,chine","3-6","garder","")
# ------------------------------------------------------------------ ECOLOGICS
E="ecologics:"
a(E+"camel","Dromadaire (Eco.)","—","sauvage","—","—","—","doublon:untamedwilds:camel/dromedary","")
a(E+"coconut_crab","Crabe de cocotier","Birgus latro","sauvage","cote (plage tropicale)","melanesie,asie_sud_est","1","garder","")
a(E+"penguin","Manchot","Spheniscidae","sauvage","banquise,cote","antarctique,cone_sud,afrique_australe,nouvelle_zelande","4-10","garder","")
a(E+"squirrel","Écureuil roux","Sciurus vulgaris","sauvage","foret",EUR+",siberie,japon_coree","1-2","garder","")
# ------------------------------------------------------------------ AQUACULTURE 2
Q="aquaculture:"
for e,n,lat,mil,ts,g in [("atlantic_cod","Morue","Gadus morhua","mer","atlantique,nordique,boreale","3-7"),
  ("atlantic_halibut","Flétan de l'Atlantique","Hippoglossus hippoglossus","mer","atlantique,nordique","1"),
  ("atlantic_herring","Hareng","Clupea harengus","mer","atlantique,nordique","5-10"),
  ("pacific_halibut","Flétan du Pacifique","Hippoglossus stenolepis","mer","boreale,japon_coree,siberie","1"),
  ("pollock","Lieu","Pollachius","mer","atlantique,nordique,boreale","3-6"),
  ("blackfish","Tautogue","Tautoga onitis","cote","grandes_plaines","1-3"),
  ("red_grouper","Mérou rouge","Epinephelus morio","mer","amerique_centrale,grandes_plaines","1"),
  ("tuna","Thon","Thunnus","large","mers_chaudes_tempérées","3-6"),
  ("pink_salmon","Saumon rose","Oncorhynchus gorbuscha","mer,eau_douce","boreale,siberie,japon_coree","3-6"),
  ("brown_trout","Truite brune","Salmo trutta","eau_douce",EUR,"2-4"),
  ("carp","Carpe","Cyprinus carpio","eau_douce","continentale,chine,japon_coree,steppes_tibet","2-4"),
  ("perch","Perche","Perca fluviatilis","eau_douce","atlantique,continentale,nordique,siberie","3-6"),
  ("muskellunge","Maskinongé","Esox masquinongy","eau_douce","boreale,grandes_plaines","1"),
  ("minnow","Vairon","Phoxinus / Pimephales","eau_douce",EUR+",boreale,grandes_plaines,siberie","5-10"),
  ("bluegill","Crapet arlequin","Lepomis macrochirus","eau_douce","grandes_plaines","3-6"),
  ("smallmouth_bass","Achigan à petite bouche","Micropterus dolomieu","eau_douce","grandes_plaines,boreale","2-4"),
  ("rainbow_trout","Truite arc-en-ciel","Oncorhynchus mykiss","eau_douce","boreale,grandes_plaines,ouest_mexique","2-4"),
  ("gar","Lépisosté","Lepisosteus","eau_douce","grandes_plaines,amerique_centrale","1-2"),
  ("arapaima","Arapaïma","Arapaima gigas","eau_douce","amazonie","1"),
  ("piranha","Piranha","Pygocentrus nattereri","eau_douce","amazonie","4-8"),
  ("tambaqui","Tambaqui","Colossoma macropomum","eau_douce","amazonie","1-3"),
  ("bayad","Bayad","Bagrus bajad","eau_douce","sahara_sahel,afrique_tropicale","1-2"),
  ("boulti","Tilapia du Nil","Oreochromis niloticus","eau_douce","sahara_sahel,afrique_tropicale,afrique_est","3-6"),
  ("capitaine","Perche du Nil","Lates niloticus","eau_douce","sahara_sahel,afrique_tropicale,afrique_est","1"),
  ("synodontis","Synodontis","Synodontis","eau_douce","sahara_sahel,afrique_tropicale","2-4")]:
    a(Q+e,n,lat,"poisson",mil,ts,g,"garder","")
a(Q+"catfish","Poisson-chat (Aq.)","Silurus glanis","poisson","eau_douce","continentale","1","garder","silure d'Europe (les espèces d'Amérique viennent d'Untamed Wilds)")
a(Q+"jellyfish","Méduse","Scyphozoa","sauvage","mer","toutes_les_mers","2-5","garder","")
a(Q+"arrau_turtle","Tortue de l'Arrau","Podocnemis expansa","sauvage","eau_douce","amazonie","1-3","garder","")
a(Q+"box_turtle","Tortue-boîte","Terrapene carolina","sauvage","foret","grandes_plaines","1","garder","")
a(Q+"starshell_turtle","Tortue étoilée de l'Inde","Geochelone elegans","sauvage","savane","inde","1","garder","")
a(Q+"red_shrooma","Shrooma rouge","—","fantastique","—","—","—","retirer","")
a(Q+"brown_shrooma","Shrooma brun","—","fantastique","—","—","—","retirer","")
# ------------------------------------------------------------------ MONSTRES DES MODS
S="savage_and_ravage:"
a(S+"creepie","Creepie","—","monstre","souterrain","—","1-3","souterrain","petit creeper : couches hautes")
a(S+"skeleton_villager","Villageois squelette","—","monstre","souterrain","—","1","souterrain","couches hautes")
for e,n in [("iceologer","Iceologer"),("griefer","Griefer"),("executioner","Bourreau"),("trickster","Trickster")]:
    a(S+e,n,"—","monstre","—","—","—","a_confirmer","illageois : laissés aux patrouilles et structures (MAJ structures) ?")
a("guardvillagers:illusioner","Illusionniste","—","monstre","—","—","—","a_confirmer","illageois : patrouilles et structures")
a("guardvillagers:guard","Garde","—","ferme","villages","—","—","garder","villages seulement, inchangé")

# ------------------------------------------------------------------ BEST REVIVED ANIMALS (portage 1.20.1 de Better Animals Plus, à installer)
# liste reprise de la page de Better Animals Plus ; identifiants (betteranimalsplus:) à vérifier dans le jar du portage
B="betteranimalsplus:"
note_b="mod à installer ; id à vérifier"
for e,n,lat,cat,mil,ts,g in [
  ("reindeer","Renne / caribou","Rangifer tarandus","sauvage","toundra,foret","arctique,siberie,nordique,boreale","4-10"),
  ("moose","Élan","Alces alces","sauvage","foret,marais","boreale,nordique,siberie","1-2"),
  ("walrus","Morse","Odobenus rosmarus","sauvage","banquise,cote","arctique","3-8"),
  ("deer","Cerf de Virginie","Odocoileus virginianus","sauvage","foret,prairie","grandes_plaines,boreale,ouest_mexique,amerique_centrale","2-4"),
  ("coyote","Coyote","Canis latrans","sauvage","prairie,desert,foret","grandes_plaines,ouest_mexique,boreale","1-3"),
  ("lammergeier","Gypaète barbu","Gypaetus barbatus","sauvage","ciel (montagne)","alpine,steppes_tibet,afrique_est,moyen_orient,maghreb","1"),
  ("badger","Blaireau","Meles meles / Taxidea taxus","sauvage","foret,prairie","atlantique,continentale,mediterranee,nordique,grandes_plaines,ouest_mexique","1-2"),
  ("pheasant","Faisan de Colchide","Phasianus colchicus","sauvage","culture,prairie","chine,steppes_tibet,japon_coree,continentale,atlantique","1-3"),
  ("goose","Oie cendrée / bernache","Anser anser / Branta canadensis","sauvage","eau_douce,marais","atlantique,continentale,nordique,siberie,boreale,grandes_plaines","4-10"),
  ("songbird","Passereaux","Passeriformes","sauvage","foret","partout_sauf:arctique,antarctique","2-4"),
  ("crab","Crabe","Brachyura","sauvage","cote","toutes_les_côtes","2-4"),
  ("horseshoe_crab","Limule","Limulus / Tachypleus","sauvage","cote (plage)","grandes_plaines,asie_sud_est,chine,japon_coree","1-3"),
  ("eel_freshwater","Anguille d'Europe","Anguilla anguilla","poisson","eau_douce","atlantique,continentale,mediterranee,nordique,maghreb","1-2"),
  ("eel_saltwater","Murène","Muraenidae","poisson","mer (récifs)","mers_chaudes_tempérées","1"),
  ("lamprey","Lamproie","Petromyzon marinus","poisson","eau_douce,mer","atlantique,nordique,grandes_plaines","1-2"),
  ("octopus","Pieuvre","Octopus vulgaris","sauvage","mer","toutes_les_mers","1"),
  ("nautilus","Nautile","Nautilus pompilius","sauvage","mer profonde","melanesie,asie_sud_est,australie","1"),
  ("barracuda","Barracuda","Sphyraena barracuda","poisson","mer (récifs)","mers_tropicales","1-4"),
  ("bobbit_worm","Ver de Bobbit","Eunice aphroditois","sauvage","mer (récifs)","asie_sud_est,australie,melanesie,japon_coree","1"),
  ("flying_fish","Poisson volant","Exocoetidae","poisson","large","mers_tropicales","3-6"),
  ("squid_giant","Calmar géant","Architeuthis dux","sauvage","abysses","mers_profondes","1"),
  ("squid_colossal","Calmar colossal","Mesonychoteuthis hamiltoni","sauvage","abysses","antarctique","1")]:
    a(B+e,n,lat,cat,mil,ts,g,"garder",note_b)
for e,n,cible in [("feral_wolf","Loup féral","minecraft:wolf"),("turkey","Dindon (BA+)","wildernature:turkey"),("boar","Sanglier (BA+)","untamedwilds:boar/eurasian"),
  ("squirrel","Écureuil (BA+)","ecologics:squirrel"),("butterfly","Papillon (BA+)","untamedwilds:butterfly"),("dragonfly","Libellule (BA+)","naturalist:dragonfly"),
  ("tarantula","Mygale (BA+)","untamedwilds:tarantula"),("piranha","Piranha (BA+)","aquaculture:piranha"),("shark","Requin (BA+)","untamedwilds:shark"),
  ("whale","Baleine (BA+)","untamedwilds:baleen_whale"),("jellyfish","Méduse (BA+)","aquaculture:jellyfish"),
  ("brownbear","Ours brun (BA+)","untamedwilds:bear/brown"),("blackbear","Ours noir (BA+)","untamedwilds:bear/black")]:
    a(B+e,n,"—","sauvage","—","—","—","doublon:"+cible,note_b)
a(B+"hirschgeist","Hirschgeist","—","fantastique","souterrain","—","1","souterrain","esprit-cerf du folklore germanique : abîmes, ou endémique des forêts d'Europe centrale (à décider)")
a(B+"zotzpyre","Zotzpyre","—","fantastique","souterrain","—","2-4","souterrain","chauve-souris vampire du mythe maya : abîmes, ou endémique d'Amérique centrale (à décider)")

# ------------------------------------------------------------------ ALEX'S MOBS (proposé, à installer ; créatures inventées envoyées sous terre)
for r in [['alexsmobs:alligator_snapping_turtle', 'Tortue alligator', 'Macrochelys temminckii', 'sauvage', 'eau_douce,marais', 'grandes_plaines', '1', 'garder', 'mod à installer'], ['alexsmobs:anaconda', 'Anaconda', 'Eunectes murinus', 'sauvage', 'eau_douce,marais', '—', '1', 'doublon:untamedwilds:large_snake/anaconda', 'mod à installer'], ['alexsmobs:anteater', 'Fourmilier', 'Myrmecophaga tridactyla', 'sauvage', 'savane,foret_tropicale', 'amazonie,cone_sud,amerique_centrale', '1', 'garder', 'mod à installer'], ['alexsmobs:bald_eagle', 'Pygargue à tête blanche', 'Haliaeetus leucocephalus', 'sauvage', "ciel (près de l'eau)", 'boreale,grandes_plaines', '1', 'garder', 'mod à installer'], ['alexsmobs:banana_slug', 'Limace banane', 'Ariolimax', 'insecte', 'foret (humide)', 'boreale', '1-2', 'garder', 'forêts côtières du Pacifique nord ; mod à installer'], ['alexsmobs:bison', 'Bison', 'Bison bison', 'sauvage', 'prairie', '—', '4-8', 'doublon:untamedwilds:bison/plains', 'mod à installer'], ['alexsmobs:blobfish', 'Blobfish', 'Psychrolutes marcidus', 'poisson', 'abysses', 'australie,nouvelle_zelande', '1', 'garder', 'fonds profonds ; mod à installer'], ['alexsmobs:blue_jay', 'Geai bleu', 'Cyanocitta cristata', 'sauvage', 'foret', '—', '1-2', 'doublon:naturalist:bluejay', 'mod à installer'], ['alexsmobs:cachalot_whale', 'Grand cachalot', 'Physeter macrocephalus', 'sauvage', 'large', 'tous_les_océans_profonds', '1-2', 'garder', 'mod à installer'], ['alexsmobs:caiman', 'Caïman', 'Caiman crocodilus', 'sauvage', 'eau_douce,marais', 'amazonie,amerique_centrale', '1-3', 'garder', 'mod à installer'], ['alexsmobs:capuchin_monkey', 'Capucin', 'Cebus', 'sauvage', 'foret_tropicale', 'amazonie,amerique_centrale', '3-6', 'garder', 'mod à installer'], ['alexsmobs:catfish', 'Poisson-chat (AM)', 'Silurus', 'poisson', 'eau_douce', '—', '1', 'doublon:untamedwilds:catfish', 'mod à installer'], ['alexsmobs:cockroach', 'Cafard', 'Blattodea', 'insecte', 'sol,souterrain', 'partout_chaud', '2-4', 'garder', 'mod à installer'], ['alexsmobs:comb_jelly', 'Cténophore', 'Ctenophora', 'sauvage', 'mer,large', 'toutes_les_mers', '1-3', 'garder', 'mod à installer'], ['alexsmobs:crocodile', 'Crocodile', 'Crocodylus niloticus / porosus', 'sauvage', 'eau_douce,cote', 'afrique_tropicale,afrique_est,inde,asie_sud_est,australie,melanesie', '1-2', 'garder', 'prédateur ; mod à installer'], ['alexsmobs:crow', 'Corbeau', 'Corvus', 'sauvage', 'culture,foret', 'partout_sauf:antarctique,amazonie', '2-5', 'garder', 'mod à installer'], ['alexsmobs:devils_hole_pupfish', 'Cyprinodon du trou du Diable', 'Cyprinodon diabolis', 'poisson', 'eau_douce', 'ouest_mexique', '2-4', 'garder', 'très rare (une seule source au Nevada) ; mod à installer'], ['alexsmobs:elephant', 'Éléphant', 'Loxodonta / Elephas', 'sauvage', 'savane,foret_tropicale', '—', '3-8', 'doublon:naturalist:elephant', 'mod à installer'], ['alexsmobs:emu', 'Émeu', 'Dromaius novaehollandiae', 'sauvage', 'savane,steppe', 'australie', '2-5', 'garder', 'mod à installer'], ['alexsmobs:flying_fish', 'Poisson volant', 'Exocoetidae', 'poisson', 'large', '—', '3-6', 'doublon:betteranimalsplus:flying_fish', 'mod à installer'], ['alexsmobs:frilled_shark', 'Requin lézard', 'Chlamydoselachus anguineus', 'poisson', 'abysses', 'japon_coree,toutes_les_mers_profondes', '1', 'garder', 'mod à installer'], ['alexsmobs:gazelle', 'Gazelle', 'Gazella', 'sauvage', 'savane,desert', 'afrique_est,sahara_sahel,maghreb,moyen_orient', '4-8', 'garder', 'mod à installer'], ['alexsmobs:gelada_monkey', 'Gélada', 'Theropithecus gelada', 'sauvage', 'montagne,prairie', 'afrique_est', '4-10', 'garder', "hauts plateaux d'Éthiopie ; mod à installer"], ['alexsmobs:giant_squid', 'Calmar géant', 'Architeuthis dux', 'sauvage', 'abysses', '—', '1', 'doublon:betteranimalsplus:squid_giant', 'mod à installer'], ['alexsmobs:gorilla', 'Gorille', 'Gorilla', 'sauvage', 'foret_tropicale', 'afrique_tropicale', '3-8', 'garder', 'mod à installer'], ['alexsmobs:grizzly_bear', 'Grizzli', 'Ursus arctos horribilis', 'sauvage', 'foret,montagne', '—', '1', 'doublon:untamedwilds:bear/brown', 'mod à installer'], ['alexsmobs:hammerhead_shark', 'Requin-marteau', 'Sphyrna', 'poisson', 'mer,large', 'mers_tropicales', '1-3', 'garder', 'prédateur ; mod à installer'], ['alexsmobs:hummingbird', 'Colibri', 'Trochilidae', 'sauvage', 'foret_tropicale,prairie', 'amerique_centrale,amazonie,andes,ouest_mexique', '1-2', 'garder', 'mod à installer'], ['alexsmobs:jerboa', 'Gerboise', 'Jaculus', 'sauvage', 'desert', 'sahara_sahel,maghreb,moyen_orient,steppes_tibet', '1-2', 'garder', 'mod à installer'], ['alexsmobs:kangaroo', 'Kangourou', 'Macropus', 'sauvage', 'savane,steppe', 'australie', '3-6', 'garder', 'mod à installer'], ['alexsmobs:komodo_dragon', 'Dragon de Komodo', 'Varanus komodoensis', 'sauvage', 'savane,foret', 'asie_sud_est', '1', 'garder', 'îles de la Sonde  ; mod à installer', ' prédateur'], ['alexsmobs:leafcutter_ant', 'Fourmi coupe-feuille', 'Atta', 'insecte', 'foret_tropicale', 'amazonie,amerique_centrale', 'fourmilière', 'garder', 'mod à installer'], ['alexsmobs:lobster', 'Homard', 'Homarus', 'sauvage', 'cote,mer', 'atlantique,nordique,boreale', '1-3', 'garder', 'mod à installer'], ['alexsmobs:maned_wolf', 'Loup à crinière', 'Chrysocyon brachyurus', 'sauvage', 'savane', 'cone_sud,amazonie', '1', 'garder', 'mod à installer'], ['alexsmobs:mantis_shrimp', 'Crevette-mante', 'Stomatopoda', 'sauvage', 'mer (récifs)', 'mers_tropicales', '1', 'garder', 'mod à installer'], ['alexsmobs:mimic_octopus', 'Poulpe mimétique', 'Thaumoctopus mimicus', 'sauvage', 'mer (récifs)', 'asie_sud_est,melanesie', '1', 'garder', 'mod à installer'], ['alexsmobs:moose', 'Élan', 'Alces alces', 'sauvage', 'foret,marais', '—', '1-2', 'doublon:betteranimalsplus:moose', 'mod à installer'], ['alexsmobs:mudskipper', 'Périophthalme', 'Periophthalmus', 'poisson', 'cote (mangrove)', 'asie_sud_est,afrique_tropicale,inde,australie', '2-4', 'garder', 'mod à installer'], ['alexsmobs:orca', 'Orque', 'Orcinus orca', 'sauvage', 'mer,large', 'toutes_les_mers_froides', '3-6', 'garder', 'prédateur ; mod à installer'], ['alexsmobs:platypus', 'Ornithorynque', 'Ornithorhynchus anatinus', 'sauvage', 'eau_douce', 'australie', '1', 'garder', 'mod à installer'], ['alexsmobs:potoo', 'Ibijau', 'Nyctibius', 'sauvage', 'foret_tropicale', 'amazonie,amerique_centrale', '1', 'garder', 'mod à installer'], ['alexsmobs:raccoon', 'Raton laveur', 'Procyon lotor', 'sauvage', 'foret', '—', '1-3', 'doublon:wildernature:raccoon', 'mod à installer'], ['alexsmobs:rain_frog', 'Grenouille de pluie', 'Breviceps', 'sauvage', 'desert (côtier)', 'afrique_australe', '1-2', 'garder', 'mod à installer'], ['alexsmobs:rattlesnake', 'Crotale', 'Crotalus', 'sauvage', 'desert,steppe', '—', '1', 'doublon:untamedwilds:snake/western_rattlesnake', 'mod à installer'], ['alexsmobs:rhinoceros', 'Rhinocéros (AM)', 'Rhinocerotidae', 'sauvage', 'savane', '—', '1-2', 'doublon:untamedwilds:rhino', 'mod à installer'], ['alexsmobs:roadrunner', 'Géocoucou', 'Geococcyx', 'sauvage', 'desert', 'ouest_mexique', '1', 'garder', 'mod à installer'], ['alexsmobs:seagull', 'Mouette', 'Laridae', 'sauvage', 'cote', 'toutes_les_côtes_sauf_tropicales', '3-6', 'garder', 'mod à installer'], ['alexsmobs:seal', 'Phoque', 'Phocidae', 'sauvage', 'cote,banquise', 'arctique,nordique,boreale,siberie,antarctique,atlantique,cone_sud,nouvelle_zelande', '3-6', 'garder', 'côtes froides seulement (règle le bug du Mexique) ; mod à installer'], ['alexsmobs:shoebill', 'Bec-en-sabot', 'Balaeniceps rex', 'sauvage', 'marais', 'afrique_est,afrique_tropicale', '1', 'garder', 'mod à installer'], ['alexsmobs:skunk', 'Moufette', 'Mephitis mephitis', 'sauvage', 'foret,prairie', 'grandes_plaines,boreale,ouest_mexique', '1-2', 'garder', 'mod à installer'], ['alexsmobs:snow_leopard', 'Léopard des neiges', 'Panthera uncia', 'sauvage', 'montagne', '—', '1', 'doublon:untamedwilds:big_cat/snow_leopard', 'mod à installer'], ['alexsmobs:sugar_glider', 'Phalanger volant', 'Petaurus breviceps', 'sauvage', 'foret', 'australie,melanesie', '1-3', 'garder', 'mod à installer'], ['alexsmobs:tarantula_hawk', 'Guêpe-tarentule', 'Pepsis', 'insecte', 'desert', 'ouest_mexique,grandes_plaines,amerique_centrale', '1', 'garder', 'mod à installer'], ['alexsmobs:tasmanian_devil', 'Diable de Tasmanie', 'Sarcophilus harrisii', 'sauvage', 'foret', 'australie', '1', 'garder', 'Tasmanie seulement ; mod à installer'], ['alexsmobs:terrapin', 'Tortue de rivière', 'Malaclemys / Trachemys', 'sauvage', 'eau_douce,marais', 'grandes_plaines', '1-3', 'garder', 'mod à installer'], ['alexsmobs:tiger', 'Tigre (AM)', 'Panthera tigris', 'sauvage', 'foret', '—', '1', 'doublon:untamedwilds:big_cat/tiger', 'mod à installer'], ['alexsmobs:toucan', 'Toucan', 'Ramphastidae', 'sauvage', 'foret_tropicale', 'amazonie,amerique_centrale', '1-3', 'garder', 'mod à installer'], ['alexsmobs:triops', 'Triops', 'Triops cancriformis', 'sauvage', 'eau_douce (mares)', 'desert,steppe', '3-6', 'garder', 'mares temporaires ; mod à installer'], ['alexsmobs:fly', 'Mouche', 'Musca domestica', 'insecte', 'partout', 'partout_sauf:antarctique', '1', 'garder', 'mod à installer'], ['alexsmobs:centipede_head', 'Mille-pattes des cavernes', '—', 'fantastique', 'souterrain', '—', '1', 'souterrain', 'profondeurs ; mod à installer'], ['alexsmobs:rocky_roller', 'Rouleau rocheux', '—', 'fantastique', 'souterrain', '—', '1', 'souterrain', 'profondeurs ; mod à installer'], ['alexsmobs:underminer', 'Sous-mineur', '—', 'fantastique', 'souterrain', '—', '1', 'souterrain', 'abîmes ; mod à installer'], ['alexsmobs:murmur', 'Murmure', '—', 'fantastique', 'souterrain', '—', '1', 'souterrain', 'abîmes ; mod à installer'], ['alexsmobs:skreecher', 'Skreecher', '—', 'fantastique', 'souterrain', '—', '1', 'souterrain', 'abîmes ; mod à installer'], ['alexsmobs:farseer', 'Voyant éloigné', '—', 'fantastique', 'souterrain', '—', '1', 'souterrain', 'abîmes ; mod à installer'], ['alexsmobs:froststalker', 'Traqueur givrant', '—', 'fantastique', 'souterrain', '—', '—', 'souterrain', 'profondeurs ; mod à installer'], ['alexsmobs:tusklin', 'Tusklin', '—', 'fantastique', 'souterrain', '—', '—', 'souterrain', 'profondeurs ; mod à installer'], ['alexsmobs:guster', 'Rafalleur', '—', 'fantastique', '—', '—', '—', 'a_confirmer', 'créature inventée : abîmes ou retirée ? ; mod à installer'], ['alexsmobs:flutter', 'Papilloneur', '—', 'fantastique', '—', '—', '—', 'a_confirmer', 'créature inventée : abîmes ou retirée ? ; mod à installer'], ['alexsmobs:sunbird', 'Oiseau de soleil', '—', 'fantastique', '—', '—', '—', 'a_confirmer', 'créature inventée : abîmes ou retirée ? ; mod à installer'], ['alexsmobs:sea_bear', 'Tardigrade géant', '—', 'fantastique', 'souterrain', '—', '—', 'souterrain', 'profondeurs ; mod à installer'], ['alexsmobs:skelewag', 'Squeladon', '—', 'fantastique', 'souterrain', '—', '—', 'souterrain', 'profondeurs ; mod à installer'], ['alexsmobs:mungus', 'Mongus', '—', 'fantastique', '—', '—', '—', 'a_confirmer', 'vit sur les îles champignons ; créature inventée : abîmes ou retirée ? ; mod à installer'], ['alexsmobs:bunfungus', 'Champilièvre', '—', 'fantastique', '—', '—', '—', 'a_confirmer', 'créature inventée : abîmes ou retirée ? ; mod à installer'], ['alexsmobs:mimicube', 'Imicube', '—', 'fantastique', 'End', '—', '—', 'garder', "End : on n'y touche pas ; mod à installer"]]:
    a(*r)

with open(os.path.join(ICI, "especes.csv"), "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f, delimiter=";")
    w.writerow(["id","nom","espece_reelle","categorie","milieu","terroirs","groupe","statut","note"])
    w.writerows(L)
print(len(L), "lignes")
