%msbuild% /t:rebuild /p:ForceImportBeforeCppTargets=%GITHUB_WORKSPACE%\tools\nosecure.props;Configuration=Debug;Platform=Win32;PlatformToolset=v142 /m %*
