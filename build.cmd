%msbuild% /t:rebuild /p:ForceImportBeforeCppTargets=%GITHUB_WORKSPACE%\tools\nosecure.props;Configuration=Debug;Platform=Win32;PlatformToolset=%DefaultPlatformToolset% /m /nologo -clp:Summary %*
