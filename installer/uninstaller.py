#!/usr/bin/env python3
"""
CECDaemon Uninstaller

This script cleanly removes CECDaemon and all its components from the system,
undoing everything the installation process created.
"""

import os
import sys
import json
import argparse
import subprocess
import shutil
from pathlib import Path


#!/usr/bin/env python3
"""
CECDaemon Uninstaller

This script cleanly removes CECDaemon and all its components from the system,
undoing everything the installation process created.
"""

import os
import sys
import json
import argparse
import subprocess
import shutil
from pathlib import Path

# Global dry-run flag
DRY_RUN = False


def print_message(*args, **kwargs):
    """Print with optional dry-run prefix"""
    if DRY_RUN:
        # Add dry-run prefix to the first argument if it's a string
        if args and isinstance(args[0], str):
            args = (f"[DRY RUN] {args[0]}",) + args[1:]
    print(*args, **kwargs)


def run_command(cmd, **kwargs):
    """Run a command with dry-run awareness"""
    if DRY_RUN:
        print_message(f"Would run: {' '.join(cmd)}")
        # Return a mock successful result for dry-run
        from types import SimpleNamespace
        mock_result = SimpleNamespace()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        return mock_result
    return subprocess.run(cmd, **kwargs)


def safe_run_command(cmd, **kwargs):
    """
    Run a safe command (for read-only operations) - always runs even in dry-run.
    
    When running as root, temporarily drops to 'nobody' user for security.
    When running as non-root, executes normally.
    """
    # If we're root, try to drop privileges temporarily
    if os.geteuid() == 0:
        return _run_with_dropped_privileges(cmd, **kwargs)
    else:
        # Non-root user, just run normally
        return subprocess.run(cmd, **kwargs)


def _run_with_dropped_privileges(cmd, **kwargs):
    """
    Helper function to run commands with temporarily dropped privileges when root.
    Uses seteuid() to temporarily switch to 'nobody' user.
    """
    import pwd
    
    # Get nobody user info
    nobody = pwd.getpwnam('nobody')
    
    # Save current effective user/group IDs
    original_euid = os.geteuid()
    original_egid = os.getegid()
    
    # Temporarily drop to nobody
    try:
        os.setegid(nobody.pw_gid)
        os.seteuid(nobody.pw_uid)
        # Run the command with dropped privileges
        return subprocess.run(cmd, **kwargs)
    finally:
        # Restore original privileges
        os.seteuid(original_euid)
        os.setegid(original_egid)


def remove_file_or_dir(path, description):
    """Remove a file or directory with dry-run awareness"""
    if DRY_RUN:
        if os.path.exists(path):
            if os.path.isdir(path):
                print_message(f"Would remove directory: {path}")
            else:
                print_message(f"Would remove file: {path}")
        else:
            print_message(f"Would skip (doesn't exist): {path}")
        return
    
    if os.path.exists(path):
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
                print_message(f"✓ Removed directory: {path}")
            else:
                os.remove(path)
                print_message(f"✓ Removed file: {path}")
        except Exception as e:
            print_message(f"✗ Failed to remove {path}: {e}")
    else:
        print_message(f"✓ {description} does not exist: {path}")


def find_config_file():
    """Find the installation config file in the same directory as the uninstaller"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    local_config = os.path.join(script_dir, 'install_config.json')
    
    if os.path.exists(local_config):
        return local_config
    
    return None


def load_installation_config():
    """Load the installation configuration to understand what was installed"""
    config_file = find_config_file()
    
    if not config_file:
        return None
    
    try:
        with open(config_file, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"⚠ Warning: Could not read config file {config_file}: {e}")
        return None


def stop_service(service_name: str):
    """Stop the CECDaemon service if it's running"""
    print_message(f"Stopping {service_name} service...")
    
    try:
        # Check if service is active
        result = safe_run_command(['systemctl', 'is-active', service_name], capture_output=True, text=True)
        
        if result.returncode == 0:  # Service is active
            print_message(f"  Service {service_name} is running, stopping...")
            run_command(['systemctl', 'stop', service_name], check=True)
            print_message(f"  ✓ Service {service_name} stopped")
        else:
            print_message(f"  ✓ Service {service_name} is not running")
            
    except Exception as e:
        print_message(f"  ⚠ Warning: Could not stop service {service_name}: {e}")


def disable_service(service_name: str):
    """Disable the CECDaemon service"""
    print_message(f"Disabling {service_name} service...")
    
    try:
        # Check if service is enabled
        result = safe_run_command(['systemctl', 'is-enabled', service_name], capture_output=True, text=True)
        
        if result.returncode == 0:  # Service is enabled
            run_command(['systemctl', 'disable', service_name], check=True)
            print_message(f"  ✓ Service {service_name} disabled")
        else:
            print_message(f"  ✓ Service {service_name} is not enabled")
            
    except Exception as e:
        print_message(f"  ⚠ Warning: Could not disable service {service_name}: {e}")


def remove_service_file(service_dir: str, service_name: str):
    """Remove the systemd service file"""
    service_file = os.path.join(service_dir, f"{service_name}.service")
    
    print_message(f"Removing service file: {service_file}")
    
    if os.path.exists(service_file):
        try:
            remove_file_or_dir(service_file, "service file")
            
            # Reload systemd to recognize the removal
            run_command(['systemctl', 'daemon-reload'], check=True)
            print_message("  ✓ Systemd daemon reloaded")
            
        except Exception as e:
            print_message(f"  ✗ Failed to remove service file: {e}")
    else:
        print_message(f"  ✓ Service file does not exist: {service_file}")


def remove_user(username: str):
    """Remove the user created during installation"""
    print_message(f"Removing user: {username}")
    
    try:
        # Check if user exists
        result = safe_run_command(['id', username], capture_output=True, text=True)
        
        if result.returncode == 0:  # User exists
            run_command(['userdel', '-r', username], check=True)
            print_message(f"  ✓ User {username} removed (including home directory)")
        else:
            print_message(f"  ✓ User {username} does not exist")
            
    except Exception as e:
        print_message(f"  ⚠ Warning: Could not remove user {username}: {e}")


def remove_group(groupname: str):
    """Remove the group created during installation"""
    print_message(f"Removing group: {groupname}")
    
    try:
        # Check if group exists
        result = safe_run_command(['getent', 'group', groupname], capture_output=True, text=True)
        
        if result.returncode == 0:  # Group exists
            run_command(['groupdel', groupname], check=True)
            print_message(f"  ✓ Group {groupname} removed")
        else:
            print_message(f"  ✓ Group {groupname} does not exist")
            
    except Exception as e:
        print_message(f"  ⚠ Warning: Could not remove group {groupname}: {e}")


def remove_directory(dir_path: str, description: str):
    """Remove a directory and its contents"""
    print_message(f"Removing {description}: {dir_path}")
    remove_file_or_dir(dir_path, description)


def remove_executable(executable_path: str):
    """Remove the CECDaemon executable"""
    print_message(f"Removing executable: {executable_path}")
    remove_file_or_dir(executable_path, "executable")


def uninstall_with_config(config: dict):
    """Uninstall using information from the installation config"""
    print_message("=== CECDaemon Uninstaller (using installation config) ===")
    print_message()
    
    service_name = config.get('service_name', 'cecdaemon')
    
    # Stop and disable service
    stop_service(service_name)
    disable_service(service_name)
    
    # Remove service file
    service_dir = config.get('service_dir', '/etc/systemd/system')
    remove_service_file(service_dir, service_name)
    
    # Remove executable
    executable_dir = config.get('executable_dir', '/usr/bin')
    executable_name = config.get('executable_name', 'cecdaemon')
    executable_path = os.path.join(executable_dir, executable_name)
    remove_executable(executable_path)
    
    # Remove directories
    work_dir = config.get('work_dir')
    if work_dir:
        remove_directory(work_dir, "work directory")
    
    config_dir = config.get('config_dir')
    if config_dir:
        remove_directory(config_dir, "configuration directory")
    
    # Remove user and group (only if they were created during installation)
    if config.get('user_created', False):
        user = config.get('user')
        if user:
            remove_user(user)
    else:
        print_message(f"Skipping user removal (user '{config.get('user', 'unknown')}' existed before installation)")
    
    if config.get('group_created', False):
        group = config.get('group')
        if group:
            remove_group(group)
    else:
        print_message(f"Skipping group removal (group '{config.get('group', 'unknown')}' existed before installation)")


def main():
    global DRY_RUN
    
    parser = argparse.ArgumentParser(description="Uninstall CECDaemon and remove all its components")
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be removed without actually doing it')
    
    args = parser.parse_args()
    DRY_RUN = args.dry_run
    
    if args.dry_run:
        print_message("🔍 DRY RUN MODE - No changes will be made")
        print_message()
    
    # Check if we're running as root/sudo
    if os.geteuid() != 0 and not args.dry_run:
        print_message("✗ This uninstaller must be run with sudo privileges")
        print_message("  Usage: sudo python3 uninstaller.py")
        sys.exit(1)
    
    # Load installation config
    install_config = load_installation_config()
    
    if not install_config:
        print_message("✗ No installation config found")
        print_message()
        print_message("Searched locations:")
        print_message("  - Current directory: install_config.json")
        print_message()
        print_message("CECDaemon cannot be safely uninstalled without the installation")
        print_message("configuration file that tracks what was installed.")
        print_message()
        print_message("This config-driven approach ensures that:")
        print_message("  • Only components that were actually installed are removed")
        print_message("  • Users/groups are only removed if they were created during install")
        print_message("  • Custom installation paths are handled correctly")
        print_message()
        print_message("If you need to remove CECDaemon manually, you can:")
        print_message("  1. Stop the service: sudo systemctl stop cecdaemon")
        print_message("  2. Disable the service: sudo systemctl disable cecdaemon")
        print_message("  3. Remove service file: sudo rm /etc/systemd/system/cecdaemon.service")
        print_message("  4. Remove executable: sudo rm /usr/bin/cecdaemon")
        print_message("  5. Remove directories as needed")
        
        if not args.dry_run:
            sys.exit(1)
        return
    
    # If we reach here, we have a valid config
    if args.dry_run:
        print_message("Found installation config, would uninstall:")
        print_message(f"  Service: {install_config.get('service_name', 'cecdaemon')}")
        executable_dir = install_config.get('executable_dir', '/usr/bin')
        executable_name = install_config.get('executable_name', 'cecdaemon')
        print_message(f"  Executable: {os.path.join(executable_dir, executable_name)}")
        print_message(f"  Work directory: {install_config.get('work_dir', 'unknown')}")
        print_message(f"  Config directory: {install_config.get('config_dir', 'unknown')}")
        print_message(f"  User: {install_config.get('user', 'unknown')} ({'would remove' if install_config.get('user_created') else 'would keep'})")
        print_message(f"  Group: {install_config.get('group', 'unknown')} ({'would remove' if install_config.get('group_created') else 'would keep'})")
    
    # Perform the actual uninstallation
    uninstall_with_config(install_config)
    
    print_message()
    print_message("✓ CECDaemon uninstallation completed!")


if __name__ == "__main__":
    main()
