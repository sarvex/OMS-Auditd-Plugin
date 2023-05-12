# coding: utf-8

import os
import scxutil

class LinuxDebFile:
    def __init__(self, intermediateDir, targetDir, stagingDir, variables, sections):
        self.intermediateDir = intermediateDir
        self.targetDir = targetDir
        self.stagingDir = stagingDir
        self.variables = variables
        self.sections = sections

        self.controlDir = os.path.join(self.stagingDir, 'DEBIAN')
        scxutil.MkAllDirs(self.controlDir)
        self.controlFileName = os.path.join(self.controlDir, 'control')
        self.configFileName = os.path.join(self.controlDir, 'conffiles')
        self.preInstallPath = os.path.join(self.controlDir, 'preinst')
        self.postInstallPath = os.path.join(self.controlDir, 'postinst')
        self.preUninstallPath = os.path.join(self.controlDir, 'prerm')
        self.postUninstallPath = os.path.join(self.controlDir, 'postrm')
        self.fullversion_dashed = self.fullversion = self.variables["VERSION"]
        if "RELEASE" in self.variables:
            self.fullversion = self.variables["VERSION"] + "." + self.variables["RELEASE"]
            self.fullversion_dashed = self.variables["VERSION"] + "-" + self.variables["RELEASE"]
        self.archType = self.variables["PFARCH"]
        if self.archType == 'x86_64':
            self.archType = 'amd64'
        elif self.archType == 'aarch64':
            self.archType = 'arm64'

    def GeneratePackageDescriptionFiles(self):
        self.GenerateScripts()
        self.GenerateControlFile()

    def WriteScriptFile(self, filePath, section):
        with open(filePath, 'w') as scriptfile:
            script = "".join(line + "\n" for line in self.sections[section]) + "exit 0\n"
            scriptfile.write(script)

    def GenerateScripts(self):
        #
        # On Ubuntu, we have four control scripts:
        #   preinst
        #   postinst
        #   prerm
        #   postrm
        #
        # Parameters passed to scripts:
        #
        #   Action	Script		Parameter
        #
        #   Install	preinst		install
        #		postinst	configure
        #
        #   Upgrade	prerm		upgrade		<version>    (from old kit)
        #		preinst		upgrade		<version>    (from new kit)
        #		postinst	configure	<version>    (from new kit)
        #
        #   Remove	prerm		remove
        #		postrm		remove
        #
        #   Purge	postrm		purge
        #
        self.WriteScriptFile(self.preInstallPath, "Preinstall")
        self.WriteScriptFile(self.postInstallPath, "Postinstall")
        self.WriteScriptFile(self.preUninstallPath, "Preuninstall")
        self.WriteScriptFile(self.postUninstallPath, "Postuninstall")

        scxutil.ChMod(self.preInstallPath, 755)
        scxutil.ChMod(self.postInstallPath, 755)
        scxutil.ChMod(self.preUninstallPath, 755)
        scxutil.ChMod(self.postUninstallPath, 755)

        retval = os.system(
            f'chown --no-dereference 0:0 {self.preInstallPath} {self.postInstallPath} {self.preUninstallPath} {self.postUninstallPath}'
        )
        if retval != 0:
            print("Error: Unable to chown package scripts.")
            exit(1)

        # Fix up owner/permissions in staging directory
        # (Files are installed on destination as staged)        

        for f in self.sections["Files"] + self.sections["Directories"]:
            filePath = self.stagingDir + f.stagedLocation
            scxutil.ChOwn(filePath, f.owner, f.group)
            scxutil.ChMod(filePath, f.permissions)

        for l in self.sections["Links"]:
            filePath = self.stagingDir + l.stagedLocation
            retval = os.system(f'chown --no-dereference {l.owner}:{l.group} {filePath}')
            if retval != 0:
                print(f"Error: Unable to chown {l.stagedLocation}")
                exit(1)

    def GetSizeInformation(self):
        pipe = os.popen(f"du -s {self.stagingDir}")

        sizeinfo = 0
        for line in pipe:
            [size, directory] = line.split()
            sizeinfo += int(size)

        return sizeinfo

    def GenerateControlFile(self):
        with open(self.controlFileName, 'w') as controlfile:
            controlfile.write('Package:      ' + self.variables["SHORT_NAME"] + '\n')
            controlfile.write('Source:       ' + self.variables["SHORT_NAME"] + '\n')
            controlfile.write(f'Version:      {self.fullversion}' + '\n')
            controlfile.write(f'Architecture: {self.archType}' + '\n')
            controlfile.write('Maintainer:   ' + self.variables["MAINTAINER"] + '\n')
            controlfile.write('Installed-Size: %d\n' % self.GetSizeInformation())

            controlfile.write('Depends:      ')
            for d in self.sections["Dependencies"]:
                controlfile.write(d)
                if d != self.sections["Dependencies"][-1]:
                    controlfile.write(", ")
            controlfile.write('\n')

            controlfile.write('Provides:     ' + self.variables["SHORT_NAME"] + '\n')
            controlfile.write('Section:      utils\n')
            controlfile.write('Priority:     optional\n')
            controlfile.write('Description:  ' + self.variables["LONG_NAME"] + '\n')
            controlfile.write(' %s\n' % self.variables['DESCRIPTION'])
            controlfile.write('\n')
        with open(self.configFileName, 'w') as conffile:
            # Now list all configuration files in staging directory
            for f in self.sections["Files"]:
                if f.type == "conffile":
                    conffile.write(f.stagedLocation + '\n')

        retval = os.system(
            f'chown --no-dereference 0:0 {self.controlFileName} {self.configFileName}'
        )
        if retval != 0:
            print("Error: Unable to chown package conf files.")
            exit(1)

    def BuildPackage(self):
        if 'OUTPUTFILE' in self.variables:
            pkgName = self.variables['OUTPUTFILE'] + '.deb'
        else:
            pkgName = self.variables["SHORT_NAME"] + '-' + \
                    self.fullversion_dashed + '.' + self.archType + '.deb'

        if "SKIP_BUILDING_PACKAGE" in self.variables:
            return

        # Build the package - 'cd' to the directory where we want to store result
        dpkg_path = 'dpkg-deb'
        if "DPKG_LOCATION" in self.variables:
            dpkg_path = self.variables["DPKG_LOCATION"]
        retval = os.system(
            f'cd {self.targetDir}; {dpkg_path} -b {self.stagingDir} {pkgName}'
        )
        if retval != 0:
            print("Error: Failed building DPKG")
            exit(1)

        with open(f"{self.targetDir}/package_filename", 'w') as package_filename:
            package_filename.write("%s\n" % pkgName)
