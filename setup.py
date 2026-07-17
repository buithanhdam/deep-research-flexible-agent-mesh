"""Setup script for easy installation."""

import subprocess
import sys
import os


def run_command(cmd, description):
    """Run a command and handle errors."""
    print(f"\n{'='*60}")
    print(f"📦 {description}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            check=True,
            text=True,
            capture_output=True
        )
        
        if result.stdout:
            print(result.stdout)
        
        print(f"✅ {description} - SUCCESS")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} - FAILED")
        print(f"Error: {e.stderr}")
        return False


def check_python_version():
    """Check Python version."""
    print("\n🔍 Checking Python version...")
    version = sys.version_info
    print(f"Python {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Python 3.8+ required")
        return False
    
    print("✅ Python version OK")
    return True


def create_venv():
    """Create virtual environment."""
    if os.path.exists("venv"):
        print("\n⚠️  Virtual environment already exists")
        response = input("Recreate? (y/N): ").strip().lower()
        if response == 'y':
            import shutil
            shutil.rmtree("venv")
        else:
            print("Skipping venv creation")
            return True
    
    return run_command(
        f"{sys.executable} -m venv venv",
        "Creating virtual environment"
    )


def install_dependencies():
    """Install dependencies."""
    if sys.platform == "win32":
        pip_cmd = "venv\\Scripts\\pip"
    else:
        pip_cmd = "venv/bin/pip"
    
    return run_command(
        f"{pip_cmd} install -r requirements.txt",
        "Installing dependencies"
    )


def create_env_file():
    """Create .env file if it doesn't exist."""
    if os.path.exists(".env"):
        print("\n⚠️  .env file already exists")
        print("Please update it manually with your API keys")
        return True
    
    env_template = """# OpenRouter Configuration (REQUIRED)
OPENROUTER_API_KEY=your_api_key_here
OPENROUTER_MODEL=anthropic/claude-3-5-sonnet

# Database Configuration (OPTIONAL - for Phase 2)

POSTGRES_HOST=
POSTGRES_PORT=
POSTGRES_USER=
POSTGRES_PASSWORD=
POSTGRES_DB=

# Logging
LOG_LEVEL=INFO
"""
    
    try:
        with open(".env", "w", encoding="utf-8") as f:
            f.write(env_template)
        
        print("\n✅ Created .env file")
        print("⚠️  IMPORTANT: Update .env with your OPENROUTER_API_KEY")
        return True
        
    except Exception as e:
        print(f"\n❌ Failed to create .env: {e}")
        return False


def run_tests():
    """Run test script."""
    print("\n" + "="*60)
    print("🧪 Running tests...")
    print("="*60)
    
    if sys.platform == "win32":
        python_cmd = "venv\\Scripts\\python"
    else:
        python_cmd = "venv/bin/python"
    
    try:
        result = subprocess.run(
            f"{python_cmd} test_system.py",
            shell=True,
            text=True,
            capture_output=True
        )
        
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
        
        return result.returncode == 0
        
    except Exception as e:
        print(f"❌ Tests failed: {e}")
        return False


def print_next_steps():
    """Print next steps."""
    print("\n" + "="*60)
    print("🎉 SETUP COMPLETE!")
    print("="*60)
    
    if sys.platform == "win32":
        activate_cmd = "venv\\Scripts\\activate"
        python_cmd = "venv\\Scripts\\python"
    else:
        activate_cmd = "source venv/bin/activate"
        python_cmd = "venv/bin/python"
    
    print(f"""
📝 Next Steps:

1. Activate virtual environment:
   {activate_cmd}

2. Update .env file with your OpenRouter API key:
   OPENROUTER_API_KEY=your_actual_key_here
   
   Get API key at: https://openrouter.ai/

3. Test the system:
   {python_cmd} test_system.py

4. Run a simple query:
   {python_cmd} -m src.main --task "Hello"

5. Run demo to see capabilities:
   {python_cmd} demo.py

6. Read documentation:
   - QUICKSTART.md - Quick start guide
   - README.md - Full documentation
   - src/prompt_templates/_STANDARD_TEMPLATE.md - Prompt guidelines

🚀 Ready to build multi-agent workflows!
    """)


def main():
    """Main setup process."""
    print("="*60)
    print("Multi-Agent System - Automated Setup")
    print("="*60)
    
    steps = [
        ("Check Python version", check_python_version),
        ("Create virtual environment", create_venv),
        ("Install dependencies", install_dependencies),
        ("Create .env file", create_env_file),
    ]
    
    for description, func in steps:
        if not func():
            print(f"\n❌ Setup failed at: {description}")
            print("Please fix the error and run setup.py again")
            return 1
    
    # Run tests (non-blocking)
    print("\n" + "="*60)
    print("⚠️  About to run tests...")
    print("Tests will fail if OPENROUTER_API_KEY is not set")
    print("="*60)
    
    response = input("\nRun tests now? (y/N): ").strip().lower()
    if response == 'y':
        run_tests()
    
    print_next_steps()
    return 0


if __name__ == "__main__":
    sys.exit(main())
