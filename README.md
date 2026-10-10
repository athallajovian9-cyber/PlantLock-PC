# PlantLock (PC Edition) 🌱

**Social media lock that only opens when you actually plant trees.** Windows
desktop edition — real CLIP vision decides if you're planting.

## Flow
1. **Start Planting** → UAC prompt (locks need admin) → camera opens
2. **CLIP ViT-B/32 zero-shot** scores your live camera every second:
   `planting prompt vs not-planting prompts`, no frames leave your PC
3. **Not planting → the number does not move.** Planting → progress grows
   (10 planting-seconds = 1 tree)
4. **Minimum 2 trees → hosts-file lock released, social media unlocked**

## What it locks
While planting, these are redirected to `0.0.0.0` via the hosts file
(marked `# <PlantLock BEGIN/END>` block — always reversible):
instagram · facebook · x/twitter · tiktok · reddit · threads

Close the app and the lock stays until 2 trees. That's the point.

## Run
```
START_PLANT.bat        # checks/installs deps, launches GUI
```
First run downloads CLIP (~600 MB once, from Hugging Face, free).

## Stack
Python · PyTorch CPU · transformers (CLIP ViT-B/32) · OpenCV · customtkinter

## Editions
- **This** — Windows PC: CLIP zero-shot vision + system-wide hosts lock
- **PlantLock (Android)** — phone APK: on-device motion+greenery heuristic,
  focus session (see github.com/athallajovian9-cyber/PlantLock)
