import os
import sys
import uuid
import subprocess
from pathlib import Path


class NSISInstallerCreator:
    """Creates Windows installers using NSIS (Nullsoft Scriptable Install System)."""

    def __init__(self, app_name, app_version, app_dir, output_dir, **kwargs):
        self.app_name = app_name
        self.app_version = app_version
        self.app_dir = Path(app_dir).resolve()
        self.output_dir = Path(output_dir).resolve()

        # Optional parameters
        self.company_name = kwargs.get('company_name', 'Unknown Company')
        self.product_id = kwargs.get('product_id', str(uuid.uuid4()))
        self.icon_path = kwargs.get('icon_path')

        # Validate inputs
        if not self.app_dir.exists():
            raise ValueError(f"Application directory does not exist: {self.app_dir}")

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def validate(self):
        """Validate the installer configuration."""
        if not self.app_name:
            raise ValueError("Application name is required")
        if not self.app_version:
            raise ValueError("Application version is required")
        if not self.app_dir.exists():
            raise ValueError(f"Application directory does not exist: {self.app_dir}")

        # Validate product ID format (should be GUID)
        try:
            uuid.UUID(self.product_id)
        except ValueError:
            raise ValueError(f"Product ID must be a valid GUID: {self.product_id}")

        # Check if NSIS is available
        if not self._is_nsis_available():
            raise RuntimeError("NSIS not found. Please ensure NSIS is installed and in your PATH.")

        return True

    def create_msi(self):
        """Create the installer using NSIS."""
        print(f"Creating NSIS installer for {self.app_name}")

        # Create safe filename
        safe_name = "".join(c for c in self.app_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        installer_filename = f"{safe_name}-{self.app_version}-installer.exe"
        installer_path = self.output_dir / installer_filename

        # Remove existing installer if it exists
        if installer_path.exists():
            installer_path.unlink()
            print(f"Removed existing installer: {installer_path}")

        # Create NSIS script
        nsis_script_path = self.output_dir / "installer.nsi"
        self._create_nsis_script(nsis_script_path, installer_filename)

        # Compile the installer
        try:
            print("Compiling NSIS installer...")
            result = subprocess.run([
                "makensis", str(nsis_script_path)
            ], capture_output=True, text=True, check=True)

            print("NSIS compilation successful")
            if result.stdout.strip():
                print(f"NSIS output: {result.stdout}")

            if installer_path.exists():
                print(f"Installer created successfully: {installer_path}")
                # Clean up script file
                nsis_script_path.unlink()
                return str(installer_path)
            else:
                raise RuntimeError("NSIS compilation succeeded but installer file not found")

        except subprocess.CalledProcessError as e:
            nsis_script_path.unlink()  # Clean up on failure
            raise RuntimeError(f"NSIS compilation failed: {e.stderr}")
        except FileNotFoundError:
            nsis_script_path.unlink()  # Clean up on failure
            raise RuntimeError("makensis not found. Please ensure NSIS is installed and in your PATH.")

    def _is_nsis_available(self):
        """Check if NSIS is available."""
        try:
            result = subprocess.run(["makensis", "/VERSION"], capture_output=True, text=True)
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def _get_main_executable(self):
        """Find the main executable file."""
        # Look for executable with app name first
        app_exe = self.app_dir / f"{self.app_name}.exe"
        if app_exe.exists():
            return app_exe.name

        # Otherwise, find any .exe file
        for file_path in self.app_dir.rglob('*.exe'):
            return file_path.name

        # Fallback to expected name
        return f"{self.app_name}.exe"

    def _create_nsis_script(self, script_path, installer_filename):
        """Create NSIS installer script."""
        main_exe = self._get_main_executable()

        # Parse version for NSIS
        version_parts = self.app_version.split('.')
        version_major = version_parts[0] if len(version_parts) > 0 else "1"
        version_minor = version_parts[1] if len(version_parts) > 1 else "0"
        version_build = version_parts[2] if len(version_parts) > 2 else "0"

        # Calculate estimated install size (in KB)
        install_size = sum(f.stat().st_size for f in self.app_dir.rglob('*') if f.is_file()) // 1024

        script_content = f'''; NSIS Installer Script for {self.app_name}
!define APPNAME "{self.app_name}"
!define COMPANYNAME "{self.company_name}"
!define DESCRIPTION "{self.app_name} Application"
!define VERSIONMAJOR "{version_major}"
!define VERSIONMINOR "{version_minor}"
!define VERSIONBUILD "{version_build}"
!define INSTALLSIZE {install_size}

RequestExecutionLevel admin
InstallDir "$PROGRAMFILES\\${{COMPANYNAME}}\\${{APPNAME}}"
Name "${{APPNAME}}"
outFile "{installer_filename}"

!include LogicLib.nsh

; Modern UI
!include "MUI2.nsh"
!define MUI_ABORTWARNING

; Pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_WELCOME
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

; Languages
!insertmacro MUI_LANGUAGE "English"

; Verify user is admin
!macro VerifyUserIsAdmin
UserInfo::GetAccountType
pop $0
${{If}} $0 != "admin"
    messageBox MB_ICONSTOP "Administrator rights required!"
    setErrorLevel 740
    quit
${{EndIf}}
!macroend

function .onInit
    setShellVarContext all
    !insertmacro VerifyUserIsAdmin
functionEnd

section "install"
    setOutPath $INSTDIR

'''

        # Add all files from the application directory
        for file_path in self.app_dir.rglob('*'):
            if file_path.is_file():
                # Create subdirectories if needed
                relative_path = file_path.relative_to(self.app_dir)
                if relative_path.parent != Path('.'):
                    script_content += f'    setOutPath "$INSTDIR\\{relative_path.parent}"\n'
                    script_content += f'    file "{file_path}"\n'
                    script_content += f'    setOutPath $INSTDIR\n'
                else:
                    script_content += f'    file "{file_path}"\n'

        script_content += f'''
    ; Create uninstaller
    writeUninstaller "$INSTDIR\\uninstall.exe"

    ; Create start menu shortcuts
    createDirectory "$SMPROGRAMS\\${{COMPANYNAME}}"
    createShortCut "$SMPROGRAMS\\${{COMPANYNAME}}\\${{APPNAME}}.lnk" "$INSTDIR\\{main_exe}" "" "$INSTDIR\\{main_exe}" 0
    createShortCut "$SMPROGRAMS\\${{COMPANYNAME}}\\Uninstall ${{APPNAME}}.lnk" "$INSTDIR\\uninstall.exe"

    ; Create desktop shortcut
    createShortCut "$DESKTOP\\${{APPNAME}}.lnk" "$INSTDIR\\{main_exe}" "" "$INSTDIR\\{main_exe}" 0

    ; Registry entries for Add/Remove Programs
    writeRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${{COMPANYNAME}} ${{APPNAME}}" "DisplayName" "${{APPNAME}}"
    writeRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${{COMPANYNAME}} ${{APPNAME}}" "UninstallString" "$\\"$INSTDIR\\uninstall.exe$\\""
    writeRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${{COMPANYNAME}} ${{APPNAME}}" "QuietUninstallString" "$\\"$INSTDIR\\uninstall.exe$\\" /S"
    writeRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${{COMPANYNAME}} ${{APPNAME}}" "InstallLocation" "$\\"$INSTDIR$\\""
    writeRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${{COMPANYNAME}} ${{APPNAME}}" "Publisher" "${{COMPANYNAME}}"
    writeRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${{COMPANYNAME}} ${{APPNAME}}" "DisplayVersion" "${{VERSIONMAJOR}}.${{VERSIONMINOR}}.${{VERSIONBUILD}}"
    writeRegDWORD HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${{COMPANYNAME}} ${{APPNAME}}" "VersionMajor" ${{VERSIONMAJOR}}
    writeRegDWORD HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${{COMPANYNAME}} ${{APPNAME}}" "VersionMinor" ${{VERSIONMINOR}}
    writeRegDWORD HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${{COMPANYNAME}} ${{APPNAME}}" "NoModify" 1
    writeRegDWORD HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${{COMPANYNAME}} ${{APPNAME}}" "NoRepair" 1
    writeRegDWORD HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${{COMPANYNAME}} ${{APPNAME}}" "EstimatedSize" ${{INSTALLSIZE}}
sectionEnd

; Uninstaller section
section "uninstall"
    ; Remove files and directories
'''

        # Add uninstall commands for all files and directories
        all_dirs = set()
        for file_path in self.app_dir.rglob('*'):
            if file_path.is_file():
                relative_path = file_path.relative_to(self.app_dir)
                script_content += f'    delete "$INSTDIR\\{relative_path}"\n'

                # Track directories
                current_dir = relative_path.parent
                while current_dir != Path('.'):
                    all_dirs.add(current_dir)
                    current_dir = current_dir.parent

        # Remove directories (in reverse order to handle nested dirs)
        for dir_path in sorted(all_dirs, reverse=True):
            script_content += f'    rmDir "$INSTDIR\\{dir_path}"\n'

        script_content += f'''
    ; Remove uninstaller and main directory
    delete "$INSTDIR\\uninstall.exe"
    rmDir "$INSTDIR"

    ; Remove shortcuts
    delete "$SMPROGRAMS\\${{COMPANYNAME}}\\${{APPNAME}}.lnk"
    delete "$SMPROGRAMS\\${{COMPANYNAME}}\\Uninstall ${{APPNAME}}.lnk"
    rmDir "$SMPROGRAMS\\${{COMPANYNAME}}"
    delete "$DESKTOP\\${{APPNAME}}.lnk"

    ; Remove registry entries
    deleteRegKey HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${{COMPANYNAME}} ${{APPNAME}}"
sectionEnd
'''

        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(script_content)


class WindowsMSIInstaller:
    """Windows installer using NSIS."""

    def __init__(self, app_name, app_version, app_dir, output_dir, **kwargs):
        self.creator = NSISInstallerCreator(app_name, app_version, app_dir, output_dir, **kwargs)

    def validate(self):
        """Validate installer requirements."""
        return self.creator.validate()

    def build(self):
        """Build the installer."""
        return self.creator.create_msi()