# KTP Tester

KTP Tester is a Python tool for checking KTP student projects.

## Features
- Fetches projects from GitHub 
- Stores projects locally in a permanent or temporary directory
- Sets up a new virtual Python environment and installs the requirements from requirements.txt
- Runs main.py to evaluate project
- Removes the virtual environment and temporary directory

## Installation
```bash
git clone https://github.com/CorSteging/KTPtester.git
cd KTPtester
pip install -r requirements.txt
```

## Run tool
```bash
python KTPtester.py
```
Then enter the GitHub project link (either latest branch or commit)

## Requirements
Student project must contain a main.py and requirement.py.
