"""
Installation action module for CECDaemon.

This module contains functions that perform actual filesystem modifications
during the installation process.
"""

from .execution_context import ExecutionContext, path_join



def create_service_from_template(ctx: ExecutionContext, template_path, work_dir, user, group, executable_path, config_dir):
    """
    Create a systemd service file from a template by replacing placeholders.
    
    Args:
        ctx: ExecutionContext for file operations
        template_path: Path to the service template file
        work_dir: Working directory for the daemon
        user: User to run the service as
        group: Group to run the service as
        executable_path: Full path to the daemon executable
        config_dir: Configuration directory for the daemon
        
    Returns:
        str: The processed service file content
    """
    try:
        with ctx.read_file(template_path) as f:
            template_content = f.read()
        
        # Replace template placeholders
        service_content = template_content.format(
            USER=user,
            GROUP=group,
            WORK_DIR=work_dir,
            EXECUTABLE_PATH=executable_path,
            CONFIG_DIR=config_dir
        )
        
        return service_content
        
    except FileNotFoundError:
        ctx.print(f"✗ Service template not found: {template_path}")
        return None
    except Exception as e:
        ctx.print(f"✗ Error processing service template: {e}")
        return None

def create_work_directory(ctx: ExecutionContext, work_dir):
    """Create work directory"""
    try:
        ctx.makedirs(work_dir, exist_ok=True)
        ctx.print(f"✓ Work directory created: {work_dir}")
        return True
    except Exception as e:
        ctx.print(f"✗ Failed to create work directory: {e}")
        return False


def create_config_directory(ctx: ExecutionContext, config_dir):
    """Create configuration directory"""
    try:
        ctx.makedirs(config_dir, exist_ok=True)
        ctx.print(f"✓ Configuration directory created: {config_dir}")
        return True
    except Exception as e:
        ctx.print(f"✗ Failed to create configuration directory: {e}")
        return False


def install_service_file(ctx: ExecutionContext, service_content, service_name, service_dir):
    """
    Install the systemd service file to the system.
    
    Args:
        ctx: ExecutionContext for file operations
        service_content: Content of the service file
        service_name: Name of the service (without .service extension)
        service_dir: Directory to install the service file
        
    Returns:
        bool: True if installation succeeded
    """
    service_file_path = path_join(service_dir, f"{service_name}.service")
    
    try:
        ctx.write_file(service_file_path, service_content)
        
        # Set proper permissions
        ctx.chmod(service_file_path, 0o644)
        
        ctx.print(f"✓ Service file installed: {service_file_path}")
        return True
        
    except Exception as e:
        ctx.print(f"✗ Failed to install service file: {e}")
        return False
