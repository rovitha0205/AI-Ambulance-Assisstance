# Camera Analysis Accuracy Guide

Use this checklist to make analysis match the real situation more closely.

## 1) Camera setup (most important)
- Keep the patient centered in the frame (head-to-knee if possible).
- Keep patient occupying at least 25-60% of the frame.
- Avoid strong red objects in foreground.
- Use steady camera (no shaking) for at least 8-10 seconds.

## 2) Lighting setup
- Use neutral white light.
- Avoid very dark scenes and direct glare/overexposure.
- Prefer even illumination on injury area.

## 3) Ensure injury area is visible
- Expose suspected wound area when possible.
- Avoid fully covering injured area with clothing.
- Clean lens before capture.

## 4) Run calibration logs
Set these environment variables before starting app:

```powershell
$env:BLEEDING_CALIBRATION_MODE="1"
$env:BLEEDING_CALIBRATION_INTERVAL="1.0"
python app.py
```

Watch console logs (`[BLEEDING_CAL]`) for:
- `patient_detected=True`
- `patient_coverage` ideally >= `0.15`
- `skin_coverage` ideally >= `0.06`
- `brightness` in a moderate range

If these are poor, fix camera position/lighting first.

## 5) Conservative reliability controls (already supported)
These variables can be tuned if needed:

```powershell
$env:BLEEDING_REQUIRE_PATIENT_DETECTION="1"
$env:BLEEDING_HIGH_SKIN_CONFIDENCE_MIN="3.0"
$env:BLEEDING_HIGH_CONTOUR_CONFIDENCE_MIN="0.9"
$env:BLEEDING_HIGH_CONFIDENCE_MARGIN="0.8"
```

## 6) Interpreting analysis quality in UI
In the Analysis page, check **Input Quality**:
- `High`: camera conditions are good
- `Medium`: usable but needs caution
- `Low`: reposition and relight, then re-capture

Do not trust fine-grained diagnosis if Input Quality is `Low`.

## 7) Best workflow in ambulance
1. Position camera -> center patient.
2. Confirm visible injury area.
3. Hold steady 8-10 sec.
4. Check Input Quality card.
5. If Low/Medium, adjust and re-capture before acting.

This system is triage support, not a final diagnosis.
