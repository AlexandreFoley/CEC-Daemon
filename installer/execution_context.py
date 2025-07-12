"""
Execution context for dry-run and actual execution modes.

This module provides a clean way to handle dry-run vs actual execution
without scattering conditional logic throughout the codebase.
"""

import os
import sys
import subprocess
import shutil
import glob
from pathlib import Path
from contextlib import contextmanager
from unittest.mock import patch, MagicMock
from typing import Any, Dict, List, Optional, Union

# Re-export commonly used exception types and constants
SubprocessError = subprocess.SubprocessError
TimeoutExpired = subprocess.TimeoutExpired
CalledProcessError = subprocess.CalledProcessError
FileNotFoundError = FileNotFoundError
PermissionError = PermissionError
OSError = OSError

# Re-export os constants
W_OK = os.W_OK
R_OK = os.R_OK
X_OK = os.X_OK
F_OK = os.F_OK

# Re-export common path utilities
path_join = os.path.join


class ExecutionContext:
    """
    Execution context that can run in dry-run or actual mode.
    
    In dry-run mode, system operations are intercepted and logged.
    In actual mode, operations are executed normally.
    """
    
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.operations_log = []
        
    def log_operation(self, operation: str, *args, **kwargs):
        """Log an operation that would be performed"""
        if args or kwargs:
            details = f" with args={args}" if args else ""
            details += f" kwargs={kwargs}" if kwargs else ""
            log_entry = f"[DRY RUN] Would execute: {operation}{details}"
        else:
            log_entry = f"[DRY RUN] Would execute: {operation}"
        
        print(log_entry)
        self.operations_log.append(log_entry)
        
    def print(self, *args, **kwargs):
        """Print with optional dry-run prefix"""
        if self.dry_run:
            # Add dry-run prefix to the first argument if it's a string
            if args and isinstance(args[0], str):
                args = (f"[DRY RUN] {args[0]}",) + args[1:]
        print(*args, **kwargs)
        
    def makedirs(self, path: Union[str, Path], exist_ok: bool = False, mode: int = 0o777):
        """Create directories (dry-run aware)"""
        if self.dry_run:
            self.log_operation(f"os.makedirs('{path}', exist_ok={exist_ok}, mode={oct(mode)})")
            return
        return os.makedirs(path, exist_ok=exist_ok, mode=mode)

    def saferun(self, cmd: List[str], **kwargs) -> subprocess.CompletedProcess:
        """
        Run subprocess command for read-only operations with temporarily dropped privileges if root.
        
        When running as root, temporarily drops to 'nobody' user for security.
        When running as non-root, executes normally.
        Always executes (even in dry-run) since these are safe, read-only operations.
        """
        if self.dry_run:
            self.log_operation(f"safe run (read-only): subprocess.run({cmd})", **kwargs)
        
        # If we're root, try to drop privileges temporarily
        if os.geteuid() == 0:
            return self._run_with_dropped_privileges(cmd, **kwargs)
        else:
            # Non-root user, just run normally
            return subprocess.run(cmd, **kwargs)
         
    def run(self, cmd: List[str], **kwargs) -> subprocess.CompletedProcess:
        """Run subprocess command (dry-run aware)"""
        if self.dry_run:
            self.log_operation(f"subprocess.run({cmd})", **kwargs)
            # Return a mock successful result for dry-run
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            mock_result.stderr = ""
            return mock_result
        return subprocess.run(cmd, **kwargs)
        
    def rmtree(self, path: Union[str, Path]):
        """Remove directory tree (dry-run aware)"""
        if self.dry_run:
            self.log_operation(f"shutil.rmtree('{path}')")
            return
        return shutil.rmtree(path)
        
    def remove(self, path: Union[str, Path]):
        """Remove file (dry-run aware)"""
        if self.dry_run:
            self.log_operation(f"os.remove('{path}')")
            return
        return os.remove(path)
        
    def copy2(self, src: Union[str, Path], dst: Union[str, Path]):
        """Copy file with metadata (dry-run aware)"""
        if self.dry_run:
            self.log_operation(f"shutil.copy2('{src}', '{dst}')")
            return
        return shutil.copy2(src, dst)
        
    def copytree(self, src: Union[str, Path], dst: Union[str, Path], **kwargs):
        """Copy directory tree (dry-run aware)"""
        if self.dry_run:
            self.log_operation(f"shutil.copytree('{src}', '{dst}')", **kwargs)
            return
        return shutil.copytree(src, dst, **kwargs)
        
    def chmod(self, path: Union[str, Path], mode: int):
        """Change file permissions (dry-run aware)"""
        if self.dry_run:
            self.log_operation(f"os.chmod('{path}', {oct(mode)})")
            return
        return os.chmod(path, mode)
        
    def chown(self, path: Union[str, Path], uid: int, gid: int):
        """Change file ownership (dry-run aware)"""
        if self.dry_run:
            self.log_operation(f"os.chown('{path}', {uid}, {gid})")
            return
        return os.chown(path, uid, gid)

    def read_file(self, path: Union[str, Path], mode: str = ''):
        """Read content from file (dry-run aware)"""
        mode = 'r' + mode
        if self.dry_run:
            self.log_operation(f"read_file('{path}', mode='{mode}')")
        return open(path, mode)
    
    def write_file(self, path: Union[str, Path], content: str, mode: str = 'w'):
        """Write content to file (dry-run aware)"""
        if self.dry_run:
            self.log_operation(f"write_file('{path}', content_length={len(content)}, mode='{mode}')")
            return
        with open(path, mode) as f:
            f.write(content)
            
    def access(self, path: Union[str, Path], mode: int) -> bool:
        """Check file access permissions (works in both modes)"""
        if self.dry_run:
            # In dry-run mode, log the check but still perform it to provide useful feedback
            self.log_operation(f"os.access('{path}', {mode})")
        return os.access(path, mode)
        
    def exists(self, path: Union[str, Path]) -> bool:
        """Check if path exists (works in both modes)"""
        if self.dry_run:
            # In dry-run mode, we might want to assume paths don't exist
            # or use the actual filesystem state - depends on use case
            return os.path.exists(path)
        return os.path.exists(path)
        
    def glob(self, pattern: str) -> List[str]:
        """Glob pattern matching (works in both modes)"""
        return glob.glob(pattern)
        
    def system_exit(self, code: int = 0):
        """Exit the system (dry-run aware)"""
        if self.dry_run:
            self.log_operation(f"sys.exit({code})")
            return
        sys.exit(code)

    def _run_with_dropped_privileges(self, cmd: List[str], **kwargs) -> subprocess.CompletedProcess:
        """
        Helper method to run commands with temporarily dropped privileges when root.
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
        

# Global execution context instance
_current_context: Optional[ExecutionContext] = None


def get_execution_context() -> ExecutionContext:
    """Get the current execution context"""
    global _current_context
    if _current_context is None:
        _current_context = ExecutionContext(dry_run=False)
    return _current_context


def set_execution_context(context: ExecutionContext):
    """Set the current execution context"""
    global _current_context
    _current_context = context


@contextmanager
def execution_context(dry_run: bool = False):
    """
    Context manager for execution mode.
    
    Usage:
        with execution_context(dry_run=True):
            # All operations will be logged instead of executed
            ctx = get_execution_context()
            ctx.makedirs('/some/path')
            ctx.run(['ls', '-la'])
    """
    previous_context = _current_context
    new_context = ExecutionContext(dry_run=dry_run)
    set_execution_context(new_context)
    
    try:
        yield new_context
    finally:
        set_execution_context(previous_context)
