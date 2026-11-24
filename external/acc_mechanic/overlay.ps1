# Always-on-top mechanic overlay for ACC (visible when ACC runs borderless or windowed).
# Polls the mechanic's /state endpoint. Drag to move; right-click to close.
param([int]$Port = 8790, [int]$X = 40, [int]$Y = 40, [double]$Opacity = 0.85)

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$form = New-Object Windows.Forms.Form
$form.FormBorderStyle = 'None'
$form.TopMost = $true
$form.ShowInTaskbar = $false
$form.StartPosition = 'Manual'
$form.Location = New-Object Drawing.Point($X, $Y)
$form.Size = New-Object Drawing.Size(520, 176)
$form.BackColor = [Drawing.Color]::FromArgb(16, 18, 24)
$form.Opacity = $Opacity
$form.Text = "ACC Mechanic"

function Lbl($x, $y, $w, $size, $bold) {
  $l = New-Object Windows.Forms.Label
  $l.Location = New-Object Drawing.Point($x, $y)
  $l.Size = New-Object Drawing.Size($w, ($size * 2 + 4))
  $style = if ($bold) { [Drawing.FontStyle]::Bold } else { [Drawing.FontStyle]::Regular }
  $l.Font = New-Object Drawing.Font("Segoe UI", $size, $style)
  $l.ForeColor = [Drawing.Color]::Gainsboro
  $l.BackColor = [Drawing.Color]::Transparent
  $form.Controls.Add($l)
  return $l
}

$status  = Lbl 10 6 330 10 $true
$delta   = Lbl 350 4 160 15 $true
$tyres   = Lbl 10 34 500 10 $false
$phase   = Lbl 10 60 500 12 $true
$coach   = Lbl 10 88 500 10 $false
$fb      = Lbl 10 112 500 10 $true
$setup   = Lbl 10 138 500 9 $false
$coach.ForeColor = [Drawing.Color]::FromArgb(190, 215, 255)
$fb.ForeColor = [Drawing.Color]::FromArgb(255, 224, 77)
$setup.ForeColor = [Drawing.Color]::FromArgb(64, 230, 115)

# drag to move, right-click to close
$script:drag = $null
$down = { param($s, $e)
  if ($e.Button -eq 'Right') { $form.Close(); return }
  $script:drag = $e.Location }
$move = { param($s, $e)
  if ($script:drag) { $form.Location = New-Object Drawing.Point(($form.Left + $e.X - $script:drag.X), ($form.Top + $e.Y - $script:drag.Y)) } }
$up = { $script:drag = $null }
foreach ($c in @($form) + @($form.Controls)) { $c.Add_MouseDown($down); $c.Add_MouseMove($move); $c.Add_MouseUp($up) }

function Rgb($c) {
  if (-not $c) { return [Drawing.Color]::Gainsboro }
  return [Drawing.Color]::FromArgb([int](255 * $c[0]), [int](255 * $c[1]), [int](255 * $c[2]))
}

$wc = New-Object Net.WebClient
$wc.Encoding = [Text.Encoding]::UTF8
$timer = New-Object Windows.Forms.Timer
$timer.Interval = 250
$timer.Add_Tick({
  try {
    $st = $wc.DownloadString("http://localhost:$Port/state") | ConvertFrom-Json
  } catch {
    $status.Text = "Mechanic not running"; return
  }
  $o = $st.overlay
  $status.Text = $o.status
  $delta.Text = $o.delta
  $delta.ForeColor = Rgb $o.delta_color
  $tyres.Text = $o.tyres
  $phase.Text = $o.phase
  $coach.Text = $o.coach
  $fb.Text = $o.feedback
  $setup.Text = $o.setup
})
$timer.Start()
[void]$form.ShowDialog()
