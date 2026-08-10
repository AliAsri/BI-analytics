<#
.SYNOPSIS
    Analyzes a CSV file containing 'Pass Jeunes' offers.

.DESCRIPTION
    This script imports a specific CSV file and outputs various statistics:
    - Grouped counts by Category.
    - Top 15 Partners by offer count.
    - Grouped counts by Category for new offers (where Fichier_Source is not 'N/A').

.EXAMPLE
    .\analyze_csv.ps1
#>

# Define the path to the CSV file
$csvPath = Join-Path -Path $PSScriptRoot -ChildPath '..\data\offres_pass_jeunes_v3.csv'

# Import the CSV data
$csvData = Import-Csv -Path $csvPath -Encoding Default

Write-Output '=== CATEGORIES ==='
$csvData | Group-Object -Property Categorie | Sort-Object -Property Count -Descending | Select-Object -Property Name, Count | Format-Table -AutoSize

Write-Output '=== PARTENAIRES (Top 15) ==='
$csvData | Group-Object -Property Partenaire | Sort-Object -Property Count -Descending | Select-Object -First 15 -Property Name, Count | Format-Table -AutoSize

Write-Output '=== NOUVELLES CATEGORIES ==='
# Filter to get only the new offers
$newOffers = $csvData | Where-Object { $_.Fichier_Source -ne 'N/A' }
$newOffers | Group-Object -Property Categorie | Sort-Object -Property Count -Descending | Select-Object -Property Name, Count | Format-Table -AutoSize
