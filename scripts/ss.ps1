# Versão super simplificada - captura e mostra comando
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms

# Captura
$b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen(0, 0, 0, 0, $b.Size)

# Salva
$f = "ss.png"
$bmp.Save("C:\Users\octav\Projetos\dashboard-eshows\$f")

# Output limpo - só o comando
Write-Host "Read /mnt/c/Users/octav/Projetos/dashboard-eshows/$f"

# Limpa
$g.Dispose()
$bmp.Dispose()