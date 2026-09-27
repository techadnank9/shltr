# Sheltr capture, iPhone

A small native app that does one thing the browser cannot: use the **depth sensor**. It runs
RoomPlan's guided scan, tells the survivor which wall still needs a second look, records the walk,
and uploads it to the same `POST /api/cases` the web pages use. **No server change was needed.**

Everything after the upload — the 3D room, the damage, the claim — is the existing web front end,
opened in a Safari view. This app is the capture step, not a second copy of the product.

## Build it

```bash
brew install xcodegen          # once
cd apps/ios && xcodegen generate
open ShltrCapture.xcodeproj
```

`ShltrCapture.xcodeproj` is generated and git-ignored, so two agents never conflict over Xcode's XML.

Building for a device needs your Apple team: set it in **Signing & Capabilities**, or put it in
`DEVELOPMENT_TEAM` in `project.yml`. To check it only compiles, no signing required:

```bash
xcodebuild -project ShltrCapture.xcodeproj -scheme ShltrCapture -destination 'generic/platform=iOS' CODE_SIGNING_ALLOWED=NO build
```

## Run it

Needs a **LiDAR** iPhone — an iPhone 12 Pro or later Pro, or a 2020-or-later iPad Pro. The
simulator has no depth sensor and cannot scan; the app says so and points at the web recorder
instead, which works on any phone.

It ships pointing at the live control plane. To aim it at a laptop, set `SHLTR_BASE` in the
scheme's environment, for example `http://192.168.1.20:8000`.

## How it works

| File | What it does |
|---|---|
| `CaptureController.swift` | Runs the walk: RoomPlan's session, the coverage engine and the recorder, all off one ARSession |
| `CoverageEngine.swift` | Decides when a wall has been seen properly — two viewpoints at least 1 m apart, within 5 m, under 60° off its normal |
| `WalkthroughRecorder.swift` | Writes `walkthrough.mp4` from RoomPlan's own frames at 15 fps, dropping to 10 when the phone gets hot |
| `UploadClient.swift` | Multipart `POST /api/cases`, fields `file` and `title` |
| `RootView.swift` | The screens: intro, scan, review, send |

Two rules carried over from the web recorder, and they matter: **never show a percentage, never
show the word confidence**, and **Done always works** however little has been covered. Someone
standing in a flooded house is not doing a survey.

## Not done yet

- **Nothing has run on a physical phone.** It compiles clean for arm64; the scan itself is
  unverified. Walking a real room is the next step.
- The walk uploads video only. `CapturedRoom` — RoomPlan's actual walls, doors and windows, which
  are what an aid form asks for — is computed and then thrown away. Sending it needs a second
  artifact on `POST /api/cases`, which is a control-plane change.
- Coverage counts walls only, not floors or objects.
