@echo off
set INCLUDE=C:\Program Files (x86)\Microsoft SDKs\Windows\V7.1A\Include;%GITHUB_WORKSPACE%\tools
call "C:\Program Files (x86)\Microsoft Visual Studio\2019\Enterprise\VC\Auxiliary\Build\vcvarsall.bat" x86
echo ПЕРЕХОЖУ В ПАПКУ %GITHUB_WORKSPACE%\lab\%1
cd %GITHUB_WORKSPACE%\lab\%1
rmdir /S /Q Debug > nul
echo CE>%1.res
set TheToolset=v142
set MSBUILD="C:\Program Files (x86)\Microsoft Visual Studio\2019\Enterprise\MSBuild\Current\Bin\MSBuild.exe"
%MSBUILD% /t:rebuild /p:ForceImportBeforeCppTargets=%GITHUB_WORKSPACE%\tools\nosecure.props;Configuration=Debug;Platform=Win32;PlatformToolset=%TheToolset%;WindowsTargetPlatformVersion=10 /m /nologo /clp:ErrorsOnly
