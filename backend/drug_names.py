"""
drug_names.py - ONE shared, curated list of medicine names, used by both the comparison feature (reconcile.py)
and the letter-to-photo matching (crossreference.py).

Why this exists: the matching code is plain code (not AI) on purpose, so it is predictable and checkable. Its accuracy
therefore depends on how complete and correct its NAME LIST is. An earlier version used a small list in one feature and a
random sample of FDA label names in the other, and the sample was full of non-medicines. This file replaces both.

Lists:
  SINGLE_BRANDS  brand -> ONE generic ingredient            (used by both features)
  COMBO_BRANDS   brand -> several ingredients                (used by the comparison feature only, which treats a
                                                              shared ingredient as "ask a pharmacist")
  SYNONYMS       other spellings of a generic name           (other countries, and Turkish spellings)
  EXTRA_GENERICS generic names with no brand listed          (so the app knows they are real medicines)

Every entry here must be checked by a pharmacist before this list is called "verified". See brand_generic_review.csv.
Keys are lower case, with hyphens written as spaces (the matching code normalizes names the same way).
"""
import re

SINGLE_BRANDS_TEXT = """
# --- heart and blood pressure
lipitor: atorvastatin | zocor: simvastatin | crestor: rosuvastatin | pravachol: pravastatin | mevacor: lovastatin | livalo: pitavastatin
zetia: ezetimibe | tricor: fenofibrate | lopid: gemfibrozil | norvasc: amlodipine | procardia: nifedipine | adalat: nifedipine
cardizem: diltiazem | calan: verapamil | zestril: lisinopril | prinivil: lisinopril | vasotec: enalapril | altace: ramipril
lotensin: benazepril | accupril: quinapril | cozaar: losartan | diovan: valsartan | benicar: olmesartan | avapro: irbesartan
micardis: telmisartan | atacand: candesartan | tenormin: atenolol | coreg: carvedilol | bystolic: nebivolol | inderal: propranolol
lasix: furosemide | bumex: bumetanide | demadex: torsemide | aldactone: spironolactone | hydrodiuril: hydrochlorothiazide
microzide: hydrochlorothiazide | lanoxin: digoxin | coumadin: warfarin | jantoven: warfarin | eliquis: apixaban | xarelto: rivaroxaban
pradaxa: dabigatran | plavix: clopidogrel | brilinta: ticagrelor | effient: prasugrel | nitrostat: nitroglycerin | imdur: isosorbide mononitrate
ranexa: ranolazine | catapres: clonidine | cordarone: amiodarone | pacerone: amiodarone
# --- diabetes and thyroid
glucophage: metformin | glucotrol: glipizide | amaryl: glimepiride | januvia: sitagliptin | jardiance: empagliflozin | farxiga: dapagliflozin
invokana: canagliflozin | victoza: liraglutide | ozempic: semaglutide | wegovy: semaglutide | rybelsus: semaglutide | trulicity: dulaglutide
mounjaro: tirzepatide | zepbound: tirzepatide | actos: pioglitazone | lantus: insulin glargine | basaglar: insulin glargine | toujeo: insulin glargine
levemir: insulin detemir | humalog: insulin lispro | novolog: insulin aspart | tresiba: insulin degludec | synthroid: levothyroxine
levoxyl: levothyroxine | unithroid: levothyroxine | euthyrox: levothyroxine | cytomel: liothyronine | tapazole: methimazole
# --- mind, sleep and nerves
zoloft: sertraline | lexapro: escitalopram | celexa: citalopram | prozac: fluoxetine | paxil: paroxetine | effexor: venlafaxine
cymbalta: duloxetine | wellbutrin: bupropion | zyban: bupropion | remeron: mirtazapine | desyrel: trazodone | elavil: amitriptyline
buspar: buspirone | xanax: alprazolam | ativan: lorazepam | klonopin: clonazepam | valium: diazepam | ambien: zolpidem
lunesta: eszopiclone | abilify: aripiprazole | seroquel: quetiapine | zyprexa: olanzapine | risperdal: risperidone | lamictal: lamotrigine
keppra: levetiracetam | tegretol: carbamazepine | dilantin: phenytoin | topamax: topiramate | neurontin: gabapentin | lyrica: pregabalin
ritalin: methylphenidate | concerta: methylphenidate | strattera: atomoxetine | intuniv: guanfacine | aricept: donepezil | namenda: memantine
imitrex: sumatriptan | maxalt: rizatriptan | lithobid: lithium | haldol: haloperidol
# --- pain and muscles
naprosyn: naproxen | celebrex: celecoxib | mobic: meloxicam | voltaren: diclofenac | toradol: ketorolac | ultram: tramadol
oxycontin: oxycodone | roxicodone: oxycodone | dilaudid: hydromorphone | flexeril: cyclobenzaprine | robaxin: methocarbamol
soma: carisoprodol | zanaflex: tizanidine | ecotrin: aspirin | lioresal: baclofen
# --- stomach
nexium: esomeprazole | prevacid: lansoprazole | protonix: pantoprazole | aciphex: rabeprazole | zantac: ranitidine | tagamet: cimetidine
zofran: ondansetron | reglan: metoclopramide | phenergan: promethazine | imodium: loperamide | colace: docusate | dulcolax: bisacodyl
miralax: polyethylene glycol | senokot: senna | pepto bismol: bismuth subsalicylate | tums: calcium carbonate | gas x: simethicone
mylicon: simethicone | carafate: sucralfate | linzess: linaclotide | metamucil: psyllium | dramamine: dimenhydrinate
# --- allergy and breathing
allegra: fexofenadine | xyzal: levocetirizine | singulair: montelukast | flonase: fluticasone | nasonex: mometasone | spiriva: tiotropium
pulmicort: budesonide | qvar: beclomethasone | atrovent: ipratropium | xopenex: levalbuterol | delsym: dextromethorphan
afrin: oxymetazoline | tessalon: benzonatate | chlor trimeton: chlorpheniramine | visine: tetrahydrozoline
# --- infection
z pak: azithromycin | biaxin: clarithromycin | cipro: ciprofloxacin | levaquin: levofloxacin | keflex: cephalexin | ceftin: cefuroxime
omnicef: cefdinir | vibramycin: doxycycline | flagyl: metronidazole | macrobid: nitrofurantoin | diflucan: fluconazole | valtrex: valacyclovir
zovirax: acyclovir | famvir: famciclovir | tamiflu: oseltamivir | plaquenil: hydroxychloroquine | stromectol: ivermectin | cleocin: clindamycin
lamisil: terbinafine
# --- hormones, steroids, bladder, bones, other
deltasone: prednisone | rayos: prednisone | orapred: prednisolone | millipred: prednisolone | pediapred: prednisolone | medrol: methylprednisolone
decadron: dexamethasone | proscar: finasteride | propecia: finasteride | flomax: tamsulosin | avodart: dutasteride | viagra: sildenafil
cialis: tadalafil | detrol: tolterodine | ditropan: oxybutynin | fosamax: alendronate | evista: raloxifene | premarin: conjugated estrogens
estrace: estradiol | provera: medroxyprogesterone | clomid: clomiphene | arimidex: anastrozole | femara: letrozole | nolvadex: tamoxifen
zyloprim: allopurinol | colcrys: colchicine | uloric: febuxostat | trexall: methotrexate | humira: adalimumab | enbrel: etanercept
imuran: azathioprine | cellcept: mycophenolate | prograf: tacrolimus | rogaine: minoxidil | narcan: naloxone | chantix: varenicline
antabuse: disulfiram | lidoderm: lidocaine | tylenol: acetaminophen | calpol: acetaminophen | panadol: acetaminophen | advil: ibuprofen
motrin: ibuprofen | nurofen: ibuprofen | aleve: naproxen | benadryl: diphenhydramine | claritin: loratadine | zyrtec: cetirizine
pepcid: famotidine | prilosec: omeprazole | ventolin: albuterol | proair: albuterol | proventil: albuterol | flovent: fluticasone
zithromax: azithromycin | amoxil: amoxicillin | iburamin: ibuprofen | oladin: olopatadine
"""

COMBO_BRANDS_TEXT = """
augmentin: amoxicillin clavulanate | advair: fluticasone salmeterol | symbicort: budesonide formoterol | combivent: ipratropium albuterol
duoneb: ipratropium albuterol | bactrim: sulfamethoxazole trimethoprim | septra: sulfamethoxazole trimethoprim | norco: hydrocodone acetaminophen
vicodin: hydrocodone acetaminophen | percocet: oxycodone acetaminophen | zestoretic: lisinopril hydrochlorothiazide
hyzaar: losartan hydrochlorothiazide | lotrel: amlodipine benazepril | vytorin: ezetimibe simvastatin | janumet: sitagliptin metformin
entresto: sacubitril valsartan | adderall: amphetamine dextroamphetamine | sinemet: carbidopa levodopa | suboxone: buprenorphine naloxone
excedrin: acetaminophen aspirin caffeine | lomotil: diphenoxylate atropine | neosporin: neomycin polymyxin bacitracin
"""

# Brands that carry a salt or release form the comparison feature must keep (so a switch is flagged, not hidden)
SALT_BRANDS = {"lopressor": "metoprolol tartrate", "toprol": "metoprolol succinate"}

SYNONYMS_TEXT = """
paracetamol: acetaminophen | salbutamol: albuterol | adrenaline: epinephrine | noradrenaline: norepinephrine | frusemide: furosemide
glibenclamide: glyburide | acetylsalicylic acid: aspirin | clavulanic acid: clavulanate
parasetamol: acetaminophen | amoksisilin: amoxicillin | prednizolon: prednisolone | prednizon: prednisone | metilprednizolon: methylprednisolone
deksametazon: dexamethasone | diklofenak: diclofenac | naproksen: naproxen | omeprazol: omeprazole | pantoprazol: pantoprazole
lansoprazol: lansoprazole | esomeprazol: esomeprazole | amlodipin: amlodipine | lizinopril: lisinopril | furosemid: furosemide
spironolakton: spironolactone | varfarin: warfarin | klopidogrel: clopidogrel | levotiroksin: levothyroxine | budesonid: budesonide
flutikazon: fluticasone | setirizin: cetirizine | feksofenadin: fexofenadine | azitromisin: azithromycin | klaritromisin: clarithromycin
siprofloksasin: ciprofloxacin | levofloksasin: levofloxacin | sefuroksim: cefuroxime | sefaleksin: cephalexin | metronidazol: metronidazole
flukonazol: fluconazole | asiklovir: acyclovir | valasiklovir: valacyclovir | insulin: insulin
"""

EXTRA_GENERICS_TEXT = """
atorvastatin simvastatin rosuvastatin amlodipine lisinopril losartan valsartan metoprolol atenolol carvedilol bisoprolol hydralazine
isosorbide nitroglycerin clonidine doxazosin terazosin prazosin labetalol nadolol sotalol flecainide digoxin amiodarone furosemide
hydrochlorothiazide chlorthalidone spironolactone warfarin apixaban rivaroxaban clopidogrel aspirin metformin glipizide glimepiride
glyburide pioglitazone sitagliptin insulin levothyroxine liothyronine methimazole prednisone prednisolone methylprednisolone dexamethasone
hydrocortisone budesonide fludrocortisone azathioprine hydroxychloroquine methotrexate leflunomide sulfasalazine colchicine allopurinol
baclofen tizanidine cyclobenzaprine methocarbamol tramadol oxycodone hydrocodone morphine hydromorphone codeine fentanyl buprenorphine
naloxone naltrexone gabapentin pregabalin duloxetine amitriptyline nortriptyline trazodone mirtazapine bupropion venlafaxine sertraline
fluoxetine paroxetine citalopram escitalopram buspirone hydroxyzine lorazepam alprazolam clonazepam diazepam temazepam zolpidem melatonin
lithium lamotrigine divalproex valproate carbamazepine oxcarbazepine phenytoin levetiracetam topiramate quetiapine olanzapine risperidone
aripiprazole haloperidol donepezil memantine pramipexole ropinirole sumatriptan rizatriptan ondansetron metoclopramide promethazine
famotidine omeprazole esomeprazole lansoprazole pantoprazole sucralfate loperamide bisacodyl docusate senna lactulose simethicone mesalamine
ursodiol amoxicillin ampicillin penicillin cephalexin cefuroxime cefdinir ceftriaxone azithromycin clarithromycin erythromycin doxycycline
minocycline ciprofloxacin levofloxacin moxifloxacin sulfamethoxazole trimethoprim nitrofurantoin metronidazole clindamycin vancomycin
linezolid fluconazole terbinafine nystatin acyclovir valacyclovir famciclovir oseltamivir ivermectin albendazole permethrin
acetaminophen ibuprofen naproxen diclofenac meloxicam celecoxib ketorolac diphenhydramine loratadine cetirizine fexofenadine
montelukast albuterol ipratropium tiotropium fluticasone mometasone guaifenesin dextromethorphan pseudoephedrine phenylephrine
oxymetazoline chlorpheniramine cyanocobalamin folic ferrous calcium magnesium potassium zinc vitamin cholecalciferol omega fluoride
epinephrine finasteride tamsulosin sildenafil tadalafil oxybutynin tolterodine alendronate estradiol medroxyprogesterone levonorgestrel
tamoxifen anastrozole letrozole
"""


def _pairs(text):
    out = {}
    for line in text.split("\n"):
        if line.strip().startswith("#"):
            continue
        for item in line.split("|"):
            item = item.strip()
            if not item:
                continue
            k, v = [x.strip() for x in item.split(":", 1)]
            if k in out and out[k] != v:
                raise ValueError(f"'{k}' is listed twice with different answers: {out[k]} / {v}")
            out[k] = v
    return out


SINGLE_BRANDS = _pairs(SINGLE_BRANDS_TEXT)
COMBO_BRANDS = _pairs(COMBO_BRANDS_TEXT)
SYNONYMS = _pairs(SYNONYMS_TEXT)
EXTRA_GENERICS = set(EXTRA_GENERICS_TEXT.split())

# every plain word that belongs to a known ingredient (so "sitagliptin metformin" is recognized word by word)
INGREDIENT_WORDS = set(EXTRA_GENERICS)
for _v in list(SINGLE_BRANDS.values()) + list(COMBO_BRANDS.values()) + list(SYNONYMS.values()):
    INGREDIENT_WORDS.update(_v.split())
INGREDIENT_WORDS -= {"acid", "and"}


def is_recognized(base):
    """True if every word of a normalized medicine name belongs to a medicine this app knows.
    'base' is the lower-case name with strengths, forms and salts removed, for example 'amoxicillin clavulanate'."""
    words = [w for w in re.split(r"[\s/\-_,+&]+", (base or "").lower().strip()) if w]
    return bool(words) and all(w in INGREDIENT_WORDS or w in SINGLE_BRANDS or w in COMBO_BRANDS for w in words)


def review_rows():
    """Rows for a pharmacist to check: (kind, name, generic)."""
    rows = [("brand", k, v) for k, v in sorted(SINGLE_BRANDS.items())]
    rows += [("combination brand", k, v) for k, v in sorted(COMBO_BRANDS.items())]
    rows += [("other spelling", k, v) for k, v in sorted(SYNONYMS.items()) if k != v]
    return rows
