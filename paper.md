---
title: 'DentIndices: open, tested oral-health epidemiology indices with cited rules'
tags:
  - Python
  - JavaScript
  - dental public health
  - oral epidemiology
  - dental caries
  - periodontitis
  - survey methods
authors:
  - name: Hossein Boustani Hezarani
    orcid: 0009-0007-8481-0498
    affiliation: 1
affiliations:
  - name: Independent researcher, Ankara, Türkiye
    index: 1
date: 23 November 2026
bibliography: paper.bib
---

# Summary

Oral-health surveys, trials and clinical audits describe populations with a small set of indices:
caries experience (DMFT and its relatives), periodontal screening codes, plaque and gingival scores,
erosive tooth wear, dental fluorosis, malocclusion, and case definitions of periodontitis.
DentIndices is a dependency-free Python package, command-line tool and in-browser application that
computes 26 of these indices — DMFT/DMFS and dmft/dmfs with World Health Organization (WHO) 2013
coding [@who2013], the Significant Caries Index [@bratthall2000], the Specific affected Caries Index
[@schmoeckel2019], care and restorative indices [@walsh1970; @jackson1973], PUFA [@monse2010], the
Basic Periodontal Examination and its simplified version for under-18s [@bsp2019; @bsp2021], CPITN
[@ainamo1982], the WHO 2013 periodontal indicators, the Plaque and Gingival Index
[@silness1964; @loe1963], the Plaque Control Record [@oleary1972], OHI-S [@greene1964], the Basic
Erosive Wear Examination [@bartlett2008], Dean's index and the Community Fluorosis Index
[@dean1934; @dean1942], the Dental Aesthetic Index [@cons1986; @jenny1996], and the CDC/AAP
[@eke2012] and ACES [@holtfreter2024] periodontitis case definitions — together with the population
summaries reported alongside them.

# Statement of need

These indices are usually computed in ad-hoc spreadsheets and scripts, and their rules contain
details that are easy to get wrong and rarely reported. WHO 2013 counts a tooth missing for reasons
other than caries only from age 30 and excludes sealants, abutments and unerupted teeth; the
Significant Caries Index requires a rule for sizing one third of a sample that its definition does not
give; and ACES, which applies the 2018 periodontitis classification [@tonetti2018; @papapanou2018] to
survey data, has separate flowcharts for completed and planned surveys and leaves several terms —
the severity level for extent, adjacency across gaps — to interpretation. When each group resolves
these silently, estimates from different studies are not comparable, a problem documented for both
caries [@broadbent2005] and periodontitis [@holtfreter2015; @tay2025].

DentIndices makes these rules explicit and shared. All code tables, thresholds and interpretation
bands are stored in a single machine-readable registry next to the publication each comes from. Each
index carries a verification level — *primary* when the original publication or manual was read,
*secondary* when the original is not openly available in full and the rule was checked against its
abstract and/or independent publications that restate it — and every point where sources are silent or disagree is recorded with the
decision taken, which users can change through options. Every result returns its value, components,
interpretation band, the source's guidance, data warnings, a step-by-step trace of the calculation
and the references to cite, so that a reported index can be audited back to its definition.

The package is aimed at dental public-health researchers analysing survey data (one row per person,
a column per tooth, as on the WHO assessment form), trialists and clinical auditors who need
reproducible scores, and educators teaching the indices. The browser application serves users who do
not program: it processes a whole CSV file on the user's own device, with no upload.

# State of the field

The closest open package is the R package `tooth` [@tooth], which computes DMFT, DMFS, dmft and
dmfs from surface-level examination data, with configurable ICDAS thresholds and publication-ready
odontogram heatmaps. The experimental R package RPerio [@rperio] implemented earlier periodontitis
surveillance case definitions (the CDC working group and the 5th European Workshop). DentIndices is
complementary: it covers the periodontal, hygiene, wear, fluorosis and occlusion indices and current
periodontitis case definitions as well as caries, reads WHO 2013 dentition codes natively, documents
the provenance of every rule in a registry, and runs both in Python and in a browser. We found no
packaged open implementation of ACES. Online calculators exist for
individual indices but rarely cite their rules or process whole surveys.

# Design and quality control

The Python package (Python 3.10 or later, no dependencies) and a JavaScript port read the same
registry. The JavaScript engine is a line-for-line translation so that the web application and the
package give identical answers; the test suite runs 2,100 randomised inputs per run through both
engines and requires identical values, categories, warnings and traces, and also compares batch
processing and survey summaries on the bundled example files. The 261 tests include worked examples
from the sources (for example Schmoeckel's SaC illustration and the DAI regression weights), the
edge cases that distinguish careful implementations — mixed dentition and the WHO same-space rule,
third molars replacing second molars in BEWE and BPE sextants, sextants with too few teeth,
edentulous people, both ACES flowcharts and grade modifiers that can only raise the grade — and
reference values for the statistical functions (Student's *t* quantiles and the Wilson interval).
Example survey files are synthetic and generated with a fixed seed.

Population summaries report the mean with a *t*-based confidence interval, the prevalence of values
above zero with a Wilson interval, and SiC and SaC per group. Weighted point estimates are available;
design-based variance estimation for complex samples is left to dedicated survey software.

# AI usage disclosure

Generative AI (Anthropic Claude) was used to help write the code, tests, documentation and this
paper, under the author's direction. The author defined the scope, checked the index rules against
the cited sources, reviewed the code and outputs, and takes responsibility for the content.

# Acknowledgements

The author thanks the authors of the indices and of the WHO, BSP and ACES documents whose clear
publication of their methods makes open implementations possible.

# References
