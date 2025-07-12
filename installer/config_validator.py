"""
Configuration validation module for CECDaemon installation.

This module contains functions to validate directories, permissions, and system requirements
for the CECDaemon installation process.
"""

from .execution_context import (
    ExecutionContext, 
    SubprocessError, 
    TimeoutExpired, 
    CalledProcessError,
    FileNotFoundError,
    PermissionError,
    OSError,
    W_OK,
    R_OK,
    X_OK,
    F_OK,
    path_join
)
from pathlib import Path


def get_canonical_directories(ctx:ExecutionContext):
    """
    Get canonical system directories using systemd-path when available,
    falling back to FHS standard paths.
    
    Returns:
        dict: Dictionary containing canonical directory paths
    """
    dirs = {}
    
    try:
        # Try to use systemd-path to get canonical directories
        result = ctx.saferun(['systemd-path'], capture_output=True, text=True)
        if result.returncode == 0:
            for line in result.stdout.strip().split('\n'):
                if ':' in line:
                    key, path = line.split(':', 1)
                    key = key.strip()
                    path = path.strip()
                    if key == 'system-state-private':
                        dirs['state_dir'] = path  # /var/lib
                    elif key == 'system-configuration':
                        dirs['config_dir'] = path  # /etc
                    elif key == 'system-binaries':
                        dirs['bin_dir'] = path  # /usr/bin
                    elif key == 'system-library-private':
                        dirs['lib_dir'] = path  # /usr/lib
                    elif key == 'systemd-system-unit':
                        dirs['service_dir'] = path  # /etc/systemd/system
        
        # If systemd-path didn't provide all needed paths, fail
        required_keys = ['state_dir', 'config_dir', 'bin_dir', 'lib_dir', 'service_dir']
        missing_keys = [key for key in required_keys if key not in dirs]
        if missing_keys:
            ctx.print(f"systemd-path did not provide required paths: {missing_keys}")
            ctx.system_exit()
            
    except (SubprocessError, FileNotFoundError):
        ctx.print("Error running systemd-path. Ensure systemd is installed.")
        ctx.system_exit()
    
    return dirs


def get_default_installation_paths(ctx: ExecutionContext, app_name='cecdaemon'):
    """
    Get default installation paths for the application using system conventions.
    
    Args:
        app_name: Name of the application (default: cecdaemon)
        
    Returns:
        dict: Dictionary with default paths for installation
    """
    canonical = get_canonical_directories(ctx)
    
    return {
        'service_dir': canonical['service_dir'],
        'work_dir': path_join(canonical['state_dir'], app_name),
        'config_dir': path_join(canonical['config_dir'], app_name),
        'executable_dir': canonical['bin_dir'],
        'lib_dir': canonical['lib_dir'],
        'user': app_name,
        'group': app_name
    }


def check_systemd_linux(ctx:ExecutionContext):
    """Check if we're running on a systemd-based Linux distribution"""
    try:
        # Check for systemd (primary requirement)
        if not ctx.exists('/usr/bin/systemctl'):
            return False, None
        
        # Check /etc/os-release for distribution information
        with ctx.read_file('/etc/os-release') as f:
            content = f.read()
            
            # Extract the distribution name from PRETTY_NAME or NAME
            distro_name = "Unknown"
            base_distro_name = "Unknown"
            for line in content.split('\n'):
                if line.startswith('ID='):
                    distro_name = line.split('=', 1)[1].strip('"')
                elif line.startswith('ID_LIKE='):
                    base_distro_name = line.split('=', 1)[1].strip('"')
            
            # Check for systemd-based distributions
            # Most modern distributions use systemd, but we'll check for common ones
            systemd_indicators = [
                'arch', 'manjaro', 'endeavouros', 'artix', 'garuda',  # Arch family
                'ubuntu', 'debian', 'mint',  # Debian family
                'fedora', 'centos', 'rhel', 'rocky', 'alma',  # Red Hat family
                'opensuse', 'suse',  # SUSE family
                'gentoo'  # Gentoo (optional systemd support)
            ]
            
            is_supported = distro_name in systemd_indicators
            if not is_supported:
                ctx.print(
                    f"Unsupported distribution: {distro_name}. "
                    "This script is designed for systemd-based distributions."
                )
                ctx.system_exit()

            
            # Additional check: try to verify systemd is actually running
            try:
                result = ctx.saferun(['systemctl', 'is-system-running'], 
                                      capture_output=True, text=True, timeout=5)
                # systemctl returns 0 for running/degraded, non-zero for other states
                # but even non-zero can mean systemd is present but in maintenance mode
                systemd_running = result.returncode is not None  # Command executed
            except (TimeoutExpired, SubprocessError):
                ctx.print(
                    "Error checking systemd status. Ensure systemd is running and accessible."
                )
                ctx.system_exit()
            
            
            return distro_name,base_distro_name
            
    except FileNotFoundError:

        ctx.print(
            "This script requires /etc/os-release to determine the distribution. "
            "Please run on a system with this file present."
        )
        ctx.system_exit()


def check_libcec_installed(ctx:ExecutionContext,base_distro_name):
    """Check if libcec system package is installed using distribution-specific package managers"""
    try:
        # Map distribution families to their package managers
        package_managers = {
            'arch': {
                'cmd': ['pacman', '-Q', 'libcec'],
                'name': 'pacman',
            },
            'debian': {
                'cmd': ['dpkg', '-l', 'libcec*'],
                'name': 'dpkg',
            },
            'fedora': {
                'cmd': ['dnf', 'list', 'installed', 'libcec*'],
                'name': 'dnf',
            },
            'suse': {
                'cmd': ['zypper', 'search', '--installed-only', 'libcec'],
                'name': 'zypper',
            }
        }

        if 'fedora' in base_distro_name or 'rhel' in base_distro_name:
            base_distro_name = 'fedora'  # Normalize Fedora derivatives: legends has it some use 'rhel fedora'
        pm_config = package_managers.get(base_distro_name)
        if not pm_config:
            ctx.print(f"✗ Unsupported base distribution {base_distro_name}")
            ctx.system_exit()

        cmd = pm_config['cmd']
        pm_name = pm_config['name']
        ctx.print(f"Checking for libcec using {pm_name}...")
        result = ctx.saferun(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            if 'libcec' in result.stdout:
                ctx.print("✓ libcec is installed")
                return True
            ctx.print(f"✗ libcec not found using {pm_name}")
            ctx.system_exit()


    except Exception as e:
        ctx.print(f"✗ Error checking libcec installation: {e}")
        ctx.system_exit()


def validate_service_directory(ctx: ExecutionContext, service_dir):
    """
    Validate service directory access and permissions
    
    Returns:
        dict: Validation result with 'accessible' bool and 'warning' message if any
    """
    result = {'accessible': True, 'warning': None}
    
    if not ctx.exists(service_dir):
        result['accessible'] = False
        result['warning'] = f"Service directory does not exist: {service_dir}"
        ctx.print(f"⚠ {result['warning']}")
        return result
    
    if not ctx.access(service_dir, W_OK):
        result['accessible'] = False
        result['warning'] = f"No write permission to service directory: {service_dir}"
        ctx.print(f"⚠ {result['warning']}")
        ctx.print("  This script may need to be run with sudo privileges")
    else:
        ctx.print(f"✓ Service directory is accessible: {service_dir}")
    
    return result


def validate_work_directory(ctx: ExecutionContext, work_dir):
    """Validate work directory and check if it needs to be created"""
    if not ctx.exists(work_dir):
        ctx.print(f"Work directory does not exist: {work_dir} - will need to be created")
        return False  # Needs creation
    else:
        ctx.print(f"✓ Work directory already exists: {work_dir}")
        return True  # Already exists


def validate_config_directory(ctx: ExecutionContext, config_dir):
    """Validate config directory and check if it needs to be created"""
    if not ctx.exists(config_dir):
        ctx.print(f"Configuration directory does not exist: {config_dir} - will need to be created")
        return False  # Needs creation
    else:
        ctx.print(f"✓ Configuration directory already exists: {config_dir}")
        return True  # Already exists


def validate_executable_directory(ctx: ExecutionContext, executable_dir):
    """
    Validate executable directory access and permissions
    
    Returns:
        dict: Validation result with 'accessible' bool and 'warning' message if any
    """
    result = {'accessible': True, 'warning': None}
    
    if not ctx.exists(executable_dir):
        result['accessible'] = False
        result['warning'] = f"Executable directory does not exist: {executable_dir}"
        ctx.print(f"⚠ {result['warning']}")
        return result
    
    if not ctx.access(executable_dir, W_OK):
        result['accessible'] = False
        result['warning'] = f"No write permission to executable directory: {executable_dir}"
        ctx.print(f"⚠ {result['warning']}")
        ctx.print("  This script may need to be run with sudo privileges")
    else:
        ctx.print(f"✓ Executable directory is accessible: {executable_dir}")
    
    return result


def check_user_and_group(ctx: ExecutionContext, user, group):
    """
    Check if user and group exist or will be created
    
    Returns:
        tuple: (user_will_be_created, group_will_be_created)
    """
    user_needs_creation = _check_user_exists(ctx, user)
    group_needs_creation = _check_group_exists(ctx, group)
    
    return user_needs_creation, group_needs_creation


def _check_user_exists(ctx: ExecutionContext, user):
    """Check if a user exists on the system"""
    try:
        result = ctx.saferun(['id', user], capture_output=True, text=True)
        if result.returncode == 0:
            ctx.print(f"✓ User '{user}' already exists")
            return False  # User exists, no creation needed
        else:
            ctx.print(f"User '{user}' does not exist - will be created during installation")
            return True  # User needs creation
    except Exception as e:
        ctx.print(f"Warning: Could not check user '{user}': {e}")
        return True  # Assume needs creation if check fails


def _check_group_exists(ctx: ExecutionContext, group):
    """Check if a group exists on the system"""
    try:
        result = ctx.saferun(['getent', 'group', group], capture_output=True, text=True)
        if result.returncode == 0:
            ctx.print(f"✓ Group '{group}' already exists")
            return False  # Group exists, no creation needed
        else:
            ctx.print(f"Group '{group}' does not exist - will be created during installation")
            return True  # Group needs creation
    except Exception as e:
        ctx.print(f"Warning: Could not check group '{group}': {e}")
        return True  # Assume needs creation if check fails


def validate_user_device_access(ctx: ExecutionContext, user, user_needs_creation, user_usb_groups=None):
    """
    Validate that the user has appropriate device access for CEC functionality.
    
    Args:
        ctx: ExecutionContext for system operations
        user: Username to check
        user_needs_creation: Whether the user will be created (True) or already exists (False)
        user_usb_groups: Optional list of user-specified USB device groups to check first
        
    Returns:
        str or None: Group name to add the user to if needed, None if no action required or no group found
    """
    usb_group = get_usb_device_group(ctx, user_usb_groups)
    if not usb_group:
        return None
        
    if user_needs_creation:
        ctx.print(f"New user '{user}' will need '{usb_group}' group membership for CEC device access")
        return usb_group
    
    # Check existing user's group membership
    ctx.print(f"Checking user '{user}' for USB device access...")
    try:
        result = ctx.saferun(['groups', user], capture_output=True, text=True)
        if result.returncode == 0:
            user_groups = result.stdout.strip().split()
            if usb_group in user_groups:
                ctx.print(f"✓ User '{user}' is in '{usb_group}' group for CEC device access")
                return None  # No action needed
            else:
                ctx.print(f"⚠ User '{user}' should be added to '{usb_group}' group for CEC device access")
                return usb_group
    except (SubprocessError, FileNotFoundError):
        pass
    
    ctx.print(f"⚠ Could not check group membership for user '{user}'")
    return usb_group  # Return group as fallback


def get_usb_device_group(ctx: ExecutionContext, additional_groups=None):
    """
    Determine the correct group for USB/serial device access on this system.
    
    Based on research:
    - Arch Linux family (Arch, Manjaro, EndeavourOS): uucp
    - Debian family (Debian, Ubuntu, Mint): dialout  
    - Most other systemd distributions: dialout
    
    User-specified groups take precedence over system defaults.
    
    Args:
        ctx: ExecutionContext for system operations
        additional_groups: List of user-specified groups to check first
    
    Returns the first group that exists on the system, or None if none found.
    """
    # User-specified groups take precedence, then check defaults
    default_groups = ['uucp', 'dialout']
    candidate_groups = (additional_groups or []) + default_groups
    
    for group in candidate_groups:
        try:
            result = ctx.saferun(['getent', 'group', group], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                return group
        except Exception:
            # If subprocess fails, continue to next group
            continue
    ctx.print("No suitable USB device group found. Okay to proceed, but CEC device access may be limited.")
    return None


def check_service_conflicts(ctx: ExecutionContext, service_name):
    """
    Check if a service with the same name already exists in systemd.
    
    Args:
        ctx: ExecutionContext for system operations
        service_name: Name of the service to check (without .service extension)
        
    Returns:
        bool: True if service exists, False if available
    """
    service_file = f"{service_name}.service"
    try:
        # Check if service unit exists in systemd
        result = ctx.saferun(['systemctl', 'list-unit-files', service_file], 
                            capture_output=True, text=True)
        if result.returncode == 0 and service_file in result.stdout:
            # Service unit file exists, check its statu
            status_result = ctx.saferun(['systemctl', 'is-active', service_file], 
                                      capture_output=True, text=True)
            status = status_result.stdout.strip()
            
            if status == 'active':
                ctx.print(f"⚠ Service '{service_name}' already exists and is ACTIVE")
            elif status == 'inactive':
                ctx.print(f"⚠ Service '{service_name}' already exists but is INACTIVE")
            else:
                ctx.print(f"⚠ Service '{service_name}' already exists with status: {status}")
            ctx.system_exit()
        else:
            ctx.print(f"✓ Service name '{service_name}' is available")
            return False
            
    except (SubprocessError, FileNotFoundError) as e:
        ctx.print(f"Warning: Could not check service '{service_name}': {e}")
        ctx.system_exit()


def validate_python_modules(ctx: ExecutionContext, required_modules=None):
    """
    Validate that required Python modules can be imported.
    Only checks system-wide modules; build dependencies will be installed in virtual environment.
    
    Args:
        ctx: ExecutionContext for system operations
        required_modules: List of module names to check, defaults to ['cec']
        
    Returns:
        bool: True if all required modules are available
    """
    import sys
    
    if required_modules is None:
        required_modules = ['cec']  # Only check system-wide dependencies
    
    ctx.print("Checking required system-wide Python modules...")
    
    for module in required_modules:
        try:
            # Try to import the module using current Python interpreter
            result = ctx.saferun([sys.executable, '-c', f'import {module}; print("OK")'], 
                                capture_output=True, text=True)
            if result.returncode == 0 and 'OK' in result.stdout:
                ctx.print(f"✓ Module '{module}' is available")
            else:
                ctx.print(f"✗ Module '{module}' is NOT available")
                ctx.print(f"  Please install {module} Python bindings system-wide")
                ctx.system_exit()
                
        except (SubprocessError, FileNotFoundError):
            ctx.print(f"✗ Could not test module '{module}'")
            ctx.print(f"  Please ensure {module} Python bindings are installed")
            ctx.system_exit()
    
    return True


def validate_installation_requirements(ctx: ExecutionContext, service_dir=None, work_dir=None, 
                                     config_dir=None, executable_dir=None, user=None, group=None, 
                                     user_usb_groups=None, app_name='cecdaemon', build_dir=None):
    """
    Comprehensive validation of all installation requirements.
    Assembles build and installation parameters into a structured configuration.
    
    Args:
        ctx: ExecutionContext for system operations
        service_dir: Directory to install systemd service (default: from systemd-path)
        work_dir: Working directory for daemon (default: from systemd-path)
        config_dir: Configuration directory (default: from systemd-path)
        executable_dir: Executable directory (default: from systemd-path)
        user: User to run daemon as (default: app_name)
        group: Group to run daemon as (default: app_name)
        user_usb_groups: Optional list of user-specified USB device groups
        app_name: Name of the application (default: cecdaemon)
        build_dir: Build directory (default: random name in /tmp)
        
    Returns:
        dict: Complete installation configuration with all validated parameters
    """
    import tempfile
    import random
    import string
    ctx.print("=== CECDaemon Installation Validation ===\n")
    
    # Generate random build directory if not provided
    if build_dir is None:
        random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        build_dir = path_join(tempfile.gettempdir(), f"cecdaemon-build-{random_suffix}")
    
    # Step 1: System compatibility validation
    ctx.print("1. Checking system compatibility...")
    distro_name, base_distro_name = check_systemd_linux(ctx)
    check_libcec_installed(ctx, base_distro_name)
    
    # Step 2: Python module validation
    ctx.print("\n2. Validating Python dependencies...")
    validate_python_modules(ctx)
    
    # Step 3: Get default installation paths and override with provided values
    ctx.print("\n3. Determining installation paths...")
    default_paths = get_default_installation_paths(ctx, app_name)
    
    # Override defaults with provided parameters
    final_paths = {
        'service_dir': service_dir or default_paths['service_dir'],
        'work_dir': work_dir or default_paths['work_dir'],
        'config_dir': config_dir or default_paths['config_dir'],
        'executable_dir': executable_dir or default_paths['executable_dir'],
        'lib_dir': default_paths['lib_dir'],
        'user': user or default_paths['user'],
        'group': group or default_paths['group']
    }
    
    # Step 4: Directory and permission validation
    ctx.print("\n4. Validating directories and permissions...")
    service_validation = validate_service_directory(ctx, final_paths['service_dir'])
    work_dir_exists = validate_work_directory(ctx, final_paths['work_dir'])
    config_dir_exists = validate_config_directory(ctx, final_paths['config_dir'])
    executable_validation = validate_executable_directory(ctx, final_paths['executable_dir'])
    
    # Step 5: User and group validation
    ctx.print("\n5. Checking user and group requirements...")
    user_needs_creation, group_needs_creation = check_user_and_group(ctx, final_paths['user'], final_paths['group'])
    usb_group_needed = validate_user_device_access(ctx, final_paths['user'], user_needs_creation, user_usb_groups)
    
    # Step 6: Service conflict check
    ctx.print("\n6. Checking for service conflicts...")
    service_exists = check_service_conflicts(ctx, app_name)
    
    # Assemble complete installation configuration
    installation_config = {
        # System information
        'system': {
            'distro_name': distro_name,
            'base_distro_name': base_distro_name,
            'app_name': app_name
        },
        
        # Installation paths
        'paths': {
            'service_dir': final_paths['service_dir'],
            'work_dir': final_paths['work_dir'],
            'config_dir': final_paths['config_dir'],
            'executable_dir': final_paths['executable_dir'],
            'lib_dir': final_paths['lib_dir'],
            'build_dir': build_dir
        },
        
        # Directory creation requirements
        'directories': {
            'work_dir_needs_creation': not work_dir_exists,
            'config_dir_needs_creation': not config_dir_exists
        },
        
        # Permission validation results
        'permissions': {
            'service_dir_accessible': service_validation['accessible'],
            'service_dir_warning': service_validation['warning'],
            'executable_dir_accessible': executable_validation['accessible'],
            'executable_dir_warning': executable_validation['warning']
        },
        
        # User and group configuration
        'user_group': {
            'user': final_paths['user'],
            'group': final_paths['group'],
            'user_needs_creation': user_needs_creation,
            'group_needs_creation': group_needs_creation,
            'usb_group_needed': usb_group_needed
        },
        
        # Service configuration
        'service': {
            'name': app_name,
            'service_exists': service_exists,
            'service_file': f"{app_name}.service"
        },
        
        # Build requirements
        'build': {
            'python_modules_validated': True,
            'libcec_available': True
        }
    }
    
    ctx.print("\n✓ All validation checks completed successfully!")
    ctx.print("\nInstallation Configuration Summary:")
    ctx.print(f"  Application: {installation_config['system']['app_name']}")
    ctx.print(f"  Service: {installation_config['service']['service_file']}")
    ctx.print(f"  User: {installation_config['user_group']['user']}")
    ctx.print(f"  Group: {installation_config['user_group']['group']}")
    ctx.print(f"  Work Directory: {installation_config['paths']['work_dir']}")
    ctx.print(f"  Config Directory: {installation_config['paths']['config_dir']}")
    ctx.print(f"  Build Directory: {installation_config['paths']['build_dir']}")
    ctx.print(f"  Executable Directory: {installation_config['paths']['executable_dir']}")
    
    if installation_config['user_group']['usb_group_needed']:
        ctx.print(f"  USB Group: {installation_config['user_group']['usb_group_needed']}")
    
    # Show permission warnings
    permission_warnings = []
    if not installation_config['permissions']['service_dir_accessible']:
        permission_warnings.append(installation_config['permissions']['service_dir_warning'])
    if not installation_config['permissions']['executable_dir_accessible']:
        permission_warnings.append(installation_config['permissions']['executable_dir_warning'])
    
    if permission_warnings:
        ctx.print(f"\n⚠ Permission Warnings (will prevent installation):")
        for warning in permission_warnings:
            ctx.print(f"  • {warning}")
        ctx.print("  Run with sudo privileges to install, or use --build-only to just build")
    
    return installation_config
