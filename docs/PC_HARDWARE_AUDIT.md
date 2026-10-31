# Bikash AI — PC and Development Environment Audit

**Audit date:** 2026-10-31  
**Workspace:** Local Windows development machine; personal paths omitted.

## Workspace and tools

- The folder began empty and had no Git repository or app files. Phase 1 files now live here.
- Node.js v24.22.1, npm v11.19.1, and Git v2.56.0.windows.2 are available.
- Python 3.14.10 was installed per-user after explicit approval. Its bundled pip works. Use the project `.venv`; the Python launcher did not detect the per-user installation during this audit.
- Docker, Ollama, and nvidia-smi were not found on PATH or in common locations. Custom install paths were not exhaustively searched.

## Hardware status

| Item | Result |
| --- | --- |
| Windows edition/version | Unverified |
| CPU and core count | Unknown |
| Installed RAM | Unknown |
| GPU, driver, VRAM | Unknown |
| CUDA/ROCm | Unknown |
| Disk size/free space | Unknown |

CIM/WMI and systeminfo returned “Access denied.” A registry query reported Windows 10 Pro, 21H2, build 22000, an inconsistent combination not treated as reliable OS identification.

## Local model feasibility

Not assessed. Do not choose model sizes or enable Ollama until CPU, RAM, GPU, VRAM, disk, and driver details are verified. The app defaults to no provider and makes no model request.

To complete the hardware check, use Windows Settings → System → About for OS/CPU/RAM and Task Manager → Performance for GPU, GPU memory, and disk capacity/free space.
