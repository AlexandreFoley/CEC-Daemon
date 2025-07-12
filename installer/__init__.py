"""
CECDaemon Installation Package

This package contains modules for configuring, building, and installing CECDaemon
on systemd-based Linux distributions.
"""

# Import all validation functions
from .config_validator import (
    check_systemd_linux,
    check_libcec_installed,
    validate_service_directory,
    validate_work_directory,
    validate_config_directory,
    validate_executable_directory,
    check_user_and_group,
    validate_user_device_access,
    get_default_installation_paths,
    get_usb_device_group,
    validate_installation_requirements
)

# Import installation action functions
from .installer_actions import (
    create_work_directory,
    create_config_directory,
    install_service_file,
    create_service_from_template
)

# Import build utilities
from .build_utils import (
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
    validate_service_file
)

# Import execution context
from .execution_context import (
    execution_context,
    get_execution_context,
    path_join
)
