# Changelog

All notable changes to BiGG are recorded here. Each release has a **Data**
section and a **Platform** section.

BiGG follows [Semantic Versioning](https://semver.org): data or feature
additions bump the minor version, fixes bump the patch version, and changes that can break existing use of BiGG bump the major version. Versions below
1.0.0 are pre-releases made before the accompanying paper is formally published.

Release headings must keep the format `## <version> - <YYYY-MM-DD>`, optionally
followed by ` - Pre-release` or highlighted tags; the /changelog page parses them.

## 0.1.0 - 2026-10-28 - Pre-release

Initial public release of BiGG, accompanying our paper in the *Nucleic Acids
Research* Database Issue.

### Data

- New pangenome-scale collections built at BRIGHT:
  [LactoPanGEM](/collections/LactoPanGEM) (2,377 models),
  [Ecoli_panGEMs](/collections/Ecoli_panGEMs) (2,313 models) and
  [iPKB_Clostridiaceae](/collections/iPKB_Clostridiaceae) (97 models)
- All available models from legacy BiGG Models migrated and re-standardized to BiGG IDs

### Platform

- Universal metabolites and reactions that merge previous BiGG identifiers and group charge-state variants, anchored to ChEBI and Rhea
- Taxonomically anchored collections for single-model, multi-strain and pangenome-scale models
- MEMOTE reports and Escher maps for every model, with API v3 and bulk downloads
