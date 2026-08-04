<#
.SYNOPSIS
    Registers a DLL into the Global Assembly Cache (GAC).

.DESCRIPTION
    This script takes a specific DLL file (MySQL Connector) and registers it
    into the GAC using System.EnterpriseServices.

.EXAMPLE
    .\register_gac.ps1
#>

function Register-DllInGac {
    <#
    .SYNOPSIS
        Registers the given DLL path in the GAC.
    
    .PARAMETER DllPath
        The absolute path to the DLL to be registered.
    #>
    [CmdletBinding()]
    param (
        [Parameter(Mandatory = $true)]
        [string]$DllPath
    )

    if (-not (Test-Path -Path $DllPath)) {
        Write-Error "DLL not found at path: $DllPath"
        return
    }

    try {
        Add-Type -AssemblyName "System.EnterpriseServices"
        $publish = New-Object System.EnterpriseServices.Internal.Publish
        $publish.GacInstall($DllPath)
        Write-Host "Successfully registered '$DllPath' in the GAC."
    } catch {
        Write-Error "Failed to register the DLL in the GAC: $_"
    }
}

$mySqlDllPath = "C:\Program Files (x86)\MySQL\MySQL Connector Net 8.0.26\Assemblies\v4.5.2\MySql.Data.dll"
Register-DllInGac -DllPath $mySqlDllPath
