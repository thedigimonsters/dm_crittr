"""
Windows installer package for creating MSI installers.
"""
import sys
from .msi_creator import WindowsMSIInstaller

__version__ = "0.1.0"

def create_installer(app_name, app_version, app_dir, output_dir, **kwargs):
    """
    Create a Windows MSI installer for the application.

    Args:
        app_name (str): Name of the application
        app_version (str): Version of the application
        app_dir (str): Directory containing the application files
        output_dir (str): Directory where the installer will be created
        **kwargs: Additional arguments to pass to the installer

    Returns:
        The installer instance
    """
    if sys.platform != "win32":
        raise RuntimeError("This installer package only supports Windows")

    # Create the installer using pure Python MSI creator
    installer = WindowsMSIInstaller(
        app_name=app_name,
        app_version=app_version,
        app_dir=app_dir,
        output_dir=output_dir,
        **kwargs
    )

    return installer