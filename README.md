# Bullseye

> *See Every Shot. Hit Every Target.*

![Python](https://img.shields.io/badge/Python-3776AB.svg?style=flat-square&logo=Python&logoColor=white)

## Overview

Bullseye is a PyQt6 desktop application for ballistic trajectory visualization. It renders a dynamic targeting canvas that models projectile paths in real time, providing a clean graphical interface for trajectory analysis and aiming adjustment.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Contributing](#contributing)
- [License](#license)

---

## Features

|      | Component         | Details                                                                                                                                                                                                                                          |
| :--- | :---------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| ⚙️  | **Architecture**  | <ul><li>Desktop application built with **Python** + **PyQt6**</li><li>GUI-driven, event-based architecture typical of Qt applications</li><li>Single-process, client-side only — no server component detected</li></ul>                          |
| 🔩 | **Code Quality**  | <ul><li>Python source files (`.py`) as primary codebase</li><li>No linter config files detected (e.g., no `.flake8`, `pyproject.toml`, or `.pylintrc`)</li><li>No evidence of type annotations or static analysis tooling</li></ul>              |
| 📄 | **Documentation** | <ul><li>No dedicated docs directory or framework detected (e.g., no Sphinx, MkDocs)</li><li>`license` file present — project has defined legal terms</li><li>`requirements.txt` serves as implicit dependency documentation</li></ul>            |
| 🔌 | **Integrations**  | <ul><li>**PyQt6** — primary UI framework integration</li><li>Package installation via `pip` from `requirements.txt`</li><li>No external API, database, or cloud service integrations detected</li></ul>                                          |
| 🧩 | **Modularity**    | <ul><li>Python's module system used for code organization (`.py` files)</li><li>Qt's signal/slot mechanism enables decoupled component communication</li><li>Extent of internal module separation unclear without full source tree</li></ul>      |
| ⚡️  | **Performance**   | <ul><li>PyQt6 wraps native **Qt6 C++ libraries** — rendering performance is hardware-accelerated</li><li>Python GIL may limit CPU-bound concurrency</li><li>No async framework (e.g., `asyncio`, `qasync`) detected</li></ul>                    |
| 🛡️ | **Security**      | <ul><li>Desktop-only scope reduces network attack surface</li><li>No secrets management or auth layer detected</li><li>Dependencies pinned via `requirements.txt` — version locking helps prevent supply chain drift</li></ul>                    |

---

## Project Structure

```
└── Bullseye/
    ├── bullseye.py
    ├── LICENSE
    ├── README.md
    └── requirements.txt
```

---

## Getting Started

### Prerequisites

- Python 3.10+ / Node.js 18+ *(depending on the stack above)*

### Installation

```sh
git clone "https://github.com/IlluzyonistCode/Bullseye
cd Bullseye"
pip install -r requirements.txt
```

### Usage

```sh
python main.py
```

---

## Contributing

- [Report Issues](https://github.com/IlluzyonistCode/Bullseye/issues)
- [Submit Pull Requests](https://github.com/IlluzyonistCode/Bullseye/pulls)
- [Discussions](https://github.com/IlluzyonistCode/Bullseye/discussions)

---

## License

Distributed under the [AGPL-3.0](LICENSE) license.
