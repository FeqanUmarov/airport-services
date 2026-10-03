# Lənkəran (UBBL) OLS: ArcGIS referensi ilə müqayisə və generatorun düzəldilməsi

Bütün ölçmələr **WGS 84 / UTM 39N (EPSG:32639)** sistemində, metrlə aparılıb.
Referens: `data/reference/lankaran_ols_arcgis.zip` (ArcGIS Pro export, Z = 0).
Standart: `ICAO_ANNEX_14_V1_ZANGILAN` (IH 4000/45, Conical 2000/100/5 %,
Approach 280 / 15 % / 3000@2 % + 3600@2.5 % + 8400@0 %, Take-off 180 / 12.5 % /
1200 / 15000 / 2 %, Transitional 1:7).

Koordinat çərçivəsi: runway centerline (Strip-in runway dəliyinin uc
ortaları) üzrə `s` (stansiya) və `v` (sol tərəf müsbət yanal məsafə). Kəsim
stansiyaları **runway ucundan kənara** ölçülür.

## 1. Problemin səbəbi

Köhnə generator hər səthi müstəqil tam poliqon kimi yaradırdı:

* Inner Horizontal və Conical — centerline buffer-ləri, Strip/Approach/Take-off
  ilə üst-üstə (IH–Approach 3.38 km², IH–Take-off 2.35 km², Conical–Approach
  3.47 km², Approach–Take-off 15.6 km² overlap);
* Approach Clearway-in üzərindən keçirdi (38 286 m² overlap);
* Transitional mütləq threshold hündürlüklərindən qurulurdu (RWY15 −15.85,
  RWY33 −10.668, IH 34.0) — eni 312.7…348.9 m arasında dəyişirdi, referensdə
  isə sabit 315 m-dir.

Yəni problem tək bir prioritet səhvi deyil: sistemdə **heç bir kəsim
(partition) mərhələsi yox idi**, Transitional isə referensdən fərqli şaquli
datumla qurulurdu.

## 2. Referensin analizi (sübutlar)

### 2.1 Referens oxboyu sıxılıb: k = 3290.177 / 3300 = 0.997023

Çəkilmiş runway (Strip dəliyi) 3290.177 m, AIP TORA isə 3300 m-dir. Referensdə
**yalnız oxboyu** ölçülər k ilə vurulub, yanal ölçülər isə yox:

| Element | Standart | Referens (oxboyu) | ÷ k | Yanal |
|---|---|---|---|---|
| Strip uzantısı | 60 | 59.822 | 60.000 | 140 (dəyişməyib) |
| Clearway (runway ucundan) | 300 | 299.107 | 300.000 | ±80 |
| Approach uzunluğu | 15 000 | 14 955.35 | 15 000.0 | 2390 (dəyişməyib) |
| Take-off 1200 m-ə çatma | 4080 | 4067.86 | 4080.0 | 600 |
| IH qövsü (v = 0) | 4000 | 3988.10 | 4000.0 | 4000 |

IH qövsü dairə yox, `(s/3988.1)² + (v/4000)² = 1` ellipsinə uyğundur, yəni
ekspertlər 3300 m-lik runway üçün qurub, sonra çəkilmiş runway-ə oxboyu
sıxıblar. Bu, sistemlə referens arasında **sistematik ~0.3 % fərq** yaradır
(məs. Approach/Take-off ucunda 15 000 × (1 − k) = **44.65 m**).

### 2.2 Kəsim stansiyaları (dizayn çərçivəsində, d = runway ucundan ÷ k)

| Kəsim | RWY 15 | RWY 33 | Qayda (nisbi datum) | Mütləq datum fərziyyəsi |
|---|---|---|---|---|
| Approach + Take-off yaxın hissə sonu (v = 0) | **2550.00** | **2550.00** | Take-off = IH: 300 + 45 / 2 % = 2550 | 2792.5 / 2533.4 — **rədd** |
| Approach yan zolaqları sonu | 2536.5–2563.6 (1.5° maili) | 2550.0 | eyni xətt | Approach = IH: 2310 — **rədd** |
| Take-off → Approach keçidi | **7800.00** | **7800.00** | T(d) = 150 (Approach horizontal) : 300 + 150 / 2 % | — |
| Approach hissə bölgüsü | 6660.00 | 6660.00 | 2-ci bölmənin sonu (60 + 6600) | — |
| Approach/Take-off yenidən başlayır | r = 4000 | r = 4000 | IH xarici sərhədi | — |
| Approach yan kənarı Conical xarici sərhədində | r = 6000 | r = 6000 | 4000 + 2000 | — |
| Transitional xarici xətti | \|v\| = 455.0 | 455.0 / 455.15–460.62 (sağ, əl ilə) | 140 + 45 × 7 | 312.7–348.9 — **rədd** |

### 2.3 Suallara cavablar

* **Approach parçalarının sərhədləri IH və Conical sərhədlərinə düşürmü?** Bəli.
  Orta parçalar IH qövsündən (r = 4000.00 ± 0.2) başlayır, yan kənar Conical
  xarici sərhədini r = 6000.00-da kəsir.
* **Approach–Take-off kəsim xətti profil bərabərliyi xəttidirmi?** Bəli, uzaq
  xətt (d = 7800) dəqiq T(d) = A(d) = 150 m bərabərliyidir; yaxında
  T < A (fərq 4.8 m) olduğundan overlap Take-off-a verilir. Overlap-ı bütövlükdə
  bir səthə vermək hər iki halda səhvdir.
* **Transitional Approach/Strip sərhədini dəqiq paylaşırmı?** Bəli (overlap
  0 m², Strip ilə 6 819.8 m, hər Approach ilə ~4 250 m ortaq sərhəd). Xarici
  xətt isə Strip yanından sabit 315 m-dir və Approach kənarına d = 2160-da
  çatanda bitir.
* **Referensdə boşluq və overlap varmı?** Runway örtüyü (148 058 m²) istisna
  olmaqla 327 m² boşluq, IH–Conical 254 m², IH–Take-off 11/21 m², IH–Approach
  ~2 m² overlap — hamısı əl ilə çəkilmə və qövs yaxınlaşdırma qalıqlarıdır.
* **Kəsimlər hansı modellə yaradılıb?** **Standarta nisbi, vahid datumlu
  profil** (bütün səthlərin bazası eyni). Mütləq threshold hündürlükləri
  istifadə olunmayıb: o halda RWY 15/33 kəsimləri 2792.5 / 2533.4 m-də, eni
  isə 349 / 313 m olardı; referensdə hər iki uc 2550.00 və 315 m-dir.
  Sırf sabit lay prioriteti də deyil: d = 7800 xətti profil bərabərliyindən
  gəlir.

### 2.4 "Effective lower envelope" fərziyyəsi yalnız qismən doğrudur

| Zona | Ciddi aşağı envelope | Referens |
|---|---|---|
| Approach ∩ Take-off | aşağı profil (d < 7800 Take-off) | ✔ eyni |
| IH daxilində Take-off | d ≥ 2550-də IH | ✔ eyni |
| IH daxilində Approach yan zolaqları | d ≥ 2310-da IH | ✘ 2550-yə qədər Approach saxlanılıb |
| IH-dan kənar, Conical zonası | Conical (məs. mərkəz xəttində d < 4967-yə qədər) | ✘ Conical Approach/Take-off ilə tam kəsilib |
| Transitional xarici xətti (Approach boyu) | 455 + 0.01·(d − 60), Approach-un IH-a çatdığı yerə qədər | ✘ sabit 455, d = 2160-da bitir |

## 3. Aşkar edilmiş referens kəsim qaydası (indi generatorda)

Bütün ölçülər standart parametrlərindən və faktiki Strip/Clearway
geometriyasından alınır (`o` = faktiki Strip ucundan məsafə):

1. **Approach ↔ Take-off**: overlap-da nisbi profili aşağı olan səth idarə
   edir; sərhəd centerline-a perpendikulyar, `A(o) = T(o)` olan stansiyadan
   keçir (hissə-hissə xətti tənlik həlli).
2. **Inner Horizontal**: `c = min(A, T)` mərkəz xətti profili IH hündürlüyünə
   çatan ilk stansiya. IH footprint daxilində `o ≥ c` olan Approach/Take-off
   hissələri IH-a verilir.
3. **Conical** = (centerline buffer R + W) − IH footprint − Approach − Take-off.
4. **Transitional** = faktiki Strip yan xəttindən `IH hündürlüyü / slope`
   məsafəyə qədər zolaq − Strip − Clearway − Approach footprint − Take-off.
   Zolaq ucları Approach kənarının bu xəttə çatdığı stansiyadır və həmin nöqtə
   Approach-a təpə nöqtəsi kimi əlavə olunur (ortaq node).
5. **Inner Horizontal** = centerline buffer R − Strip (xarici kontur) − Clearway
   − Transitional − Approach − Take-off.
6. **Approach** faktiki Strip ucundan, **Take-off** öz istiqamətinin Clearway
   xarici kənarından başlayır; Clearway hər ikisindən çıxılır.
7. **Z dəyərləri** hər təpə nöqtəsində səthin öz mütləq funksiyasından
   hesablanır (Approach: threshold + A(o); Take-off: Clearway sonu + T(o);
   IH: aerodrom + 45; Conical: IH + 5 % × (r − 4000); Transitional: Strip/Approach
   kənarı + 1:7, IH-dan yuxarı deyil).

## 4. Dəyişdirilən backend hissələri

* `app/modules/ols/envelope.py` (yeni): profil riyaziyyatı (`ApproachProfile`,
  `TakeoffProfile`, `controlling_intervals`, `inner_horizontal_cut_station`),
  metrik çərçivə və qövs dəqiqliyi.
* `app/modules/ols/service.py`: `generate()` indi əvvəlcə bütün səthləri
  `_partitioned_surfaces()` ilə vahid partition kimi qurur, sonra yazır.
  Köhnə müstəqil qurucular (`_segmented_surface`, `_transitional_*`) silinib;
  `gap_m`/`overlap_m` artıq sabit 0 deyil, ölçülür.
* `app/modules/ols/repository.py`: PostGIS sabit-dəqiqlikli overlay
  primitivləri (`difference/intersection/union` gridSize = 1 µm), ortaq
  node-ların əlavəsi (`node`), topologiya ölçüləri; köhnə 3D qurucular silinib.
* Həndəsi toleranslar (OLS ölçüsü deyil): overlay grid 1 µm, node 10 µm,
  Strip snap 1 mm, qövs sagitası ≤ 1 sm, topologiya 1 sm.

## 5. Əvvəl / sonra (faktiki Lənkəran girişləri)

### Əvvəl (köhnə generator)

| Lay | Ref sahə m² | Sistem sahə m² | Δ m² | Ref komp. | Sis. komp. | Hausdorff m | Sym. diff m² |
|---|---|---|---|---|---|---|---|
| Approach 15 | 30 454 675.6 | 37 950 001.1 | +7 495 325.4 | 5 | 1 | 1 283.19 | 7 687 936.9 |
| Approach 33 | 30 454 660.3 | 37 950 001.0 | +7 495 340.7 | 5 | 1 | 1 283.19 | 7 687 952.1 |
| Take-off 15 | 5 867 404.5 | 15 919 200.0 | +10 051 795.5 | 3 | 1 | 600.00 | 10 058 010.0 |
| Take-off 33 | 5 864 291.4 | 15 919 200.0 | +10 054 908.6 | 3 | 1 | 600.00 | 10 061 124.1 |
| Inner Horizontal | 68 721 340.2 | 76 264 540.8 | +7 543 200.7 | 1 | 1 | 3 527.93 | 7 855 417.6 |
| Conical | 68 951 579.7 | 75 589 612.2 | +6 638 032.5 | 2 | 1 | 1 022.18 | 7 647 058.0 |
| Transitional | 3 473 306.9 | 3 823 654.9 | +350 347.9 | 2 | 2 | 403.07 | 353 249.0 |

### Sonra (yeni generator)

| Lay | Ref sahə m² | Sistem sahə m² | Δ m² | Ref komp. | Sis. komp. | Hausdorff m | Sym. diff m² |
|---|---|---|---|---|---|---|---|
| Approach 15 | 30 454 675.6 | 30 545 556.3 | +90 880.7 (0.30 %) | 5 | 3 | 44.65 | 346 687.4 |
| Approach 33 | 30 454 660.3 | 30 545 556.2 | +90 895.9 (0.30 %) | 5 | 3 | 44.65 | 345 292.3 |
| Take-off 15 | 5 867 404.5 | 5 879 845.9 | +12 441.4 (0.21 %) | 3 | 3 | 44.65 | 152 350.0 |
| Take-off 33 | 5 864 291.4 | 5 879 845.7 | +15 554.4 (0.27 %) | 3 | 3 | 44.65 | 155 110.3 |
| Inner Horizontal | 68 721 340.2 | 68 907 882.2 | +186 542.0 (0.27 %) | 1 | 1 | 20.27 | 215 795.9 |
| Conical | 68 951 579.7 | 69 000 102.0 | +48 522.2 (0.07 %) | 2 | 2 | 22.51 | 516 487.5 |
| Transitional | 3 473 306.9 | 3 471 192.5 | −2 114.4 (0.06 %) | 2 | 2 | 31.61 | 9 998.5 |

Approach-un 5 vs 3 komponenti: referens 6660 m-dəki bölmə sərhədində əlavə
feature bölgüsü edir. Bir MultiPolygon daxilində kənar boyu toxunan hissələr
OGC-yə görə etibarsızdır, ona görə sistem həmin hissələri birləşmiş saxlayır
(bölmə sərhədində təpə nöqtəsi var).

### Mərkəz xətti boyunca kəsim stansiyaları (runway ucundan, m)

| | Take-off intervalları | Approach (v = 0) | Transitional təpəsi |
|---|---|---|---|
| Referens RWY 15 | 299.11–2542.41; 3988.09–7776.78; 15015.17–15254.46 | 7776.78–15015.17 | 2153.57 |
| Əvvəl RWY 15 | 299.11–15299.11 | 59.82–15059.82 | 2552.32 |
| Sonra RWY 15 | 299.11–2549.11; 4000.00–7799.11; 15059.82–15299.11 | 7799.11–15059.82 | 2159.83 |
| Referens RWY 33 | 299.11–2542.41; 3988.09–7776.78; 15015.17–15254.46 | 7776.78–15015.17 | 2190.93 |
| Əvvəl RWY 33 | 299.11–15299.11 | 59.82–15059.82 | 2293.22 |
| Sonra RWY 33 | 299.11–2549.11; 4000.00–7799.11; 15059.82–15299.11 | 7799.11–15059.82 | 2159.83 |

Sonrakı qiymətlər = faktiki Clearway sonu (299.11) + 2250 / 7500 / 15000;
referensdəkilər isə 2550·k, 7800·k, 15060·k.

### Topologiya

| | Referens | Əvvəl | Sonra |
|---|---|---|---|
| OLS lay cütləri arasında maksimal overlap | 254.4 m² (IH–Conical) | 15 632 057 m² | **0.00 m²** |
| Runway örtüyündən başqa boşluq | 327 m² | 0 (overlap hesabına) | **0.00 m²** (yalnız runway 148 058 m²) |
| Clearway–Approach / Clearway–Take-off ortaq sərhəd | 478.8 / 160.1 m | 160.1 / 160.1 m (+38 286 m² overlap) | **478.8 / 160.1 m** |
| Strip–Transitional ortaq sərhəd | 6 819.8 m | 6 819.8 m | **6 819.8 m** |
| Ortaq təpələrdə ΔZ (IH–Conical, Approach–Transitional) | — | — | **0.000 m** |

### Dizayn çərçivəsində (k təsiri çıxılmaqla, hər iki dataset 3300 m)

| Lay | Hausdorff m | Sym. diff m² | Qalıq səbəbi |
|---|---|---|---|
| Approach 33 | **0.24** | 156 | — |
| Take-off 33 | **0.20** | 127 | — |
| Approach 15 | 13.78 | 3 477 | RWY 15 IH kəsim xətti referensdə 1.5° maili çəkilib |
| Take-off 15 | 10.44 | 6 915 | eyni + uzaq uc küncü −15264.87 (digəri −15254.46) |
| Inner Horizontal | 13.78 | 56 233 | referens qövsü 3996.9–4000.0 m (±55°-də 3.1 m içəri) + RWY 15 maili kəsim |
| Conical | 22.51 | 141 529 | eyni qövs + düz xarici kənarda 6022.5 m əl ilə təpə |
| Transitional | 37.88 | 6 079 | sağ/SE künc əl ilə 455.15 / 460.62 (sol tərəf dəqiq 455) |

## 6. Qalan fərqlər və səbəbləri

1. **k = 0.997023 oxboyu sıxılma** (ən böyük qalıq, 44.65 m). Sistem standart
   ölçülərini metrlə tətbiq edir; ölçünü statik "fit" etmək tələblərə ziddir.
   Kök səbəb: DB/referensdəki çəkilmiş runway 3290.18 m, AIP 3300 m-dir
   (həmçinin AIP threshold 15 runway ucundan 8.76 m, 33 isə 1.48 m
   kənardadır — generator bunu Approach üçün WARNING kimi bildirir).
   Runway/Strip geometriyası AIP-ə uyğunlaşdırılsa, bu fərq yox olacaq.
2. Referensdəki əl ilə çəkilmə qalıqları (yuxarıdakı cədvəl).
3. Approach komponent sayı (5 vs 3) — yuxarıda izah olunub.

## 7. Diqqət tələb edən qərarlar

* **Təhlükəsizlik baxımından**: referens qaydası iki zonada ciddi aşağı
  envelope-dan daha yüksək səth saxlayır: (a) IH daxilində Approach yan
  zolaqları d = 2310…2550-də (IH-dan 4.8 m-ə qədər yuxarı), (b) IH-dan kənarda
  Conical əvəzinə Approach/Take-off (IH sərhədində 38 m-ə qədər yuxarı). Bu
  generator referensi təkrarlayır; maneə analizində ciddi lower-envelope
  istənirsə, bu ayrıca qərar tələb edir.
* IH artıq Strip və Clearway üzərini əhatə etmir (referensdəki kimi); Strip
  daxilindəki obyektlər OLS ilə deyil, Strip qaydaları ilə yoxlanmalıdır.
* `app/scripts/refresh_ubbl_clearways.py` Clearway-i Strip ucundan **300 m**
  qurur (runway ucundan 360 m). AIP TODA − TORA = 300 m və referens
  Clearway-i runway ucundan 300 m (Strip ucundan 240 m) göstərir. Bu skript
  DB-də işə salınıbsa, Take-off referensdən 60 m kənarda başlayacaq —
  DB-dəki Clearway yoxlanmalıdır.

## 8. Testlər

* `tests/ols_envelope_smoke.py` — profil riyaziyyatı (DB-siz).
* `tests/ols_lankaran_reference_smoke.py` — referens ZIP-dən Strip/Clearway
  ilə müvəqqəti aeroport qurur, generasiya edir və hər lay üçün sahə,
  komponent, Hausdorff, symmetric difference, overlap və boşluğu PostGIS-də
  (EPSG:32639) yoxlayır.
* `tests/ols_generation_smoke.py` — sahə yoxlamaları partition invariantlarına
  (cüt overlap < 0.01 m², IH/Conical zonalarının tam örtülməsi) çevrilib.
* Bütün 14 smoke test keçir.
