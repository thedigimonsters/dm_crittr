import os
import shutil
import subprocess
import sys
from app_config import APP_NAME, APP_VERSION, COMPANY_NAME, APP_UUID as PRODUCT_ID, APP_ICON


# ============================================================
# Configuration Options - Set these to control the build process
# ============================================================
# Set to True to compile Cython modules
COMPILE_CYTHON = True
# Set to True to build the executable with PyInstaller
BUILD_EXECUTABLE = False
# Set to True to create an installer package
CREATE_INSTALLER = False
# Set to True to clean up build artifacts after completion
CLEANUP_AFTER_BUILD = True
# ============================================================

# Directories
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
BUILD_DIR = os.path.join(ROOT_DIR, 'build')
DIST_DIR = os.path.join(ROOT_DIR, 'dist')
LOGIC_DIR = os.path.join(ROOT_DIR, 'cython_logic')
INSTALLER_DIR = os.path.join(ROOT_DIR, 'installer_output')


def print_header(title):
    """Prints a formatted header to the console."""
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)


def run_command(command, cwd):
    """Runs a command in a specified directory and exits if it fails."""
    print(f"Executing: {' '.join(command)} in {cwd}")
    # Use shell=True on Windows for compatibility with commands in Scripts/
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, shell=sys.platform == 'win32')
    if result.returncode != 0:
        print("Error:")
        print(result.stdout)
        print(result.stderr)
    print(result.stdout)


def cleanup():
    """Removes all temporary build files and folders."""
    print_header("Cleaning up all build artifacts")

    # Remove PyInstaller build folder
    if os.path.exists(BUILD_DIR):
        shutil.rmtree(BUILD_DIR)
        print(f"Removed PyInstaller build directory: {BUILD_DIR}")

    # Remove Cython build folder inside logic directory
    cython_build_dir = os.path.join(LOGIC_DIR, 'build')
    if os.path.exists(cython_build_dir):
        shutil.rmtree(cython_build_dir)
        print(f"Removed Cython build directory: {cython_build_dir}")

    # Remove generated C files and compiled modules from logic directory
    if os.path.exists(LOGIC_DIR):
        for item in os.listdir(LOGIC_DIR):
            item_path = os.path.join(LOGIC_DIR, item)
            if item.endswith('.c'):
                os.remove(item_path)
                print(f"Removed generated C source file: {item}")
            if item.endswith('.pyd'):
                shutil.copy(item_path, os.path.join(ROOT_DIR, f"crittr/logic/{os.path.basename(item)}"))
                os.remove(item_path)


def compile_cython():
    print_header("Building Cython Logic")
    run_command([sys.executable, 'setup.py', 'build_ext', '--inplace'], cwd=LOGIC_DIR)


def build_executable():
    print_header("Building Executable with PyInstaller")
    try:
        import PyInstaller.__main__

        # Save the current working directory
        original_cwd = os.getcwd()

        try:
            # Change to the ROOT_DIR before running PyInstaller
            os.chdir(ROOT_DIR)
            print(f"Working directory changed to: {ROOT_DIR}")

            # Just run PyInstaller with the spec file
            PyInstaller.__main__.run(['crittr.spec', '--noconfirm'])
        finally:
            # Restore the original working directory
            os.chdir(original_cwd)
    except ImportError:
        print("PyInstaller module not found. Make sure it's installed in your virtual environment.")
        print("You can install it with: pip install pyinstaller")
        sys.exit(1)
    except Exception as e:
        print(f"Error running PyInstaller: {e}")
        sys.exit(1)


def create_installer_package():
    """Create an MSI installer package for the application."""
    print_header(f"Creating Windows MSI Installer")

    app_dir = os.path.join(DIST_DIR, APP_NAME)

    if not os.path.exists(app_dir):
        print(f"Error: Application directory not found: {app_dir}")
        print("Make sure to build the executable first.")
        return False

    try:
        # Import installer module
        from installer import create_installer

        # Create output directory if it doesn't exist
        if not os.path.exists(INSTALLER_DIR):
            os.makedirs(INSTALLER_DIR)

        # Create installer with company information
        installer = create_installer(
            app_name=APP_NAME,
            app_version=APP_VERSION,
            app_dir=app_dir,
            output_dir=INSTALLER_DIR,
            company_name=COMPANY_NAME,
            product_id=PRODUCT_ID,
            icon_path=APP_ICON
        )

        # Build the installer
        installer.validate()
        installer_path = installer.build()

        print(f"\nInstaller created successfully: {installer_path}")
        return True
    except Exception as e:
        print(f"Error creating installer: {e}")
        print(f"Exception details: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main build process."""
    # Print application information
    print_header("Building Application")
    print(f"Application: {APP_NAME}")
    print(f"Version:     {APP_VERSION}")
    print(f"Company:     {COMPANY_NAME}")
    print(f"Product ID:  {PRODUCT_ID}")

    # 1. Build the Cython Logic
    if COMPILE_CYTHON:
        try:
            compile_cython()
        except Exception as e:
            print(f"Error compiling Cython logic: {e}")
            return

    # 2. Build the executable with PyInstaller
    if BUILD_EXECUTABLE:
        try:
            build_executable()
        except Exception as e:
            print(f"Error building executable: {e}")
            return

    # 3. Create installer package
    if CREATE_INSTALLER:
        try:
            create_installer_package()
        except Exception as e:
            print(f"Error creating installer: {e}")
            return

    # 4. Clean up build artifacts if requested
    if CLEANUP_AFTER_BUILD:
        cleanup()

    print(f"\nBuild process completed successfully!")


if __name__ == "__main__":
    main()