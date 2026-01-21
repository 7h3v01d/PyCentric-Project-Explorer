# PyCentric Project Explorer

️ **LICENSE & USAGE NOTICE — READ FIRST**

This repository is **source-available for private technical evaluation and testing only**.

- ❌ No commercial use  
- ❌ No production use  
- ❌ No academic, institutional, or government use  
- ❌ No research, benchmarking, or publication  
- ❌ No redistribution, sublicensing, or derivative works  
- ❌ No independent development based on this code  

All rights remain exclusively with the author.  
Use of this software constitutes acceptance of the terms defined in **LICENSE.txt**.

---

**PyCentric** is a lightweight, Python-focused file manager and development environment built with PyQt5. It provides a streamlined interface for navigating project directories, editing code with syntax highlighting, managing virtual environments, and executing Python scripts—all within a single application.

## 🚀 Key Features

- Python-Centric File Navigation: Optimized tree-view that filters for common development files (.py, .md, .json, .ini, etc.).
- Built-in Code Editor:
  - Monokai-inspired dark theme.
  - Real-time syntax highlighting for Python via Pygments.
  - Integrated file saving and editing.
- Virtual Environment (venv) Management:
  - Automatic detection of existing venv or .venv folders.
  - One-click creation of new virtual environments.
  - Dependency installation directly from requirements.txt.
- Script Execution & Linting:
  - Run Python scripts directly within the app using the selected virtual environment.
  - Integrated flake8 support for instant code linting and PEP8 checks.
- Multi-threaded Background Search: Search for specific text within files across your entire project without freezing the UI.
- Markdown Preview: Side-by-side live preview for Markdown files using an integrated WebEngine.
- Archive Tools: Quickly Zip or Unzip files and folders through a context-sensitive right-click menu.🛠️ PrerequisitesBefore running PyCentric, ensure you have Python 3.x installed along with the following dependencies:Bashpip install PyQt5 PyQtWebEngine pygments markdown2 flake8

---

## 💻 Installation & Usage
1. Clone the repository:
```Bash
git clone https://github.com/yourusername/pycentric.git
cd pycentric
```
2. Run the application:Bashpython Pyfilemanager3.py
3. Select a Project: Click "Select Project Folder" to load your Python project. PyCentric will automatically look for a virtual environment and update the status bar.

---

## 📂 UI Overview

```text
Component          Description
Left Panel         File system explorer with context menus for file operations (New, Delete, Zip).
Top Right          Code editor with syntax highlighting and file metadata (size, last modified).
Center Right       Toggleable Markdown previewer.
Bottom Right       Output console for script execution, linting results, and error logs.
Search Bar         Real-time content filtering across project files.
```

---

## 🛠️ Built With

- PyQt5 - The GUI framework.
- Pygments - For robust syntax highlighting.
- Markdown2 - For converting Markdown to HTML preview.
- QProcess - For asynchronous script execution.

## Contribution Policy

Feedback, bug reports, and suggestions are welcome.

You may submit:

- Issues
- Design feedback
- Pull requests for review

However:

- Contributions do not grant any license or ownership rights
- The author retains full discretion over acceptance and future use
- Contributors receive no rights to reuse, redistribute, or derive from this code

---

## License
This project is not open-source.

It is licensed under a private evaluation-only license.
See LICENSE.txt for full terms.
