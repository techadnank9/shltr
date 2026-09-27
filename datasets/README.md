# Datasets

Real photos for testing the photo sandbox. The images themselves are not in git; `fetch.py` downloads them into `test-photos/` (which git ignores).

```
python datasets/fetch.py        # 5 images into test-photos/fema/, about 2 MB total
python datasets/drone/fetch.py  # 16 drone photos into test-photos/drone/harvey-fort-bend-tx/, about 7 MB
```

## fema-interiors

Five photos of real flood-damaged home interiors, taken by FEMA staff photographers and published on Wikimedia Commons. `fema-interiors/manifest.json` lists, for each one: the Commons title and page URL, the original file URL and size, the 1920 px download URL (Commons serves thumbnails in fixed size steps; 1920 px is the step nearest 1600) and size, the licence, the photographer and the Commons description.

| Name | Place, date | Photographer | Shows |
|---|---|---|---|
| `liberty-ky` | Liberty, KY, June 2010 | Liz Roll / FEMA | Room with the flood water line on the wall, open ceiling joists |
| `acy-la` | Acy, LA, Aug 2016 | J.T. Blatty / FEMA | Open-plan living room with the lower drywall cut out |
| `belfry-ky` | Belfry, KY, June 2009 | Rob Melendez / FEMA | Room stripped to the studs, debris on the floor |
| `ponce-pr` | Ponce, Puerto Rico, Oct 2008 | Andrea Booher / FEMA | Living room with a wet floor and water-stained ceiling |
| `hanover-wv` | Hanover, WV, May 2009 | Louis Sohn / FEMA | Kitchen wall with drywall removed |

All five were checked by eye to be indoor rooms. Candidates that turned out to be outdoor shots (FEMA 35583, 25261, 21401, 41443) were left out.

## drone

Sixteen real drone photos of one flooded subdivision after Hurricane Harvey (2017), from the FloodNet dataset, licence CDLA-Permissive-1.0 (credit line required). See [drone/README.md](drone/README.md) for provenance, the credit line to show in the app, and why FloodNet was chosen over the other sources.

## Rights (fema-interiors)

These are works of the US federal government (FEMA photographers taking photos as part of their official duties), so they are in the **public domain** in the United States (17 U.S.C. § 105). Wikimedia Commons marks each one `Public domain`, which `manifest.json` records from the Commons API (`extmetadata.LicenseShortName`). We credit FEMA and the photographer anyway, as above.

People appear in some photos (`ponce-pr`, `hanover-wv`). Public domain covers copyright, not personality rights, so use them for testing and don't put them in marketing material.
