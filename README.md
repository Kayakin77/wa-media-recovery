# WhatsApp Media Recover (2026 Edition) 🚀

This repository provides tools to download and decrypt WhatsApp media files (`.enc`) directly from the Android `msgstore.db` database. This project was updated to ensure compatibility with **Python 3.13** and **Termux** environments.

## 🌟 Why this project?
Many legacy extractors depend on libraries like `curve25519` (Curve Donna), which often face critical compilation errors in modern environments. This project solves these issues by:
- **Native AES-CBC Decryption**: Implemented with `pycryptodome` to avoid obsolete dependencies.
- **Mass Processing**: Automatically processes hundreds of files via a SQL-generated CSV.
- **Header Cleaning**: Automatic JPG padding correction to ensure files are immediately viewable.

## 🛠️ Requirements
Tested on **Termux** and standard Linux environments:

```bash
pkg install sqlite python
pip install pycryptodome requests

