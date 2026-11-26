# DentIndices — index reference

This document specifies every index DentIndices computes: the input it expects, the codes and
thresholds it uses, the rules it applies, and the choices made where the sources are silent or
disagree. The numbers themselves live in one machine-readable file,
[`dentindices/data/indices.json`](../dentindices/data/indices.json), which both the Python package
and the web app read; this document explains them.

**Verification levels.** *Primary* means the original publication or manual was read and the rule
transcribed from it. *Secondary* means the original is not openly available in full and the rule was
checked against its abstract and/or independent publications that restate it (the registry names
them in each index's `checked` note). The level of every index is
returned by `dentindices.list_indices()` and shown in the web app.

**Results.** Every function returns an `IndexResult` with `value`, `components` (each part of the
calculation), `category` (interpretation band, where the source gives one), `guidance` (the source's
recommendation for that band, where it gives one), `warnings`, `trace` (each step in plain language)
and `sources`. A value of `None` means the index is undefined for that input (for example DMFT for a
person with no permanent teeth), and such people are left out of group summaries.

**Teeth and sextants.** Teeth use FDI two-digit numbers (`16`, `"16"`, `"1.6"` and `"t16"` are all
accepted). Sextants are S1 = 17–14, S2 = 13–23, S3 = 24–27, S4 = 37–34, S5 = 33–43, S6 = 44–47
(WHO); the BSP names UR, UA, UL, LL, LA, LR and the numbers 1–6 are accepted as aliases. A sextant
value can be given as a list of six values in UR, UA, UL, LL, LA, LR order or as a mapping.

---

## 1. Caries

### 1.1 DMFT and dmft — `dmft_permanent()`, `dmft_primary()`, `caries_experience()`

Sources: WHO *Oral health surveys: basic methods* 5th ed. (2013), section on the dentition status
and the dental caries indices; WHO 4th ed. (1997); Klein, Palmer & Knutson (1938). **Primary.**

Input: a mapping of tooth → WHO 2013 dentition-status code. Permanent teeth use digits, primary teeth
letters:

| Permanent | Primary | Status | Counted as |
|---|---|---|---|
| 0 | A | Sound | present |
| 1 | B | Caries | D / d |
| 2 | C | Filled, with caries | D / d |
| 3 | D | Filled, no caries | F / f |
| 4 | E | Missing due to caries | M / m |
| 5 | — | Missing for any other reason | M only from age 30 |
| 6 | F | Fissure sealant | present, not counted |
| 7 | G | Fixed prosthesis abutment, special crown or veneer/implant | present, not counted |
| 8 | — | Unerupted tooth | excluded |
| 9 | — | Not recorded | excluded |

Rules:

- DMFT = DT + MT + FT on a 32-tooth basis (third molars included, as WHO); `include_third_molars=False`
  restricts to 28 teeth.
- The M component counts code 4 only below age 30 and codes 4 and 5 from age 30 (WHO 2013, which notes
  that above 30 it can be difficult to tell caries from periodontal reasons for loss). If the age is
  unknown and a code 5 is present, code 5 is not counted and a warning is raised. `m_rule="caries_only"`
  or `"any_reason"` overrides this.
- Each tooth is counted in one component only (a filled tooth with caries, code 2, is D).
- Letter codes can be keyed by the primary tooth (`55`) or by the space it shares with its permanent
  successor (`15`), as on the WHO form, where both use the same box. If a permanent and a primary tooth
  are both coded in one space, the permanent tooth is recorded and the primary tooth ignored, as WHO
  instructs, with a warning; code 8 (unerupted) in a space occupied by a primary tooth is ignored, also
  with a warning.
- The value is `None` when no permanent (or, for dmft, no primary) teeth are recorded.
- Components also report teeth present, sealed teeth, unerupted and not-recorded teeth, whether the
  person is caries-free (DMFT = 0) and whether untreated caries is present (DT > 0).

`caries_experience()` returns both dentitions from one mapping, for mixed dentitions.

### 1.2 DMFS and dmfs — `dmfs_permanent()`, `dmfs_primary()`

Sources: WHO 2013 (Annex 3 assessment form, surface codes); Broadbent & Thomson (2005). **Primary.**

Input: a mapping of tooth → surfaces → code, or tooth → code for whole-tooth codes. Posterior teeth have
five surfaces (O, M, B, D, L) and anterior teeth four (M, B, D, L). A missing tooth (code 4, or 5 from
age 30; E for primary teeth) counts **all** its surfaces as M (5 posterior, 4 anterior), as in WHO's
analysis. Unerupted teeth and teeth coded 8 or 9 are excluded. Broadbent & Thomson (2005) discuss why
this convention inflates the M component; it is kept for comparability with WHO surveys.

### 1.3 PUFA/pufa — `pufa()`

Source: Monse et al. (2010). **Secondary.**

One letter per tooth: P (pulpal involvement), U (ulceration from dislocated fragments), F (fistula),
A (abscess); upper case for permanent and lower case for primary teeth (the case is taken from the
tooth number). The index is the number of affected teeth; P/U/F/A counts are reported separately. If
the number of decayed teeth is given (`decayed_teeth=D+d`), the share of decayed teeth that progressed
to PUFA is reported.

### 1.4 Significant Caries Index — `sic()`

Sources: Bratthall (2000); Nishi et al. (2002). **Secondary** (Bratthall's abstract and Nishi et al.).

The mean DMFT of the one third of the group with the highest DMFT. People are sorted from highest to
lowest. When the group size is not divisible by three, Bratthall's description does not say how to
round the third; DentIndices uses the nearest whole number by default (halves up) and offers
`rounding="ceil"`, `"floor"` or `"fractional"` (the person at the boundary counts with a partial
weight). `fraction=0.1` gives the SiC10 variant. A warning is raised when the top third contains
caries-free people, because SiC is then less informative and SaC is preferable.

### 1.5 Specific affected Caries Index — `sac()`

Source: Schmoeckel et al. (2019). **Secondary** (abstract). The mean DMFT among people with DMFT > 0,
for populations with low caries prevalence. The test suite reproduces the figures given in the
abstract (prevalence 21.2%, SaC 2.1).

### 1.6 Care Index and Restorative Index — `care_index()`, `restorative_index()`, `component_percentages()`

Sources: Walsh (1970); Jackson (1973); Gupta et al. (2017) scoping review. **Secondary.**

For a group, components are summed first: Care Index = ΣF / ΣDMF × 100; Restorative Index =
ΣF / (ΣD + ΣF) × 100. `component_percentages()` gives the shares of D, M and F in total DMF. All three
accept DMFT or dmft result rows (or `IndexResult` objects).

### 1.7 WHO caries-experience levels — `who_caries_level()`

Source: WHO 2013. **Primary.** The bands as WHO prints them:

| 12-year-olds | Level | 35–44-year-olds | Level |
|---|---|---|---|
| < 1.2 | Very low | < 5.0 | Very low |
| 1.2–2.6 | Low | 5.0–8.9 | Low |
| 2.7–4.4 | Moderate | 9.0–13.9 | Moderate |
| 4.5–6.5 | High | > 13.9 | High |
| > 6.5 | Very high | | |

The unrounded mean is compared with these limits, so 1.15 is very low and 6.52 very high. Only a
mean that falls in a gap between two printed bands (such as 2.65, between 2.6 and 2.7) is read to
one decimal, rounding half up (2.65 → 2.7, moderate).

---

## 2. Periodontal screening

### 2.1 Basic Periodontal Examination — `bpe()`, `bpe_from_teeth()`

Source: British Society of Periodontology (2019). **Primary.**

| Code | Finding | BSP guidance (abridged; full text in the result) |
|---|---|---|
| 0 | Pockets < 3.5 mm, no calculus or overhangs, no bleeding | No need for periodontal treatment |
| 1 | As 0, with bleeding on probing | Oral hygiene instruction (OHI) |
| 2 | Calculus or overhangs | As 1, plus removal of plaque-retentive factors |
| 3 | Probing depth 3.5–5.5 mm | As 2, plus root-surface debridement if required; 6-point chart in that sextant after initial therapy |
| 4 | Probing depth > 5.5 mm | OHI and RSD; assess need for complex treatment; 6-point chart of the entire dentition |
| * | Furcation involvement | Treat according to the code; consider referral |

Input: one code per sextant; append `*` for furcation involvement; `-` or blank marks a sextant with
fewer than two teeth (excluded). The result is the highest code (with `*` if any sextant has
furcation), the list of code 3 and code 4 sextants, whether a full chart is indicated and for which
sextants radiographs should be available. `bpe_from_teeth()` takes a code per tooth and applies the
sextant rules: at least two teeth per sextant, and third molars only when the first or second molar of
that sextant is missing.

### 2.2 Simplified BPE for under-18s — `sbpe()`

Source: BSP/BSPD guidelines for children and adolescents (Clerehugh & Kindelan, updated 2021).
**Primary.** Six index teeth (16, 11, 26, 36, 31, 46). Ages 7–11 use codes 0–2 only; ages 12–17 use the
full range including 3, 4 and `*`. Ages outside 7–17 raise an error (use `bpe()` from 18).

### 2.3 CPITN / CPI (1982, 1997) — `cpitn()`

Sources: Ainamo et al. (1982); WHO (1997). **Secondary.**

One code per sextant (0 healthy, 1 bleeding, 2 calculus, 3 pocket 4–5 mm, 4 pocket ≥ 6 mm; X excluded
sextant; 9 not recorded). Treatment need: 0 → TN0, 1 → TN1, 2 and 3 → TN2, 4 → TN3. Index teeth from age
20: 17/16, 11, 26/27, 36/37, 31, 46/47; under 20: 16, 11, 26, 36, 31, 46. Pockets are not recorded under
age 15: codes 3 and 4 given for a child under 15 raise a warning. The result also counts sextants
scored and sextants with codes 3 and 4. A sextant with fewer than two functional teeth is coded X, as
WHO (1997) instructs; the 1982 rule of adding a single remaining tooth to the adjacent sextant is not
used.

### 2.4 CPI modified (WHO 2013) — `cpi_modified()`

Source: WHO 2013. **Primary.** Gingival bleeding (0 absent, 1 present, 9 excluded, X not present) and
pocket scores (0, 1 = 4–5 mm, 2 = ≥ 6 mm, 9, X) for all teeth present. Reported: number and percentage of
teeth with bleeding, teeth with pockets 4–5 mm and ≥ 6 mm, and the highest pocket score. Pocket scores
given for a child under 15 are ignored with a warning.

### 2.5 Loss of attachment (WHO 2013) — `loss_of_attachment()`

Source: WHO 2013. **Primary.** One code per sextant (0 = 0–3 mm, 1 = 4–5 mm, 2 = 6–8 mm, 3 = 9–11 mm,
4 = ≥ 12 mm; X excluded; 9 not recorded) on the index teeth 17/16, 11, 26/27, 36/37, 31, 46/47. The
result is the highest code with counts of sextants per code. Not recorded under age 15 (an age under 15
raises an error).

---

## 3. Oral hygiene and gingival indices

### 3.1 Plaque Index — `plaque_index()`

Sources: Silness & Löe (1964); Löe (1967); interpretation bands from secondary literature (D'Elia et
al. 2023). **Secondary** (the bands only).

Scores 0–3 on four areas (distofacial, facial, mesiofacial, lingual) of each tooth examined, by default
the Ramfjord teeth 16, 21, 24, 36, 41, 44. Tooth score = mean of its areas; person score = mean of the
tooth scores. The bands (0 excellent, 0.1–0.9 good, 1.0–1.9 fair, 2.0–3.0 poor) are a textbook
convention, not part of the original index, and the result says so.

### 3.2 Gingival Index — `gingival_index()`

Sources: Löe & Silness (1963); Löe (1967). **Secondary.** Same layout as the Plaque Index, with scores
0 normal, 1 mild, 2 moderate (bleeding on probing), 3 severe (spontaneous bleeding). Bands from Löe
(1967): 0.1–1.0 mild, 1.1–2.0 moderate, 2.1–3.0 severe gingivitis.

### 3.3 Plaque Control Record — `plaque_control_record()`

Sources: O'Leary, Drake & Naylor (1972); D'Elia et al. (2023). **Secondary.** Plaque present or absent on
four surfaces (M, D, B, L) of every tooth present; the score is the percentage of surfaces with plaque.
Reference points in the result: 10% or less (O'Leary's commonly cited target) and about 20–25% (an
often-cited threshold for maintaining periodontal health).

### 3.4 Simplified Oral Hygiene Index — `ohi_s()`

Source: Greene & Vermillion (1964). **Primary.**

Debris (DI-S) and calculus (CI-S), 0–3 each, on six surfaces: buccal of 16 and 26, labial of 11 and 31,
lingual of 36 and 46. If a first molar is missing, not fully erupted or crowned, the second (then the
third) molar is scored; 21 and 41 replace 11 and 31. Give the scores keyed by the tooth actually
examined (for example `17` instead of `16`); substitutions are listed in the trace. At least two
surfaces are required. DI-S and CI-S
are means over the surfaces scored; OHI-S = DI-S + CI-S (0–6). The interpretation bands (good, fair,
poor) are a textbook convention, reported with a warning.

---

## 4. Tooth wear — `bewe()`, `bewe_from_teeth()`

Sources: Bartlett, Ganss & Lussi (2008); Aránguiz et al. (2020). **Primary.**

Each surface is scored 0 (no erosive wear), 1 (initial loss of surface texture), 2 (distinct defect,
hard-tissue loss < 50% of the surface) or 3 (hard-tissue loss ≥ 50%). The highest score in each sextant
is recorded; the cumulative score (0–18) gives the risk level and management:

| Sum | Risk level | Repeat |
|---|---|---|
| ≤ 2 | None | every 3 years |
| 3–8 | Low | every 2 years |
| 9–13 | Medium | every 6–12 months |
| ≥ 14 | High | every 6–12 months |

The authors state that the cut-offs are based on experience; the result carries that caveat.
`bewe_from_teeth()` takes scores per tooth: third molars replace a missing second molar, and a sextant
with a single remaining tooth has that tooth scored with the adjacent sextant (Aránguiz et al. 2020) —
a posterior tooth with the anterior sextant of the same arch, an anterior tooth with the posterior
sextant on its side — provided that sextant has at least two teeth of its own; otherwise it is scored
in place (see discrepancies).

---

## 5. Fluorosis

### 5.1 Dean's index — `dean_index()`

Sources: WHO 2013; Dean (1934, 1942). **Primary.** WHO 2013 codes: 0 normal, 1 questionable, 2 very
mild, 3 mild, 4 moderate, 5 severe; 8 excluded, 9 not recorded. The person's score is based on the two
most affected teeth: if they differ, the less affected of the two is recorded. `scale="dean"` accepts
Dean's original weights (0, 0.5, 1, 2, 3, 4) instead of WHO codes.

### 5.2 Community Fluorosis Index — `community_fluorosis_index()`

Sources: Dean (1942); WHO 2013. **Secondary.** CFI = Σ(weight × people) / people, with weights 0, 0.5,
1, 2, 3, 4. Public-health significance (each band includes its upper end point): up to 0.4 negative, up to 0.6
borderline, up to 1.0 slight, up to 2.0 medium, up to 3.0 marked, up to 4.0 very marked. A CFI above 0.6 indicates a public-health problem.

---

## 6. Occlusion — `dai()`

Sources: Cons, Jenny & Kohout (1986); Jenny & Cons (1996); WHO (1997). **Primary.**

DAI = 6 × missing visible teeth + crowding + spacing + 3 × diastema + largest maxillary anterior
irregularity + largest mandibular anterior irregularity + 2 × anterior maxillary overjet + 4 × anterior
mandibular overjet + 4 × vertical anterior openbite + 3 × antero-posterior molar relation + 13.

| DAI | Severity | Treatment |
|---|---|---|
| ≤ 25 | No abnormality or minor malocclusion | No or slight need |
| 26–30 | Definite malocclusion | Elective |
| 31–35 | Severe malocclusion | Highly desirable |
| ≥ 36 | Very severe or handicapping malocclusion | Mandatory |

Crowding and spacing are the number of crowded or spaced incisal segments (0–2); the molar relation is
0 normal, 1 half cusp, 2 full cusp; measurements are in whole millimetres as WHO records them.

---

## 7. Periodontitis case definitions

All three take a periodontal chart built with `perio_chart()`: probing depth (PD), clinical
attachment level (CAL) and bleeding on probing (BOP) per site, for six sites per tooth — MB, B, DB
(buccal) and ML, L, DL (lingual/palatal). Charts can be given as a nested mapping
(`{16: {"pd": {...}, "cal": {...}, "bop": {...}}}`) or as long-format rows (`id, tooth, site, pd, cal,
bop`). Third molars are excluded, as both definitions require.

### 7.1 CDC/AAP surveillance case definitions — `cdc_aap()`

Sources: Page & Eke (2007); Eke et al. (2012). **Primary.** Interproximal sites only (MB, DB, ML, DL):

| Case | Definition |
|---|---|
| Severe | ≥ 2 interproximal sites with CAL ≥ 6 mm (not on the same tooth) **and** ≥ 1 interproximal site with PD ≥ 5 mm |
| Moderate | ≥ 2 interproximal sites with CAL ≥ 4 mm (not on the same tooth) **or** ≥ 2 interproximal sites with PD ≥ 5 mm (not on the same tooth) |
| Mild | ≥ 2 interproximal sites with CAL ≥ 3 mm **and** ≥ 2 interproximal sites with PD ≥ 4 mm (not on the same tooth) **or** one site with PD ≥ 5 mm |
| No periodontitis | none of the above |

People with no natural teeth are *edentulous*; fewer than two teeth with interproximal CAL are
*non-classified*. Two details of the mild definition are not spelled out, and both have options:

- Whether the two CAL ≥ 3 mm sites must be on different teeth. By default they must, as for moderate
  and severe; `mild_cal_distinct_teeth=False` follows the literal wording and gives a slightly higher
  prevalence (compare with published estimates using the same reading).
- Whether "one site with PD ≥ 5 mm" must be interproximal. By default it must, like every other
  criterion; `mild_pd5_any_site=True` also counts buccal and lingual sites.

### 7.2 ACES — the 2018 classification for survey data — `aces()`

Sources: Holtfreter et al. (2024) for the framework; Tonetti, Greenwell & Kornman (2018), Papapanou
et al. (2018) and Chapple et al. (2018) for the classification; grading criteria as tabulated in Sanz
et al. (2020). **Primary.**

**Case.** A person is a periodontitis case if interdental CAL ≥ 1 mm is present at ≥ 2 non-adjacent
teeth, **or** buccal/oral CAL ≥ 3 mm with PD > 3 mm is present at ≥ 2 teeth. A person who is not a
case is *non-classified* if fewer than two non-adjacent teeth have interdental CAL **or** fewer than
two teeth have buccal/oral CAL and PD (as restated by Tay et al. 2025); otherwise the person is
classified by bleeding on probing: < 10% of sites *periodontal health*, 10–30% *localized gingivitis*,
> 30% *generalized gingivitis* (Chapple et al. 2018). Without bleeding data the result is "health or
gingivitis".

**Stage.** The initial stage comes from the maximum interdental CAL: 1–2 mm stage I, 3–4 mm stage II,
≥ 5 mm stage III. It is then modified:

- *Completed surveys* (ACES Figure 2): stage II becomes III with complexity (PD ≥ 6 mm at ≥ 2
  non-adjacent teeth, disregarding distal sites of second molars; furcation involvement class II/III;
  vertical bone loss ≥ 3 mm). Stage III becomes IV when fewer than 10 opposing pairs of natural teeth
  remain. Tooth loss due to periodontitis is not used.
- *Planned surveys* (ACES Figure 3, `survey="planned"`): teeth lost to periodontitis (0, 1–4, ≥ 5),
  mobility ≥ degree 2 at ≥ 2 teeth and bite collapse, drifting or flaring are also used. Losing 1–4
  teeth raises stage I or II to III and losing 5 or more gives stage IV; whenever stage III is
  reached, the stage IV complexity factors (mobility, bite collapse/drifting/flaring, fewer than 10
  opposing pairs) raise it to IV (Tonetti et al. 2018).

Opposing pairs are counted from `teeth_present` when it is given, otherwise from the charted teeth.
**For partial-mouth recordings always give `teeth_present`** (every natural tooth present):
otherwise the uncharted teeth look missing and the fewer-than-10-pairs rule can wrongly raise the
stage to IV. The result warns whenever this rule alone raised the stage to IV without
`teeth_present`. In survey files, give a `teeth_present` column (one list per person);
`batch_perio()` passes ACES options such as `survey="planned"` to everyone and CDC/AAP options through
`cdc_options`.

**Extent.** The share of teeth (with interdental CAL recorded) whose maximum interdental CAL reaches the
lower bound of the band that set the initial stage: < 30% *localized*, ≥ 30% *generalized*. When all
affected teeth are incisors or first molars a warning notes a possible molar-incisor pattern.

**Grade.** From percentage bone loss / age at the worst tooth (`bone_loss_percent`, or, with
`root_length_mm`, the worst interdental CAL as a percentage of the root length): < 0.25 grade A, 0.25–1.0 grade B, > 1.0 grade C. Without this evidence grade B
is assumed and flagged. Modifiers can only raise the grade: smoking < 10 cigarettes per day → at least
B, ≥ 10 → C; diabetes with HbA1c < 7.0% → at least B, ≥ 7.0% → C.

### 7.3 Continuous measures — `perio_summary()`

Sources: Holtfreter et al. (2015, 2024). **Primary.** Teeth and sites examined, mean and maximum PD
and CAL, percentage of sites with PD ≥ 4 and ≥ 6 mm and with CAL ≥ 3 and ≥ 5 mm, and percentage of
sites with bleeding — the continuous measures recommended for reporting alongside any case definition.

---

## 8. Population summaries — `summarize()`, `summary_table()`

For a list of values (or result rows): n, mean, SD, SE, a t-based confidence interval for the mean,
median, minimum, maximum, the number and percentage of values above zero (prevalence) with a Wilson
confidence interval, and — in `summary_table()` — SiC and SaC per group and for the whole sample.
Undefined values (`None`) are skipped. With `weights`, weighted point estimates are added; standard
errors for complex survey designs need survey software.

---

## 9. Where sources are silent or disagree

Every decision below is also recorded, with its sources, in the `discrepancies` section of
[`indices.json`](../dentindices/data/indices.json).

| Index | Issue | Decision |
|---|---|---|
| DAI | WHO 1997 prints the lowest band as "< 25" while the next starts at 26, leaving 25 unassigned | ≤ 25, as in Jenny & Cons (1996) |
| CDC/AAP | In the mild definition, "not on same tooth" follows the pocket-depth clause, so it is unclear whether the two CAL sites must also be on different teeth | Different teeth by default, as for moderate and severe; `mild_cal_distinct_teeth=False` for the looser reading |
| SiC | Rounding of one third when n is not divisible by 3 | Nearest whole number; ceil, floor and fractional available |
| CFI | Published public-health bands share their end points (0.0–0.4, 0.4–0.6, …) and some textbooks print other limits | Each band includes its upper end point (0.4 negative, 0.6 borderline), consistent with "above 0.6 is a public-health problem" |
| PlI, GI | Secondary sources list the Ramfjord teeth as 16, 21, 24, 36, 41, 44 or as 16, 12, 24, 36, 32, 44 | Any teeth are accepted; the preset is 16, 21, 24, 36, 41, 44 (D'Elia 2023). Report the teeth you used |
| BEWE | Aránguiz 2020 adds a single remaining tooth to "the adjacent sextant" without naming it | Posterior → anterior sextant of the same arch; anterior → posterior sextant on the same side (only into a sextant with ≥ 2 teeth) |
| ACES | Interdental CAL 1–2 mm with ≥ 5 teeth lost (planned survey) is not covered by Figure 3 | Stage IV (Tonetti 2018 tooth-loss criterion), with a warning |
| ACES | "At the stage-defining severity level" is not specified for extent | Lower bound of the band that set the initial stage (1, 3 or 5 mm) |
| ACES | "Non-adjacent" across gaps (e.g. 14 and 16 when 15 is missing) | By arch position: 14 and 16 are non-adjacent; 11–21 and 31–41 are adjacent |
| ACES | A case met through the buccal/oral criterion with interdental CAL < 1 mm | Stage I, with a warning |
| DMFT | M rule needs age; third molars | Age used when given; code 5 not counted without age (warning); third molars included by default |
| WHO caries levels | Strict outer limits (< 1.2, > 6.5) but one-decimal inner bands leave gaps (2.6–2.7 …) | Unrounded mean against the printed limits; only means in a gap are read to one decimal |
| CDC/AAP | "One site with PD ≥ 5 mm" in the mild definition does not repeat "interproximal" | Interproximal by default; `mild_pd5_any_site=True` for any site |
| CPITN | 1982 added a single remaining tooth to the adjacent sextant; WHO 1997 codes such sextants X | WHO 1997 rule |
| ACES | Restatements of Figure 3 differ on applying stage IV complexity after stage III is reached through tooth loss | Applied whenever stage III is reached (Tonetti 2018) |
| ACES | Non-classified: "fewer than two non-adjacent teeth with CAL **or** fewer than two teeth with buccal/oral CAL and PD" (Tay 2025) | Applied only to people who meet no case criterion |
| ACES | Relative CAL for grading with root lengths | Worst interdental CAL only, so buccal recession does not raise the grade |

---

## References

Full references with DOIs are in the [README](../README.md#references--prior-work), and every result's
`references()` method returns the ones for that index.
