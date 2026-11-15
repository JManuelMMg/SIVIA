# Baja más fotos de Mapillary sin guardar el token en ningún archivo: lo pide oculto y lo borra al terminar.
# Uso: & .\bajar_mapillary.ps1   (opcional: -PorInstitucion 3)
param([int]$PorInstitucion = 3)
Set-Location $PSScriptRoot
$env:PYTHONIOENCODING = 'utf-8'
$seguro = Read-Host -AsSecureString "Pega tu token de Mapillary (MLY|...) y presiona Enter"
$env:MAPILLARY_TOKEN = [System.Net.NetworkCredential]::new('', $seguro).Password
try {
    python mapillary_instituciones.py --por-institucion $PorInstitucion
} finally {
    Remove-Item Env:MAPILLARY_TOKEN -ErrorAction SilentlyContinue
}
Write-Host "`nDescarga terminada. Ya puedes avisarle a Claude."
