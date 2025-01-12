# Groq Chat API Integration

Simple Python script for getting JSON responses from Groq's AI API.


##Working with GIT - Clonning, Branching, Commiting
```bash
cd C:\Users\YourUsername\Desktop\YourNewFolder
git clone https://github.com/GiladShkalim/Intelli-Shop.git
```
1. **Creating a New Branch**
   ```bash
   # Create and switch to a new branch:
   git checkout -b new-feature-branch
   ```

2. **Making Changes**
   Make your desired changes to the project files.

3. **Committing Changes**
   ```bash
   # Stage your changes:
   git add .
   ```
   ```bash
   # Commit your changes:
   git commit -m "Add short detail on waht is being commited here"
   ```
4. **Pushing Changes to the Remote Repository**
   ```bash
   git push -u origin new-feature-branch
   ```


## Quick Start

1. **Setup Environment**
   ```bash
   # Deactivate the current virtual environment:
   deactivate

   # Remove the existing virtual environment:
   rm -rf venv

   # Ensure you have the necessary tools installed:
   sudo apt update
   sudo apt install python3-venv python3-pip

   # Create a new virtual environment using the full path to python3:
   /usr/bin/python3 -m venv venv

   # Activate the new virtual environment:
   source venv/bin/activate

   # Upgrade pip within the virtual environment:
   pip install --upgrade pip

   # Now try installing the requirements again:
   pip install -r requirements.txt
   ```

2. **Add API Key**
   Address to your Groq's Admin user to receive API key.
   Create `.env` file:
   ```bash
   GROQ_API_KEY=<your_api_key_here>
   ```

*** //TODO: Remove for full project.
3. **Run**
   ```bash
   python groq_chat.py
   ```
***

## Files
- `groq_chat.py` - Main script
- `requirements.txt` - Dependencies
- `.env` - Your API key (private)
- `.gitignore` - Git ignore rules

## Packages Used
- python-dotenv (1.0.0)
- groq (0.13.1)

## Features
✓ JSON responses
✓ Error handling
✓ Clean code (PEP 8) 