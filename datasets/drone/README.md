# Drone flyover set: Hurricane Harvey, one flooded subdivision

Sixteen real drone (UAS) photos of **one flooded residential subdivision in the Houston area after Hurricane Harvey (September 2017)**, for the "drone flyover" mode: each photo is analysed in a sandbox, then the results are rolled up into an area damage report. The images are not in git; `fetch.py` downloads them into `test-photos/drone/harvey-fort-bend-tx/`, which git ignores.

```
python datasets/drone/fetch.py     # 16 images, 1600x1070 JPEG, about 7 MB in total
```

`manifest.json` lists each image's title (split and file name inside FloodNet), source folder URL, the 1600 px download URL, the full-size original URL (4592x3072, about 8 MB), licence, credit, capture date and location, and width and height (downloaded and original).

## What the photos show

Nadir (straight-down) views from low altitude over the same subdivision. They are frames 7300 to 7612 of one numbered FloodNet image sequence, and nearby frames overlap.

- Streets and cul-de-sacs under brown floodwater, with cars standing in it (`floodnet-7305`, `7587`, `7612`).
- Water up to driveways, garages and front doors, and back gardens flooded (`7300`, `7311`, `7320`, `7328`, `7406`, `7575`).
- Backyard pools turned brown with floodwater, and mud lines on roads where the water has pulled back (`7587`).
- A flooded detention basin and a tennis court beside the houses (`7337`, `7370`, `7476`, `7483`).

Roofs are intact: this is flood damage, not wind damage. The vision model should flag flooded roads, flooded buildings (water touching the house) and flooded yards and pools, not roof damage.

Location: FloodNet reports its flights over Fort Bend County, Texas and nearby areas. GPS has been stripped from the files, so we don't know the exact subdivision and should not name one in the app. Date: the original of `7320.jpg` has EXIF `DateTimeOriginal 2017:09:04 16:01:50`, camera `NIKON 1 S2`.

## Licence and attribution

FloodNet is released under the **Community Data License Agreement – Permissive, Version 1.0** (`CDLA-Permissive-1.0`), as stated in the dataset README at https://github.com/BinaLab/FloodNet-Supervised_v1.0. Licence text: https://cdla.dev/permissive-1-0/.

What that licence lets us do and what it asks (section 3):

- We may use and publish the data, including commercially. Showing the photos in a public demo is fine.
- Anyone we give the data to must also get the licence text. The app shows a link to it with the photos.
- We must keep the credit to the data provider.
- If we change the image files (for example, draw boxes onto them) and publish those files, they must say they were changed.
- Results of analysis (our damage labels, counts, the report) carry no obligations.

Attribution line to show in the app, next to the drone photos:

> Drone imagery: FloodNet (Rahnemoonfar et al., 2021, BinaLab/UMBC), Hurricane Harvey 2017. Licence: CDLA-Permissive-1.0 (cdla.dev/permissive-1-0). Overlays added by Shltr.

Paper to cite: M. Rahnemoonfar, T. Chowdhury, A. Sarkar, D. Varshney, M. Yari, R. Murphy, "FloodNet: A High Resolution Aerial Imagery Dataset for Post Flood Scene Understanding", IEEE Access, 2021. https://ieeexplore.ieee.org/document/9460988

Download route: the FloodNet README links a public Google Drive folder. `download_url` is Drive's thumbnail endpoint (`drive.google.com/thumbnail?id=<file>&sz=w1600`), which needs no account. It returned HTTP 500 when we sent many requests in parallel, so `fetch.py` downloads one at a time with retries. If Drive ever blocks it, `original_url` still works (full size, about 8 MB each).

## Why this source

| Source | Licence found | Verdict |
|---|---|---|
| **FloodNet** (Hurricane Harvey UAS, BinaLab) | CDLA-Permissive-1.0 (dataset README) | **Chosen.** Real drone photos, permissive licence that allows public and commercial use, every file downloadable without an account, and a dense run over one flooded subdivision |
| RescueNet (Hurricane Michael UAV, BinaLab) | CC BY-NC-ND 4.0 (dataset README; the GitHub repo's MIT licence covers only the code) | Rejected for the demo: non-commercial and no-derivatives (our overlays would be derivatives). Better wind and roof damage; note as **future** if we get permission |
| NOAA Emergency Response Imagery (storms.ngs.noaa.gov) | US government work, public domain | Not chosen: it is aircraft orthomosaic imagery, not drone photos, served as map tiles or multi-GB archives; making photo-sized frames needs tile stitching. Good **future** source for Hurricane Michael roof damage (Mexico Beach) |
| OpenAerialMap | Usually CC BY 4.0, set per upload | Not chosen: coverage of damaged neighbourhoods is patchy and each upload is a large GeoTIFF; would need checking per image |
| Wikimedia Commons (FEMA, USCG, Army, CAP aerials) | Public domain (US government) | Not chosen: searches found only single aerial shots (for example one USCG view of Mexico Beach), not a set over one neighbourhood |
| OpenDroneMap `odm_data_*` sample sets | Mostly CC0-1.0 (for example aukerman, bellus, seneca, lewis); some GPL-3.0, CC BY-SA 4.0 or unstated | Not disaster imagery (fields, campuses, parks). Useful only to test the 3D pipeline (see below) |

## 3D from this set (not tried)

FloodNet frames are nadir photos taken in sequence, and neighbouring frames (for example 7300 to 7305) cover overlapping ground, so OpenDroneMap may be able to reconstruct them. Two caveats: the files have no GPS, so ODM would produce a model in local coordinates without scale, and we have not measured the overlap. A test would use 20–40 consecutive originals (not the 1600 px thumbnails) from one run, for example 7300–7340.

A known-good overlapping set with a usable licence is OpenDroneMap's `odm_data_aukerman` (CC0-1.0, 77 images, about 500 MB repo) if we just need to show the 3D step working.

Rough runtime for 20–40 images on 4 vCPU / 16 GB with `docker run opendronemap/odm --fast-orthophoto` (or `--pc-quality lowest`): about 10–30 minutes. That estimate is based on community reports of about 19–28 minutes for 28–68 images with `--fast-orthophoto`. It is too slow to run live in the demo, so precompute the result.
