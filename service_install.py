import os
import subprocess
import sys
import argparse
import json
from pathlib import Path

from installer import (
    validate_installation_requirements,
    create_service_from_template,
    install_service_file,
    # Build utilities
    create_build_directory,
    create_virtual_environment,
    get_venv_executables,
    install_build_dependencies,
    compile_with_nuitka,
    verify_build_output,
    remove_build_directory,
    remove_build_artifacts,
    copy_uninstaller_to_build,
    create_distribution_package,
    substitute_work_dir_in_build,
    verify_uninstaller_functionality,
    # Execution context
    execution_context,
    get_execution_context,
    path_join
)

# Global configuration
CONFIG = None

def configure(service_dir=None, work_dir=None, config_dir=None, executable_dir=None, user=None, group=None, user_usb_groups=None, build_dir=None):
    """
    Configure the environment for CECDaemon installation
    
    Args:
        service_dir: Directory to install the systemd service file (default: from systemd-path)
        work_dir: Working directory for the daemon (default: from systemd-path)
        config_dir: Directory for configuration files (default: from systemd-path)
        executable_dir: Directory for the executable (default: from systemd-path)
        user: User to run the daemon as (default: cecdaemon)
        group: Group to run the daemon as (default: cecdaemon)
        user_usb_groups: List of user-specified USB device groups to check for CEC access
        build_dir: Build directory (default: random name in /tmp)
        
    Returns:
        dict: Complete installation configuration with all validated parameters
    """
    global CONFIG
    
    ctx = get_execution_context()
    
    # Run comprehensive validation and get configuration
    CONFIG = validate_installation_requirements(
        ctx, service_dir, work_dir, config_dir, executable_dir, 
        user, group, user_usb_groups, 'cecdaemon', build_dir
    )
    
    return CONFIG

def build():
    """Build the CECDaemon application"""
    global CONFIG
    ctx = get_execution_context()
    
    if CONFIG is None:
        ctx.print("✗ Configuration not loaded. Run configure() first.")
        ctx.system_exit(1)
    
    build_dir = CONFIG['paths']['build_dir']
    work_dir = CONFIG['paths']['work_dir']
    venv_dir = path_join(build_dir, "env")
    
    ctx.print("Building CECDaemon...")
    
    try:
        # Execute build steps using utility functions
        create_build_directory(build_dir)
        create_virtual_environment(venv_dir)
        
        venv_python, venv_pip = get_venv_executables(venv_dir)
        
        install_build_dependencies(venv_pip)
        
        # Add uninstaller and create distribution package first
        copy_uninstaller_to_build(build_dir)
        create_distribution_package(build_dir)
        
        # Substitute working directory in the copied source
        substitute_work_dir_in_build(build_dir, work_dir)
        
        # Compile with the modified source
        compile_with_nuitka(venv_python, build_dir)
        verify_build_output(build_dir)
        
        verify_uninstaller_functionality()
            
    except Exception as e:
        ctx.print(f"✗ Build failed: {e}")
        ctx.system_exit(1)

def cleanup():
    """Clean up temporary files and build artifacts"""
    global CONFIG
    ctx = get_execution_context()
    ctx.print("Cleaning up build artifacts...")

    try:
        remove_build_directory()
        remove_build_artifacts()
        ctx.print("✓ Cleanup completed")
        
    except Exception as e:
        ctx.print(f"⚠ Cleanup warning: {e}")
        # Don't exit on cleanup errors

def install():
    """Install CECDaemon to the system"""
    global CONFIG
    
    ctx = get_execution_context()
    
    if CONFIG is None:
        ctx.print("✗ Configuration not loaded. Run configure() first.")
        ctx.system_exit(1)
    
    # Check for permission issues before attempting installation
    permission_issues = []
    if not CONFIG['permissions']['service_dir_accessible']:
        permission_issues.append(CONFIG['permissions']['service_dir_warning'])
    if not CONFIG['permissions']['executable_dir_accessible']:
        permission_issues.append(CONFIG['permissions']['executable_dir_warning'])
    
    if permission_issues and not ctx.dry_run:
        # We have permission issues and we're not in dry-run mode
        if os.geteuid() != 0:
            # We're not running as root, so we need to save config and re-exec just the install step with sudo
            ctx.print("⚠ Installation requires elevated privileges:")
            for issue in permission_issues:
                ctx.print(f"  • {issue}")
            
            # Save the current config to a temporary file
            config_file = path_join(CONFIG['paths']['build_dir'], 'install_config.json')
            try:
                ctx.write_file(config_file, json.dumps(CONFIG, indent=2))
                ctx.print(f"✓ Configuration saved to {config_file}")
            except Exception as e:
                ctx.print(f"✗ Failed to save configuration: {e}")
                ctx.system_exit(1)
            
            ctx.print("\nRe-executing install step with sudo privileges...")
            
            # Construct command to run only the install step with the saved config
            install_cmd = [
                sys.executable, sys.argv[0], 
                '--install-only', 
                '--config-file', config_file
            ]
            
            # Re-execute with sudo for install only
            try:
                os.execvp('sudo', ['sudo'] + install_cmd)
                return
            except Exception as e:
                ctx.print(f"✗ Failed to restart with sudo: {e}")
                ctx.print("Please run manually with sudo:")
                ctx.print(f"  sudo {' '.join(install_cmd)}")
                ctx.system_exit(1)
        else:
            # We're already running as root but still have permission issues
            # This shouldn't happen, but let's handle it gracefully
            ctx.print("✗ Unexpected permission issues despite running as root:")
            for issue in permission_issues:
                ctx.print(f"  • {issue}")
            ctx.system_exit(1)
    elif permission_issues and ctx.dry_run:
        # In dry-run mode, just show what we would need
        ctx.print("ℹ Installation would require elevated privileges:")
        for issue in permission_issues:
            ctx.print(f"  • {issue}")
        ctx.print("  (Would save config and re-execute install step with sudo in normal mode)")
    
    # At this point we either have no permission issues or we're in dry-run mode
    
    # Extract values from config for readability
    service_dir = CONFIG['paths']['service_dir']
    work_dir = CONFIG['paths']['work_dir']
    config_dir = CONFIG['paths']['config_dir']
    executable_dir = CONFIG['paths']['executable_dir']
    user = CONFIG['user_group']['user']
    group = CONFIG['user_group']['group']
    user_not_created = CONFIG['user_group']['user_needs_creation']
    group_not_created = CONFIG['user_group']['group_needs_creation']
    
    # Actual installation logic will be implemented here
    ctx.print("Installing CECDaemon...")
    
    build_dir = CONFIG['paths']['build_dir']
    
    # 0. Create user and group if needed
    if user_not_created:
        ctx.print(f"Creating user: {user}")
        ctx.run(['useradd', '--system', '--no-create-home', '--shell', '/usr/sbin/nologin', user])
        ctx.print(f"✓ User '{user}' created")
    
    if group_not_created:
        ctx.print(f"Creating group: {group}")
        ctx.run(['groupadd', '--system', group])
        ctx.print(f"✓ Group '{group}' created")
    
    # Add user to necessary groups for CEC device access
    usb_group = CONFIG['user_group']['usb_group_needed']
    if usb_group:
        ctx.print(f"Adding user '{user}' to group '{usb_group}' for CEC device access")
        ctx.run(['usermod', '-a', '-G', usb_group, user])
        ctx.print(f"✓ User '{user}' added to group '{usb_group}'")
    
    # 1. Create necessary directories
    ctx.print("Creating directories...")
    
    # Create work directory with proper ownership
    ctx.makedirs(work_dir, exist_ok=True)
    ctx.run(['chown', f'{user}:{group}', work_dir])
    ctx.run(['chmod', '755', work_dir])
    ctx.print(f"✓ Work directory created: {work_dir}")
    
    # Create config directory (already done above but ensure ownership)
    ctx.makedirs(config_dir, exist_ok=True)
    ctx.run(['chown', 'root:root', config_dir])
    ctx.run(['chmod', '755', config_dir])
    ctx.print(f"✓ Config directory created: {config_dir}")
    
    # 2. Install the executable
    ctx.print("Installing CECDaemon executable...")
    executable_source = path_join(build_dir, "cecdaemon.bin")
    executable_dest = path_join(executable_dir, "cecdaemon")
    
    if not ctx.exists(executable_source):
        ctx.print(f"✗ Built executable not found: {executable_source}")
        ctx.print("✗ Make sure build() was called first")
        ctx.system_exit(1)
    
    ctx.copy2(executable_source, executable_dest)
    ctx.run(['chown', 'root:root', executable_dest])
    ctx.run(['chmod', '755', executable_dest])
    ctx.print(f"✓ Executable installed: {executable_dest}")
    
    # 3. Install the uninstaller to config directory
    ctx.print("Copying uninstaller...")
    uninstaller_source = path_join(build_dir, "uninstaller.py")
    uninstaller_dest = path_join(config_dir, "uninstaller.py")
    
    if ctx.exists(uninstaller_source):
        ctx.copy2(uninstaller_source, uninstaller_dest)
        ctx.run(['chown', 'root:root', uninstaller_dest])
        ctx.run(['chmod', '755', uninstaller_dest])
        ctx.print(f"✓ Uninstaller installed: {uninstaller_dest}")
    else:
        ctx.print(f"⚠ Warning: Uninstaller not found in build: {uninstaller_source}")
    
    # 4. Create and install systemd service from template
    ctx.print("Installing systemd service...")
    template_path = "service/cecdaemon.service"
    executable_path = path_join(executable_dir, "cecdaemon")
    service_content = create_service_from_template(
        ctx, template_path, work_dir, user, group, executable_path
    )
    
    if not service_content:
        ctx.print("✗ Failed to create service from template")
        ctx.system_exit(1)
    
    # 5. Install the service file
    if not install_service_file(ctx, service_content, "cecdaemon", service_dir):
        ctx.print("✗ Failed to install systemd service")
        ctx.system_exit(1)
    
    # TODO: Validate the service file after executable installation
    # This should be done here now that the executable is in place
    
    # 6. Save installation configuration for the uninstaller
    ctx.print("Saving installation configuration...")
    uninstaller_config = {
        'service_dir': service_dir,
        'work_dir': work_dir,
        'config_dir': config_dir,
        'executable_dir': executable_dir,
        'user': user,
        'group': group,
        'user_created': user_not_created,
        'group_created': group_not_created,
        'service_name': 'cecdaemon',
        'executable_name': 'cecdaemon',
        'uninstaller_path': path_join(config_dir, "uninstaller.py"),
        'config_file_path': path_join(config_dir, 'install_config.json')
    }
    
    # Save config to the config directory (not work directory)
    config_file = path_join(config_dir, 'install_config.json')
    try:
        ctx.write_file(config_file, json.dumps(uninstaller_config, indent=2))
        ctx.run(['chown', 'root:root', config_file])
        ctx.run(['chmod', '444', config_file])
        ctx.print(f"✓ Installation configuration saved to {config_file}")
    except Exception as e:
        ctx.print(f"⚠ Warning: Could not save installation configuration: {e}")
    
    # 7. Enable and start the service
    ctx.print("Enabling and starting CECDaemon service...")
    try:
        ctx.run(['systemctl', 'daemon-reload'])
        ctx.run(['systemctl', 'enable', 'cecdaemon'])
        ctx.print("✓ Service enabled to start on boot")
        
        # Optionally start the service immediately
        ctx.run(['systemctl', 'start', 'cecdaemon'])
        ctx.print("✓ Service started")
        
        # Check service status
        result = ctx.run(['systemctl', 'is-active', 'cecdaemon'], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip() == 'active':
            ctx.print("✓ Service is running successfully")
        else:
            ctx.print("⚠ Warning: Service may not be running properly")
            ctx.print("   Check service status with: sudo systemctl status cecdaemon")
            
    except Exception as e:
        ctx.print(f"⚠ Warning: Could not start service: {e}")
        ctx.print("   You can start it manually with: sudo systemctl start cecdaemon")
    
    ctx.print("✓ CECDaemon installation completed successfully!")


def load_config_from_file(config_file):
    """Load configuration from a JSON file"""
    global CONFIG
    
    ctx = get_execution_context()
    
    try:
        with open(config_file, 'r') as f:
            CONFIG = json.load(f)
        ctx.print(f"✓ Configuration loaded from {config_file}")
        return CONFIG
    except Exception as e:
        ctx.print(f"✗ Failed to load configuration from {config_file}: {e}")
        ctx.system_exit(1)

def main():
    """Main entry point for the installation script"""
    parser = argparse.ArgumentParser(description='CECDaemon Installation Script')
    parser.add_argument('--service-dir', default=None, 
                       help='Directory to install systemd service (default: /etc/systemd/system)')
    parser.add_argument('--work-dir', default=None,
                       help='Working directory for daemon (default: /var/lib/cecdaemon)')
    parser.add_argument('--config-dir', default=None,
                       help='Configuration directory (default: /etc/cecdaemon)')
    parser.add_argument('--executable-dir', default=None,
                       help='Executable directory (default: /usr/bin)')
    parser.add_argument('--user', default=None,
                       help='User to run daemon as (default: cecdaemon)')
    parser.add_argument('--group', default=None,
                       help='Group to run daemon as (default: cecdaemon)')
    parser.add_argument('--usb-groups', nargs='*', default=None,
                       help='USB device groups to check for CEC access (space-separated list)')
    parser.add_argument('--build-dir', default=None,
                       help='Build directory (default: random name in /tmp)')
    parser.add_argument('--configure-only', action='store_true',
                       help='Only run configuration checks')
    parser.add_argument('--build-only', action='store_true',
                       help='Only run configuration and build steps (no install)')
    parser.add_argument('--install-only', action='store_true',
                       help='Only run installation step (requires --config-file)')
    parser.add_argument('--config-file', default=None,
                       help='Load configuration from JSON file (for install-only mode)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without making any changes')
    
    args = parser.parse_args()
    
    # Use execution context for dry-run handling
    with execution_context(dry_run=args.dry_run) as ctx:
        if args.dry_run:
            print("🔍 Running in DRY RUN mode - no changes will be made\n")
        
        try:
            if args.install_only:
                # Install-only mode: load config from file and run install
                if not args.config_file:
                    ctx.print("✗ --config-file is required when using --install-only")
                    ctx.system_exit(1)
                
                load_config_from_file(args.config_file)
                ctx.print("\n=== Installing CECDaemon (install-only mode) ===")
                install()
                
            else:
                # Normal mode: configure, build, and optionally install
                configure(args.service_dir, args.work_dir, args.config_dir, 
                         args.executable_dir, args.user, args.group, args.usb_groups, args.build_dir)
                
                if not args.configure_only:
                    ctx.print("\n=== Building CECDaemon ===")
                    build()
                    
                    if not args.build_only:
                        ctx.print("\n=== Installing CECDaemon ===")
                        install()
                        
                        ctx.print("\n=== Cleaning up ===")
                        cleanup()
                
            if args.dry_run:
                print("\n🔍 DRY RUN completed - no actual changes were made")
                print("   Run without --dry-run to perform the actual installation")
                
        except KeyboardInterrupt:
            ctx.print("\n\nInstallation interrupted by user")
            ctx.system_exit(1)
        except Exception as e:
            ctx.print(f"\n✗ Installation failed: {e}")
            ctx.system_exit(1)

if __name__ == "__main__":
    main()

