"""
Build utilities for CECDaemon installation.

This module contains functions for building CECDaemon using Nuitka and managing
build artifacts including virtual environments, dependencies, and cleanup.
"""

import os
import sys
import subprocess
import shutil
import glob


def create_build_directory(build_dir):
    """Create the build directory"""
    from .execution_context import get_execution_context
    
    ctx = get_execution_context()
    ctx.makedirs(build_dir, exist_ok=True)
    ctx.print(f"✓ Build directory created: {build_dir}")


def create_virtual_environment(venv_dir):
    """Create a Python virtual environment with system site packages"""
    from .execution_context import get_execution_context
    
    ctx = get_execution_context()
    ctx.print("Creating Python virtual environment...")
    result = ctx.run([
        sys.executable, "-m", "venv", venv_dir, "--system-site-packages"
    ], capture_output=True, text=True)
    
    if result.returncode != 0:
        ctx.print(f"✗ Failed to create virtual environment:")
        ctx.print(result.stderr)
        sys.exit(1)
    ctx.print(f"✓ Virtual environment created: {venv_dir}")


def get_venv_executables(venv_dir):
    """Get the paths to Python and pip executables in the virtual environment"""
    # Linux/Unix paths (systemd-based systems only)
    venv_python = os.path.join(venv_dir, "bin", "python")
    venv_pip = os.path.join(venv_dir, "bin", "pip")
    
    return venv_python, venv_pip


def install_build_dependencies(venv_pip):
    """Install required packages for building"""
    from .execution_context import get_execution_context
    
    ctx = get_execution_context()
    ctx.print("Installing build dependencies...")
    packages = get_build_required_packages()
    # ["daemonocle", "click", "nuitka", "filelock","patchelf"]
    
    result = ctx.run([
        venv_pip, "install"
    ] + packages, capture_output=True, text=True)
    
    if result.returncode != 0:
        ctx.print(f"✗ Failed to install packages:")
        ctx.print(result.stderr)
        sys.exit(1)
    ctx.print(f"✓ Installed packages: {', '.join(packages)}")


def compile_with_nuitka(venv_python, build_dir):
    """Compile the application using Nuitka"""
    from .execution_context import get_execution_context
    
    ctx = get_execution_context()
    ctx.print("Building CECDaemon with Nuitka...")
    
    # Use the daemon source from the build directory
    daemon_source_path = os.path.join(build_dir, "cecdaemon.py")
    
    nuitka_cmd = [
        venv_python, "-m", "nuitka", 
        "--standalone", "--onefile", "--deployment", 
        "--output-dir=" + build_dir,
        daemon_source_path
    ]
    
    ctx.print(f"Running: {' '.join(nuitka_cmd)}")
    result = ctx.run(nuitka_cmd, text=True)
    
    if result.returncode != 0:
        ctx.print("✗ Nuitka build failed")
        sys.exit(1)
    
    ctx.print("✓ CECDaemon build completed successfully!")


def verify_build_output(build_dir):
    """Verify that the build output exists"""
    from .execution_context import get_execution_context
    
    ctx = get_execution_context()
    expected_output = os.path.join(build_dir, "cecdaemon.dist")
    if not ctx.dry_run:
        if ctx.exists(expected_output):
            ctx.print(f"✓ Build output available at: {expected_output}")
        else:
            ctx.print(f"⚠ Build completed but expected output not found at: {expected_output}")


def remove_build_directory():
    """Remove the build directory and its contents"""
    from .execution_context import get_execution_context
    
    ctx = get_execution_context()
    if os.path.exists("build"):
        ctx.rmtree("build")
        ctx.print("✓ Build directory removed")
    else:
        ctx.print("✓ No build directory to clean")


def remove_build_artifacts():
    """Remove additional build artifacts like __pycache__, *.pyc files, etc."""
    from .execution_context import get_execution_context
    
    ctx = get_execution_context()
    artifacts = [
        "__pycache__",
        "*.pyc", 
        "*.pyo",
        "*.pyd",
        ".nuitka"
    ]
    
    for pattern in artifacts:
        if '*' in pattern:
            for file in ctx.glob(pattern):
                if os.path.isfile(file):
                    ctx.remove(file)
                    ctx.print(f"✓ Removed: {file}")
        else:
            if os.path.exists(pattern):
                if os.path.isdir(pattern):
                    ctx.rmtree(pattern)
                else:
                    ctx.remove(pattern)
                ctx.print(f"✓ Removed: {pattern}")


def get_build_required_packages():
    """Get the list of packages required for building"""
    return ["daemonocle", "click", "nuitka", "filelock","patchelf"]


def copy_uninstaller_to_build(build_dir):
    """Copy the uninstaller script to the build directory for distribution"""
    from .execution_context import get_execution_context
    
    ctx = get_execution_context()
    # Uninstaller is now in the installer directory
    uninstaller_source = os.path.join("installer", "uninstaller.py")
    uninstaller_dest = os.path.join(build_dir, "uninstaller.py")
    
    if os.path.exists(uninstaller_source):
        ctx.copy2(uninstaller_source, uninstaller_dest)
        ctx.print(f"✓ Copied uninstaller to build: {uninstaller_dest}")
    else:
        ctx.print(f"⚠ Warning: Uninstaller not found at: {uninstaller_source}")


def create_distribution_package(build_dir):
    """Create a distribution package with all necessary files"""
    from .execution_context import get_execution_context
    
    ctx = get_execution_context()
    ctx.print("Creating distribution package...")
    
    # List of files to include in distribution
    dist_files = [
        ("cecdaemon.py", "Main daemon script"),
        ("cecclient.py", "Client utilities"),
        ("service/cecdaemon.service", "Systemd service template"),
        ("LICENSE", "License file")
    ]
    
    # Copy files to build directory
    for file_path, description in dist_files:
        if os.path.exists(file_path):
            dest_path = os.path.join(build_dir, os.path.basename(file_path))
            if file_path.startswith("service/"):
                # Create service subdirectory
                service_dir = os.path.join(build_dir, "service")
                ctx.makedirs(service_dir, exist_ok=True)
                dest_path = os.path.join(build_dir, file_path)
            
            ctx.copy2(file_path, dest_path)
            ctx.print(f"✓ Added to distribution: {file_path} ({description})")
        else:
            ctx.print(f"⚠ Warning: Distribution file not found: {file_path}")
    
    # Note: Uninstaller is already copied by copy_uninstaller_to_build()
    # and doesn't need to be copied again here
    
    ctx.print(f"✓ Distribution package created in: {build_dir}")


def verify_uninstaller_functionality():
    """Verify that the uninstaller script is functional"""
    from .execution_context import get_execution_context
    
    ctx = get_execution_context()
    ctx.print("Verifying uninstaller functionality...")
    
    try:
        # Test dry-run mode of uninstaller
        result = ctx.run([
            sys.executable, "installer/uninstaller.py", "--dry-run"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            ctx.print("✓ Uninstaller dry-run test passed")
            return True
        else:
            ctx.print(f"⚠ Uninstaller dry-run test failed: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        ctx.print("⚠ Uninstaller test timed out")
        return False
    except FileNotFoundError:
        ctx.print("⚠ Uninstaller script not found")
        return False
    except Exception as e:
        ctx.print(f"⚠ Uninstaller test error: {e}")
        return False


def substitute_work_dir_in_build(build_dir, work_dir):
    """
    Substitute the working directory in the copied daemon source file.
    
    This function modifies the cecdaemon.py file that was already copied to the 
    build directory by create_distribution_package, replacing the hardcoded 
    work_dir with the configured one.
    
    Args:
        build_dir: Build directory containing the copied source files
        work_dir: The actual working directory to substitute in the source
    """
    from .execution_context import get_execution_context
    import re
    
    ctx = get_execution_context()
    
    # Path to the daemon source in the build directory
    build_source_path = os.path.join(build_dir, "cecdaemon.py")
    
    ctx.print(f"Substituting work_dir in build source: {work_dir}")
    
    # Check if source exists (handles dry-run mode)
    if not ctx.exists(build_source_path):
        if ctx.dry_run:
            ctx.print(f"[DRY RUN] Would substitute work_dir in: {build_source_path}")
            ctx.print(f"[DRY RUN] Would change work_dir to: {work_dir}")
            ctx.print("✓ Work directory substitution prepared (dry-run)")
            return
        else:
            ctx.print(f"✗ Daemon source not found in build directory: {build_source_path}")
            ctx.print("✗ Make sure create_distribution_package() was called first")
            sys.exit(1)
    
    # Read the copied source content
    try:
        if ctx.dry_run:
            # In dry-run, simulate reading the original source for pattern matching
            with open("cecdaemon.py", 'r') as f:
                source_content = f.read()
            ctx.print(f"[DRY RUN] Simulating read of: {build_source_path}")
        else:
            # In normal mode, read the actual copied file
            with open(build_source_path, 'r') as f:
                source_content = f.read()
    except Exception as e:
        ctx.print(f"✗ Failed to read daemon source: {e}")
        if not ctx.dry_run:
            sys.exit(1)
        else:
            ctx.print(f"Cannot simulate work_dir substitution - source not available")
            return
    
    # Substitute the hardcoded work_dir with the actual one
    # Look for the line: work_dir = "/path/to/hardcoded/dir/"
    # Pattern to match: work_dir = "any/path/here"
    pattern = r'^work_dir\s*=.*$'
    replacement = f'work_dir = "{work_dir}"'
    
    # Replace the work_dir assignment
    modified_content = re.sub(pattern, replacement, source_content, flags=re.MULTILINE)
    
    # Verify the substitution was made
    if modified_content == source_content:
        ctx.print("⚠ Warning: No work_dir assignment found to substitute")
        ctx.print("⚠ The daemon may use a hardcoded working directory")
    else:
        # Show what changed
        import difflib
        original_lines = source_content.splitlines()
        modified_lines = modified_content.splitlines()
        
        for i, (orig, mod) in enumerate(zip(original_lines, modified_lines)):
            if orig != mod:
                ctx.print(f"✓ Line {i+1}: {orig.strip()} → {mod.strip()}")
                break
        
        ctx.print(f"✓ Substituted work_dir with: {work_dir}")
    
    # Write the modified source back to the build directory
    try:
        if ctx.dry_run:
            ctx.print(f"[DRY RUN] Would write modified source to: {build_source_path}")
        else:
            with open(build_source_path, 'w') as f:
                f.write(modified_content)
    except Exception as e:
        ctx.print(f"✗ Failed to write modified source: {e}")
        if not ctx.dry_run:
            sys.exit(1)
    
    ctx.print(f"✓ Modified daemon source in build directory: {build_source_path}")


def validate_service_file(service_file_path):
    """
    Validate a systemd service file using systemd-analyze
    
    Args:
        service_file_path: Absolute path to the service file to validate
        
    Returns:
        bool: True if validation passed, False otherwise
    """
    from .execution_context import get_execution_context
    
    ctx = get_execution_context()
    
    try:
        ctx.print(f"Validating service file: {service_file_path}")
        
        # Use systemd-analyze to verify the service file syntax
        result = ctx.saferun([
            'systemd-analyze', 'verify', service_file_path
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            ctx.print("✓ Service file syntax validation passed")
            return True
        else:
            ctx.print(f"✗ Service file validation failed:")
            if result.stderr:
                ctx.print(f"  Error: {result.stderr.strip()}")
            if result.stdout:
                ctx.print(f"  Output: {result.stdout.strip()}")
            return False
            
    except subprocess.TimeoutExpired:
        ctx.print("⚠ Service validation timed out")
        return False
    except FileNotFoundError:
        ctx.print("⚠ systemd-analyze not found - cannot validate service file")
        return False
    except Exception as e:
        ctx.print(f"⚠ Service validation error: {e}")
        return False
